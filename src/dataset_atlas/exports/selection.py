"""Bounded portable selection exports with stable record identities."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from dataset_atlas.models import Record, Selection

from .security import MAX_EXCHANGE_BYTES, ExchangeError, compact_json, contained_file, digest, read_json, safe_member, scan_public, validate_image

_FILES = ("selection.json", "records.json")


def _check_identity(selection: Selection, records: Sequence[Record]) -> None:
    if not selection.ids or len(selection.ids) != len(set(selection.ids)):
        raise ExchangeError("Selection IDs must be nonempty and unique")
    if not selection.snapshot_ids or not selection.dataset_ids:
        raise ExchangeError("Selection needs dataset and snapshot identities")
    if len(records) != len(selection.ids):
        raise ExchangeError("Export must include exactly the selected records")
    by_id = {record.id: record for record in records}
    if len(by_id) != len(records) or set(by_id) != set(selection.ids):
        raise ExchangeError("Record IDs do not match the selection")
    for record in records:
        if record.unit != selection.unit or record.dataset_id not in selection.dataset_ids or record.snapshot_id not in selection.snapshot_ids:
            raise ExchangeError(f"Record identity does not match selection: {record.id}")
        for asset in record.assets:
            if asset.dataset_id != record.dataset_id or asset.release_id != record.release_id:
                raise ExchangeError(f"Asset identity does not match selected record: {asset.id}")


def selection_export_payload(selection: Selection, records: Sequence[Record]) -> dict:
    """Return a JSON-compatible API payload with records and their provenance."""
    _check_identity(selection, records)
    ordered = {record.id: record for record in records}
    public_records = []
    for record_id in selection.ids:
        value = ordered[record_id].model_dump(mode="json")
        value["human"] = {}
        value["annotations"] = [item for item in value["annotations"] if item["namespace"] != "human"]
        for asset in value["assets"]:
            asset["uri"] = None
            asset["metadata"] = {}
        public_records.append(value)
    payload = {
        "schema_version": "1.0",
        "selection": selection.model_dump(mode="json"),
        "records": public_records,
    }
    scan_public(payload, label="selection export")
    return payload


def export_selection(selection: Selection, records: Sequence[Record], output_dir: Path, *, media_root: Path | None = None, approved_media_ids: set[str] | None = None, max_bytes: int = MAX_EXCHANGE_BYTES) -> Path:
    """Write a portable JSON directory atomically. Existing exports are never overwritten."""
    output_dir = Path(output_dir)
    payload = selection_export_payload(selection, records)
    approved = approved_media_ids or set()
    if approved and media_root is None:
        raise ExchangeError("Approved media requires an explicit media root")
    media: dict[str, bytes] = {}
    found: set[str] = set()
    if approved:
        by_id = {record.id: record for record in records}
        for value in payload["records"]:
            original = by_id[value["id"]]
            originals = {asset.id: asset for asset in original.assets}
            for asset in value["assets"]:
                if asset["id"] not in approved:
                    continue
                source = originals[asset["id"]]
                if not source.uri:
                    raise ExchangeError(f"Approved media has no source: {asset['id']}")
                if media_root is None:
                    raise ValueError('Media export requires a configured media root')
                file = contained_file(Path(media_root), source.uri)
                if file.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"} or file.stat().st_size > 10_000_000:
                    raise ExchangeError(f"Approved media type or size is unsupported: {asset['id']}")
                data = file.read_bytes()
                if source.sha256 and digest(data) != source.sha256:
                    raise ExchangeError(f"Approved original media checksum changed: {asset['id']}")
                validate_image(data, file.suffix.lower())
                member = f"media/{digest(data)}{file.suffix.lower()}"
                media[member] = data
                asset["uri"] = member
                asset["sha256"] = digest(data)
                found.add(asset["id"])
        if found != approved:
            raise ExchangeError("Approved media IDs must match selected assets")
    contents = {
        "selection.json": compact_json(payload["selection"]),
        "records.json": compact_json(payload["records"]),
        **media,
    }
    manifest = {"schema_version": "1.0", "kind": "selection", "checksums": {name: digest(data) for name, data in contents.items()}, "files": [*_FILES, *sorted(media)]}
    contents["manifest.json"] = compact_json(manifest)
    if sum(map(len, contents.values())) > max_bytes:
        raise ExchangeError("Selection export exceeds size limit")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise ExchangeError(f"Export destination exists: {output_dir}")
    with tempfile.TemporaryDirectory(prefix=".atlas-export-", dir=output_dir.parent) as temp:
        stage = Path(temp) / "artifact"
        stage.mkdir()
        for name, data in contents.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        os.replace(stage, output_dir)
    return output_dir


def import_selection(path: Path, *, max_bytes: int = MAX_EXCHANGE_BYTES) -> tuple[Selection, list[Record]]:
    """Validate a non-executable selection export before returning any data."""
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ExchangeError("Selection import requires a directory")
    manifest = read_json(path / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or manifest.get("kind") != "selection":
        raise ExchangeError("Unsupported selection manifest")
    members = manifest.get("files")
    checksums = manifest.get("checksums")
    if not isinstance(members, list) or any(not isinstance(name, str) for name in members) or not isinstance(checksums, dict) or members[:2] != list(_FILES) or len(members) != len(set(members)) or set(checksums) != set(members):
        raise ExchangeError("Selection manifest has unexpected files")
    for name in members[2:]:
        safe_member(name)
        if not name.startswith("media/") or Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            raise ExchangeError("Selection manifest has unsafe media member")
    present = {item.relative_to(path).as_posix() for item in path.rglob("*") if item.is_file() or item.is_symlink()}
    if present != {*members, "manifest.json"}:
        raise ExchangeError("Selection export contains unexpected files")
    total = (path / "manifest.json").stat().st_size
    for name in members:
        target = contained_file(path, name)
        total += target.stat().st_size
    if total > max_bytes:
        raise ExchangeError("Selection import exceeds size limit")
    for name in members:
        if digest((path / name).read_bytes()) != manifest["checksums"][name]:
            raise ExchangeError(f"Checksum mismatch: {name}")
    try:
        selection = Selection.model_validate(read_json(path / "selection.json", limit=max_bytes))
        record_values = read_json(path / "records.json", limit=max_bytes)
        if not isinstance(record_values, list):
            raise ExchangeError("Records must be an array")
        records = [Record.model_validate(item) for item in record_values]
    except ValidationError as exc:
        raise ExchangeError("Invalid selection or record schema") from exc
    _check_identity(selection, records)
    payload = {"selection": selection.model_dump(mode="json"), "records": [record.model_dump(mode="json") for record in records]}
    scan_public(payload, label="selection import")
    referenced_media = {asset.uri for record in records for asset in record.assets if asset.uri}
    if referenced_media != set(members[2:]):
        raise ExchangeError("Media references do not match selection manifest")
    for record in records:
        for asset in record.assets:
            if asset.uri and (not asset.sha256 or digest(contained_file(path, asset.uri).read_bytes()) != asset.sha256):
                raise ExchangeError(f"Included original media checksum differs from asset: {asset.id}")
    return selection, records
