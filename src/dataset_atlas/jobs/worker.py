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
            if not output.exists():
                try:
                    result = run_processor(plan["processor_id"], [item["record"] for item in plan["items"]], plan["config"])
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
