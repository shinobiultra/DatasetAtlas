"""Processors that use a local model server: answers, tags, verdicts, embeddings, and VQA scoring of saved answers.

These run only in columnar mode. Their results are text and numbers per record, stored as arrays and text columns, so a
whole dataset's answers are a few files rather than a JSON item each, and they join onto records like any other result.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from dataset_atlas.models import Record, content_id
from dataset_atlas.storage import arrays as store
from dataset_atlas.vlm import client as model_client
from dataset_atlas.vlm import images, tasks, vqa
from .bulk import BulkResult

KINDS = {"vlm.answer": "answer", "vlm.tag": "tag", "vlm.judge": "judge"}
_THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)
_RESERVED = {"status", "prompt_tokens", "completion_tokens", "latency_ms", "finish_reason"}


@dataclass
class Plan:
    kind: str
    template: str
    system: str | None
    use_images: bool
    schema: dict[str, Any] | None
    explain: bool
    max_tokens: int
    temperature: float
    thinking: bool | None
    extra_body: dict[str, Any]
    image_options: dict[str, int]
    provider: dict[str, Any]
    api: str
    concurrency: int
    spell_out_schema: bool = True


def _bounded_int(config: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = config.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer within {low}..{high}")
    return value


def make_plan(processor_id: str, config: dict[str, Any]) -> Plan:
    if processor_id not in KINDS:
        raise ValueError(f"Unknown model-server processor: {processor_id}")
    kind = KINDS[processor_id]
    provider = config.get("provider")
    if not isinstance(provider, dict) or not provider.get("base_url") or not provider.get("model"):
        raise ValueError("Choose a model server (provider_id) for this run")
    if not model_client.is_loopback(str(provider["base_url"])):
        raise ValueError("Batch model runs send only to a loopback server")
    preset = tasks.PRESETS[kind]
    template = config.get("template", preset["template"])
    if not isinstance(template, str) or not template.strip() or len(template) > min(4000, int(provider.get("max_input_characters", 4000))):
        raise ValueError("template must be a non-empty string within the provider's input limit")
    cap = int(provider.get("max_output_tokens", 512))
    max_tokens = _bounded_int(config, "max_tokens", min(preset["max_tokens"], cap), 1, cap)
    temperature = config.get("temperature", 0.0)
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ValueError("temperature must be within 0..2")
    thinking = config.get("thinking")
    if thinking is not None and not isinstance(thinking, bool):
        raise ValueError("thinking must be true, false or unset")
    extra_body = config.get("extra_body") or {}
    if not isinstance(extra_body, dict) or len(json.dumps(extra_body)) > 4096:
        raise ValueError("extra_body must be a small JSON object")
    use_images = config.get("use_images", preset["use_images"])
    if not isinstance(use_images, bool):
        raise ValueError("use_images must be true or false")
    if use_images and int(provider.get("max_images", 2)) < 1:
        raise ValueError("This provider is configured for no images")
    schema = None
    explain = bool(config.get("explain", False))
    if kind == "tag":
        schema = tasks.tag_schema(config.get("schema") or [])
    elif kind == "judge":
        schema = tasks.judge_schema(explain)
    structured = config.get("structured", "auto")
    if structured not in {"auto", "on", "off"}:
        raise ValueError("structured must be auto, on or off")
    return Plan(kind=kind, template=template, system=config.get("system") if isinstance(config.get("system"), str) else None,
                use_images=use_images, schema=schema if structured != "off" else None, explain=explain, max_tokens=max_tokens,
                temperature=float(temperature), thinking=thinking, extra_body=extra_body,
                image_options={"max_side": _bounded_int(config, "image_max_side", 672, 64, 2048), "quality": _bounded_int(config, "image_quality", 90, 50, 100),
                               "max_pixels": _bounded_int(config, "max_pixels", 50_000_000, 1, 200_000_000)},
                provider=provider, api=str(config.get("api", "auto")), concurrency=_bounded_int(config, "concurrency", 16, 1, 128),
                spell_out_schema=bool(config.get("spell_out_schema", True)))


def _image_asset(record: Record):
    return next((asset for asset in record.assets if asset.modality.lower() in {"image", "photo"}), None)


@lru_cache(maxsize=2)
def _text_column(directory: str, ids_sha: str, text_sha: str, column: str, manifest_json: str) -> dict[str, str]:
    manifest = json.loads(manifest_json)
    return dict(zip(store.read_ids(Path(directory), manifest), store.read_texts(Path(directory), manifest["texts"][column])))


def load_text_column(source: dict[str, Any]) -> dict[str, str]:
    """Saved text results (a model's answers) keyed by record id, from an array-backed artifact referenced by the run.

    Read once per worker process however many groups of records the run is split into.
    """
    manifest = source["manifest"]
    column = source.get("column", "answer")
    if column not in manifest.get("texts", {}):
        raise ValueError(f"The saved results have no text column {column!r}")
    return _text_column(str(source["dir"]), manifest["ids"]["sha256"], manifest["texts"][column]["sha256"], column, json.dumps(manifest, sort_keys=True))


def _candidate_and_reference(record: Record, config: dict[str, Any], candidates: dict[str, str] | None):
    candidate = candidates.get(record.id) if candidates is not None else (tasks.record_value(record, config["candidate_field"]) if config.get("candidate_field") else None)
    reference = tasks.record_value(record, config["reference_field"]) if config.get("reference_field") else None
    return candidate, reference


def build_messages(plan: Plan, record: Record, *, candidate: str | None = None, reference: Any = None, encoded_image: str | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if plan.system:
        messages.append({"role": "system", "text": plan.system})
    text = tasks.render(plan.template, record, candidate=candidate, reference=reference)
    if plan.schema is not None and plan.spell_out_schema:
        text += "\n\n" + tasks.schema_instruction(plan.schema)
    user: dict[str, Any] = {"role": "user", "text": text}
    if encoded_image:
        user["images"] = [encoded_image]
    messages.append(user)
    return messages


def estimate_model_run(processor_id: str, records: list[Any], config: dict[str, Any]) -> dict[str, Any]:
    """What the run will send, without sending anything: the server, the counts and the first record's exact prompt."""
    plan = make_plan(processor_id, config) if processor_id in KINDS else None
    provider = config.get("provider") or {}
    info: dict[str, Any] = {"remote_calls": len(records), "loopback_only": True, "provider": {k: provider.get(k) for k in ("id", "model", "base_url")},
                            "concurrency": plan.concurrency if plan else config.get("concurrency", 16)}
    if plan and records:
        first = records[0]
        candidates = load_text_column(config["text_source"]) if config.get("text_source") else None
        candidate, reference = _candidate_and_reference(first, config, candidates)
        messages = build_messages(plan, first, candidate=candidate, reference=reference)
        asset = _image_asset(first) if plan.use_images else None
        info.update({"template": plan.template, "max_tokens": plan.max_tokens, "temperature": plan.temperature, "thinking": plan.thinking,
                     "structured_output": plan.schema is not None, "images_per_request": 1 if plan.use_images else 0,
                     "example_record": first.id, "example_prompt": [{"role": m["role"], "text": m["text"]} for m in messages],
                     "example_image": {"asset_id": asset.id, "resized_to_max_side": plan.image_options["max_side"]} if asset else None})
    return info


def run_model_task(processor_id: str, records: list[Record], config: dict[str, Any]):
    plan = make_plan(processor_id, config)
    server = model_client.ModelServer(plan.provider, api=plan.api, concurrency=plan.concurrency)
    roots = list(config.get("asset_roots", []))
    candidates = load_text_column(config["text_source"]) if config.get("text_source") else None
    if plan.kind == "judge" and candidates is None and not config.get("candidate_field"):
        raise ValueError("Judging needs saved answers (candidate_artifact_id) or a candidate_field")
    skipped: dict[str, dict[str, Any]] = {}

    def skip(record: Record, status: str, error: str | None = None):
        skipped[record.id] = {"status": status, **({"error": error} if error else {})}

    encoded: dict[str, str | Exception] = {}
    if plan.use_images:
        encoded = images.encode_many([asset for asset in (_image_asset(record) for record in records) if asset], roots, **plan.image_options)
    sendable: list[tuple[Record, list[dict[str, Any]]]] = []
    for record in records:
        candidate, reference = _candidate_and_reference(record, config, candidates)
        if plan.kind == "answer" and not (record.question or "").strip():
            skip(record, "not_applicable", "The record has no question")
            continue
        if plan.kind == "judge" and not (candidate or "").strip():
            skip(record, "not_applicable", "No saved answer to judge for this record")
            continue
        picture = None
        if plan.use_images:
            asset = _image_asset(record)
            if asset is None:
                skip(record, "not_applicable", "The record has no image")
                continue
            picture = encoded[asset.id]
            if isinstance(picture, Exception):
                skip(record, "failed", f"{type(picture).__name__}: {picture}"[:300])
                continue
        sendable.append((record, build_messages(plan, record, candidate=candidate, reference=reference, encoded_image=picture)))
    requests = [server.chat_request(messages, max_tokens=plan.max_tokens, temperature=plan.temperature, schema=plan.schema,
                                    thinking=plan.thinking if plan.thinking is not None else (False if server.api == "ollama" else None), extra=plan.extra_body)
                for _, messages in sendable]
    replies = server.complete_many(requests)
    ids: list[str] = []
    columns: dict[str, list[Any]] = defaultdict(list)
    prompt_tokens: list[int] = []
    completion_tokens: list[int] = []
    latency: list[float] = []
    for (record, _), reply in zip(sendable, replies):
        if isinstance(reply, model_client.ModelServerError):
            skip(record, "failed", str(reply))
            continue
        text = _THINKING.sub("", reply.text).strip()
        try:
            if not text:
                if reply.reasoned:
                    raise ValueError(f"The model spent its whole token budget reasoning and replied with nothing (stopped: {reply.finish_reason or 'unknown'}); "
                                     "raise max_tokens, set thinking to false, or use a non-thinking variant of the model")
                raise ValueError(f"The model returned nothing (stopped: {reply.finish_reason or 'unknown'})")
            if plan.kind == "answer":
                row = {"answer": tasks.clean_answer(text)}
                if not row["answer"]:
                    raise ValueError("The model returned no answer text")
            elif plan.kind == "tag":
                typed = tasks.parse_tags(text, plan.schema or {})
                row = {name: (("true" if value else "false") if isinstance(value, bool) else str(value)) for name, value in typed.items()}
            else:
                row = tasks.parse_verdict(text, plan.explain)
        except ValueError as exc:
            skip(record, "failed", str(exc))
            continue
        ids.append(record.id)
        for name, value in row.items():
            columns[name].append(value)
        if plan.kind == "tag":
            for name, value in typed.items():
                columns[f"__typed_{name}"].append(value)
        columns["finish_reason"].append(reply.finish_reason or "")
        prompt_tokens.append(-1 if reply.prompt_tokens is None else int(reply.prompt_tokens))
        completion_tokens.append(-1 if reply.completion_tokens is None else int(reply.completion_tokens))
        latency.append(float(reply.latency_ms))
    texts: dict[str, list[str]] = {}
    arrays: dict[str, np.ndarray] = {"prompt_tokens": np.asarray(prompt_tokens, dtype=np.int32), "completion_tokens": np.asarray(completion_tokens, dtype=np.int32),
                                    "latency_ms": np.asarray(latency, dtype=np.float32)}
    for name, values in columns.items():
        if name.startswith("__typed_"):
            continue
        spec = (plan.schema or {}).get("properties", {}).get(name) if plan.kind == "tag" else None
        if spec and spec["type"] == "boolean":
            arrays[name] = np.asarray([1 if v == "true" else 0 for v in values], dtype=np.int8)
        elif spec and spec["type"] == "number":
            arrays[name] = np.asarray(columns[f"__typed_{name}"], dtype=np.float32)
        else:
            texts[name] = values
    if plan.kind == "judge":
        arrays["correct"] = np.asarray([1 if v == "correct" else 0 if v == "incorrect" else -1 for v in columns["verdict"]], dtype=np.int8)
    example = estimate_model_run(processor_id, records[:1], config)
    provenance = {"method": "model server", "kind": plan.kind, "api": server.api,
                  "provider": {k: plan.provider.get(k) for k in ("id", "model", "base_url")},
                  "parameters": {"template": plan.template, "system": plan.system, "max_tokens": plan.max_tokens, "temperature": plan.temperature, "thinking": plan.thinking,
                                 "structured_output": plan.schema is not None, "use_images": plan.use_images, "image": plan.image_options if plan.use_images else None,
                                 "concurrency": plan.concurrency, "extra_body": plan.extra_body or None, **({"schema": plan.schema} if plan.schema else {})},
                  "template_sha256": content_id({"template": plan.template, "system": plan.system, "schema": plan.schema}, "prompt:"),
                  "example_prompt": example.get("example_prompt"), "sent": len(sendable)}
    return BulkResult(ids=ids, arrays=arrays, texts=texts, skipped=skipped, provenance=provenance,
                      summary=model_run_summary(plan, ids, columns, skipped, prompt_tokens, completion_tokens, latency)), provenance


def model_run_summary(plan: Plan, ids: list[str], columns: dict[str, list[Any]], skipped: dict[str, dict[str, Any]],
                      prompt_tokens: list[int], completion_tokens: list[int], latency: list[float]) -> dict[str, Any]:
    """What a finished model run looks like at a glance: how many records got a reply, why the rest did not, and the cost."""
    reasons: dict[str, int] = defaultdict(int)
    for entry in skipped.values():
        reasons[entry.get("error") or entry["status"]] += 1
    counted = lambda values: sum(value for value in values if value >= 0)
    summary: dict[str, Any] = {"kind": plan.kind, "completed": len(ids), "not_completed": len(skipped),
                               "reasons": [{"reason": reason, "count": count} for reason, count in sorted(reasons.items(), key=lambda item: -item[1])[:10]],
                               "prompt_tokens": counted(prompt_tokens), "completion_tokens": counted(completion_tokens),
                               "mean_latency_ms": round(float(np.mean(latency)), 1) if latency else None}
    if plan.kind == "judge":
        verdicts: dict[str, int] = defaultdict(int)
        for verdict in columns["verdict"]:
            verdicts[verdict] += 1
        summary["verdicts"] = dict(verdicts)
    if plan.kind == "tag":
        # How the values are spread, for the fields with a few distinct values (enums and yes/no).
        spread: dict[str, list[dict[str, Any]]] = {}
        for name, spec in (plan.schema or {}).get("properties", {}).items():
            if spec["type"] in {"string", "boolean"} and not (spec["type"] == "string" and "enum" not in spec):
                counts: dict[str, int] = defaultdict(int)
                for value in columns[name]:
                    counts[value] += 1
                spread[name] = [{"value": value, "count": count} for value, count in sorted(counts.items(), key=lambda item: -item[1])[:12]]
        summary["values"] = spread
    return summary


def run_api_embeddings(records: list[Record], config: dict[str, Any]):
    provider = config.get("provider")
    if not isinstance(provider, dict) or not provider.get("base_url") or not provider.get("model"):
        raise ValueError("Choose a model server (provider_id) that serves an embedding model")
    mode = str(config.get("representation", "text"))
    if mode not in {"text", "question"}:
        raise ValueError("representation must be text or question")
    storage_dtype = str(config.get("storage_dtype", "float32"))
    if storage_dtype not in {"float32", "float16"}:
        raise ValueError("storage_dtype must be float32 or float16")
    document_prefix = _prefix(config, "document_prefix")
    query_prefix = _prefix(config, "query_prefix")
    server = model_client.ModelServer(provider, api="openai", concurrency=_bounded_int(config, "concurrency", 8, 1, 64))
    skipped: dict[str, dict[str, Any]] = {}
    owners: list[Record] = []
    texts: list[str] = []
    for record in records:
        value = getattr(record, mode)
        if isinstance(value, str) and value.strip():
            owners.append(record)
            texts.append(document_prefix + value)
        else:
            skipped[record.id] = {"status": "not_applicable"}
    results = server.embed_many(texts, batch_size=_bounded_int(config, "batch_size", 64, 1, 512))
    ids: list[str] = []
    rows: list[np.ndarray] = []
    for record, result in zip(owners, results):
        if isinstance(result, model_client.ModelServerError):
            skipped[record.id] = {"status": "failed", "error": str(result)}
            continue
        norm = float(np.linalg.norm(result))
        if not np.isfinite(result).all() or norm == 0:
            skipped[record.id] = {"status": "failed", "error": "The embedding was zero or not finite"}
            continue
        ids.append(record.id)
        rows.append(result / norm)
    matrix = np.stack(rows).astype(storage_dtype) if rows else np.zeros((0, 0), dtype=storage_dtype)
    recipe = {"model_id": str(provider["model"]), "source": "model server /v1/embeddings", "representation": mode,
              "dimension": int(matrix.shape[1]) if len(rows) else None, "normalization": "L2", "distance_metric": "cosine"}
    if document_prefix:
        recipe["document_prefix"] = document_prefix  # changes the stored vectors, so it is part of the space's identity
    if query_prefix:
        recipe["query_prefix"] = query_prefix  # only changes how a search text is encoded, so it is not
    identity = ("model_id", "source", "representation", "normalization", "distance_metric") + (("document_prefix",) if document_prefix else ())
    provenance = {"model_id": recipe["model_id"], "provider": {k: provider.get(k) for k in ("id", "model", "base_url")}, "recipe": recipe,
                  "embedding_space_id": content_id({key: recipe[key] for key in identity}, "space:"),
                  "storage_dtype": storage_dtype, "path": "model server", "method": "model server embeddings"}
    return BulkResult(ids=ids, arrays={"vector": matrix}, skipped=skipped, provenance=provenance), provenance


def _prefix(config: dict[str, Any], key: str) -> str:
    value = config.get(key) or ""
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError(f"{key} must be text of at most 200 characters")
    return value


def encode_api_query(provider: dict[str, Any], recipe: dict[str, Any], text: str) -> list[float]:
    """Embed a search text with the model server that produced a stored space, the way that space's recipe says."""
    if provider.get("model") != recipe.get("model_id"):
        raise ValueError("The model server now serves a different model than the one that embedded this dataset")
    server = model_client.ModelServer(provider, api="openai", concurrency=1)
    (result,) = server.embed_many([str(recipe.get("query_prefix") or "") + text], batch_size=1)
    if isinstance(result, model_client.ModelServerError):
        raise ValueError(f"The model server could not embed the query: {result}")
    norm = float(np.linalg.norm(result))
    if not np.isfinite(result).all() or norm == 0:
        raise ValueError("The query embedding was zero or not finite")
    if recipe.get("dimension") and len(result) != recipe["dimension"]:
        raise ValueError("The query vector has a different dimension than the stored vectors")
    return (result / norm).tolist()


def run_vqa_scoring(records: list[Record], config: dict[str, Any]):
    if not config.get("text_source"):
        raise ValueError("Scoring needs saved answers (answers_artifact_id)")
    candidates = load_text_column(config["text_source"])
    answers_field = str(config.get("answers_field", "source.answers"))
    group_fields = [str(field) for field in config.get("group_fields", ["source.question_type", "source.answer_type"])]
    ids: list[str] = []
    scores: list[float] = []
    skipped: dict[str, dict[str, Any]] = {}
    groups: dict[str, dict[str, list[float]]] = {field: defaultdict(list) for field in group_fields}
    for record in records:
        candidate = candidates.get(record.id)
        if candidate is None:
            skipped[record.id] = {"status": "not_applicable", "error": "No saved answer for this record"}
            continue
        try:
            humans = vqa.answer_texts(tasks.record_value(record, answers_field) or [])
        except ValueError as exc:
            skipped[record.id] = {"status": "failed", "error": str(exc)}
            continue
        if not humans:
            skipped[record.id] = {"status": "not_applicable", "error": "The record has no human answers"}
            continue
        score = vqa.vqa_accuracy(candidate, humans)
        ids.append(record.id)
        scores.append(score)
        for field in group_fields:
            groups[field][str(tasks.record_value(record, field))].append(score)
    mean = lambda values: round(float(np.mean(values)), 6) if values else None
    summary = {"metric": "vqa_accuracy", "scored": len(ids), "unscored": len(skipped), "mean_accuracy": mean(scores),
               "by": {field: sorted(({"value": value, "count": len(values), "mean_accuracy": mean(values)} for value, values in table.items()),
                                    key=lambda row: -row["count"])[:50] for field, table in groups.items()}}
    provenance = {"method": "VQA accuracy, official formula and normalisation (reimplemented; GT-Vision-Lab/VQA vqaEval.py)", "metric": "vqa_accuracy",
                  "answers_field": answers_field, "group_fields": group_fields, "candidate_artifact_id": config.get("answers_artifact_id"),
                  "parameters": {"answers_field": answers_field, "group_fields": group_fields}, "summary": {"mean_accuracy": summary["mean_accuracy"], "scored": len(ids)}}
    return BulkResult(ids=ids, arrays={"accuracy": np.asarray(scores, dtype=np.float32)}, skipped=skipped, summary=summary, provenance=provenance), provenance
