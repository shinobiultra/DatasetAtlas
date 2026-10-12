"""Subprocess entry point. Workers write staged files; only the coordinator writes SQLite."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


class OutputBudgetExceeded(Exception):
    pass


def _atomic_json(path: Path, value: dict, max_bytes: int) -> int:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    if len(payload) > max_bytes:
        raise OutputBudgetExceeded("Staged output exceeds the approved byte budget")
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return len(payload)


def _write_shard(stage: Path, group_id: str, key_map: dict[str, str], result: dict, array_budget: int) -> int:
    """Write one columnar result as ``shard-<id>/`` and publish it with an atomic directory rename.

    The coordinator imports a shard only once its ``meta.json`` is complete, so a worker killed
    mid-write leaves nothing it would trust. Returns the array bytes written.
    """
    from dataset_atlas.storage.arrays import write_bundle
    bulk = result["bulk"]
    work = stage / f".shard-{group_id}.{uuid4().hex}.tmp"
    work.mkdir()
    try:
        manifest = write_bundle(work, bulk.ids, bulk.arrays, bulk.extras)
        size = sum(entry["bytes"] for group in ("arrays", "extras") for entry in manifest.get(group, {}).values())
        if size > array_budget:
            raise OutputBudgetExceeded("Staged arrays exceed the approved byte budget")
        meta = {"keys": key_map, "skipped": bulk.skipped, "summary": bulk.summary, "manifest": manifest, "array_bytes": size,
                "provenance": result["provenance"], "coverage": result["coverage"], "processor_id": result["processor_id"], "unit": result["unit"]}
        (work / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, allow_nan=False), encoding="utf-8")
        descriptor = os.open(work, os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(work, stage / f"shard-{group_id}")
        return size
    except BaseException:
        import shutil
        shutil.rmtree(work, ignore_errors=True)
        raise


def _record_batches(items: list[dict], size: int) -> list[list[dict]]:
    return [items[start:start + size] for start in range(0, len(items), size)]


def _asset_batches(items: list[dict], max_records: int = 16) -> list[list[dict]]:
    """Keep all references to one asset in one checkpointed processor batch."""
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    seen: dict[str, int] = {}
    for index, item in enumerate(items):
        for asset in item["record"].get("assets", []):
            identity = asset.get("sha256") or asset["id"]
            if identity in seen:
                parent[find(index)] = find(seen[identity])
            else:
                seen[identity] = index
    components: dict[int, list[dict]] = {}
    for index, item in enumerate(items):
        components.setdefault(find(index), []).append(item)
    batches: list[list[dict]] = []
    current: list[dict] = []
    for component in components.values():
        if current and len(current) + len(component) > max_records:
            batches.append(current)
            current = []
        current.extend(component)
    if current:
        batches.append(current)
    return batches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.input.read_text(encoding="utf-8"))
    from dataset_atlas.jobs.limits import install
    install(plan.get('config', {}), args.input.parent)
    budget = plan.get("budget_remaining_bytes", plan.get("config", {}).get("max_output_bytes", 64 * 1024 * 1024))
    if type(budget) is not int or budget < 0:
        raise ValueError("Invalid remaining output budget")
    stage = args.input.parent
    with (stage / "worker.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 75
        from dataset_atlas.processors import run_processor

        if plan.get("batching") == "selection":
            if (stage / "cancel").exists():
                return 0
            output = stage / "batch.json"
            key_map = {item["record"]["id"]: item["key"] for item in plan["items"]}
            shard = stage / f"shard-{hashlib.sha256(json.dumps(key_map, sort_keys=True).encode()).hexdigest()[:24]}"
            if not output.exists() and not shard.exists():
                try:
                    result = run_processor(plan["processor_id"], [item["record"] for item in plan["items"]], plan["config"])
                    if result.get("bulk") is not None:
                        _write_shard(stage, shard.name[6:], key_map, result, plan.get("array_bytes_remaining", 0))
                        return 0
                    if hasattr(result, "model_dump"):
                        result = result.model_dump(mode="json")
                    value = {"keys": {item["record"]["id"]: item["key"] for item in plan["items"]}, "result": result}
                except Exception as exc:
                    value = {"keys": {item["record"]["id"]: item["key"] for item in plan["items"]},
                             "result": {"items": [{"id": item["record"]["id"], "status": "failed",
                                                    "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
                                                   for item in plan["items"]]}}
                budget -= _atomic_json(output, value, budget)
            return 0
        arrays_mode = plan.get("config", {}).get("storage") == "arrays"
        if arrays_mode and plan.get("batching") in ("assets", "records"):
            size = int(plan["config"].get("batch_records", 512))
            groups = _asset_batches(plan["items"], size) if plan["batching"] == "assets" else _record_batches(plan["items"], size)
            remaining = plan.get("array_bytes_remaining", 0)
            for group in groups:
                if (stage / "cancel").exists():
                    return 0
                key_map = {item["record"]["id"]: item["key"] for item in group}
                group_id = hashlib.sha256(json.dumps(key_map, sort_keys=True).encode()).hexdigest()[:24]
                if (stage / f"shard-{group_id}").exists():
                    continue
                try:
                    result = run_processor(plan["processor_id"], [item["record"] for item in group], plan["config"])
                    if result.get("bulk") is None:
                        raise ValueError("Processor did not return columnar output in arrays mode")
                    remaining -= _write_shard(stage, group_id, key_map, result, remaining)
                except OutputBudgetExceeded:
                    raise
                except Exception as exc:
                    failed = {"items": [{"id": item["record"]["id"], "status": "failed",
                                         "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}} for item in group]}
                    budget -= _atomic_json(stage / f"group-{group_id}.json", {"keys": key_map, "result": failed}, budget)
            return 0
        if plan.get("batching") == "assets":
            for group in _asset_batches(plan["items"]):
                if (stage / "cancel").exists():
                    return 0
                key_map = {item["record"]["id"]: item["key"] for item in group}
                group_id = hashlib.sha256(json.dumps(key_map, sort_keys=True).encode()).hexdigest()[:24]
                output = stage / f"group-{group_id}.json"
                if output.exists():
                    continue
                try:
                    result = run_processor(plan["processor_id"], [item["record"] for item in group], plan["config"])
                    if hasattr(result, "model_dump"):
                        result = result.model_dump(mode="json")
                except Exception as exc:
                    result = {"items": [{"id": item["record"]["id"], "status": "failed",
                                         "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
                                        for item in group]}
                budget -= _atomic_json(output, {"keys": key_map, "result": result}, budget)
            return 0
        for item in plan["items"]:
            if (stage / "cancel").exists():
                return 0
            output = stage / (item["key"] + ".json")
            if output.exists():
                continue
            try:
                result = run_processor(plan["processor_id"], [item["record"]], plan["config"])
                if hasattr(result, "model_dump"):
                    result = result.model_dump(mode="json")
                value = {"key": item["key"], "record_id": item["record"]["id"], "result": result}
            except Exception as exc:
                value = {"key": item["key"], "record_id": item["record"]["id"],
                         "result": {"items": [{"id": item["record"]["id"], "status": "failed",
                                                "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}]}}
            budget -= _atomic_json(output, value, budget)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OutputBudgetExceeded:
        raise SystemExit(76)
