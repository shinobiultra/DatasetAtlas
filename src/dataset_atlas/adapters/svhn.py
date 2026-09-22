"""Pinned, bounded reader for Stanford's cropped SVHN digit MAT files.

The original train/test MAT files stay unchanged. Preparation verifies both
source files and stages row-major RGB pixels plus raw labels for indexed reads.
The source's label 10 means the digit 0; both values remain explicit.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image

from dataset_atlas.models import Asset, Record, stable_id
from .core import DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource, RecordBatch, SourceDescription


class SVHNAdapter(DatasetAdapter):
    COUNTS = {"train": 73_257, "test": 26_032}
    SOURCE_BYTES = {"train": 182_040_794, "test": 64_275_384}
    SOURCE_MD5 = {"train": "e26dedcc434d2e4c54c9b2d4a06d8373",
                  "test": "eb5a983be6a315427106f1b164d9cef3"}
    PIXEL_BYTES = 32 * 32 * 3
    MAX_SOURCE_BYTES = 250_000_000

    def _root(self) -> Path:
        return Path(self.config["root"]).expanduser().resolve()

    def _source(self, split: str) -> Path:
        return self._root() / f"{split}_32x32.mat"

    def _prepared(self) -> Path:
        return self._root() / "prepared"

    def probe(self) -> SourceDescription:
        paths = [self._source(split) for split in self.COUNTS]
        exists = all(path.is_file() for path in paths)
        size = sum(path.stat().st_size for path in paths) if exists else None
        return SourceDescription("svhn_cropped_mat", str(self._root()), exists,
                                 self.revision, size, False, True, True, True, True,
                                 ("Official Stanford cropped 32x32 train and test MAT files; extra split excluded",
                                  "SciPy is needed only to prepare verified MAT files"))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        compressed = sum(self.SOURCE_BYTES.values())
        prepared = sum(count * (self.PIXEL_BYTES + 1) for count in self.COUNTS.values())
        # Leave room for one complete pass over labels and requested media.
        # The latter is an upper budget, not a claim about PNG size.
        required = compressed + prepared + sum(self.COUNTS.values()) + limit * 10_000
        if max_bytes < required:
            raise ValueError(f"SVHN preparation needs at least {required} bytes for verified source and pixels")
        for split in self.COUNTS:
            if self._source(split).stat().st_size != self.SOURCE_BYTES[split]:
                raise ValueError(f"SVHN {split} source has unexpected size")
        if not all(self.config.get("sha256", {}).get(split) for split in self.COUNTS):
            raise ValueError("SVHN requires pinned SHA-256 values for both official MAT files")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit, max_bytes,
                               compressed, prepared,
                               ("Verify official MD5 and pinned SHA-256 for both files",
                                "Stage original RGB pixels and raw 1..10 labels; map 10 to digit 0"))

    @staticmethod
    def _digests(path: Path, source: PreparedSource) -> tuple[str, str]:
        md5 = hashlib.md5(usedforsecurity=False)
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(4 << 20):
                source.charge(len(chunk))
                md5.update(chunk)
                sha.update(chunk)
        return md5.hexdigest(), sha.hexdigest()

    def _cache_matches(self, source_hashes: dict[str, str]) -> bool:
        root = self._prepared()
        manifest = root / "manifest.json"
        try:
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            if saved.get("source_sha256") != source_hashes or saved.get("release") != self.revision:
                return False
            for split, count in self.COUNTS.items():
                for suffix, expected in (("pixels", count * self.PIXEL_BYTES), ("labels", count)):
                    path = root / f"{split}.{suffix}.bin"
                    if path.stat().st_size != expected:
                        return False
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        while chunk := stream.read(4 << 20):
                            digest.update(chunk)
                    if digest.hexdigest() != saved.get("prepared_sha256", {}).get(f"{split}.{suffix}"):
                        return False
            return True
        except (FileNotFoundError, OSError, ValueError, KeyError):
            return False

    @staticmethod
    def _load_mat(path: Path, count: int):
        try:
            from scipy.io import loadmat
        except ImportError as exc:
            raise RuntimeError("SVHN MAT preparation needs scipy; install the projection optional dependencies or scipy") from exc
        data = loadmat(path, variable_names=["X", "y"], verify_compressed_data_integrity=True)
        x, labels = data.get("X"), data.get("y")
        if x is None or labels is None or x.shape != (32, 32, 3, count) or str(x.dtype) != "uint8":
            raise ValueError("SVHN MAT X has unexpected shape or dtype")
        if labels.size != count or str(labels.dtype) != "uint8":
            raise ValueError("SVHN MAT y has unexpected shape or dtype")
        flat = labels.reshape(-1)
        if not bool(((flat >= 1) & (flat <= 10)).all()):
            raise ValueError("SVHN raw labels must be 1..10")
        return x, flat

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        source_hashes = {}
        for split in self.COUNTS:
            path = self._source(split)
            if path.stat().st_size != self.SOURCE_BYTES[split] or path.stat().st_size > self.MAX_SOURCE_BYTES:
                raise ValueError(f"SVHN {split} source exceeds expected size")
            md5, sha = self._digests(path, source)
            if md5 != self.SOURCE_MD5[split] or sha != self.config["sha256"][split]:
                raise ValueError(f"SVHN {split} differs from official MD5 or pinned SHA-256")
            source_hashes[split] = sha
        if self._cache_matches(source_hashes):
            return source
        prepared = self._prepared()
        prepared.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[Path, Path]] = []
        prepared_hashes: dict[str, str] = {}
        try:
            for split, count in self.COUNTS.items():
                x, labels = self._load_mat(self._source(split), count)
                for suffix in ("pixels", "labels"):
                    target = prepared / f"{split}.{suffix}.bin"
                    staged.append((target.with_name(target.name + ".part"), target))
                pixel_part, label_part = staged[-2][0], staged[-1][0]
                pixel_sha = hashlib.sha256()
                with pixel_part.open("wb") as out:
                    for start in range(0, count, 1024):
                        end = min(start + 1024, count)
                        pixels = x[:, :, :, start:end].transpose(3, 0, 1, 2).copy(order="C")
                        chunk = pixels.tobytes(order="C")
                        source.charge(len(chunk))
                        out.write(chunk)
                        pixel_sha.update(chunk)
                raw_labels = labels.tobytes(order="C")
                source.charge(len(raw_labels))
                label_part.write_bytes(raw_labels)
                prepared_hashes[f"{split}.pixels"] = pixel_sha.hexdigest()
                prepared_hashes[f"{split}.labels"] = hashlib.sha256(raw_labels).hexdigest()
                if pixel_part.stat().st_size != count * self.PIXEL_BYTES or label_part.stat().st_size != count:
                    raise ValueError(f"SVHN {split} prepared output has unexpected size")
                del x, labels
            for part, target in staged:
                os.replace(part, target)
            manifest = {"release": self.revision, "source_sha256": source_hashes,
                        "prepared_sha256": prepared_hashes,
                        "splits": self.COUNTS, "pixel_encoding": "uint8_rgb_32x32_row_major",
                        "raw_label_10_meaning": "digit_0"}
            fd, temp_name = tempfile.mkstemp(dir=prepared, prefix="manifest.")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(manifest, handle, indent=2)
                    handle.write("\n")
                os.replace(temp_name, prepared / "manifest.json")
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        finally:
            for part, _ in staged:
                part.unlink(missing_ok=True)
        return source

    def _locate(self, absolute: int) -> tuple[str, int]:
        for split, count in self.COUNTS.items():
            if absolute < count:
                return split, absolute
            absolute -= count
        raise ValueError("SVHN cursor outside release")

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        total = sum(self.COUNTS.values())
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("Invalid SVHN cursor") from exc
        if not 0 <= start <= total:
            raise ValueError("SVHN cursor outside release")
        size = min(limit or source.limit, source.limit, total - start)
        if size < 0:
            raise ValueError("Invalid SVHN batch size")
        records: list[Record] = []
        labels: dict[str, bytes] = {}
        for split, count in self.COUNTS.items():
            overlap_start = max(start, 0 if split == "train" else self.COUNTS["train"])
            overlap_end = min(start + size, self.COUNTS["train"] if split == "train" else total)
            if overlap_start >= overlap_end:
                continue
            first = overlap_start if split == "train" else overlap_start - self.COUNTS["train"]
            span = overlap_end - overlap_start
            with (self._prepared() / f"{split}.labels.bin").open("rb") as stream:
                stream.seek(first)
                labels[split] = stream.read(span)
            source.charge(len(labels[split]))
            if len(labels[split]) != span:
                raise ValueError("SVHN prepared raw label array is truncated")
        for absolute in range(start, start + size):
            split, index = self._locate(absolute)
            first = start if split == "train" else max(start, self.COUNTS["train"])
            raw_label = labels[split][absolute - first]
            if not 1 <= raw_label <= 10:
                raise ValueError("SVHN prepared raw label missing or invalid")
            source_key = f"{split}:{index}"
            aid = stable_id(self.dataset.id, self.revision, "asset", source_key)
            rid = stable_id(self.dataset.id, self.revision, "example", source_key)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=f"{split}/{index:06d}.png",
                          representation="lossless_png_from_original_svhn_cropped_pixels",
                          metadata={"source_split": split, "source_index": index,
                                    "source_encoding": "MAT v5 X uint8 32x32x3xN"})
            records.append(Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                                  snapshot_id=self.dataset.snapshot_id, unit="example",
                                  asset_ids=[aid], assets=[asset],
                                  source={"split": split, "index": index,
                                          "raw_label": raw_label, "digit": 0 if raw_label == 10 else raw_label}))
        end = start + len(records)
        return RecordBatch(records, str(end) if end < total else None, len(records))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        match = re.fullmatch(r"(train|test)/(\d{6})\.png", asset_ref)
        if not match:
            raise ValueError("Invalid SVHN asset reference")
        split, number = match.groups()
        index = int(number)
        if index >= self.COUNTS[split]:
            raise ValueError("SVHN asset index outside release")
        with (self._prepared() / f"{split}.pixels.bin").open("rb") as stream:
            stream.seek(index * self.PIXEL_BYTES)
            pixels = stream.read(self.PIXEL_BYTES)
        source.charge(len(pixels))
        if len(pixels) != self.PIXEL_BYTES:
            raise ValueError("SVHN prepared image is truncated")
        image = Image.frombytes("RGB", (32, 32), pixels)
        output = io.BytesIO()
        image.save(output, format="PNG")
        content = output.getvalue()
        source.charge(len(content))
        return MediaHandle(content, "image/png", hashlib.sha256(content).hexdigest(),
                           f"{split}_32x32.mat:X:{index}")
