"""What to ask a model about a record, and how to read what it says: answers, tags and verdicts.

Prompts are templates over a handful of named placeholders, rendered per record, so a run's exact wording is in its
configuration (and its estimate shows the first record's rendered prompt). Replies are validated, never trusted: a reply that
does not parse or does not fit the requested schema is a failed record with a reason, not a silent guess.
"""
from __future__ import annotations

import json
import re
from typing import Any

PLACEHOLDER = re.compile(r"\{(question|text|choices|candidate|reference|field:[A-Za-z0-9_.:-]+)\}")
_ANSWER_PREFIX = re.compile(r"^\s*(?:final\s+)?answer\s*[:\-]\s*", re.IGNORECASE)

PRESETS: dict[str, dict[str, Any]] = {
    "answer": {
        "template": "Answer the question about the image with a single word or short phrase. Do not explain.\nQuestion: {question}",
        "use_images": True, "max_tokens": 24,
    },
    "tag": {
        "template": "Fill in the requested fields for this example.\nQuestion: {question}\nText: {text}",
        "use_images": False, "max_tokens": 160,
    },
    "judge": {
        "template": ("You are checking an answer.\nQuestion: {question}\nProposed answer: {candidate}\nReference answers: {reference}\n"
                     "Does the proposed answer mean the same as the reference answers? Reply with a verdict."),
        "use_images": False, "max_tokens": 96,
    },
}
VERDICTS = ("correct", "incorrect", "unsure")


def record_value(record: Any, field_id: str) -> Any:
    """A record's field by id (``source.x``, ``prediction.x``, ``human.x``, or ``record.id|text|question|unit``)."""
    namespace, _, key = field_id.partition(".")
    if namespace == "record":
        if key not in {"id", "text", "question", "unit"}:
            raise ValueError(f"Unsupported record field: {field_id}")
        return getattr(record, key, None)
    if namespace not in {"source", "prediction", "human"} or not key:
        raise ValueError(f"A record field must be namespace.key, not {field_id!r}")
    return (getattr(record, namespace, None) or {}).get(key)


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " | ".join(_plain(item.get("answer") if isinstance(item, dict) and "answer" in item else item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def referenced_fields(config: dict[str, Any]) -> list[str]:
    """Record field ids a run reads beyond the standard ones, so a run freezes just those."""
    fields = [m.group(1)[6:] for m in PLACEHOLDER.finditer(str(config.get("template", ""))) if m.group(1).startswith("field:")]
    for key in ("reference_field", "candidate_field", "answers_field"):
        if config.get(key):
            fields.append(str(config[key]))
    fields.extend(str(field) for field in config.get("group_fields", []))
    return list(dict.fromkeys(fields))


def render(template: str, record: Any, *, candidate: str | None = None, reference: Any = None) -> str:
    def value(match: re.Match) -> str:
        name = match.group(1)
        if name == "question":
            return _plain(record.question)
        if name == "text":
            return _plain(record.text)
        if name == "choices":
            return "\n".join(f"- {_plain(choice)}" for choice in record.choices)
        if name == "candidate":
            return _plain(candidate)
        if name == "reference":
            return _plain(reference)
        return _plain(record_value(record, name[6:]))
    return PLACEHOLDER.sub(value, template)


# --- structured output ---------------------------------------------------------

def tag_schema(properties: list[dict[str, Any]]) -> dict[str, Any]:
    """JSON Schema for the requested tag fields: ``{"name", "type": enum|string|boolean|number, "values"?, "description"?}``."""
    if not 1 <= len(properties) <= 16:
        raise ValueError("Tagging needs between 1 and 16 fields")
    schema: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    for item in properties:
        name, kind = item.get("name"), item.get("type", "string")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
            raise ValueError("A tag name must be lower-case letters, digits and underscores")
        if name in schema["properties"] or name in {"status", "prompt_tokens", "completion_tokens", "latency_ms", "finish_reason"}:
            raise ValueError(f"Tag name {name!r} repeats or collides with a result column")
        if kind == "enum":
            values = item.get("values")
            if not isinstance(values, list) or not 2 <= len(values) <= 64 or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"Enum tag {name} needs 2 to 64 non-empty string values")
            schema["properties"][name] = {"type": "string", "enum": values}
        elif kind in {"string", "boolean", "number"}:
            schema["properties"][name] = {"type": kind}
        else:
            raise ValueError(f"Tag type must be enum, string, boolean or number, not {kind!r}")
        if item.get("description"):
            schema["properties"][name]["description"] = str(item["description"])[:300]
        schema["required"].append(name)
    return schema


def schema_instruction(schema: dict[str, Any]) -> str:
    """Say in words which JSON object is wanted. Servers differ in whether they enforce a response schema (a model that
    ignores it returns other keys or prose), so the prompt asks for it too and the reply is validated regardless."""
    lines = []
    for name, spec in schema["properties"].items():
        kind = "true or false" if spec["type"] == "boolean" else "a number" if spec["type"] == "number" else (
            "one of: " + ", ".join(spec["enum"]) if "enum" in spec else "a string")
        lines.append(f"- {name}: {kind}" + (f" ({spec['description']})" if spec.get("description") else ""))
    return "Reply with only a JSON object with exactly these keys, and nothing else:\n" + "\n".join(lines)


def judge_schema(explain: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {"verdict": {"type": "string", "enum": list(VERDICTS)}}
    if explain:
        properties["explanation"] = {"type": "string"}
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _json_object(text: str) -> dict[str, Any]:
    """The reply as a JSON object, tolerating a code fence or prose around it (not every server enforces the schema)."""
    candidate = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except ValueError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The reply was not JSON")
        try:
            value = json.loads(candidate[start:end + 1])
        except ValueError as exc:
            raise ValueError("The reply was not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("The reply was JSON but not an object")
    return value


def parse_tags(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Validated values per tag field, typed (str, bool, float)."""
    reply = _json_object(text)
    parsed: dict[str, Any] = {}
    for name, spec in schema["properties"].items():
        if name not in reply:
            raise ValueError(f"The reply has no {name!r} field")
        value = reply[name]
        kind = spec["type"]
        if kind == "string":
            if not isinstance(value, str) or ("enum" in spec and value not in spec["enum"]):
                raise ValueError(f"{name!r} is not one of the allowed values" if "enum" in spec else f"{name!r} is not a string")
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{name!r} is not true or false")
        elif kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name!r} is not a number")
            value = float(value)
        parsed[name] = value
    return parsed


def parse_verdict(text: str, explain: bool) -> dict[str, str]:
    reply = _json_object(text)
    verdict = reply.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError("The verdict is not correct, incorrect or unsure")
    return {"verdict": verdict, **({"explanation": str(reply.get("explanation", ""))[:1000]} if explain else {})}


def clean_answer(text: str) -> str:
    """One short answer: first non-empty line, an 'Answer:' prefix and wrapping quotes removed."""
    for line in text.strip().splitlines():
        line = _ANSWER_PREFIX.sub("", line.strip()).strip()
        if line:
            return line.strip("\"'`").strip()
    return ""
