"""Durable, single-writer run coordinator for trusted local processors."""
from __future__ import annotations

import hashlib
import fcntl
import shutil
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from dataset_atlas.models import Artifact, Record, Run, Selection
from dataset_atlas.storage.local import read_rooted_file

DEFAULT_MAX_OUTPUT_BYTES = 64 * 1024 * 1024
HARD_MAX_OUTPUT_BYTES = 512 * 1024 * 1024
# Columnar ("arrays") runs write binary arrays, not JSON, so their budget is measured in array bytes.
DEFAULT_ARRAY_BYTES = 8 * 1024 ** 3
HARD_MAX_ARRAY_BYTES = 64 * 1024 ** 3


def _frozen_documents(processor_id: str, config: dict, parsed: list[Record]) -> list[dict]:
    """The records as a run freezes and ships them.

    A columnar run freezes what its processor reads, not whole records: identity for projection, clustering and
    neighbours (they read vectors by id), and the text and assets for embeddings. Dumping and parsing every answer of
    every record of a 200k-record run cost minutes, and a snapshot is immutable, so the selection already pins the rest.
    """
    if not _uses_arrays(config) or not processor_id.startswith(("embed.", "project.", "cluster.", "outlier.", "vlm.", "score.")):
        return [record.model_dump(mode="json") for record in parsed]
    content = processor_id.startswith(("embed.", "vlm.", "score."))
    fields = [str(field) for field in config.get("record_fields", [])]
    documents = []
    for record in parsed:
        document = {"id": record.id, "dataset_id": record.dataset_id, "release_id": record.release_id, "snapshot_id": record.snapshot_id, "unit": record.unit}
        if content:
            document.update(text=record.text, question=record.question, choices=list(record.choices), asset_ids=list(record.asset_ids),
                            assets=[asset.model_dump(mode="json") for asset in record.assets])
            for field in fields:  # only the record fields this run's prompts and scoring refer to
                namespace, _, key = field.partition(".")
                if namespace in {"source", "prediction", "human"} and key in getattr(record, namespace):
                    document.setdefault(namespace, {})[key] = getattr(record, namespace)[key]
        documents.append(document)
    return documents


def _uses_arrays(config: dict) -> bool:
    storage = config.get("storage", "json")
    if storage not in ("json", "arrays"):
        raise ValueError("storage must be json or arrays")
    return storage == "arrays"


def _output_budget(config: dict) -> int:
    return config.get("max_output_bytes", DEFAULT_ARRAY_BYTES if _uses_arrays(config) else DEFAULT_MAX_OUTPUT_BYTES)


def _hard_budget(config: dict) -> int:
    return HARD_MAX_ARRAY_BYTES if _uses_arrays(config) else HARD_MAX_OUTPUT_BYTES


def _resource_class(description,config):
    if config.get('resource_class'):return config['resource_class']
    device=str(config.get('device','auto' if description.get('supported_devices') else description['device'])).lower()
    # Auto may select an accelerator inside the worker. Reserve its exclusive
    # lease conservatively without importing the ML stack in the API process.
    if description.get('supported_devices') and device in {'auto','mps'}:return 'gpu'
    # Columnar analysis may run on the GPU (cuML, torch); take the same exclusive lease so it cannot contend with an embedding run for VRAM.
    if description.get('backends') and config.get('storage')=='arrays' and config.get('backend','auto')!='cpu':return 'gpu'
    return 'gpu' if device.startswith(('cuda','gpu')) else description['device']


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_once(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _json(value).encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Immutable artifact collision: {path.name}")
        return
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError(f"Immutable artifact collision: {path.name}")
    finally:
        temporary.unlink(missing_ok=True)
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class JobManager:
    """One coordinator per work directory. Call close() on service shutdown.

    Processor code is resolved only inside the trusted worker process through
    ``dataset_atlas.processors.run_processor``. Run inputs are frozen at create.
    """

    def __init__(self, work_dir: str | Path, *, auto_recover: bool = True):
        self.work_dir = Path(work_dir).resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.work_dir / "jobs.sqlite3"
        self.artifact_dir = self.work_dir / "artifacts"
        self.stage_dir = self.work_dir / "jobs"
        self.artifact_dir.mkdir(exist_ok=True)
        self.stage_dir.mkdir(exist_ok=True)
        self._active: dict[str, threading.Thread] = {}
        self._guard = threading.RLock()
        self._closed = False
        # Registered artifacts are immutable (INSERT OR IGNORE, never updated),
        # so each is parsed once; embedding runs alone are tens of megabytes.
        self._artifacts: dict[str, Artifact] = {}
        self._artifact_lock = threading.Lock()
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                  id TEXT PRIMARY KEY, run_json TEXT NOT NULL,
                  selection_json TEXT NOT NULL, records_json TEXT NOT NULL,
                  cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS run_items (
                  run_id TEXT NOT NULL, record_id TEXT NOT NULL, item_key TEXT NOT NULL,
                  status TEXT NOT NULL, error_json TEXT, output_bytes INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY(run_id, record_id), FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS completed_items (
                  item_key TEXT PRIMARY KEY, relative_path TEXT NOT NULL,
                  sha256 TEXT NOT NULL, record_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                  id TEXT PRIMARY KEY, artifact_json TEXT NOT NULL
                );
            """)
            if "output_bytes" not in {row[1] for row in db.execute("PRAGMA table_info(run_items)")}:
                db.execute("ALTER TABLE run_items ADD COLUMN output_bytes INTEGER NOT NULL DEFAULT 0")
        if auto_recover:
            self.recover()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def estimate(self, selection: Selection | dict, records: list[Record | dict],
                 processor_id: str, config: dict | None = None) -> dict:
        """Return a read-only execution plan for explicit budget review."""
        parsed = [record if isinstance(record, Record) else Record.model_validate(record) for record in records]
        config = json.loads(_json(config or {}))
        return self._estimate(Selection.model_validate(selection), parsed, _frozen_documents(processor_id, config, parsed), processor_id, config)

    def _estimate(self, selection: Selection, parsed: list[Record], documents: list[dict], processor_id: str, config: dict | None) -> dict:
        """Estimate over records that are already validated, so a large run parses each record once."""
        if not isinstance(processor_id, str) or not processor_id:
            raise ValueError("processor_id is required")
        if (len(selection.ids) != len(set(selection.ids)) or
                len(documents) != len(selection.ids) or
                set(selection.ids) != {record["id"] for record in documents}):
            raise ValueError("Records must match the frozen selection IDs exactly")
        if any(record["unit"] != selection.unit or record["snapshot_id"] not in selection.snapshot_ids or
               record["dataset_id"] not in selection.dataset_ids for record in documents):
            raise ValueError("Record unit, snapshot, or dataset differs from selection")
        config = json.loads(_json(config or {}))
        from dataset_atlas.jobs.limits import limits, enforcement
        resource_limits = limits(config)
        max_output = _output_budget(config)
        if type(max_output) is not int or not 1 <= max_output <= _hard_budget(config):
            raise ValueError(f"max_output_bytes must be an integer within 1..{_hard_budget(config)}")
        from dataset_atlas.processors import get_processor
        processor = get_processor(processor_id)
        description = processor.describe()
        validation = processor.validate_inputs(parsed, config)
        processor_estimate = processor.estimate(parsed, config)
        resource = _resource_class(description,config)
        if resource not in ("cpu", "gpu", "network", "external_api"):
            raise ValueError("Invalid resource class")
        asset_keys: set[str] = set()
        known_bytes: dict[str, int] = {}
        unknown_bytes = False
        asset_refs = 0
        for record in documents:
            for asset in record.get("assets", []):
                asset_refs += 1
                identity = asset.get("sha256") or asset["id"]
                asset_keys.add(identity)
                size = asset.get("metadata", {}).get("size_bytes")
                if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
                    known_bytes[identity] = size
                else:
                    unknown_bytes = True
        result = {"processor_id": processor_id, "selection_id": selection.id,
                  "selected_count": len(documents), "unit": selection.unit,
                  "snapshot_ids": selection.snapshot_ids, "dataset_ids": selection.dataset_ids,
                  "asset_references": asset_refs, "unique_assets": len(asset_keys),
                  "resource_class": resource, "input_representation": config.get("input_representation", "original"),
                  "known_input_bytes": sum(known_bytes.values()),
                  "input_bytes_status": "unknown" if unknown_bytes else "known",
                  "expected_download_bytes": 0, "model_download_bytes": 0, "remote_calls": processor_estimate.get("remote_calls", 0),
                  "output_bytes": None, "output_bytes_status": "unknown", "max_output_bytes": max_output, "storage": "arrays" if _uses_arrays(config) else "json",
                  "resource_limits": resource_limits, "memory_enforcement": enforcement(),
                  "validation": validation, "processor_estimate": processor_estimate,
                  "available": description["available"], "missing_dependencies": description["missing_dependencies"]}
        # A columnar run is bound to its selection, which is content-addressed over immutable snapshots; hashing every
        # record again would cost seconds per hundred thousand and bind nothing the selection does not.
        result["estimate_digest"] = _digest({"selection": selection.model_dump(mode="json"),
                                             "records": None if _uses_arrays(config) else documents, "config": config, "processor_id": processor_id,
                                             "estimate": result})
        return result

    def create(self, selection: Selection | dict, records: list[Record | dict],
               processor_id: str, config: dict | None = None, *, estimate: dict | None = None) -> Run:
        """Freeze a run. A caller that has just computed and checked this run's estimate may pass it instead of paying for it twice."""
        selection = Selection.model_validate(selection)
        parsed = [record if isinstance(record, Record) else Record.model_validate(record) for record in records]
        config = json.loads(_json(config or {}))
        documents = _frozen_documents(processor_id, config, parsed) if isinstance(processor_id, str) else []
        if not processor_id or not isinstance(processor_id, str):
            raise ValueError("processor_id is required")
        if len(selection.ids) != len(set(selection.ids)) or set(selection.ids) != {record["id"] for record in documents} or len(documents) != len(selection.ids):
            raise ValueError("Records must match the frozen selection IDs exactly")
        if any(record["unit"] != selection.unit or record["snapshot_id"] not in selection.snapshot_ids or record["dataset_id"] not in selection.dataset_ids for record in documents):
            raise ValueError("Record unit, snapshot, or dataset differs from selection")
        from dataset_atlas.processors import get_processor
        processor = get_processor(processor_id)
        description = processor.describe()
        if any(record["unit"] not in description["input_units"] for record in documents):
            raise ValueError("Processor does not support selection unit")
        validation = processor.validate_inputs(parsed, config)
        if estimate is None:
            estimate = self._estimate(selection, parsed, documents, processor_id, config)
        batching = description["batching"]
        arrays = _uses_arrays(config)
        population_key = _digest([by for by in sorted(documents, key=lambda item: item["id"])]) if batching == "selection" and not arrays else None
        resource = _resource_class(description,config)
        if resource not in ("cpu", "gpu", "network", "external_api"):
            raise ValueError("Invalid resource class")
        run_id = uuid4().hex
        run = Run(id=run_id, processor_id=processor_id, selection_id=selection.id,
                  config=config, created_at=_now(),
                  provenance={"selection": selection.model_dump(mode="json"),
                              "input_representation": config.get("input_representation", "original"),
                              "model_revision": config.get("model_revision"),
                              "resource_class": resource, "batching": batching,
                              "validation": validation, "estimate": estimate},
                  progress={"total": len(documents), "completed": 0, "failed": 0, "queued": len(documents)})
        by_id = {record["id"]: record for record in documents}
        with self._db() as db:
            db.execute("INSERT INTO runs(id,run_json,selection_json,records_json) VALUES(?,?,?,?)",
                       (run_id, _json(run.model_dump(mode="json")), _json(selection.model_dump(mode="json")),
                        json.dumps([by_id[record_id] for record_id in selection.ids], ensure_ascii=False, separators=(",", ":")) if arrays
                        else _json([by_id[record_id] for record_id in selection.ids])))
            if arrays:
                # One digest binding the config and the content-addressed selection, then one hash per id; no per-item result files exist to reuse.
                shared = _digest({"processor_id": processor_id, "model_revision": config.get("model_revision"), "config": config,
                                  "input_representation": config.get("input_representation", "original"), "selection": _digest(selection.model_dump(mode="json"))})
                db.executemany("INSERT INTO run_items(run_id,record_id,item_key,status,output_bytes) VALUES(?,?,?,?,0)",
                               ((run_id, record_id, hashlib.sha256((shared + record_id).encode()).hexdigest(), "queued")
                                for record_id in selection.ids))
            else:
                for record_id in selection.ids:
                    record = by_id[record_id]
                    key = _digest({"processor_id": processor_id, "model_revision": config.get("model_revision"),
                                   "config": config, "input_representation": config.get("input_representation", "original"),
                                   "record": record, "population_key": population_key})
                    cached = db.execute("SELECT relative_path,sha256 FROM completed_items WHERE item_key=?", (key,)).fetchone()
                    valid = bool(cached and self._valid_item(cached[0], cached[1]))
                    db.execute("INSERT INTO run_items(run_id,record_id,item_key,status,output_bytes) VALUES(?,?,?,?,?)",
                               (run_id, record_id, key, "completed" if valid else "queued",
                                (self.artifact_dir / cached[0]).stat().st_size if valid else 0))
            self._refresh(db, run_id)
        self._launch(run_id)
        return self.get_run(run_id)

    def _valid_item(self, relative_path: str, sha256: str) -> bool:
        path = self.artifact_dir / relative_path
        return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256

    def _refresh(self, db: sqlite3.Connection, run_id: str, *, final: bool = False, exit_code: int = 0) -> Run:
        row = db.execute("SELECT run_json,cancel_requested FROM runs WHERE id=?", (run_id,)).fetchone()
        run = Run.model_validate_json(row[0])
        counts = dict(db.execute("SELECT status,count(*) FROM run_items WHERE run_id=? GROUP BY status", (run_id,)).fetchall())
        total = sum(counts.values())
        run.progress = {"total": total, "completed": counts.get("completed", 0),
                        "failed": counts.get("failed", 0), "queued": counts.get("queued", 0),
                        "running": counts.get("running", 0), "skipped": counts.get("skipped", 0),
                        "not_applicable": counts.get("not_applicable", 0),
                        "output_bytes": db.execute("SELECT COALESCE(SUM(output_bytes),0) FROM run_items WHERE run_id=?", (run_id,)).fetchone()[0],
                        "max_output_bytes": _output_budget(run.config)}
        run.errors = [json.loads(error) for (error,) in db.execute(
            "SELECT error_json FROM run_items WHERE run_id=? AND error_json IS NOT NULL ORDER BY record_id", (run_id,))]
        if final:
            if row[1]:
                run.status = "cancelled"
            elif counts.get("queued", 0) or counts.get("failed", 0):
                run.status = "partial" if counts.get("completed", 0) else "failed"
            elif exit_code:
                run.status = "failed"
            else:
                run.status = "completed"
            run.completed_at = _now()
        db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
        return run

    def get_run(self, run_id: str) -> Run:
        with self._db() as db:
            row = db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return Run.model_validate_json(row[0])

    def list_runs(self) -> list[Run]:
        with self._db() as db:
            rows = db.execute("SELECT run_json FROM runs ORDER BY rowid DESC").fetchall()
        return [Run.model_validate_json(row[0]) for row in rows]

    def item_statuses(self, run_id: str) -> dict[str, str]:
        with self._db() as db:
            return dict(db.execute("SELECT record_id,status FROM run_items WHERE run_id=? ORDER BY record_id", (run_id,)))

    def cancel(self, run_id: str) -> Run:
        existing = self.get_run(run_id)
        if existing.status in ("completed", "partial", "failed", "cancelled"):
            return existing
        with self._db() as db:
            db.execute("UPDATE runs SET cancel_requested=1 WHERE id=?", (run_id,))
            run = self._refresh(db, run_id)
            if run.status in ("queued", "running") and run_id not in self._active:
                self._refresh(db, run_id, final=True)
        (self.stage_dir / run_id).mkdir(exist_ok=True)
        (self.stage_dir / run_id / "cancel").touch()
        return self.get_run(run_id)

    def retry(self, run_id: str) -> Run:
        with self._db() as db:
            row = db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            run = Run.model_validate_json(row[0])
            if run.status not in ("partial", "failed", "cancelled"):
                raise ValueError("Only partial, failed, or cancelled runs may be retried")
            db.execute("UPDATE run_items SET status='queued',error_json=NULL,output_bytes=0 WHERE run_id=? AND status!='completed'", (run_id,))
            db.execute("UPDATE runs SET cancel_requested=0 WHERE id=?", (run_id,))
            run.status = "queued"
            run.completed_at = None
            db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
            self._refresh(db, run_id)
        (self.stage_dir / run_id / "cancel").unlink(missing_ok=True)
        with self._guard:
            previous = self._active.get(run_id)
        if previous and previous.is_alive() and previous is not threading.current_thread():
            previous.join()
        self._launch(run_id)
        return self.get_run(run_id)

    @staticmethod
    def _plan_record(run: Run, record: dict) -> dict:
        """Columnar projection, clustering and neighbour runs read vectors by id, so the worker needs identity only."""
        if run.config.get("storage") == "arrays" and run.processor_id.startswith(("project.", "cluster.", "outlier.")):
            return {key: record[key] for key in ("id", "dataset_id", "release_id", "snapshot_id", "unit")}
        return record

    def _launch(self, run_id: str) -> None:
        with self._guard:
            if self._closed or (run_id in self._active and self._active[run_id].is_alive()):
                return
            thread = threading.Thread(target=self._execute, args=(run_id,), daemon=True, name=f"atlas-job-{run_id[:8]}")
            self._active[run_id] = thread
            thread.start()

    def _import_staged(self, db: sqlite3.Connection, run_id: str) -> None:
        stage = self.stage_dir / run_id
        if not stage.exists():
            return
        for shard in sorted(stage.glob("shard-*")):
            if shard.is_dir() and shard.suffix != ".invalid":
                self._import_shard(db, run_id, shard)
        for path in stage.glob("*.json"):
            if path.name == "input.json":
                continue
            payload = None
            try:
                budget = _output_budget(json.loads(db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()[0])["config"])
                if path.stat().st_size > budget:
                    raise ValueError("Staged output exceeds max_output_bytes")
                payload = json.loads(path.read_text(encoding="utf-8"))
                if path.name == "batch.json" or path.name.startswith("group-"):
                    keys = payload["keys"]
                    items = payload["result"]["items"]
                    expected = dict(db.execute("SELECT record_id,item_key FROM run_items WHERE run_id=?", (run_id,)))
                    if (not keys or (path.name == "batch.json" and set(keys) != set(expected)) or
                            any(expected.get(record_id) != key for record_id, key in keys.items()) or
                            len(items) != len(keys) or {item["id"] for item in items} != set(keys)):
                        raise ValueError("Batch result does not match frozen run IDs and keys")
                    current = db.execute("SELECT COALESCE(SUM(output_bytes),0) FROM run_items WHERE run_id=?", (run_id,)).fetchone()[0]
                    new_bytes = sum(len(_json({**payload["result"], "items": [item]}).encode()) for item in items
                                    if db.execute("SELECT status FROM run_items WHERE run_id=? AND record_id=?",
                                                  (run_id, item["id"])).fetchone()[0] != "completed" and item["status"] == "completed")
                    if current + new_bytes > budget:
                        for item in items:
                            db.execute("UPDATE run_items SET status='failed',error_json=?,output_bytes=0 WHERE run_id=? AND record_id=? AND status!='completed'",
                                       (_json({"record_id": item["id"], "type": "OutputBudgetExceeded",
                                               "message": "Run output exceeds max_output_bytes"}), run_id, item["id"]))
                        path.unlink()
                        continue
                    for item in items:
                        single = {**payload["result"], "items": [item]}
                        self._import_item(db, run_id, keys[item["id"]], item["id"], single)
                    path.unlink()
                    continue
                key, record_id, result = payload["key"], payload["record_id"], payload["result"]
                self._import_item(db, run_id, key, record_id, result)
                path.unlink()
            except Exception as exc:
                # A corrupt stage is not promoted. Keep it for diagnosis and let retry recompute.
                path.rename(path.with_suffix(".invalid"))
                if path.name == "batch.json" or path.name.startswith("group-"):
                    if isinstance(payload, dict) and isinstance(payload.get("keys"), dict):
                        record_ids = [row[0] for row in db.execute("SELECT record_id FROM run_items WHERE run_id=?", (run_id,)) if row[0] in payload["keys"]]
                    else:
                        record_ids = [row[0] for row in db.execute("SELECT record_id FROM run_items WHERE run_id=?", (run_id,))]
                else:
                    key = payload.get("key") if isinstance(payload, dict) else path.stem
                    record_ids = [row[0] for row in db.execute(
                        "SELECT record_id FROM run_items WHERE run_id=? AND item_key=?", (run_id, key))]
                for record_id in record_ids:
                    db.execute("UPDATE run_items SET status='failed',error_json=? WHERE run_id=? AND record_id=? AND status!='completed'",
                               (_json({"record_id": record_id, "type": "StageValidationError", "message": str(exc)[:1000]}), run_id, record_id))

    def _import_shard(self, db: sqlite3.Connection, run_id: str, shard: Path) -> None:
        """Verify a staged columnar shard against the frozen run, keep it, and mark its records done."""
        from dataset_atlas.storage.arrays import read_ids, sha256_file
        keys: dict = {}
        try:
            meta = json.loads((shard / "meta.json").read_text(encoding="utf-8"))
            keys, manifest, skipped = meta["keys"], meta["manifest"], meta["skipped"]
            # Only this shard's keys: reading every item of a 200k-record run once per shard was most of the import time.
            expected: dict[str, str] = {}
            wanted = list(keys)
            for start in range(0, len(wanted), 500):
                chunk = wanted[start:start + 500]
                expected.update(db.execute(f"SELECT record_id,item_key FROM run_items WHERE run_id=? AND record_id IN ({','.join('?' * len(chunk))})", [run_id, *chunk]))
            if not keys or any(expected.get(record_id) != key for record_id, key in keys.items()):
                raise ValueError("Shard does not match frozen run IDs and keys")
            ids = read_ids(shard, manifest)
            if len(ids) + len(skipped) != len(keys) or set(ids) | set(skipped) != set(keys) or set(ids) & set(skipped):
                raise ValueError("Shard rows and skipped records do not account for its keys exactly")
            if any(row.get("status") not in ("skipped", "not_applicable", "failed") for row in skipped.values()):
                raise ValueError("Invalid skipped status in shard")
            for entry in [*manifest["arrays"].values(), *manifest.get("extras", {}).values(), *manifest.get("texts", {}).values()]:
                if sha256_file(shard / entry["file"]) != entry["sha256"]:
                    raise ValueError("Shard array does not match its checksum")
            destination = self.artifact_dir / "shards" / run_id / shard.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(shard, destination)
            per_row = meta["array_bytes"] // max(1, len(ids))
            db.executemany("UPDATE run_items SET status='completed',error_json=NULL,output_bytes=? WHERE run_id=? AND record_id=?",
                           [(per_row, run_id, record_id) for record_id in ids])
            db.executemany("UPDATE run_items SET status=?,error_json=?,output_bytes=0 WHERE run_id=? AND record_id=?",
                           [(row["status"], _json({"record_id": record_id, **{k: v for k, v in row.items() if k != "status"}}) if len(row) > 1 else None,
                             run_id, record_id) for record_id, row in skipped.items()])
        except Exception as exc:
            shard.rename(shard.with_name(shard.name + ".invalid"))
            targets = list(keys) if isinstance(keys, dict) and keys else [row[0] for row in db.execute("SELECT record_id FROM run_items WHERE run_id=?", (run_id,))]
            db.executemany("UPDATE run_items SET status='failed',error_json=? WHERE run_id=? AND record_id=? AND status!='completed'",
                           [(_json({"record_id": record_id, "type": "StageValidationError", "message": str(exc)[:1000]}), run_id, record_id) for record_id in targets])

    def _import_item(self, db: sqlite3.Connection, run_id: str, key: str, record_id: str, result: dict) -> None:
        expected = db.execute("SELECT item_key FROM run_items WHERE run_id=? AND record_id=?", (run_id, record_id)).fetchone()
        if not expected or key != expected[0]:
            raise ValueError("Staged item identity does not match frozen run")
        items = result["items"]
        if not isinstance(items, list) or len(items) != 1 or items[0]["id"] != record_id:
            raise ValueError("Processor output must contain exactly the requested record ID")
        status = items[0]["status"]
        if status not in ("completed", "failed", "skipped", "not_applicable"):
            raise ValueError("Invalid processor item status")
        if status == "completed":
            size = len(_json(result).encode())
            limit = _output_budget(json.loads(db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()[0])["config"])
            old = db.execute("SELECT output_bytes FROM run_items WHERE run_id=? AND record_id=?", (run_id, record_id)).fetchone()[0]
            used = db.execute("SELECT COALESCE(SUM(output_bytes),0) FROM run_items WHERE run_id=?", (run_id,)).fetchone()[0]
            if used - old + size > limit:
                db.execute("UPDATE run_items SET status='failed',error_json=?,output_bytes=0 WHERE run_id=? AND record_id=? AND status!='completed'",
                           (_json({"record_id": record_id, "type": "OutputBudgetExceeded",
                                   "message": "Run output exceeds max_output_bytes"}), run_id, record_id))
                return
            relative = f"items/{key}.json"
            item_path = self.artifact_dir / relative
            _write_once(item_path, result)
            sha = hashlib.sha256(item_path.read_bytes()).hexdigest()
            db.execute("INSERT OR IGNORE INTO completed_items(item_key,relative_path,sha256,record_id) VALUES(?,?,?,?)",
                       (key, relative, sha, record_id))
            db.execute("UPDATE run_items SET status='completed',error_json=NULL,output_bytes=? WHERE run_id=? AND record_id=?", (size, run_id, record_id))
        else:
            error = items[0].get("error", {"record_id": record_id, "status": status})
            if not isinstance(error, dict):
                error = {"record_id": record_id, "message": str(error)}
            error.setdefault("record_id", record_id)
            db.execute("UPDATE run_items SET status=?,error_json=?,output_bytes=0 WHERE run_id=? AND record_id=?",
                       (status, _json(error), run_id, record_id))

    def _register_bulk_artifact(self, db: sqlite3.Connection, run_id: str, run: Run) -> Run:
        """One array-backed artifact from a columnar run's shards, with rows in selection order."""
        import numpy as np
        from dataset_atlas.storage import arrays as store
        rows = db.execute("SELECT record_id,status,error_json FROM run_items WHERE run_id=?", (run_id,)).fetchall()
        selection = json.loads(db.execute("SELECT selection_json FROM runs WHERE id=?", (run_id,)).fetchone()[0])
        status = {record_id: state for record_id, state, _ in rows}
        root = self.artifact_dir / "shards" / run_id
        shards = sorted(path for path in root.glob("shard-*") if path.is_dir() and path.suffix != ".invalid") if root.is_dir() else []
        order = [record_id for record_id in selection["ids"] if status.get(record_id) == "completed"]
        if not shards or not order:
            return run
        metas = [json.loads((path / "meta.json").read_text(encoding="utf-8")) for path in shards]
        shard_ids = [store.read_ids(path, meta["manifest"]) for path, meta in zip(shards, metas)]
        if sum(map(len, shard_ids)) != len(order) or set().union(*map(set, shard_ids)) != set(order):
            raise ValueError("Shards do not cover the completed records exactly")
        names = list(metas[0]["manifest"]["arrays"])
        carriers = [(path, meta) for path, meta in zip(shards, metas) if meta["manifest"].get("extras")]
        if len(carriers) > 1:
            raise ValueError("Only one shard may carry non-row arrays")
        artifact_id = _digest({"run_id": run_id, "processor_id": run.processor_id, "selection_id": run.selection_id, "config_digest": _digest(run.config),
                               "shards": [[path.name, {name: entry["sha256"] for group in ("arrays", "extras", "texts") for name, entry in meta["manifest"].get(group, {}).items()}]
                                          for path, meta in zip(shards, metas)]})[:24]
        relative_dir = f"arrays/{artifact_id}"
        target = self.artifact_dir / relative_dir
        skipped = {record_id: {"status": state, **{k: v for k, v in (json.loads(error) if error else {}).items() if k != "record_id"}}
                   for record_id, state, error in rows if state != "completed"}
        if target.is_dir():
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        else:
            work = target.with_name(f".{artifact_id}.{uuid4().hex}.tmp")
            work.mkdir(parents=True)
            try:
                rank = {record_id: index for index, record_id in enumerate(order)}
                entries = {}
                for name in names:
                    first = metas[0]["manifest"]["arrays"][name]
                    if any(meta["manifest"]["arrays"][name]["dtype"] != first["dtype"] or meta["manifest"]["arrays"][name]["shape"][1:] != first["shape"][1:] for meta in metas):
                        raise ValueError(f"Shards disagree on the dtype or shape of {name}")
                    out = store.allocate_array(work, name, [len(order), *first["shape"][1:]], first["dtype"])
                    for path, meta, ids in zip(shards, metas, shard_ids):
                        out[np.fromiter((rank[record_id] for record_id in ids), dtype=np.int64, count=len(ids))] = store.read_array(path, meta["manifest"]["arrays"][name])
                    out.flush()
                    del out
                    entries[name] = store.describe_array(work, name)
                extras = {}
                for path, meta in carriers:
                    for name, entry in meta["manifest"]["extras"].items():
                        shutil.copyfile(path / entry["file"], work / entry["file"])
                        extras[name] = store.describe_array(work, name)
                texts = {}
                for name in metas[0]["manifest"].get("texts", {}):
                    merged: list[str | None] = [None] * len(order)
                    for path, meta, ids in zip(shards, metas, shard_ids):
                        part = store.read_texts(path, meta["manifest"]["texts"][name])
                        for record_id, value in zip(ids, part):
                            merged[rank[record_id]] = value
                    texts[name] = store.write_texts(work, name, merged)
                manifest = {"count": len(order), "ids": store.write_ids(work, order), "arrays": entries, **({"extras": extras} if extras else {}),
                            **({"texts": texts} if texts else {})}
                (work / "skipped.json").write_text(_json(skipped), encoding="utf-8")
                (work / "manifest.json").write_text(_json(manifest), encoding="utf-8")
                os.replace(work, target)
            except BaseException:
                shutil.rmtree(work, ignore_errors=True)
                raise
        bulk = {"dir": relative_dir, **manifest}
        _write_once(self.artifact_dir / f"runs/{artifact_id}.json", {"run_id": run_id, "storage": "arrays", "bulk": bulk, "processor_id": run.processor_id,
                                                                    "selection_id": run.selection_id, "coverage": run.progress})
        portable_config_keys = {"extraction_threshold", "max_pixels", "seed", "neighbors", "metric", "clusters", "dimensions", "backend", "min_dist",
                                "min_cluster_size", "min_samples", "n_init", "linkage", "left_field", "right_field", "kind", "embedding_space_id",
                                "embedding_run_id", "representation", "input_representation", "model_revision", "model_sha256", "weights_sha256",
                                "storage_dtype", "precision"}
        by_status = {}
        for entry in skipped.values():
            by_status[entry["status"]] = by_status.get(entry["status"], 0) + 1
        artifact = Artifact(id=artifact_id, kind=run.processor_id, run_id=run_id, snapshot_ids=selection["snapshot_ids"], unit=selection["unit"],
                            ids=list(selection["ids"]), files={"manifest": f"runs/{artifact_id}.json"},
                            provenance={"processor_id": run.processor_id, "selection_id": run.selection_id,
                                        "config": {key: value for key, value in run.config.items() if key in portable_config_keys},
                                        "config_digest": _digest(run.config), "input_representation": run.provenance.get("input_representation"),
                                        "model_revision": run.provenance.get("model_revision"), "processor_provenance": metas[0]["provenance"],
                                        "output_schema": "1.0", "storage": "arrays"},
                            coverage={**run.progress, "status": run.status},
                            data={"bulk": bulk, "summary": metas[0]["summary"] if len(metas) == 1 else {},
                                  "skipped": {"count": len(skipped), "by_status": by_status, "examples": dict(list(skipped.items())[:50])}})
        db.execute("INSERT OR IGNORE INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact_id, _json(artifact.model_dump(mode="json"))))
        run.artifact_ids = [artifact_id]
        db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
        return run

    def _register_artifact(self, db: sqlite3.Connection, run_id: str, run: Run) -> Run:
        if _uses_arrays(run.config):
            return self._register_bulk_artifact(db, run_id, run)
        rows = db.execute("SELECT record_id,item_key,status,error_json FROM run_items WHERE run_id=? ORDER BY record_id", (run_id,)).fetchall()
        selection = json.loads(db.execute("SELECT selection_json FROM runs WHERE id=?", (run_id,)).fetchone()[0])
        completed = {record_id: f"items/{key}.json" for record_id, key, status, _ in rows if status == "completed"}
        if not completed:
            return run
        manifest = {"run_id": run_id, "status": run.status, "coverage": run.progress,
                    "items": completed, "item_statuses": {record_id: status for record_id, _, status, _ in rows},
                    "selection_id": run.selection_id, "processor_id": run.processor_id}
        artifact_id = _digest(manifest)[:24]
        relative = f"runs/{artifact_id}.json"
        _write_once(self.artifact_dir / relative, manifest)
        points = []
        artifact_items = []
        for record_id, key, status, error in rows:
            if status == "completed":
                item = json.loads((self.artifact_dir / f"items/{key}.json").read_text())["items"][0]
                artifact_items.append(item)
                points.append({"id": record_id, **(item.get("output") if isinstance(item.get("output"), dict) else {"value": item.get("output")})})
            else:
                artifact_items.append({"id": record_id, "status": status, "output": None,
                                       **({"error": json.loads(error)} if error else {})})
        first_result = json.loads((self.artifact_dir / f"items/{next(key for _, key, status, _ in rows if status == 'completed')}.json").read_text())
        portable_config_keys = {"extraction_threshold", "max_pixels", "seed", "neighbors", "metric", "clusters",
                                "left_field", "right_field", "kind", "embedding_space_id", "embedding_run_id",
                                "representation", "input_representation", "model_revision", "model_sha256", "weights_sha256"}
        portable_config = {key: value for key, value in run.config.items() if key in portable_config_keys}
        artifact = Artifact(id=artifact_id, kind=run.processor_id, run_id=run_id,
                            snapshot_ids=selection["snapshot_ids"], unit=selection["unit"],
                            ids=[record_id for record_id, _, _, _ in rows], files={"manifest": relative},
                            provenance={"processor_id": run.processor_id, "selection_id": run.selection_id,
                                        "config": portable_config, "config_digest": _digest(run.config),
                                        "input_representation": run.provenance.get("input_representation"),
                                        "model_revision": run.provenance.get("model_revision"),
                                        "processor_provenance": first_result.get("provenance", {}),
                                        "output_schema": first_result.get("schema_version")},
                            coverage={**run.progress, "status": run.status}, data={"points": points, "items": artifact_items})
        db.execute("INSERT OR IGNORE INTO artifacts(id,artifact_json) VALUES(?,?)",
                   (artifact_id, _json(artifact.model_dump(mode="json"))))
        run.artifact_ids = [artifact_id]
        db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
        return run

    def _execute(self, run_id: str) -> None:
        stage = self.stage_dir / run_id
        stage.mkdir(exist_ok=True)
        try:
            # A restarted coordinator must let an orphan worker finish staging
            # before deciding which frozen items still need computation.
            with (stage / "worker.lock").open("a+b") as prior_worker:
                fcntl.flock(prior_worker, fcntl.LOCK_EX)
                fcntl.flock(prior_worker, fcntl.LOCK_UN)
            with self._db() as db:
                self._import_staged(db, run_id)
                db.execute("UPDATE run_items SET status='queued' WHERE run_id=? AND status='running'", (run_id,))
                row = db.execute("SELECT run_json,records_json,cancel_requested FROM runs WHERE id=?", (run_id,)).fetchone()
                if row[2]:
                    run = self._refresh(db, run_id, final=True)
                    self._register_artifact(db, run_id, run)
                    return
                run = Run.model_validate_json(row[0])
                run.status = "running"
                db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
                records = {record["id"]: record for record in json.loads(row[1])}
                pending = db.execute("SELECT record_id,item_key FROM run_items WHERE run_id=? AND status='queued'", (run_id,)).fetchall()
                if run.provenance.get("batching") == "selection" and pending:
                    pending = db.execute("SELECT record_id,item_key FROM run_items WHERE run_id=?", (run_id,)).fetchall()
                db.execute("UPDATE run_items SET status='running' WHERE run_id=? AND status='queued'", (run_id,))
                self._refresh(db, run_id)
                plan = {"processor_id": run.processor_id, "config": run.config,
                        "array_bytes_remaining": max(0, _output_budget(run.config) - db.execute(
                            "SELECT COALESCE(SUM(output_bytes),0) FROM run_items WHERE run_id=?", (run_id,)).fetchone()[0]),
                        "batching": run.provenance.get("batching"),
                        "budget_remaining_bytes": _output_budget(run.config) -
                        db.execute("SELECT COALESCE(SUM(output_bytes),0) FROM run_items WHERE run_id=?", (run_id,)).fetchone()[0],
                        "items": [{"record": self._plan_record(run, records[record_id]), "key": key} for record_id, key in pending]}
            exit_code = 0
            if pending:
                (stage / 'resource-error.receipt').unlink(missing_ok=True)
                (stage / "input.json").write_text(_json(plan), encoding="utf-8")
                env = os.environ.copy()
                env["PYTHONPATH"] = os.pathsep.join([path for path in sys.path if path] + [env.get("PYTHONPATH", "")])
                resource = run.provenance.get("resource_class", "cpu")
                if resource not in ("cpu", "gpu", "network", "external_api"):
                    raise ValueError("Invalid resource class")
                lock_path = self.work_dir / f"resource-{resource}.lock"
                with lock_path.open("a+b") as lock:
                    if resource == "gpu":
                        fcntl.flock(lock, fcntl.LOCK_EX)
                    from dataset_atlas.jobs.limits import worker_command
                    process = subprocess.Popen(worker_command([sys.executable, "-m", "dataset_atlas.jobs.worker", str(stage / "input.json")],run.config), env=env, start_new_session=True)
                    while process.poll() is None:
                        with self._db() as db:
                            self._import_staged(db, run_id)
                            self._refresh(db, run_id)
                        time.sleep(0.2)
                    exit_code = process.wait()
                    if resource == "gpu":
                        fcntl.flock(lock, fcntl.LOCK_UN)
                if exit_code == 75:
                    # An orphan worker from an earlier coordinator still owns the lock.
                    # Wait for it to stage its results, then import without recomputation.
                    with (stage / "worker.lock").open("a+b") as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        fcntl.flock(lock, fcntl.LOCK_UN)
                    exit_code = 0
            with self._db() as db:
                self._import_staged(db, run_id)
                db.execute("UPDATE run_items SET status='queued' WHERE run_id=? AND status='running'", (run_id,))
                if exit_code == 76:
                    db.execute("UPDATE run_items SET status='failed',error_json=? WHERE run_id=? AND status='queued'",
                               (_json({"type": "OutputBudgetExceeded", "message": "Worker output exceeded max_output_bytes"}), run_id))
                run = self._refresh(db, run_id, final=True, exit_code=exit_code)
                receipt=stage/'resource-error.receipt'
                if receipt.is_file():
                    run.errors.append(json.loads(receipt.read_text()))
                    db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode='json')), run_id))
                self._register_artifact(db, run_id, run)
            if run.status == "completed" and run.artifact_ids and _uses_arrays(run.config):
                # Kept for partial or failed runs so a retry can still assemble the finished shards.
                shutil.rmtree(self.artifact_dir / "shards" / run_id, ignore_errors=True)
        except Exception as exc:
            with self._db() as db:
                row = db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()
                if row:
                    run = Run.model_validate_json(row[0])
                    run.status = "partial" if run.progress.get("completed") else "failed"
                    run.errors.append({"type": type(exc).__name__, "message": str(exc)[:1000]})
                    run.completed_at = _now()
                    db.execute("UPDATE runs SET run_json=? WHERE id=?", (_json(run.model_dump(mode="json")), run_id))
        finally:
            with self._guard:
                self._active.pop(run_id, None)

    def recover(self) -> None:
        with self._db() as db:
            rows = db.execute("SELECT id,run_json FROM runs").fetchall()
        for run_id, raw in rows:
            if Run.model_validate_json(raw).status in ("queued", "running"):
                self._launch(run_id)

    def _import_array_run(self, source: Path, connection: sqlite3.Connection, run: Run, raw_run: str, raw_selection: str, raw_records: str, cancelled: bool) -> Run:
        """Verify and register one completed array-backed run from another workspace (a cluster's, say), then copy its bundle.

        Every file is hashed while it is copied and compared with the checksum in the artifact's manifest; the frozen
        selection, the item keys and the per-record outcomes are re-derived from the run's own configuration, so a bundle
        cannot be attached to a run it does not belong to. Nothing is registered unless all of it checks out.
        """
        from dataset_atlas.storage import arrays as store
        run_id = run.id
        selection = Selection.model_validate_json(raw_selection)
        records = [Record.model_validate(record) for record in json.loads(raw_records)]
        if run.status != "completed" or cancelled:
            raise ValueError("Only fully completed, uncancelled runs can be imported")
        if (run.selection_id != selection.id or len(selection.ids) != len(set(selection.ids)) or [record.id for record in records] != selection.ids or
                any(record.unit != selection.unit or record.snapshot_id not in selection.snapshot_ids or record.dataset_id not in selection.dataset_ids for record in records)):
            raise ValueError("Frozen selection and records disagree")
        rows = connection.execute("SELECT record_id,item_key,status,error_json,output_bytes FROM run_items WHERE run_id=?", (run_id,)).fetchall()
        shared = _digest({"processor_id": run.processor_id, "model_revision": run.config.get("model_revision"), "config": run.config,
                          "input_representation": run.config.get("input_representation", "original"), "selection": _digest(selection.model_dump(mode="json"))})
        if len(rows) != len(records) or {row[0] for row in rows} != set(selection.ids):
            raise ValueError("Run item receipts are incomplete")
        if any(hashlib.sha256((shared + row[0]).encode()).hexdigest() != row[1] for row in rows):
            raise ValueError("Frozen item key does not match record and configuration")
        if any(row[2] not in ("completed", "failed", "skipped", "not_applicable") for row in rows):
            raise ValueError("Run item receipts are incomplete")
        status = {row[0]: row[2] for row in rows}
        completed = [record_id for record_id in selection.ids if status[record_id] == "completed"]
        if (not completed or run.progress.get("total") != len(records) or run.progress.get("completed") != len(completed) or len(run.artifact_ids) != 1):
            raise ValueError("Run item receipts are incomplete")
        skipped = {row[0]: {"status": row[2], **{key: value for key, value in (json.loads(row[3]) if row[3] else {}).items() if key != "record_id"}} for row in rows if row[2] != "completed"}

        artifact_id = run.artifact_ids[0]
        artifact_row = connection.execute("SELECT artifact_json FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if not artifact_row:
            raise ValueError("Run artifact receipt is missing")
        artifact = Artifact.model_validate_json(artifact_row[0])
        bulk = artifact.data.get("bulk")
        relative_dir, relative_manifest = f"arrays/{artifact_id}", f"runs/{artifact_id}.json"
        if (artifact.id != artifact_id or artifact.run_id != run_id or artifact.kind != run.processor_id or artifact.files != {"manifest": relative_manifest} or
                artifact.provenance.get("selection_id") != selection.id or artifact.provenance.get("storage") != "arrays" or
                artifact.ids != selection.ids or artifact.snapshot_ids != selection.snapshot_ids or artifact.unit != selection.unit or
                artifact.coverage != {**run.progress, "status": run.status} or artifact.provenance.get("config_digest") != _digest(run.config) or
                not isinstance(bulk, dict) or bulk.get("dir") != relative_dir):
            raise ValueError("Artifact identity disagrees with run")
        manifest = {key: value for key, value in bulk.items() if key != "dir"}
        run_manifest = {"run_id": run_id, "storage": "arrays", "bulk": bulk, "processor_id": run.processor_id, "selection_id": run.selection_id, "coverage": run.progress}
        source_artifacts = source / "artifacts"
        source_dir = source_artifacts / relative_dir
        if source_dir.is_symlink() or not source_dir.resolve().is_relative_to(source_artifacts.resolve()):
            raise ValueError("Bundle directory is a symbolic link or leaves the artifact store")
        raw_run_manifest = read_rooted_file(source_artifacts / relative_manifest, [source_artifacts], max_bytes=1 << 20)
        if raw_run_manifest != _json(run_manifest).encode():
            raise ValueError("Artifact manifest does not match the run")
        if store.read_ids(source_dir, manifest) != completed:
            raise ValueError("Result rows do not match the completed records in selection order")
        names = [manifest["ids"], *manifest["arrays"].values(), *manifest.get("extras", {}).values(), *manifest.get("texts", {}).values()]
        if len({entry["file"] for entry in names}) != len(names) or {"manifest.json", "skipped.json"} & {entry["file"] for entry in names}:
            raise ValueError("Bundle files repeat or collide with its manifest")
        if _json(skipped).encode() != (source_dir / "skipped.json").read_bytes() or _json(manifest).encode() != (source_dir / "manifest.json").read_bytes():
            raise ValueError("Bundle manifest or skipped list does not match the run receipts")

        target = self.artifact_dir / relative_dir
        with self._db() as db:
            existing = db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()
            if existing:
                if existing[0] != raw_run:
                    raise ValueError("Run ID already exists with different content")
                return Run.model_validate_json(existing[0])
            prior = db.execute("SELECT artifact_json FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            if prior and prior[0] != _json(artifact.model_dump(mode="json")):
                raise ValueError("Artifact ID collision")
            if target.is_dir():
                if (target / "manifest.json").read_bytes() != _json(manifest).encode():
                    raise ValueError("Artifact ID collision")
            else:
                work = target.with_name(f".{artifact_id}.{uuid4().hex}.tmp")
                work.mkdir(parents=True)
                try:
                    for entry in names:
                        self._copy_verified(store._inside(source_dir, entry["file"]), work / entry["file"], entry["sha256"])
                    for name, entry in {**manifest["arrays"], **manifest.get("extras", {})}.items():
                        array = store.read_array(work, entry)  # the dtype and shape the manifest promised; never unpickled
                        if name in manifest["arrays"] and len(array) != manifest["count"]:
                            raise ValueError(f"Array {name} does not have one row per result")
                    for entry in manifest.get("texts", {}).values():
                        if len(store.read_texts(work, entry)) != manifest["count"]:
                            raise ValueError("A text column does not have one row per result")
                    (work / "skipped.json").write_bytes(_json(skipped).encode())
                    (work / "manifest.json").write_bytes(_json(manifest).encode())
                    os.replace(work, target)
                except BaseException:
                    shutil.rmtree(work, ignore_errors=True)
                    raise
            _write_once(self.artifact_dir / relative_manifest, run_manifest)
            db.execute("INSERT INTO runs(id,run_json,selection_json,records_json,cancel_requested) VALUES(?,?,?,?,0)", (run_id, raw_run, raw_selection, raw_records))
            db.executemany("INSERT INTO run_items(run_id,record_id,item_key,status,error_json,output_bytes) VALUES(?,?,?,?,?,?)",
                           [(run_id, record_id, key, state, error, size) for record_id, key, state, error, size in rows])
            db.execute("INSERT OR IGNORE INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact_id, _json(artifact.model_dump(mode="json"))))
        return run

    @staticmethod
    def _copy_verified(source_file: Path, destination: Path, sha256: str) -> None:
        """Copy one bundle file, refusing symbolic links, and check its checksum on the bytes actually copied."""
        if source_file.is_symlink() or not source_file.is_file():
            raise ValueError("Bundle file is missing or is a symbolic link")
        digest = hashlib.sha256()
        with source_file.open("rb") as reader, destination.open("xb") as writer:
            while block := reader.read(8 * 1024 * 1024):
                digest.update(block)
                writer.write(block)
            writer.flush()
            os.fsync(writer.fileno())
        if digest.hexdigest() != sha256:
            raise ValueError("Bundle file does not match its recorded checksum")

    def import_completed_run(self, source_work_dir: str | Path, run_id: str) -> Run:
        """Verify and register one completed isolated run without replacing this work DB.

        The source database is opened read-only. Item bytes, receipt hashes, frozen
        input identities, and artifact manifests are checked before any registration.
        Files are copied immutably; this coordinator is the only destination DB writer.
        """
        source = Path(source_work_dir).resolve()
        if source == self.work_dir:
            raise ValueError("Source and destination work directories must differ")
        source_db = source / "jobs.sqlite3"
        if not source_db.is_file():
            raise FileNotFoundError(source_db)
        source_artifacts = source / "artifacts"

        def read_json_file(relative: str, max_bytes: int) -> tuple[dict, bytes]:
            parts = Path(relative).parts
            if (len(parts) != 2 or parts[0] not in ("items", "runs") or
                    not parts[1].endswith(".json") or
                    any(ch not in "0123456789abcdef" for ch in parts[1][:-5]) or
                    len(parts[1][:-5]) not in (24, 64)):
                raise ValueError("Invalid artifact relative path")
            raw = read_rooted_file(source_artifacts / relative, [source_artifacts], max_bytes=max_bytes)
            value = json.loads(raw)
            if not isinstance(value, dict) or raw != _json(value).encode():
                raise ValueError("Artifact bytes are not canonical JSON")
            return value, raw

        with self._guard:
            source_connection = sqlite3.connect(source_db.as_uri() + "?mode=ro", uri=True, timeout=30)
            try:
                source_connection.execute("PRAGMA query_only=ON")
                source_row = source_connection.execute(
                    "SELECT run_json,selection_json,records_json,cancel_requested FROM runs WHERE id=?", (run_id,)).fetchone()
                if not source_row:
                    raise KeyError(run_id)
                raw_run, raw_selection, raw_records, cancelled = source_row
                run = Run.model_validate_json(raw_run)
                if _uses_arrays(run.config):
                    return self._import_array_run(source, source_connection, run, raw_run, raw_selection, raw_records, bool(cancelled))
                selection = Selection.model_validate_json(raw_selection)
                records = [Record.model_validate(record) for record in json.loads(raw_records)]
                if run.id != run_id or run.status != "completed" or cancelled:
                    raise ValueError("Only fully completed, uncancelled runs can be imported")
                if (run.selection_id != selection.id or len(selection.ids) != len(set(selection.ids)) or
                        [record.id for record in records] != selection.ids or
                        any(record.unit != selection.unit or record.snapshot_id not in selection.snapshot_ids or
                            record.dataset_id not in selection.dataset_ids for record in records)):
                    raise ValueError("Frozen selection and records disagree")
                rows = source_connection.execute(
                    "SELECT record_id,item_key,status,error_json FROM run_items WHERE run_id=? ORDER BY record_id", (run_id,)).fetchall()
                if (len(rows) != len(records) or {row[0] for row in rows} != set(selection.ids) or
                        any(row[2] != "completed" or row[3] for row in rows) or
                        run.progress.get("completed") != len(records) or
                        run.progress.get("total") != len(records) or not run.artifact_ids):
                    raise ValueError("Run item receipts are incomplete")
                documents = [record.model_dump(mode="json") for record in records]
                population_key = _digest(sorted(documents, key=lambda item: item["id"])) if run.provenance.get("batching") == "selection" else None
                expected_keys = {
                    record["id"]: _digest({"processor_id": run.processor_id,
                                           "model_revision": run.config.get("model_revision"),
                                           "config": run.config,
                                           "input_representation": run.config.get("input_representation", "original"),
                                           "record": record, "population_key": population_key})
                    for record in documents}
                if any(expected_keys.get(record_id) != key for record_id, key, _, _ in rows):
                    raise ValueError("Frozen item key does not match record and configuration")
                max_output = _output_budget(run.config)
                if type(max_output) is not int or not 1 <= max_output <= HARD_MAX_OUTPUT_BYTES:
                    raise ValueError("Invalid source output budget")
                files: dict[str, dict] = {}
                file_bytes: dict[str, int] = {}
                total_bytes = 0
                for record_id, key, _, _ in rows:
                    receipt = source_connection.execute(
                        "SELECT relative_path,sha256,record_id FROM completed_items WHERE item_key=?", (key,)).fetchone()
                    relative = f"items/{key}.json"
                    if not receipt or receipt[0] != relative or receipt[2] != record_id:
                        raise ValueError("Missing or mismatched completed item receipt")
                    item, raw = read_json_file(relative, max_output)
                    if hashlib.sha256(raw).hexdigest() != receipt[1]:
                        raise ValueError("Completed item SHA-256 mismatch")
                    items = item.get("items")
                    if (not isinstance(items, list) or len(items) != 1 or
                            items[0].get("id") != record_id or items[0].get("status") != "completed"):
                        raise ValueError("Completed item content disagrees with frozen record")
                    total_bytes += len(raw)
                    if total_bytes > max_output:
                        raise ValueError("Source run exceeds its output budget")
                    files[relative] = item
                    file_bytes[relative] = len(raw)
                artifacts: list[Artifact] = []
                for artifact_id in run.artifact_ids:
                    artifact_row = source_connection.execute(
                        "SELECT artifact_json FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
                    if not artifact_row:
                        raise ValueError("Run artifact receipt is missing")
                    artifact = Artifact.model_validate_json(artifact_row[0])
                    relative = f"runs/{artifact_id}.json"
                    if (artifact.id != artifact_id or artifact.run_id != run_id or
                            artifact.kind != run.processor_id or artifact.files != {"manifest": relative} or
                            artifact.provenance.get("selection_id") != selection.id):
                        raise ValueError("Artifact identity disagrees with run")
                    manifest, _ = read_json_file(relative, max_output)
                    if (_digest(manifest)[:24] != artifact_id or
                            manifest != {"run_id": run_id, "status": run.status,
                                         "coverage": run.progress,
                                         "items": {record_id: f"items/{key}.json" for record_id, key, _, _ in rows},
                                         "item_statuses": {record_id: "completed" for record_id, _, _, _ in rows},
                                         "selection_id": selection.id, "processor_id": run.processor_id} or
                            set(artifact.ids) != set(selection.ids) or
                            artifact.snapshot_ids != selection.snapshot_ids or artifact.unit != selection.unit or
                            artifact.coverage != {**run.progress, "status": run.status} or
                            artifact.provenance.get("config_digest") != _digest(run.config)):
                        raise ValueError("Artifact manifest or provenance does not match run receipts")
                    expected_items = [files[f"items/{key}.json"]["items"][0] for _, key, _, _ in rows]
                    expected_points = [{"id": item["id"], **(item.get("output") if isinstance(item.get("output"), dict)
                                        else {"value": item.get("output")})} for item in expected_items]
                    if artifact.data.get("items") != expected_items or artifact.data.get("points") != expected_points:
                        raise ValueError("Artifact data does not match verified item outputs")
                    files[relative] = manifest
                    artifacts.append(artifact)
            finally:
                source_connection.close()

            with self._db() as db:
                existing = db.execute("SELECT run_json FROM runs WHERE id=?", (run_id,)).fetchone()
                if existing:
                    if existing[0] != raw_run:
                        raise ValueError("Run ID already exists with different content")
                    return Run.model_validate_json(existing[0])
                for record_id, key, _, _ in rows:
                    existing_item = db.execute("SELECT sha256,record_id FROM completed_items WHERE item_key=?", (key,)).fetchone()
                    if existing_item:
                        raw = _json(files[f"items/{key}.json"]).encode()
                        if existing_item != (hashlib.sha256(raw).hexdigest(), record_id):
                            raise ValueError("Completed item cache identity collision")
                for artifact in artifacts:
                    prior = db.execute("SELECT artifact_json FROM artifacts WHERE id=?", (artifact.id,)).fetchone()
                    if prior and prior[0] != _json(artifact.model_dump(mode="json")):
                        raise ValueError("Artifact ID collision")
                for relative, value in files.items():
                    _write_once(self.artifact_dir / relative, value)
                db.execute("INSERT INTO runs(id,run_json,selection_json,records_json,cancel_requested) VALUES(?,?,?,?,0)",
                           (run_id, raw_run, raw_selection, raw_records))
                for record_id, key, _, _ in rows:
                    relative = f"items/{key}.json"
                    raw = _json(files[relative]).encode()
                    db.execute("INSERT INTO run_items(run_id,record_id,item_key,status,output_bytes) VALUES(?,?,?,?,?)",
                               (run_id, record_id, key, "completed", file_bytes[relative]))
                    db.execute("INSERT OR IGNORE INTO completed_items(item_key,relative_path,sha256,record_id) VALUES(?,?,?,?)",
                               (key, relative, hashlib.sha256(raw).hexdigest(), record_id))
                for artifact in artifacts:
                    db.execute("INSERT OR IGNORE INTO artifacts(id,artifact_json) VALUES(?,?)",
                               (artifact.id, _json(artifact.model_dump(mode="json"))))
            return run

    def list_artifacts(self, snapshot_ids: set[str] | None = None) -> list[Artifact]:
        """Registered artifacts, newest first; optionally only those on given snapshots.

        Returned objects are shared, immutable registrations; copy before changing."""
        with self._db() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM artifacts ORDER BY rowid DESC")]
            with self._artifact_lock:
                missing = [identity for identity in ids if identity not in self._artifacts]
            for start in range(0, len(missing), 256):
                chunk = missing[start:start + 256]
                rows = db.execute(f"SELECT id,artifact_json FROM artifacts WHERE id IN ({','.join('?' * len(chunk))})", chunk).fetchall()
                parsed = {identity: self._loaded(Artifact.model_validate_json(body)) for identity, body in rows}
                with self._artifact_lock:
                    self._artifacts.update(parsed)
        with self._artifact_lock:
            result = [self._artifacts[identity] for identity in ids if identity in self._artifacts]
        if snapshot_ids is not None:
            result = [artifact for artifact in result if snapshot_ids.intersection(artifact.snapshot_ids)]
        return result

    def _loaded(self, artifact: Artifact) -> Artifact:
        artifact._store_root = self.artifact_dir
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact:
        with self._artifact_lock:
            cached = self._artifacts.get(artifact_id)
        if cached is not None:
            return cached
        with self._db() as db:
            row = db.execute("SELECT artifact_json FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        if not row:
            raise KeyError(artifact_id)
        artifact = self._loaded(Artifact.model_validate_json(row[0]))
        with self._artifact_lock:
            self._artifacts.setdefault(artifact_id, artifact)
        return artifact

    def close(self) -> None:
        self._closed = True
