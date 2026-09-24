"""Immutable Parquet snapshots and bounded DuckDB queries over registered fields.

This module is optional to the preview Pack reader. It never opens a caller-supplied
SQL expression or an arbitrary Parquet path: the file belongs to a configured root,
and all query identifiers come from the snapshot's field registry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import sqlite3
import tempfile
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np

from dataset_atlas.models import Artifact, FieldDescriptor, Query, QueryResult, Record, Unit, content_id
from dataset_atlas.queries import validate_filter

_BASE_FIELDS = {
    "id": "string", "text": "string", "question": "string", "unit": "string",
    "dataset_id": "string", "release_id": "string", "snapshot_id": "string",
}
_OPS = {"eq", "ne", "in", "contains", "gt", "gte", "lt", "lte", "is_null"}
_TYPES = {"string", "category", "number", "boolean", "array", "object"}


def _result_values(item: dict[str, Any]) -> dict[str, Any]:
    """Scalar aggregation contract shared with preview result attachment.

    A completed empty detection list is zero. A failed item has only its status;
    a record with no item has no row in the result relation and remains NULL.
    """
    status = item.get("status", "unknown")
    if not isinstance(status, str):
        raise ValueError("Result item status must be a string")
    values: dict[str, Any] = {"status": status}
    if status != "completed":
        return values
    output = item.get("output", {})
    if not isinstance(output, dict):
        raise ValueError("Completed result output must be an object")
    for key, value in output.items():
        if not isinstance(key, str):
            raise ValueError("Result output keys must be strings")
        if value is None or isinstance(value, (str, bool, int, float)):
            if not isinstance(value, float) or math.isfinite(value):
                values[key] = value
    detections = output.get("detections")
    if isinstance(detections, list):
        values["detection_count"] = len(detections)
    asset_outputs = output.get("assets")
    if isinstance(asset_outputs, list):
        completed = [asset for asset in asset_outputs if isinstance(asset, dict) and asset.get("status") == "completed"]
        if len(completed) == len(asset_outputs) == 1:
            for key, value in completed[0].items():
                if key not in {"asset_id", "status"} and (value is None or isinstance(value, (str, bool, int, float))):
                    if not isinstance(key, str):
                        raise ValueError("Result asset output keys must be strings")
                    if not isinstance(value, float) or math.isfinite(value):
                        values[key] = value
        if len(completed) == len(asset_outputs):
            detection_sets = [asset.get("detections", asset.get("output", {}).get("detections")) for asset in completed]
            if all(isinstance(group, list) for group in detection_sets):
                boxes = [box for group in detection_sets for box in group]
                values["detection_count"] = len(boxes)
                values["person_count"] = sum(isinstance(box, dict) and box.get("class") == "person" for box in boxes)
    return values


def _result_dtype(value: Any) -> str:
    return "boolean" if isinstance(value, bool) else "number" if isinstance(value, (int, float)) else "string"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> Path:
    real_root = root.resolve()
    real_path = path.resolve()
    if not real_path.is_relative_to(real_root):
        raise ValueError("Snapshot path is outside the configured root")
    return real_path


def _registry(fields: Sequence[FieldDescriptor]) -> dict[str, tuple[str, str, set[str]]]:
    registry = {name: (name, dtype, set(_OPS)) for name, dtype in _BASE_FIELDS.items()}
    for number, descriptor in enumerate(fields):
        if descriptor.id in registry:
            raise ValueError(f"Duplicate registered field: {descriptor.id}")
        namespace, dot, key = descriptor.id.partition(".")
        if not dot or not key or namespace not in {"source", "prediction", "human"} or namespace != descriptor.namespace:
            raise ValueError(f"Field requires a matching source/prediction/human namespace: {descriptor.id}")
        if descriptor.dtype not in _TYPES or not set(descriptor.query_ops).issubset(_OPS):
            raise ValueError(f"Unsupported field type or operation: {descriptor.id}")
        registry[descriptor.id] = (f"f_{number}", descriptor.dtype, set(descriptor.query_ops))
    return registry


def _arrow_type(dtype: str) -> pa.DataType:
    return {"number": pa.float64(), "boolean": pa.bool_()}.get(dtype, pa.string())


def _field_value(record: Record, field_id: str) -> Any:
    if field_id in _BASE_FIELDS:
        return getattr(record, field_id)
    namespace, _, key = field_id.partition(".")
    return getattr(record, namespace).get(key)


def _encode_field(value: Any, dtype: str, field_id: str) -> Any:
    if value is None:
        return None
    if dtype == "category":
        return _category_value(value)[0]
    if dtype == "string":
        if not isinstance(value, str):
            raise ValueError(f"Expected string for {field_id}")
        return value
    if dtype == "number":
        if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2**53:
            raise ValueError(f"Number exceeds exact query range for {field_id}; register it as a string")
        try:
            number = float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) else math.nan
        except OverflowError:
            number = math.nan
        if not math.isfinite(number):
            raise ValueError(f"Expected finite number for {field_id}")
        return number
    if dtype == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"Expected boolean for {field_id}")
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _category_value(value: Any) -> tuple[str, str]:
    """Encode scalar categories without conflating 1, '1', and true."""
    if isinstance(value, bool):
        return ("b:1" if value else "b:0", "boolean")
    if isinstance(value, str):
        return ("s:" + value, "string")
    if isinstance(value, (int, float)):
        if isinstance(value, int) and abs(value) > 2**53:
            raise ValueError("Category integer exceeds exact query range; register it as a string")
        try:
            number = float(value)
        except OverflowError as exc:
            raise ValueError("Category number is too large") from exc
        if not math.isfinite(number):
            raise ValueError("Category number must be finite")
        return ("n:" + repr(number), "number")
    raise ValueError("Category value must be a string, finite number, boolean, or null")


def build_parquet_snapshot(
    records: Iterable[Record], fields: Sequence[FieldDescriptor], output_dir: Path, *,
    root: Path, dataset_id: str, release_id: str, snapshot_id: str,
    expected_count: int, unit: Unit = "example", population_scope: str = "preview",
    batch_size: int = 512, max_bytes: int = 20_000_000_000,
    max_record_bytes: int = 2_000_000,
) -> Path:
    """Stream records into a new, checksum-bound snapshot; never alter originals.

    `expected_count` is mandatory so a truncated iterator cannot be registered as a
    complete release. A partial iterator must use a distinct explicit scope.
    """
    root = Path(root)
    output_dir = Path(output_dir)
    if not root.is_dir() or not _inside(root, output_dir.parent).is_dir():
        raise ValueError("Snapshot root and destination parent must exist")
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError("Snapshot destination already exists")
    if not dataset_id or not release_id or not snapshot_id or type(expected_count) is not int or expected_count < 0:
        raise ValueError("Snapshot identity and expected count are required")
    if population_scope not in {"complete", "preview"}:
        raise ValueError("Unsupported population scope")
    if type(batch_size) is not int or not 1 <= batch_size <= 4096 or max_bytes <= 0:
        raise ValueError("Invalid snapshot bounds")
    if type(max_record_bytes) is not int or not 1 <= max_record_bytes <= 16_000_000:
        raise ValueError("Record bound must be within 1..16 MB")
    fields = list(fields)
    registry = _registry(fields)
    schema = pa.schema([
        *[pa.field(name, pa.string()) for name in _BASE_FIELDS],
        pa.field("record_json", pa.string()),
        pa.field("search_text", pa.string()),
        *[pa.field(column, _arrow_type(dtype)) for field_id, (column, dtype, _) in registry.items() if field_id not in _BASE_FIELDS],
    ], metadata={b"dataset_id": dataset_id.encode(), b"release_id": release_id.encode(), b"snapshot_id": snapshot_id.encode(), b"unit": unit.encode()})
    with tempfile.TemporaryDirectory(prefix=".atlas-parquet-", dir=output_dir.parent) as temp:
        stage = Path(temp) / "snapshot"
        stage.mkdir()
        parquet = stage / "records.parquet"
        writer = pq.ParquetWriter(parquet, schema=schema, compression="zstd")
        rows: list[dict[str, Any]] = []
        rows_bytes = 0
        count = 0
        category_kinds: dict[str, set[str]] = {field_id: set() for field_id, (_, dtype, _) in registry.items() if dtype == "category"}
        identity_db = sqlite3.connect(stage / "ids.sqlite")
        identity_db.execute("CREATE TABLE ids (id TEXT PRIMARY KEY) WITHOUT ROWID")
        try:
            for record in records:
                if record.dataset_id != dataset_id or record.release_id != release_id or record.snapshot_id != snapshot_id or record.unit != unit:
                    raise ValueError(f"Record identity does not match snapshot: {record.id}")
                if not record.id:
                    raise ValueError(f"Duplicate or empty record ID: {record.id}")
                try:
                    identity_db.execute("INSERT INTO ids(id) VALUES (?)", (record.id,))
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"Duplicate or empty record ID: {record.id}") from exc
                encoded = record.model_dump_json()
                if len(encoded.encode("utf-8")) > max_record_bytes:
                    raise ValueError(f"Record exceeds {max_record_bytes} byte bound: {record.id}; source={record.source.get('_atlas_origin', {})}")
                row = {name: _field_value(record, name) for name in _BASE_FIELDS}
                row["record_json"] = encoded
                row["search_text"] = "\n".join([record.text or "", record.question or "", json.dumps(record.source, ensure_ascii=False, separators=(",", ":"))]).lower()
                for field_id, (column, dtype, _) in registry.items():
                    if field_id not in _BASE_FIELDS:
                        value = _field_value(record, field_id)
                        row[column] = _encode_field(value, dtype, field_id)
                        if dtype == "category" and value is not None:
                            category_kinds[field_id].add(_category_value(value)[1])
                rows.append(row)
                rows_bytes += len(encoded.encode("utf-8"))
                count += 1
                if count > expected_count:
                    raise ValueError("More records than declared expected_count")
                if len(rows) >= batch_size or rows_bytes >= 8_000_000:
                    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                    rows.clear()
                    rows_bytes = 0
                    if parquet.stat().st_size > max_bytes:
                        raise ValueError("Snapshot exceeds byte budget")
            if rows:
                writer.write_table(pa.Table.from_pylist(rows, schema=schema))
            if count != expected_count:
                raise ValueError(f"Snapshot has {count} records; expected {expected_count}")
        finally:
            writer.close()
            identity_db.close()
        (stage / "ids.sqlite").unlink()
        if parquet.stat().st_size > max_bytes:
            raise ValueError("Snapshot exceeds byte budget")
        manifest = {
            "schema_version": "1.0", "dataset_id": dataset_id, "release_id": release_id,
            "snapshot_id": snapshot_id, "unit": unit, "population_scope": population_scope,
            "record_count": count, "fields": [field.model_dump(mode="json") for field in fields],
            "category_kinds": {field_id: sorted(kinds) for field_id, kinds in category_kinds.items()},
            "checksums": {"records.parquet": _sha256(parquet)},
            "parquet_bytes": parquet.stat().st_size,
            "max_record_bytes": max_record_bytes,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        parquet.chmod(0o444)
        (stage / "manifest.json").chmod(0o444)
        os.replace(stage, output_dir)
    return output_dir


class ParquetSnapshot:
    """Validated immutable snapshot. Call `interrupt()` from another thread to cancel."""

    def __init__(self, root: Path, snapshot_dir: Path, *, memory_mb: int = 256, threads: int = 4, timeout_seconds: float = 30):
        root = Path(root)
        directory = Path(snapshot_dir)
        if not root.is_dir() or directory.is_symlink() or not directory.is_dir():
            raise ValueError("Snapshot directory is unavailable")
        _inside(root, directory)
        manifest_path = directory / "manifest.json"
        parquet = directory / "records.parquet"
        if manifest_path.is_symlink() or parquet.is_symlink() or not manifest_path.is_file() or not parquet.is_file():
            raise ValueError("Snapshot files are missing or linked")
        if manifest_path.stat().st_size > 1_000_000:
            raise ValueError("Snapshot manifest exceeds 1 MB")
        try:
            manifest = json.loads(manifest_path.read_text())
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid snapshot manifest") from exc
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("checksums"), dict) or set(manifest["checksums"]) != {"records.parquet"} or not isinstance(manifest.get("fields"), list) or manifest.get("population_scope") not in {"preview", "complete"}:
            raise ValueError("Unsupported snapshot manifest")
        if manifest.get("parquet_bytes") != parquet.stat().st_size or manifest["checksums"]["records.parquet"] != _sha256(parquet):
            raise ValueError("Snapshot checksum mismatch")
        parquet_metadata = pq.read_metadata(parquet)
        for key in ("dataset_id", "release_id", "snapshot_id", "unit"):
            if parquet_metadata.metadata.get(key.encode(), b"").decode() != manifest.get(key):
                raise ValueError("Snapshot manifest identity differs from Parquet")
        if parquet_metadata.num_rows != manifest.get("record_count"):
            raise ValueError("Snapshot record count differs from Parquet")
        if type(manifest.get("record_count")) is not int or manifest["record_count"] < 0:
            raise ValueError("Invalid snapshot count")
        if type(memory_mb) is not int or not 64 <= memory_mb <= 2048 or type(threads) is not int or not 1 <= threads <= 8:
            raise ValueError("Invalid query resource bounds")
        fields = [FieldDescriptor.model_validate(value) for value in manifest["fields"]]
        self.registry = _registry(fields)
        category_kinds = manifest.get("category_kinds", {})
        if not isinstance(category_kinds, dict) or set(category_kinds) != {field_id for field_id, (_, dtype, _) in self.registry.items() if dtype == "category"} or any(not isinstance(kinds, list) or set(kinds) - {"string", "number", "boolean"} for kinds in category_kinds.values()):
            raise ValueError("Invalid category type registry")
        self.category_kinds = category_kinds
        self.fields = fields
        self.manifest = manifest
        self.dataset_id = manifest["dataset_id"]
        self.release_id = manifest["release_id"]
        self.snapshot_id = manifest["snapshot_id"]
        self.unit = manifest["unit"]
        self.population_scope = manifest["population_scope"]
        self.record_count = manifest["record_count"]
        self.parquet = parquet
        self._stat = (parquet.stat().st_size, parquet.stat().st_mtime_ns)
        self.memory_mb = memory_mb
        self.threads = threads
        if isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not 0 < timeout_seconds <= 300:
            raise ValueError("Query timeout must be within 0..300 seconds")
        self.timeout_seconds=timeout_seconds
        self._active: set[duckdb.DuckDBPyConnection] = set()
        self._lock = threading.Lock()

    def interrupt(self) -> None:
        """Interrupt active DuckDB work; the querying thread receives ValueError."""
        with self._lock:
            connections = list(self._active)
        for connection in connections:
            try:
                connection.interrupt()
            except duckdb.Error:
                pass

    @staticmethod
    def _column(field_id: str, registry: dict[str, tuple[str, str, set[str]]]) -> tuple[str, str, set[str]]:
        if field_id not in registry:
            raise ValueError(f"Unknown field: {field_id}")
        return registry[field_id]

    def _prepare_results(self, artifacts: Sequence[Artifact]) -> tuple[list[FieldDescriptor], pa.Table]:
        if len(artifacts) > 32 or len({artifact.id for artifact in artifacts}) != len(artifacts):
            raise ValueError("Result snapshots must be unique and limited to 32")
        fields: dict[str, FieldDescriptor] = {}
        observed_types: dict[str, str] = {}
        rows: dict[str, dict[str, Any]] = {}
        item_count = 0
        for artifact in artifacts:
            if artifact.snapshot_ids != [self.snapshot_id] or artifact.unit != self.unit:
                raise ValueError("Result snapshot or unit is incompatible with this Parquet snapshot")
            if len(artifact.ids) != len(set(artifact.ids)):
                raise ValueError("Result artifact IDs must be unique")
            allowed_ids = set(artifact.ids)
            items = artifact.data.get("items", [])
            if not isinstance(items, list):
                raise ValueError("Result artifact items must be an array")
            seen: set[str] = set()
            for item in items:
                item_count += 1
                if item_count > 250_000:
                    raise ValueError("Result join exceeds 250,000 items")
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] not in allowed_ids or item["id"] in seen:
                    raise ValueError("Result item has duplicate or unregistered record ID")
                seen.add(item["id"])
                record_id = item["id"]
                prediction = rows.setdefault(record_id, {})
                for key, value in _result_values(item).items():
                    name = artifact.id + "." + key
                    field_id = "prediction." + name
                    if field_id in self.registry:
                        raise ValueError(f"Result field collides with source snapshot: {field_id}")
                    prediction[name] = value
                    if value is not None:
                        dtype = _result_dtype(value)
                        previous = observed_types.get(field_id)
                        if previous is not None and previous != dtype:
                            raise ValueError(f"Result field has mixed scalar types: {field_id}")
                        observed_types[field_id] = dtype
                    if field_id not in fields:
                        dtype = observed_types.get(field_id, "string")
                        fields[field_id] = FieldDescriptor(
                            id=field_id, name=artifact.kind + " · " + key, namespace="prediction",
                            dtype=dtype, unit=self.unit,
                            provenance={"artifact_id": artifact.id, "run_id": artifact.run_id, "aggregation_version": "1.0"},
                            query_ops=["eq", "ne", "in", "contains", "is_null"] + (["gt", "gte", "lt", "lte"] if dtype == "number" else []),
                        )
                    elif value is not None and fields[field_id].dtype != observed_types[field_id]:
                        dtype = observed_types[field_id]
                        fields[field_id] = fields[field_id].model_copy(update={
                            "dtype": dtype,
                            "query_ops": ["eq", "ne", "in", "contains", "is_null"] + (["gt", "gte", "lt", "lte"] if dtype == "number" else []),
                        })
        descriptors = list(fields.values())
        schema = pa.schema([pa.field("id", pa.string()), pa.field("prediction_json", pa.string()),
                            *[pa.field(f"r_{index}", _arrow_type(field.dtype)) for index, field in enumerate(descriptors)]])
        table_rows = []
        total_json_bytes = 0
        for record_id, prediction in rows.items():
            row = {"id": record_id, "prediction_json": json.dumps(prediction, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)}
            row_bytes = len(row["prediction_json"].encode("utf-8"))
            total_json_bytes += row_bytes
            if row_bytes > 2_000_000:
                raise ValueError("Result item exceeds 2 MB bound")
            if total_json_bytes > 128_000_000:
                raise ValueError("Result join exceeds 128 MB scalar output budget")
            for index, field in enumerate(descriptors):
                name = field.id.removeprefix("prediction.")
                row[f"r_{index}"] = _encode_field(prediction.get(name), field.dtype, field.id)
            table_rows.append(row)
        return descriptors, pa.Table.from_pylist(table_rows, schema=schema)

    def result_fields(self, artifacts: Sequence[Artifact]) -> list[FieldDescriptor]:
        """Descriptors available when these explicit immutable results are joined."""
        return self._prepare_results(artifacts)[0]

    def query_fields(self, artifacts: Sequence[Artifact] = ()) -> list[FieldDescriptor]:
        """Registered source and selected result fields for a complete-data UI."""
        return [*self.fields, *self.result_fields(artifacts)] if artifacts else list(self.fields)

    @staticmethod
    def _operand(value: Any, dtype: str) -> Any:
        if dtype == "category":
            return _category_value(value)[0]
        if dtype == "number" and not isinstance(value, bool) and isinstance(value, (int, float)):
            if isinstance(value, int) and abs(value) > 2**53:
                raise ValueError("Number exceeds exact query range; filter as a string field")
            try:
                number = float(value)
                if math.isfinite(number):
                    return number
            except OverflowError:
                pass
        if dtype == "boolean" and isinstance(value, bool):
            return value
        if dtype in {"string", "category"} and isinstance(value, str):
            return value
        raise ValueError(f"Filter operand must match registered {dtype} field type")

    @staticmethod
    def _category_sort_expression(field_id: str, column: str, category_kinds: dict[str, list[str]]) -> tuple[str, str]:
        kinds = category_kinds[field_id]
        if len(kinds) > 1:
            raise ValueError(f"Cannot order mixed-type category field: {field_id}")
        kind = kinds[0] if kinds else "string"
        raw = f"substr({column}, 3)"
        if kind == "number":
            return f"TRY_CAST({raw} AS DOUBLE)", kind
        if kind == "boolean":
            return f"TRY_CAST({raw} AS INTEGER)", kind
        return raw, kind

    def _predicate(self, node: dict[str, Any], params: list[Any], registry: dict[str, tuple[str, str, set[str]]], category_kinds: dict[str, list[str]]) -> str:
        if "and" in node:
            return "(" + " AND ".join(self._predicate(child, params, registry, category_kinds) for child in node["and"]) + ")"
        if "or" in node:
            return "(" + " OR ".join(self._predicate(child, params, registry, category_kinds) for child in node["or"]) + ")"
        if "not" in node:
            return "(NOT " + self._predicate(node["not"], params, registry, category_kinds) + ")"
        field_id = node["field_id"]
        col, dtype, allowed = self._column(field_id, registry)
        op = node["op"]
        if op not in allowed:
            raise ValueError(f"Operation {op} is not registered for {field_id}")
        if op == "is_null":
            return f"({col} IS {'NULL' if node['value'] else 'NOT NULL'})"
        value = node.get("value")
        if value is None:
            return "FALSE"
        if dtype in {"array", "object"}:
            raise ValueError(f"Structured field does not support {op}: {field_id}")
        if op == "in":
            choices = [self._operand(item, dtype) for item in value if item is not None]
            if not choices:
                return "FALSE"
            params.extend(choices)
            return f"({col} IS NOT NULL AND {col} IN ({','.join('?' for _ in choices)}))"
        if op == "contains":
            if dtype not in {"string", "category"}:
                raise ValueError(f"Contains requires a string field: {field_id}")
            if not isinstance(value, str):
                raise ValueError("Contains expects a literal string")
            params.append(value)
            if dtype == "category":
                return f"({col} IS NOT NULL AND starts_with({col}, 's:') AND instr(lower(substr({col}, 3)), lower(?)) > 0)"
            return f"({col} IS NOT NULL AND instr(lower({col}), lower(?)) > 0)"
        if op in {"gt", "gte", "lt", "lte"} and dtype == "boolean":
            raise ValueError(f"Boolean field does not support ordering: {field_id}")
        if op in {"gt", "gte", "lt", "lte"} and dtype == "category":
            expression, kind = self._category_sort_expression(field_id, col, category_kinds)
            if kind == "boolean":
                raise ValueError(f"Boolean category does not support ordering: {field_id}")
            candidate, operand_kind = _category_value(value)
            if operand_kind != kind:
                raise ValueError(f"Filter operand must match category kind {kind}")
            params.append(float(candidate[2:]) if kind == "number" else candidate[2:])
            symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            return f"({col} IS NOT NULL AND {expression} {symbol} ?)"
        params.append(self._operand(value, dtype))
        symbol = {"eq": "=", "ne": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
        return f"({col} IS NOT NULL AND {col} {symbol} ?)"

    def query(self, query: Query, artifacts: Sequence[Artifact] = ()) -> QueryResult:
        selected = query.result_snapshot_ids
        if len(selected) != len(set(selected)) or set(selected) != {artifact.id for artifact in artifacts}:
            raise ValueError("Explicit result snapshot IDs must match supplied artifacts")
        if query.snapshot_id != self.manifest["snapshot_id"]:
            raise ValueError("Snapshot mismatch; reload dataset before querying")
        requested_scope = getattr(query, "population_scope", None)
        if requested_scope is not None and requested_scope != self.population_scope:
            raise ValueError("Population scope differs from snapshot; choose the matching scope")
        if query.unit != self.manifest["unit"]:
            raise ValueError("This snapshot does not support the requested record unit")
        if (self.parquet.stat().st_size, self.parquet.stat().st_mtime_ns) != self._stat:
            raise ValueError("Snapshot changed after validation")
        if len(query.search) > 4000:
            raise ValueError("Search exceeds 4000 characters")
        result_fields, result_table = self._prepare_results(artifacts)
        registry = {field_id: (f'source."{column}"', dtype, allowed) for field_id, (column, dtype, allowed) in self.registry.items()}
        for index, field in enumerate(result_fields):
            registry[field.id] = (f'results."r_{index}"', field.dtype, set(field.query_ops))
        validate_filter(query.filter, set(registry))
        params: list[Any] = []
        predicates: list[str] = []
        if query.filter:
            predicates.append(self._predicate(query.filter, params, registry, self.category_kinds))
        if query.search:
            predicates.append('instr(source."search_text", ?) > 0')
            params.append(query.search.lower())
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        sorts: list[str] = []
        for sort in query.sort:
            if set(sort) != {"field_id", "direction"} or sort["direction"] not in {"asc", "desc"}:
                raise ValueError("Invalid sort specification")
            column, dtype, _ = self._column(sort["field_id"], registry)
            if dtype in {"array", "object"}:
                raise ValueError(f"Cannot sort structured field: {sort['field_id']}")
            expression = self._category_sort_expression(sort["field_id"], column, self.category_kinds)[0] if dtype == "category" else column
            sorts.append(f'{expression} {sort["direction"].upper()} NULLS LAST')
        if not any(sort.get("field_id") == "id" for sort in query.sort):
            sorts.append('source."id" ASC')
        order = " ORDER BY " + ", ".join(sorts)
        method = "source"
        seed = 0
        sample_field = None
        if query.sample:
            options = query.sample
            if set(options) - {"method", "seed", "size", "field_id"} or options.get("method", "source") not in {"source","random","stratified"}:
                raise ValueError("Invalid sampling method or options")
            method=options.get("method","source")
            seed=options.get("seed",0)
            sample_field=options.get("field_id")
            if method=="stratified" and sample_field not in registry:raise ValueError("Stratified sampling requires a registered field")
            size = options.get("size", 100)
            if type(size) is not int or not 1 <= size <= 10000 or type(options.get("seed", 0)) is not int:
                raise ValueError("Invalid source sample size or seed")
        else:
            size = None
        fingerprint = content_id(query.model_dump(exclude={"cursor"}))
        offset = 0
        if query.cursor:
            try:
                if len(query.cursor) > 1024:
                    raise ValueError()
                cursor = json.loads(base64.urlsafe_b64decode(query.cursor.encode()))
                if cursor["query"] != fingerprint or type(cursor["offset"]) is not int or cursor["offset"] < 0:
                    raise ValueError()
                offset = cursor["offset"]
            except Exception as exc:
                raise ValueError("Invalid cursor or query changed; restart pagination") from exc
        connection = duckdb.connect(database=":memory:")
        connection.execute(f"SET memory_limit = '{self.memory_mb}MB'")
        connection.execute("SET max_temp_directory_size = '1024MB'")
        connection.execute(f"SET threads = {self.threads}")
        with self._lock:
            self._active.add(connection)
        expired=threading.Event()
        def expire():
            expired.set()
            connection.interrupt()
        timer=threading.Timer(self.timeout_seconds,expire)
        timer.daemon=True
        timer.start()
        try:
            if method in {"random","stratified"}:
                def rank_batch(identities):
                    encoded=[f"{seed}:{identity}".encode() for identity in identities.to_pylist()]
                    if not encoded:return pa.array([],type=pa.uint64())
                    lengths=np.array([len(value) for value in encoded])
                    width=int(lengths.max())
                    octets=np.frombuffer(b''.join(value.ljust(width,b'\0') for value in encoded),dtype=np.uint8).reshape(len(encoded),width)
                    ranks=np.full(len(encoded),2166136261,dtype=np.uint32)
                    for column in range(width):
                        ranks=np.where(lengths>column,(ranks ^ octets[:,column])*np.uint32(16777619),ranks)
                    return pa.array(ranks.astype(np.uint64))
                connection.create_function("atlas_rank", rank_batch, ["VARCHAR"], "UBIGINT",type="arrow")
                order=' ORDER BY atlas_rank(source."id"), source."id"'
            if method=="stratified":
                def stratum(record_json, prediction_json):
                    if record_json is None:return "null"
                    row=json.loads(record_json)
                    namespace,_,key=sample_field.partition('.')
                    if namespace in {'source','prediction','human'}:
                        values=row.get(namespace,{})
                        if namespace=='prediction' and prediction_json:values={**values,**json.loads(prediction_json)}
                        value=values.get(key)
                    else:value=row.get(sample_field)
                    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
                def stratum_batch(records,predictions):
                    return pa.array([stratum(row,prediction) for row,prediction in zip(records.to_pylist(),predictions.to_pylist(),strict=True)],type=pa.string())
                connection.create_function("atlas_stratum",stratum_batch,["VARCHAR","VARCHAR"],"VARCHAR",null_handling="special",type="arrow")
                order=' ORDER BY atlas_stratum_rank, atlas_stratum_key'
            if artifacts:
                connection.register("result_table", result_table)
            source = 'read_parquet(?) AS source' + (' LEFT JOIN result_table AS results ON source."id" = results."id"' if artifacts else '')
            if expired.is_set():raise ValueError("Query exceeded its time budget")
            # An unfiltered, unjoined population is exactly the manifest count, already checked against Parquet metadata.
            count = self.record_count if not where and not artifacts else connection.execute(f"SELECT count(*) FROM {source}{where}", [str(self.parquet), *params]).fetchone()[0]
            sampled_count = min(size, count) if size is not None else count
            if offset > sampled_count:
                raise ValueError("Cursor offset exceeds current result; restart pagination")
            take = min(query.limit, sampled_count - offset)
            if take:
                selected_columns = 'source."record_json", results."prediction_json"' if artifacts else 'source."record_json"'
                if method=='stratified':
                    prediction='results."prediction_json"' if artifacts else 'NULL'
                    strata=f'atlas_stratum(source."record_json", {prediction})'
                    selected_columns+=f', row_number() OVER (PARTITION BY {strata} ORDER BY atlas_rank(source."id"), source."id") AS atlas_stratum_rank, {strata} AS atlas_stratum_key'
                if expired.is_set():raise ValueError("Query exceeded its time budget")
                reader = connection.execute(f"SELECT {selected_columns} FROM {source}{where}{order} LIMIT ? OFFSET ?", [str(self.parquet), *params, take, offset])
                result_rows = []; page_bytes = 0
                while row := reader.fetchone():
                    payload_bytes = len(row[0].encode()) + (len(row[1].encode()) if artifacts and row[1] else 0)
                    if payload_bytes > 32_000_000:
                        raise ValueError("Single query record exceeds 32 MB response payload bound")
                    if result_rows and page_bytes + payload_bytes > 32_000_000:
                        break
                    result_rows.append(row); page_bytes += payload_bytes
            else:
                result_rows = []
            # An interrupt delivered between statements is otherwise lost; the budget still applies.
            if expired.is_set():raise ValueError("Query exceeded its time budget")
        except duckdb.InterruptException as exc:
            raise ValueError("Query exceeded its time budget" if expired.is_set() else "Query cancelled") from exc
        finally:
            timer.cancel()
            timer.join()
            with self._lock:
                self._active.discard(connection)
            connection.close()
        records = [Record.model_validate_json(row[0]) for row in result_rows]
        if artifacts:
            for record, row in zip(records, result_rows, strict=True):
                if row[1] is not None:
                    record.prediction.update(json.loads(row[1]))
        if any(record.snapshot_id != query.snapshot_id or record.unit != query.unit for record in records):
            raise ValueError("Parquet record identity does not match snapshot")
        next_offset = offset + len(records)
        next_cursor = base64.urlsafe_b64encode(json.dumps({"query": fingerprint, "offset": next_offset}).encode()).decode() if next_offset < sampled_count else None
        warnings = []
        if len(records) < take:
            warnings.append("Page shortened to the 32 MB record payload budget; continue with its cursor.")
        if method=="stratified":warnings.append("Stratified samples do not estimate population prevalence.")
        if self.manifest["population_scope"] != "complete":
            warnings.append(f"Counts describe the available {self.manifest['population_scope']} snapshot, not a complete release.")
        return QueryResult(
            snapshot_id=query.snapshot_id, unit=query.unit, population_scope=self.manifest["population_scope"],
            records=records, returned_count=len(records), matched_count=count,
            coverage={"available_count": self.manifest["record_count"], "sampled_count": sampled_count, "sampling": query.sample},
            ordering=query.sort, cursor=next_cursor, warnings=warnings,
        )

    def aggregate(self, query: Query, field_ids: Sequence[str], artifacts: Sequence[Artifact] = (), *, top: int = 24) -> dict[str, Any]:
        """Distributions for named fields over the population the filter matched.

        This exists so a dataset overview can state real counts for a complete
        index instead of extrapolating from a loaded page. Any sampling in the
        browsing query is deliberately not applied, and the response says so:
        a stratified preview is not a prevalence estimate.
        """
        if query.snapshot_id != self.manifest["snapshot_id"]:
            raise ValueError("Snapshot mismatch; reload dataset before aggregating")
        if query.unit != self.manifest["unit"]:
            raise ValueError("This snapshot does not support the requested record unit")
        if len(field_ids) > 12:
            raise ValueError("Aggregate at most 12 fields per request")
        if type(top) is not int or not 1 <= top <= 200:
            raise ValueError("Invalid aggregation width")
        selected = query.result_snapshot_ids
        if len(selected) != len(set(selected)) or set(selected) != {artifact.id for artifact in artifacts}:
            raise ValueError("Explicit result snapshot IDs must match supplied artifacts")
        result_fields, result_table = self._prepare_results(artifacts)
        registry = {field_id: (f'source."{column}"', dtype, allowed) for field_id, (column, dtype, allowed) in self.registry.items()}
        for index, field in enumerate(result_fields):
            registry[field.id] = (f'results."r_{index}"', field.dtype, set(field.query_ops))
        validate_filter(query.filter, set(registry))
        params: list[Any] = []
        predicates: list[str] = []
        if query.filter:
            predicates.append(self._predicate(query.filter, params, registry, self.category_kinds))
        if query.search:
            if len(query.search) > 4000:
                raise ValueError("Search exceeds 4000 characters")
            predicates.append('instr(source."search_text", ?) > 0')
            params.append(query.search.lower())
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        source = 'read_parquet(?) AS source' + (' LEFT JOIN result_table AS results ON source."id" = results."id"' if artifacts else '')

        connection = duckdb.connect(database=":memory:")
        connection.execute(f"SET memory_limit = '{self.memory_mb}MB'")
        connection.execute("SET max_temp_directory_size = '1024MB'")
        connection.execute(f"SET threads = {self.threads}")
        with self._lock:
            self._active.add(connection)
        expired = threading.Event()

        def expire() -> None:
            expired.set()
            connection.interrupt()

        timer = threading.Timer(self.timeout_seconds, expire)
        timer.daemon = True
        timer.start()
        results: list[dict[str, Any]] = []
        try:
            if artifacts:
                connection.register("result_table", result_table)
            denominator = connection.execute(f"SELECT count(*) FROM {source}{where}", [str(self.parquet), *params]).fetchone()[0]
            for field_id in field_ids:
                column, dtype, _ = self._column(field_id, registry)
                if dtype in {"array", "object"}:
                    results.append({"field_id": field_id, "kind": "unsupported", "reason": "Structured fields are not aggregated."})
                    continue
                missing = connection.execute(f"SELECT count(*) FROM {source}{where}{' AND' if where else ' WHERE'} {column} IS NULL", [str(self.parquet), *params]).fetchone()[0]
                if dtype == "category":
                    expression, kind = self._category_sort_expression(field_id, column, self.category_kinds) if len(self.category_kinds.get(field_id, [])) == 1 else (f"substr({column}, 3)", "string")
                    key = f"substr({column}, 3)" if kind != "number" else expression
                else:
                    key = column
                if dtype == "number":
                    row = connection.execute(
                        f'SELECT min({column}), max({column}), avg({column}), count({column}) FROM {source}{where}',
                        [str(self.parquet), *params],
                    ).fetchone()
                    results.append({
                        "field_id": field_id, "kind": "numeric", "denominator": denominator, "missing": missing,
                        "min": row[0], "max": row[1], "mean": row[2], "present": row[3],
                    })
                    continue
                rows = connection.execute(
                    f'SELECT CAST({key} AS VARCHAR) AS k, count(*) AS n FROM {source}{where}{" AND" if where else " WHERE"} {column} IS NOT NULL GROUP BY 1 ORDER BY n DESC, k ASC LIMIT ?',
                    [str(self.parquet), *params, top + 1],
                ).fetchall()
                truncated = len(rows) > top
                results.append({
                    "field_id": field_id, "kind": "categorical", "denominator": denominator, "missing": missing,
                    "counts": [{"value": row[0], "count": row[1]} for row in rows[:top]], "truncated": truncated,
                })
        except duckdb.InterruptException as exc:
            raise ValueError("Aggregation exceeded its time budget" if expired.is_set() else "Aggregation cancelled") from exc
        finally:
            timer.cancel()
            timer.join()
            with self._lock:
                self._active.discard(connection)
            connection.close()
        return {
            "snapshot_id": self.snapshot_id, "unit": self.unit, "population_scope": self.population_scope,
            "denominator": denominator, "count_status": "exact", "results": results,
            "sampling_applied": False,
            "warnings": (["Sampling in the browsing query was not applied; these counts describe the filtered population."] if query.sample else [])
                        + ([] if self.population_scope == "complete" else [f"Counts describe the available {self.population_scope} snapshot, not a complete release."]),
        }
