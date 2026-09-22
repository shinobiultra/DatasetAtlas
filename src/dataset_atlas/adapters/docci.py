"""DOCCI author descriptions joined to the original image archive.

The gzip TAR is verified and extracted once with strict member/byte limits.
Only exact image names in the description release are accepted, and media reads
use a rooted no-follow open plus the extraction manifest's per-image digest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tarfile

from dataset_atlas.storage.local import read_rooted_file

from .core import (
    DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource, SourceDescription,
    StructuredAdapter, _write_rooted_atomic,
)


_IMAGE_NAME = re.compile(r"(?:train|test|qual_dev|qual_test)_[0-9]{5}\.jpg\Z")
_MAX_ARCHIVE_BYTES = 8_000_000_000
_MAX_EXTRACTED_BYTES = 16_000_000_000
_MAX_IMAGE_BYTES = 25_000_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DocciAdapter(StructuredAdapter):
    """One author example per long description and matching original JPEG."""

    def _images_archive(self) -> Path:
        return Path(self.config["images_archive"]).expanduser().resolve()

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        descriptions, images = self._path(), self._images_archive()
        exists = descriptions.is_file() and images.is_file()
        size = descriptions.stat().st_size + images.stat().st_size if exists else None
        return SourceDescription(
            "jsonl", str(descriptions), exists, self.revision,
            size, True, True, True, False, True,
            ("Author JSONL joined by image_file to author gzip TAR; extracted with bounded validation",),
        )

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = DatasetAdapter.plan(self, limit, max_bytes, cursor)
        if not all(re.fullmatch(r"[0-9a-f]{64}", self.config.get(key, ""))
                   for key in ("sha256", "images_sha256")):
            raise ValueError("DOCCI source files require pinned SHA-256 checksums")
        if base.expected_download_bytes is None or base.expected_download_bytes > max_bytes:
            raise ValueError("DOCCI sources exceed approved preparation byte budget")
        if self._images_archive().stat().st_size > _MAX_ARCHIVE_BYTES:
            raise ValueError("DOCCI image archive exceeds explicit 8 GB cap")
        return PreparationPlan(
            self.dataset.id, self.revision, cursor, limit, max_bytes, 0,
            _MAX_EXTRACTED_BYTES,
            ("verify both original files; join every image filename; extract only regular JPEG members",),
            "Extracted JPEG byte total is checked while streaming, with a 16 GB cap",
        )

    def _description_names(self) -> set[str]:
        names: set[str] = set()
        ids: set[str] = set()
        count = 0
        for row in self._rows():
            count += 1
            if not isinstance(row, dict):
                raise ValueError("DOCCI description row is not an object")
            name, example_id, split = row.get("image_file"), row.get("example_id"), row.get("split")
            if not isinstance(name, str) or not _IMAGE_NAME.fullmatch(name):
                raise ValueError("DOCCI description has invalid image_file")
            if example_id != name[:-4] or split != name.rsplit("_", 1)[0]:
                raise ValueError("DOCCI description identity/split differs from image_file")
            if name in names or example_id in ids:
                raise ValueError("duplicate DOCCI image or example ID")
            if not isinstance(row.get("description"), str) or not row["description"]:
                raise ValueError("DOCCI description is missing")
            names.add(name)
            ids.add(example_id)
        expected = self.config.get("expected_records")
        if expected is not None and count != expected:
            raise ValueError("DOCCI description count differs from pinned release")
        return names

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = DatasetAdapter.prepare(self, approved_plan)
        descriptions, archive_path = self._path(), self._images_archive()
        if descriptions.stat().st_size + archive_path.stat().st_size > source.max_bytes:
            raise ValueError("DOCCI sources exceed approved preparation byte budget")
        description_hash, archive_hash = _sha256(descriptions), _sha256(archive_path)
        if description_hash != self.config["sha256"] or archive_hash != self.config["images_sha256"]:
            raise ValueError("DOCCI source checksum differs from pinned release")
        names = self._description_names()
        prepared = self._prepared()
        prepared.mkdir(parents=True, exist_ok=True)
        index_path = prepared / "index.json"
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if (index.get("descriptions_sha256") == description_hash
                    and index.get("images_archive_sha256") == archive_hash
                    and set(index.get("images", {})) == names
                    and index.get("image_count") == len(names)
                    and index.get("extracted_bytes", 0) <= _MAX_EXTRACTED_BYTES):
                self._image_index = index["images"]
                return source
            raise ValueError("DOCCI extracted media index differs from pinned sources")

        image_index: dict[str, dict[str, int | str]] = {}
        total = 0
        with tarfile.open(archive_path, "r|gz") as archive:
            for member in archive:
                if member.name == "images" and member.isdir():
                    continue
                if not member.isreg() or not member.name.startswith("images/"):
                    raise ValueError(f"unexpected DOCCI archive member: {member.name!r}")
                name = member.name[len("images/"):]
                if not _IMAGE_NAME.fullmatch(name) or name not in names:
                    raise ValueError(f"DOCCI archive image not in description release: {member.name!r}")
                if name in image_index:
                    raise ValueError(f"duplicate DOCCI archive image: {name}")
                if member.size < 3 or member.size > _MAX_IMAGE_BYTES:
                    raise ValueError(f"DOCCI image exceeds per-image byte cap: {name}")
                total += member.size
                if total > _MAX_EXTRACTED_BYTES:
                    raise ValueError("DOCCI extraction exceeds 16 GB cap")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"DOCCI image member cannot be read: {name}")
                data = stream.read(member.size + 1)
                if len(data) != member.size or not data.startswith(b"\xff\xd8\xff"):
                    raise ValueError(f"DOCCI image is not an intact JPEG: {name}")
                digest = hashlib.sha256(data).hexdigest()
                _write_rooted_atomic(prepared / "images", name, data)
                image_index[name] = {"sha256": digest, "bytes": member.size}
        if set(image_index) != names:
            missing = sorted(names - set(image_index))
            raise ValueError(f"DOCCI archive lacks {len(missing)} description images: {missing[:3]}")
        index = {
            "descriptions_sha256": description_hash,
            "images_archive_sha256": archive_hash,
            "image_count": len(image_index),
            "extracted_bytes": total,
            "images": image_index,
        }
        staged = index_path.with_suffix(".json.part")
        staged.write_text(json.dumps(index, sort_keys=True), encoding="utf-8")
        staged.replace(index_path)
        self._image_index = image_index
        return source

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        if not _IMAGE_NAME.fullmatch(asset_ref):
            raise ValueError("invalid DOCCI image reference")
        index = getattr(self, "_image_index", None)
        if index is None:
            index = json.loads((self._prepared() / "index.json").read_text(encoding="utf-8"))["images"]
        info = index.get(asset_ref)
        if info is None:
            raise FileNotFoundError("DOCCI image reference is absent from pinned release")
        remaining = source.max_bytes - source.bytes_read
        if info["bytes"] > remaining:
            raise ValueError("DOCCI image exceeds remaining byte budget")
        root = self._prepared() / "images"
        data = read_rooted_file(root / asset_ref, [root], remaining)
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != info["bytes"] or digest != info["sha256"]:
            raise ValueError("DOCCI extracted image differs from pinned archive")
        source.charge(len(data))
        return MediaHandle(data, "image/jpeg", digest, asset_ref)
