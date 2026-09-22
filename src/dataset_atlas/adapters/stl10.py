"""Bounded full-release reader for Stanford's original STL-10 binary archive.

The source tarball remains unchanged. Only documented members are streamed into
a local prepared cache after whole-archive and member integrity verification.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import re
import tarfile

import numpy as np
from PIL import Image

from dataset_atlas.models import Asset, Record, stable_id
from .core import DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource, RecordBatch, SourceDescription


class STL10BinaryAdapter(DatasetAdapter):
    IMAGE_BYTES = 3 * 96 * 96
    COUNTS = {"train": 5000, "test": 8000, "unlabeled": 100000}
    MEMBER_SIZES = {
        "train_X.bin": COUNTS["train"] * IMAGE_BYTES,
        "train_y.bin": COUNTS["train"],
        "test_X.bin": COUNTS["test"] * IMAGE_BYTES,
        "test_y.bin": COUNTS["test"],
        "unlabeled_X.bin": COUNTS["unlabeled"] * IMAGE_BYTES,
    }
    # Official member MD5 values are also published in torchvision's STL10 reader.
    MEMBER_MD5 = {
        "train_X.bin": "918c2871b30a85fa023e0c44e0bee87f",
        "train_y.bin": "5a34089d4802c674881badbb80307741",
        "test_X.bin": "7f263ba9f9e0b06b93213547f721ac82",
        "test_y.bin": "36f9794fa4beb8a2c72628de14fa638e",
        "unlabeled_X.bin": "5242ba1fed5e4be9e1e742405eb56ca4",
    }
    EXTRA_MEMBERS = {"class_names.txt", "fold_indices.txt"}

    def _root(self) -> Path:
        return Path(self.config["root"]).expanduser().resolve()

    def _archive(self) -> Path:
        return self._root() / "stl10_binary.tar.gz"

    def _prepared(self) -> Path:
        return self._root() / "prepared"

    def probe(self) -> SourceDescription:
        archive = self._archive()
        exists = archive.is_file()
        return SourceDescription(
            "stl10_binary", str(archive), exists, self.revision,
            archive.stat().st_size if exists else None,
            True, True, True, False, True,
            ("Original STL-10 binary train/test/unlabeled splits; ten source training folds",),
        )

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        expected = sum(self.MEMBER_SIZES.values()) + 2_000_000
        if max_bytes < expected:
            raise ValueError(f"STL-10 preparation requires at least {expected} output bytes")
        if base.expected_download_bytes is None or base.expected_download_bytes > 3_000_000_000:
            raise ValueError("STL-10 source archive exceeds 3 GB download bound")
        if not self.config.get("archive_sha256") or not self.config.get("archive_md5"):
            raise ValueError("STL-10 requires pinned archive SHA-256 and official MD5")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit, max_bytes,
                               0, expected,
                               ("Verify pinned original archive and official member hashes; extract documented binary members into local cache",))

    @staticmethod
    def _digest(path: Path, kind: str) -> str:
        h = hashlib.new(kind)
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _valid_prepared(self) -> bool:
        prepared = self._prepared()
        return all((prepared / name).is_file() and (prepared / name).stat().st_size == self.MEMBER_SIZES[name]
                   and self._digest(prepared / name, "md5") == self.MEMBER_MD5[name]
                   for name in self.MEMBER_SIZES) and all((prepared / name).is_file() for name in self.EXTRA_MEMBERS)

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        archive = self._archive()
        if archive.stat().st_size > 3_000_000_000:
            raise ValueError("STL-10 source archive exceeds 3 GB download bound")
        if self._digest(archive, "sha256") != self.config["archive_sha256"] or self._digest(archive, "md5") != self.config["archive_md5"]:
            raise ValueError("STL-10 archive checksum differs from pinned original")
        if not self._valid_prepared():
            prepared = self._prepared()
            prepared.mkdir(parents=True, exist_ok=True)
            wanted = set(self.MEMBER_SIZES) | self.EXTRA_MEMBERS
            found: set[str] = set()
            staged: list[Path] = []
            try:
                with tarfile.open(archive, "r:gz") as bundle:
                    for member in bundle:
                        parts = Path(member.name).parts
                        if member.issym() or member.islnk() or (parts and parts[0] != "stl10_binary") or ".." in parts:
                            raise ValueError("Unsafe STL-10 archive member")
                        if not member.isfile() or len(parts) != 2 or parts[1] not in wanted:
                            continue
                        name = parts[1]
                        if name in found:
                            raise ValueError(f"Duplicate STL-10 archive member: {name}")
                        found.add(name)
                        expected = self.MEMBER_SIZES.get(name)
                        if expected is not None and member.size != expected:
                            raise ValueError(f"STL-10 {name} has unexpected byte count")
                        if expected is None and member.size > 1_000_000:
                            raise ValueError(f"STL-10 {name} exceeds text member bound")
                        input_stream = bundle.extractfile(member)
                        if input_stream is None:
                            raise ValueError(f"STL-10 archive member is unreadable: {name}")
                        target = prepared / (name + ".part")
                        staged.append(target)
                        md5 = hashlib.md5(usedforsecurity=False)
                        written = 0
                        with target.open("wb") as output:
                            while chunk := input_stream.read(4 << 20):
                                source.charge(len(chunk))
                                output.write(chunk)
                                md5.update(chunk)
                                written += len(chunk)
                        if written != member.size:
                            raise ValueError(f"Truncated STL-10 archive member: {name}")
                        if name in self.MEMBER_MD5 and md5.hexdigest() != self.MEMBER_MD5[name]:
                            raise ValueError(f"STL-10 {name} differs from official member MD5")
                if found != wanted:
                    raise ValueError(f"STL-10 archive missing members: {sorted(wanted - found)}")
                for name in sorted(wanted):
                    (prepared / (name + ".part")).replace(prepared / name)
            finally:
                for path in staged:
                    path.unlink(missing_ok=True)
        self._validate_metadata()
        return source

    def _validate_metadata(self) -> None:
        root = self._prepared()
        names = (root / "class_names.txt").read_text(encoding="utf-8").splitlines()
        if len(names) != 10 or len(set(names)) != 10 or any(not name for name in names):
            raise ValueError("STL-10 class names must contain ten distinct names")
        for split in ("train", "test"):
            labels = (root / f"{split}_y.bin").read_bytes()
            if len(labels) != self.COUNTS[split] or any(label < 1 or label > 10 for label in labels):
                raise ValueError(f"Invalid STL-10 {split} labels")
        folds = self._folds()
        expected_fold_size = min(1000, self.COUNTS["train"])
        if len(folds) != 10 or any(len(fold) != expected_fold_size or len(set(fold)) != expected_fold_size
                                    or any(index < 0 or index >= self.COUNTS["train"] for index in fold)
                                    for fold in folds):
            raise ValueError("STL-10 training folds are invalid")

    def _folds(self) -> list[list[int]]:
        path = self._prepared() / "fold_indices.txt"
        return [[int(value) for value in line.split()] for line in path.read_text(encoding="utf-8").splitlines()]

    def _locate(self, absolute: int) -> tuple[str, int]:
        for split, count in self.COUNTS.items():
            if absolute < count:
                return split, absolute
            absolute -= count
        raise IndexError("STL-10 cursor beyond release")

    def _record(self, split: str, index: int, label: int | None, names: list[str],
                fold_memberships: list[list[int]]) -> Record:
        key = f"{split}:{index}"
        aid = stable_id(self.dataset.id, self.revision, "asset", key)
        rid = stable_id(self.dataset.id, self.revision, "example", key)
        asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                      modality="image", uri=f"{split}/{index:06d}.png",
                      representation="lossless_png_from_original_stl10_pixels",
                      metadata={"source_split": split, "source_index": index,
                                "source_encoding": "uint8 RGB 96x96, channel-major with transposed spatial axes"})
        return Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                      snapshot_id=self.dataset.snapshot_id, asset_ids=[aid], assets=[asset],
                      source={"split": split, "index": index, "label": label,
                              "class_name": names[label - 1] if label is not None else None,
                              "label_status": "source_labeled" if label is not None else "unlabeled_by_source",
                              "fold_memberships": fold_memberships[index] if split == "train" else []})

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        total = sum(self.COUNTS.values())
        try:
            start = int(cursor or 0)
        except ValueError as exc:
            raise ValueError("Invalid STL-10 cursor") from exc
        if not 0 <= start <= total:
            raise ValueError("STL-10 cursor outside release")
        size = min(limit or source.limit, source.limit, total - start)
        if size < 0:
            raise ValueError("Invalid STL-10 batch size")
        root = self._prepared()
        names = (root / "class_names.txt").read_text(encoding="utf-8").splitlines()
        folds = self._folds()
        fold_memberships: list[list[int]] = [[] for _ in range(self.COUNTS["train"])]
        for number, fold in enumerate(folds):
            for index in fold:
                fold_memberships[index].append(number)
        labels = {split: (root / f"{split}_y.bin").read_bytes() for split in ("train", "test")}
        records = []
        for absolute in range(start, start + size):
            split, index = self._locate(absolute)
            source.charge(self.IMAGE_BYTES + (1 if split != "unlabeled" else 0))
            label = labels[split][index] if split != "unlabeled" else None
            records.append(self._record(split, index, label, names, fold_memberships))
        end = start + len(records)
        return RecordBatch(records, str(end) if end < total else None, len(records))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        match = re.fullmatch(r"(train|test|unlabeled)/(\d{6})\.png", asset_ref)
        if not match:
            raise ValueError("Invalid STL-10 asset reference")
        split, index = match.group(1), int(match.group(2))
        if index >= self.COUNTS[split]:
            raise ValueError("STL-10 asset index outside split")
        with (self._prepared() / f"{split}_X.bin").open("rb") as stream:
            stream.seek(index * self.IMAGE_BYTES)
            pixels = stream.read(self.IMAGE_BYTES)
        if len(pixels) != self.IMAGE_BYTES:
            raise ValueError("Truncated STL-10 source image")
        # The official files store each channel as a transposed 96x96 plane.
        image = np.frombuffer(pixels, dtype=np.uint8).reshape(3, 96, 96).transpose(2, 1, 0)
        output = io.BytesIO()
        Image.fromarray(image, mode="RGB").save(output, format="PNG")
        data = output.getvalue()
        source.charge(len(pixels) + len(data))
        return MediaHandle(data, "image/png", hashlib.sha256(data).hexdigest(), asset_ref)
