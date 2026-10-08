"""Non-executable portable directory form of a canonical Pack."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from dataset_atlas.models import Pack

from .security import MAX_EXCHANGE_BYTES, ExchangeError, compact_json, contained_file, digest, read_json, scan_public

_PARTS = ("dataset.json", "fields.json", "preview/samples-000.json", "artifacts/artifacts.json", "pack-meta.json")


def _validate_pack(pack: Pack) -> None:
    if not pack.dataset.id or pack.population_scope not in {"preview", "complete", "selection"}:
        raise ExchangeError("Invalid pack identity or population scope")
    ids = [record.id for record in pack.records]
    if len(ids) != len(set(ids)):
        raise ExchangeError("Duplicate record ID in pack")
    for record in pack.records:
        if record.dataset_id != pack.dataset.id or record.snapshot_id != pack.dataset.snapshot_id or record.release_id != pack.dataset.release:
            raise ExchangeError(f"Record identity does not match pack: {record.id}")
        for asset in record.assets:
            if asset.dataset_id != record.dataset_id or asset.release_id != record.release_id:
                raise ExchangeError(f"Asset identity does not match pack: {asset.id}")
    artifact_ids = [artifact.id for artifact in pack.artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ExchangeError("Duplicate artifact ID in pack")
    subjects = {unit: {record.id for record in pack.records if record.unit == unit}
                for unit in ('asset', 'example', 'entity', 'conversation')}
    subjects['asset'].update(asset.id for record in pack.records for asset in record.assets)
    for artifact in pack.artifacts:
        if artifact.snapshot_ids != [pack.dataset.snapshot_id]:
            raise ExchangeError(f"Artifact snapshot does not match pack: {artifact.id}")
        if len(artifact.ids) != len(set(artifact.ids)) or not set(artifact.ids).issubset(subjects[artifact.unit]):
            raise ExchangeError(f"Artifact subjects do not match pack unit and IDs: {artifact.id}")
        declared = set(artifact.ids)
        for key in ('items', 'points', 'rows', 'ids'):
            if key not in artifact.data:
                continue
            values = artifact.data[key]
            if not isinstance(values, list):
                raise ExchangeError(f"Artifact {key} must be a list: {artifact.id}")
            embedded = values if key == 'ids' else [value.get('id') if isinstance(value, dict) else None for value in values]
            if any(not isinstance(identity, str) or identity not in declared for identity in embedded) or len(embedded) != len(set(embedded)):
                raise ExchangeError(f"Artifact {key} subjects differ from its declared IDs: {artifact.id}")
    if pack.checksums:
        raise ExchangeError("Nested external file checksums are not portable; include content in a new pack")


def export_pack(pack: Pack, output_dir: Path, *, max_bytes: int = MAX_EXCHANGE_BYTES) -> Path:
    """Export a JSON pack directory; caller must supply authorized, path-free content."""
    _validate_pack(pack)
    dataset = pack.dataset.model_dump(mode="json", exclude={"adapter_config", "evidence", "relationships"})
    dataset.update(adapter_config={}, evidence=[], relationships=[])
    parts = {
        "dataset.json": compact_json(dataset),
        "fields.json": compact_json([field.model_dump(mode="json") for field in pack.fields]),
        "preview/samples-000.json": compact_json([record.model_dump(mode="json") for record in pack.records]),
        "artifacts/artifacts.json": compact_json([artifact.model_dump(mode="json") for artifact in pack.artifacts]),
        "pack-meta.json": compact_json({"schema_version": pack.schema_version, "population_scope": pack.population_scope, "sampling": pack.sampling}),
    }
    for name, content in parts.items():
        value = read_json_bytes(content)
        if name == "dataset.json":
            value = {key: item for key, item in value.items() if key not in {"adapter_config", "evidence"}}
        scan_public(value, label=name)
    manifest = {"schema_version": "1.0", "kind": "pack", "dataset_id": pack.dataset.id, "snapshot_id": pack.dataset.snapshot_id, "files": list(_PARTS), "checksums": {name: digest(content) for name, content in parts.items()}}
    parts["manifest.json"] = compact_json(manifest)
    if sum(len(item) for item in parts.values()) > max_bytes:
        raise ExchangeError("Pack export exceeds size limit")
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise ExchangeError("Pack export destination already exists")
    with tempfile.TemporaryDirectory(prefix=".atlas-pack-", dir=output_dir.parent) as temp:
        stage = Path(temp) / "pack"
        stage.mkdir()
        for name, content in parts.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        os.replace(stage, output_dir)
    return output_dir


def read_json_bytes(data: bytes):
    import json
    return json.loads(data)


def import_pack(path: Path, *, max_bytes: int = MAX_EXCHANGE_BYTES) -> Pack:
    """Reject unknown files, traversal, links, size excess, invalid checksums and IDs."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ExchangeError("Pack import requires a directory")
    manifest = read_json(path / "manifest.json", limit=1_000_000)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or manifest.get("kind") != "pack":
        raise ExchangeError("Unsupported pack manifest")
    if manifest.get("files") != list(_PARTS) or not isinstance(manifest.get("checksums"), dict) or set(manifest["checksums"]) != set(_PARTS):
        raise ExchangeError("Unexpected pack files")
    all_files = {item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file() or item.is_symlink()}
    if all_files != {*_PARTS, "manifest.json"}:
        raise ExchangeError("Pack contains unexpected files")
    total = (path / "manifest.json").stat().st_size
    for name in _PARTS:
        file = contained_file(path, name)
        total += file.stat().st_size
    if total > max_bytes:
        raise ExchangeError("Pack import exceeds size limit")
    for name in _PARTS:
        if digest((path / name).read_bytes()) != manifest["checksums"][name]:
            raise ExchangeError(f"Pack checksum mismatch: {name}")
    try:
        dataset = read_json(path / "dataset.json", limit=max_bytes)
        fields = read_json(path / "fields.json", limit=max_bytes)
        records = read_json(path / "preview/samples-000.json", limit=max_bytes)
        artifacts = read_json(path / "artifacts/artifacts.json", limit=max_bytes)
        meta = read_json(path / "pack-meta.json", limit=max_bytes)
        if not isinstance(meta, dict) or set(meta) != {"schema_version", "population_scope", "sampling"}:
            raise ExchangeError("Invalid pack metadata")
        pack = Pack.model_validate({"dataset": dataset, "fields": fields, "records": records, "artifacts": artifacts, **meta})
    except ValidationError as exc:
        raise ExchangeError("Invalid pack schema") from exc
    _validate_pack(pack)
    for name in _PARTS:
        value = read_json(path / name, limit=max_bytes)
        if name == "dataset.json":
            if value.get("adapter_config") or value.get("evidence"):
                raise ExchangeError("Portable pack contains private registry fields")
            value = {key: item for key, item in value.items() if key not in {"adapter_config", "evidence"}}
        scan_public(value, label=name)
    if pack.dataset.id != manifest.get("dataset_id") or pack.dataset.snapshot_id != manifest.get("snapshot_id"):
        raise ExchangeError("Pack manifest identity mismatch")
    return pack
