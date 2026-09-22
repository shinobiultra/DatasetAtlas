"""Full-release readers for compact image benchmarks with documented binary layouts."""
from __future__ import annotations

import gzip
import hashlib
import io
from pathlib import Path
import re
import struct
import tarfile

from PIL import Image
import numpy as np

from dataset_atlas.models import Asset, Record, stable_id

from .core import (DatasetAdapter, MediaHandle, PreparationPlan, PreparedSource,
                   RecordBatch, SourceDescription, ValidationReport)


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class IDXAdapter(DatasetAdapter):
    """MNIST-family gzip IDX images and labels, with direct row access after preparation."""

    def _root(self) -> Path:
        return Path(self.config["root"]).expanduser().resolve()

    def _label_mapping(self) -> dict[int, tuple[str, int]] | None:
        name = self.config.get("mapping_file")
        if not name:
            return None
        path = self._root() / name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.config.get("mapping_sha256"):
            raise ValueError("IDX label mapping differs from pinned checksum")
        mapping: dict[int, tuple[str, int]] = {}
        for line in data.decode("ascii").splitlines():
            parts = line.split()
            if len(parts) != 2:
                raise ValueError("IDX label mapping requires class and ASCII code")
            label, code = map(int, parts)
            if label in mapping or not 0 <= code <= 127:
                raise ValueError("IDX label mapping has duplicate or invalid class")
            mapping[label] = (chr(code), code)
        if len(mapping) != self.config.get("class_count") or set(mapping) != set(range(len(mapping))):
            raise ValueError("IDX label mapping differs from declared contiguous classes")
        return mapping

    def probe(self) -> SourceDescription:
        root = self._root()
        paths = [root / item[key] for item in self.config["splits"].values()
                 for key in ("images", "labels")]
        missing = [str(p) for p in paths if not p.is_file()]
        size = sum(p.stat().st_size for p in paths if p.is_file())
        return SourceDescription("idx", str(root), not missing, self.revision,
                                 size if not missing else None, True, True, True, False, True,
                                 tuple(f"missing source file: {p}" for p in missing))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        counts = self.config["counts"]
        output = sum(counts[name] * 785 + 24 for name in self.config["splits"])
        if output > max_bytes:
            raise ValueError("IDX prepared output exceeds byte budget")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, output,
                               ("verify source hashes and decompress IDX files into work cache",))

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        self._label_mapping()
        if self.config.get("pixel_transform", "none") not in ("none", "transpose"):
            raise ValueError("unsupported IDX display pixel transform")
        root = self._root(); prepared = root / "prepared"; prepared.mkdir(exist_ok=True)
        for split, files in self.config["splits"].items():
            for key in ("images", "labels"):
                compressed = root / files[key]
                expected = files[f"{key}_md5"]
                if _md5(compressed) != expected:
                    raise ValueError(f"{compressed.name} differs from pinned checksum")
                output = prepared / f"{split}-{key}.idx"
                if not output.is_file():
                    staged = output.with_suffix(".part")
                    try:
                        with gzip.open(compressed, "rb") as input_handle, staged.open("wb") as output_handle:
                            for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                                source.charge(len(chunk))
                                output_handle.write(chunk)
                        staged.replace(output)
                    finally:
                        staged.unlink(missing_ok=True)
            count, rows, cols = self._image_shape(split)
            label_count = self._label_count(split)
            if count != self.config["counts"][split] or label_count != count or (rows, cols) != (28, 28):
                raise ValueError("IDX dimensions or labels disagree with declared source")
        return source

    def _image_shape(self, split: str) -> tuple[int, int, int]:
        with (self._root() / "prepared" / f"{split}-images.idx").open("rb") as handle:
            magic, count, rows, cols = struct.unpack(">IIII", handle.read(16))
        if magic != 2051:
            raise ValueError("invalid IDX image magic")
        return count, rows, cols

    def _label_count(self, split: str) -> int:
        with (self._root() / "prepared" / f"{split}-labels.idx").open("rb") as handle:
            magic, count = struct.unpack(">II", handle.read(8))
        if magic != 2049:
            raise ValueError("invalid IDX label magic")
        return count

    def _location(self, global_index: int) -> tuple[str, int]:
        for split, count in self.config["counts"].items():
            if global_index < count:
                return split, global_index
            global_index -= count
        raise IndexError("IDX cursor beyond release")

    def _pixels_label(self, split: str, index: int) -> tuple[bytes, int]:
        prepared = self._root() / "prepared"
        with (prepared / f"{split}-images.idx").open("rb") as handle:
            handle.seek(16 + index * 784)
            pixels = handle.read(784)
        with (prepared / f"{split}-labels.idx").open("rb") as handle:
            handle.seek(8 + index)
            label = handle.read(1)
        if len(pixels) != 784 or len(label) != 1:
            raise ValueError("truncated IDX row")
        return pixels, label[0]

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        mapping = self._label_mapping()
        total = sum(self.config["counts"].values())
        start = int(cursor or 0)
        if start < 0 or start > total:
            raise ValueError("cursor outside IDX release")
        size = min(limit or source.limit, source.limit, total - start)
        out = []
        for absolute in range(start, start + size):
            split, index = self._location(absolute)
            pixels, label = self._pixels_label(split, index)
            source.charge(len(pixels) + 1)
            key = f"{split}:{index}"
            aid = stable_id(self.dataset.id, self.revision, "asset", key)
            rid = stable_id(self.dataset.id, self.revision, "example", key)
            transform = self.config.get("pixel_transform", "none")
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=f"{split}/{index:06d}.png",
                          representation=("lossless_png_transposed_from_source_pixels" if transform == "transpose"
                                          else "lossless_png_from_source_pixels"),
                          metadata={"source_index": index, "source_split": split,
                                    "source_encoding": "IDX uint8 28x28",
                                    "display_transform": transform})
            fields = {"label": label, "split": split, "index": index}
            if mapping is not None:
                if label not in mapping:
                    raise ValueError(f"IDX row label {label} absent from pinned mapping")
                fields.update({"character": mapping[label][0], "ascii_code": mapping[label][1]})
            out.append(Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                              snapshot_id=self.dataset.snapshot_id,
                              asset_ids=[aid], assets=[asset],
                              source=fields))
        end = start + len(out)
        return RecordBatch(out, str(end) if end < total else None, len(out))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        match = re.fullmatch(r"(train|test)/(\d{6})\.png", asset_ref)
        if not match or match.group(1) not in self.config["splits"]:
            raise ValueError("invalid IDX asset reference")
        split, index = match.group(1), int(match.group(2))
        if index >= self.config["counts"][split]:
            raise ValueError("IDX asset index out of range")
        pixels, _ = self._pixels_label(split, index)
        output = io.BytesIO()
        image = Image.frombytes("L", (28, 28), pixels)
        if self.config.get("pixel_transform") == "transpose":
            image = image.transpose(Image.Transpose.TRANSPOSE)
        image.save(output, format="PNG")
        data = output.getvalue()
        source.charge(len(data))
        return MediaHandle(data, "image/png", hashlib.sha256(data).hexdigest(), asset_ref)


class CIFARBinaryAdapter(DatasetAdapter):
    """CIFAR-10 binary archive. No Python pickle deserialization."""

    BATCH_BYTES = 30_730_000

    def _archive(self) -> Path:
        return Path(self.config["archive"]).expanduser().resolve()

    def _prepared(self) -> Path:
        return Path(self.config["prepared_root"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        archive = self._archive()
        return SourceDescription("cifar_binary", str(archive), archive.is_file(), self.revision,
                                 archive.stat().st_size if archive.is_file() else None,
                                 True, True, True, False, True,
                                 ("extracts six documented binary batch members after archive integrity check",))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = super().plan(limit, max_bytes, cursor)
        output = 6 * self.BATCH_BYTES + 1024
        if output > max_bytes:
            raise ValueError("CIFAR prepared output exceeds byte budget")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, output,
                               ("verify official archive MD5 and extract six binary batches",))

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = super().prepare(approved_plan)
        archive_path = self._archive()
        if _md5(archive_path) != self.config["archive_md5"]:
            raise ValueError("CIFAR archive differs from official checksum")
        root = self._prepared(); root.mkdir(parents=True, exist_ok=True)
        wanted = {f"data_batch_{i}.bin" for i in range(1, 6)} | {"test_batch.bin", "batches.meta.txt"}
        with tarfile.open(archive_path, "r:gz") as archive:
            members = {Path(m.name).name: m for m in archive.getmembers()
                       if m.isfile() and Path(m.name).name in wanted}
            if set(members) != wanted:
                raise ValueError("CIFAR archive lacks required batch members")
            for name, member in members.items():
                expected_size = self.BATCH_BYTES if name.endswith(".bin") else member.size
                if member.size != expected_size or expected_size > source.max_bytes:
                    raise ValueError("invalid CIFAR batch size")
                output = root / name
                if output.is_file():
                    if output.stat().st_size != expected_size:
                        raise ValueError("existing prepared batch has wrong size")
                    continue
                input_handle = archive.extractfile(member)
                if input_handle is None:
                    raise ValueError("missing CIFAR archive member")
                staged = output.with_suffix(output.suffix + ".part")
                try:
                    with staged.open("wb") as handle:
                        while True:
                            chunk = input_handle.read(1024 * 1024)
                            if not chunk:
                                break
                            source.charge(len(chunk))
                            handle.write(chunk)
                    staged.replace(output)
                finally:
                    staged.unlink(missing_ok=True)
        if len([line for line in (root / "batches.meta.txt").read_text().splitlines() if line]) != 10:
            raise ValueError("invalid CIFAR class names")
        return source

    def _row(self, split: str, index: int) -> tuple[bytes, int]:
        if split == "train" and 0 <= index < 50_000:
            file = self._prepared() / f"data_batch_{index // 10_000 + 1}.bin"
            offset = index % 10_000
        elif split == "test" and 0 <= index < 10_000:
            file = self._prepared() / "test_batch.bin"
            offset = index
        else:
            raise ValueError("CIFAR source index out of range")
        with file.open("rb") as handle:
            handle.seek(offset * 3073)
            row = handle.read(3073)
        if len(row) != 3073 or row[0] > 9:
            raise ValueError("invalid CIFAR binary row")
        return row[1:], row[0]

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        start = int(cursor or 0)
        if not 0 <= start <= 60_000:
            raise ValueError("cursor outside CIFAR release")
        size = min(limit or source.limit, source.limit, 60_000 - start)
        classes = [line for line in (self._prepared() / "batches.meta.txt").read_text().splitlines() if line]
        out = []
        for absolute in range(start, start + size):
            split, index = ("train", absolute) if absolute < 50_000 else ("test", absolute - 50_000)
            pixels, label = self._row(split, index)
            source.charge(len(pixels) + 1)
            key = f"{split}:{index}"
            aid = stable_id(self.dataset.id, self.revision, "asset", key)
            rid = stable_id(self.dataset.id, self.revision, "example", key)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=f"{split}/{index:06d}.png",
                          representation="lossless_png_from_source_pixels",
                          metadata={"source_index": index, "source_split": split,
                                    "source_encoding": "CIFAR RGB planar uint8 32x32"})
            out.append(Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                              snapshot_id=self.dataset.snapshot_id,
                              asset_ids=[aid], assets=[asset],
                              source={"label": label, "class_name": classes[label],
                                      "split": split, "index": index}))
        end = start + len(out)
        return RecordBatch(out, str(end) if end < 60_000 else None, len(out))

    def resolve_asset(self, source: PreparedSource, asset_ref: str) -> MediaHandle:
        match = re.fullmatch(r"(train|test)/(\d{6})\.png", asset_ref)
        if not match:
            raise ValueError("invalid CIFAR asset reference")
        pixels, _ = self._row(match.group(1), int(match.group(2)))
        array = np.frombuffer(pixels, dtype=np.uint8).reshape(3, 32, 32).transpose(1, 2, 0)
        output = io.BytesIO()
        Image.fromarray(array, "RGB").save(output, format="PNG")
        data = output.getvalue()
        source.charge(len(data))
        return MediaHandle(data, "image/png", hashlib.sha256(data).hexdigest(), asset_ref)


class CIFAR100BinaryAdapter(CIFARBinaryAdapter):
    """Original CIFAR-100 two-label binary release; no pickle deserialization."""

    TRAIN_COUNT = 50_000
    TEST_COUNT = 10_000
    ROW_BYTES = 3074

    def probe(self) -> SourceDescription:
        archive = self._archive()
        return SourceDescription("cifar100_binary", str(archive), archive.is_file(),
                                 self.revision, archive.stat().st_size if archive.is_file() else None,
                                 True, True, True, False, True,
                                 ("extracts train/test two-label binary members after official MD5 check",))

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = DatasetAdapter.plan(self, limit, max_bytes, cursor)
        output = (self.TRAIN_COUNT + self.TEST_COUNT) * self.ROW_BYTES + 20_000
        if output > max_bytes:
            raise ValueError("CIFAR-100 prepared output exceeds byte budget")
        return PreparationPlan(base.dataset_id, base.source_revision, cursor, limit,
                               max_bytes, 0, output,
                               ("verify official archive MD5 and extract two binary batches",))

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        source = DatasetAdapter.prepare(self, approved_plan)
        if _md5(self._archive()) != self.config["archive_md5"]:
            raise ValueError("CIFAR-100 archive differs from official checksum")
        root = self._prepared(); root.mkdir(parents=True, exist_ok=True)
        wanted = {"train.bin", "test.bin", "fine_label_names.txt", "coarse_label_names.txt"}
        with tarfile.open(self._archive(), "r:gz") as archive:
            members = {Path(m.name).name: m for m in archive.getmembers()
                       if m.isfile() and Path(m.name).name in wanted}
            if set(members) != wanted:
                raise ValueError("CIFAR-100 archive lacks required binary or label members")
            for name, member in members.items():
                expected = (self.TRAIN_COUNT if name == "train.bin" else self.TEST_COUNT) * self.ROW_BYTES \
                    if name.endswith(".bin") else member.size
                if member.size != expected or expected > source.max_bytes:
                    raise ValueError("invalid CIFAR-100 member size")
                output = root / name
                if output.is_file():
                    if output.stat().st_size != expected:
                        raise ValueError("existing prepared CIFAR-100 member has wrong size")
                    continue
                input_handle = archive.extractfile(member)
                if input_handle is None:
                    raise ValueError("missing CIFAR-100 archive member")
                staged = output.with_suffix(output.suffix + ".part")
                try:
                    with staged.open("wb") as handle:
                        while True:
                            chunk = input_handle.read(1024 * 1024)
                            if not chunk:
                                break
                            source.charge(len(chunk))
                            handle.write(chunk)
                    staged.replace(output)
                finally:
                    staged.unlink(missing_ok=True)
        if len(self._names("fine")) != 100 or len(self._names("coarse")) != 20:
            raise ValueError("invalid CIFAR-100 class name lists")
        return source

    def _names(self, kind: str) -> list[str]:
        return [line for line in (self._prepared() / f"{kind}_label_names.txt").read_text().splitlines() if line]

    def _row_labels(self, split: str, index: int) -> tuple[bytes, int, int]:
        count = self.TRAIN_COUNT if split == "train" else self.TEST_COUNT if split == "test" else 0
        if not 0 <= index < count:
            raise ValueError("CIFAR-100 source index out of range")
        with (self._prepared() / f"{split}.bin").open("rb") as handle:
            handle.seek(index * self.ROW_BYTES)
            row = handle.read(self.ROW_BYTES)
        if len(row) != self.ROW_BYTES or row[0] > 19 or row[1] > 99:
            raise ValueError("invalid CIFAR-100 binary row")
        return row[2:], row[0], row[1]

    def _row(self, split: str, index: int) -> tuple[bytes, int]:
        pixels, _, fine = self._row_labels(split, index)
        return pixels, fine

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        total = self.TRAIN_COUNT + self.TEST_COUNT
        start = int(cursor or 0)
        if not 0 <= start <= total:
            raise ValueError("cursor outside CIFAR-100 release")
        size = min(limit or source.limit, source.limit, total - start)
        fine_names, coarse_names = self._names("fine"), self._names("coarse")
        out = []
        for absolute in range(start, start + size):
            split, index = ("train", absolute) if absolute < self.TRAIN_COUNT else ("test", absolute - self.TRAIN_COUNT)
            pixels, coarse, fine = self._row_labels(split, index)
            source.charge(len(pixels) + 2)
            key = f"{split}:{index}"
            aid = stable_id(self.dataset.id, self.revision, "asset", key)
            rid = stable_id(self.dataset.id, self.revision, "example", key)
            asset = Asset(id=aid, dataset_id=self.dataset.id, release_id=self.revision,
                          modality="image", uri=f"{split}/{index:06d}.png",
                          representation="lossless_png_from_source_pixels",
                          metadata={"source_index": index, "source_split": split,
                                    "source_encoding": "CIFAR RGB planar uint8 32x32"})
            out.append(Record(id=rid, dataset_id=self.dataset.id, release_id=self.revision,
                              snapshot_id=self.dataset.snapshot_id,
                              asset_ids=[aid], assets=[asset],
                              source={"coarse_label": coarse, "coarse_class_name": coarse_names[coarse],
                                      "fine_label": fine, "fine_class_name": fine_names[fine],
                                      "split": split, "index": index}))
        end = start + len(out)
        return RecordBatch(out, str(end) if end < total else None, len(out))
