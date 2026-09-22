"""Pinned VHD11K annotation rows with bounded, read-only ZIP media access."""
from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

from dataset_atlas.models import Asset, Record, stable_id

from .core import MediaHandle, PreparedSource, StructuredAdapter, _media_type


def _source_member_name(value: str) -> str:
    """Undo the release ZIP's UTF-8 bytes decoded as CP437 for 18 video names."""
    name = PurePosixPath(value).name
    try:
        return name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


class VHD11KAdapter(StructuredAdapter):
    """Read all 11,000 source annotations; fetch individual image/video bytes from local ZIPs."""

    def _record(self, row: dict[str, Any], ordinal: int) -> Record:
        modality = row.get("modality")
        ref = row.get("media_ref")
        source_id = row.get("source_id")
        if modality not in {"image", "video"} or not isinstance(ref, str) or not source_id:
            raise ValueError("invalid VHD11K source row")
        prefix = f"{modality}s/"
        if not ref.startswith(prefix) or len(PurePosixPath(ref).parts) != 2:
            raise ValueError("invalid VHD11K media reference")
        record_id = stable_id(self.dataset.id, self.revision, "example", str(source_id))
        asset_id = stable_id(self.dataset.id, self.revision, "asset", ref)
        asset = Asset(id=asset_id, dataset_id=self.dataset.id, release_id=self.revision,
                      modality=modality, uri=ref,
                      metadata={"source_field": "imagePath" if modality == "image" else "videoPath",
                                "source_ref": ref})
        return Record(id=record_id, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, unit="example",
                      asset_ids=[asset_id], assets=[asset], source=dict(row))

    def _known_refs(self) -> set[str]:
        cached = getattr(self, "_refs", None)
        if cached is not None:
            return cached
        refs = {str(row["media_ref"]) for row in self._rows()}
        self._refs = refs
        return refs

    def _archive(self, modality: str) -> tuple[Path, str]:
        path = Path(self.config[f"{modality}s_archive"]).expanduser().resolve()
        expected = self.config[f"{modality}s_sha256"]
        if not path.is_file():
            raise FileNotFoundError(path)
        verified = getattr(self, "_verified_archives", set())
        if modality not in verified:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(4 << 20), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"VHD11K {modality} archive checksum mismatch")
            verified.add(modality)
            self._verified_archives = verified
        return path, expected

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if asset_ref not in self._known_refs():
            raise ValueError("asset is not referenced by the pinned VHD11K annotations")
        parts = PurePosixPath(asset_ref).parts
        if len(parts) != 2 or parts[0] not in {"images", "videos"} or parts[1] in {"", ".", ".."}:
            raise ValueError("invalid VHD11K asset reference")
        modality = "image" if parts[0] == "images" else "video"
        archive_path, _ = self._archive(modality)
        member_name = parts[1]
        with zipfile.ZipFile(archive_path) as archive:
            matches = [info for info in archive.infolist()
                       if not info.is_dir() and _source_member_name(info.filename) == member_name]
            if len(matches) != 1:
                raise ValueError("VHD11K archive member is missing or ambiguous")
            info = matches[0]
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("VHD11K archive member cannot be a symlink")
            if info.file_size > source.max_bytes - source.bytes_read:
                raise ValueError("VHD11K asset exceeds remaining byte budget")
            with archive.open(info) as handle:
                data = handle.read(source.max_bytes - source.bytes_read + 1)
            source.charge(len(data))
            if len(data) != info.file_size:
                raise ValueError("VHD11K archive member has unexpected size")
        return MediaHandle(data, _media_type(member_name), hashlib.sha256(data).hexdigest(), asset_ref)
