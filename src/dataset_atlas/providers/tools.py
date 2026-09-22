"""Read-only model tool dispatcher; data access is supplied by trusted Atlas services."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from .schemas import ToolName, ToolResult

TOOL_NAMES: tuple[ToolName, ...] = (
    "describe_dataset", "describe_fields", "search_records", "get_records",
    "aggregate", "inspect_images", "get_run_results",
)
_FORBIDDEN = {"url", "uri", "path", "sql", "command", "code", "shell", "python", "download", "export", "save", "run_job"}
_EVAL_HIDDEN = {"label", "labels", "gold", "answer", "target", "filename", "file_name", "path", "uri", "prediction", "predictions", "annotation", "annotations", "human", "source"}

# Callback must implement these tools using the same query/media services as the UI.
# It receives the immutable approved scope and must not fetch outside that scope.
ToolBackend = Callable[[ToolName, dict[str, Any], frozenset[str], int], ToolResult]


def tool_definitions() -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": name,
            "description": "Read-only Atlas query over the approved selected records. Return stable IDs, scope, coverage and truncation.",
            "parameters": {"type": "object", "properties": {
                "record_ids": {"type": "array", "items": {"type": "string"}},
                "query": {"type": "string"}, "field_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                "dataset_id": {"type": "string"}, "run_id": {"type": "string"},
            }, "additionalProperties": False},
        },
    } for name in TOOL_NAMES]


def _reject_hidden(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _EVAL_HIDDEN:
                raise ValueError("evaluation tool result contains a hidden field")
            _reject_hidden(item)
    elif isinstance(value, list):
        for item in value:
            _reject_hidden(item)


def execute_tool(
    name: str, arguments: str | dict[str, Any], backend: ToolBackend,
    scope: frozenset[str], remaining_rows: int, mode: str,
) -> dict[str, Any]:
    if name not in TOOL_NAMES:
        raise ValueError("tool is not allowlisted")
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    if not isinstance(args, dict) or set(args) - {"record_ids", "query", "field_id", "limit", "dataset_id", "run_id"}:
        raise ValueError("tool arguments contain unsupported keys")
    if any(key.lower() in _FORBIDDEN for key in args):
        raise ValueError("unsafe tool argument")
    if "record_ids" in args and (not isinstance(args["record_ids"], list) or not set(args["record_ids"]).issubset(scope)):
        raise ValueError("tool requested records outside approved scope")
    if "limit" in args and (not isinstance(args["limit"], int) or not 1 <= args["limit"] <= remaining_rows):
        raise ValueError("tool row limit exceeds remaining budget")
    if "field_id" in args:
        field = args["field_id"]
        if not isinstance(field, str) or len(field) > 256:
            raise ValueError("invalid field_id")
        if mode == "evaluation" and field.startswith(("source.", "prediction.", "human.")):
            raise ValueError("evaluation excludes auxiliary fields")
    if "query" in args and (not isinstance(args["query"], str) or len(args["query"]) > 1000):
        raise ValueError("invalid search query")
    result = backend(name, args, scope, remaining_rows)
    if not isinstance(result, ToolResult):
        result = ToolResult.model_validate(result)
    if len(result.rows) > remaining_rows:
        raise ValueError("tool backend exceeded row budget")
    serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    if len(serialized) > 100_000:
        raise ValueError("tool result exceeds size budget")
    if "data:image/" in serialized:
        raise ValueError("tool results cannot transmit image bytes; select images in inspected context")
    for row in result.rows:
        if row.get("id") not in scope and row.get("record_id") not in scope:
            raise ValueError("tool backend returned an unapproved record")
    if mode == "evaluation":
        _reject_hidden(result.model_dump(mode="json"))
    if result.population_scope != "approved_selection" or not result.coverage:
        raise ValueError("tool result lacks approved selection scope or coverage")
    if any(ref not in scope for ref in result.source_refs):
        raise ValueError("tool cited a record outside approved scope")
    value = result.model_dump(mode="json")
    citation_id = "atlas-tool:" + hashlib.sha256(json.dumps({"name": name, "arguments": args, "result": value}, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:24]
    return {"citation_id": citation_id, "name": name, "arguments": args, "result": value}


def grounded_citations(response: str, results: list[dict[str, Any]]) -> list[str]:
    """Only accept explicit citations to deterministic tool receipts present in this turn."""
    cited = []
    for receipt in results:
        citation = receipt["citation_id"]
        if citation in response:
            cited.append(citation)
    return cited


def validate_record_citations(response: str, scope: frozenset[str]) -> list[str]:
    """Recognize one- or two-bracket record citations and reject unavailable IDs."""
    cited = re.findall(r"\[{1,2}record:([^\]\s]+)\]{1,2}", response)
    if any(record_id not in scope for record_id in cited):
        raise ValueError("model cited a record outside the approved interaction")
    return cited


def validate_tool_citations(response: str, results: list[dict[str, Any]]) -> list[str]:
    cited = re.findall(r"atlas-tool:[0-9a-f]{24}", response)
    available = {item["citation_id"] for item in results}
    if any(citation not in available for citation in cited):
        raise ValueError("model cited an unavailable Atlas tool receipt")
    return cited
