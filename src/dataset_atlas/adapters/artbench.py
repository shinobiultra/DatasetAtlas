"""ArtBench-10 32px CIFAR binary with the author's exact CSV index join."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import tarfile

from .binary import CIFARBinaryAdapter
from .core import DatasetAdapter, PreparationPlan, PreparedSource, RecordBatch, SourceDescription


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtBenchBinaryAdapter(CIFARBinaryAdapter):
    """Preserve the author CSV artwork attributes at their CIFAR row indices."""

    def _metadata_path(self) -> Path:
        return Path(self.config["metadata_csv"]).expanduser().resolve()

    def probe(self) -> SourceDescription:
        archive, metadata = self._archive(), self._metadata_path()
        exists = archive.is_file() and metadata.is_file()
        size = archive.stat().st_size + metadata.stat().st_size if exists else None
        return SourceDescription(
            "artbench_10_cifar_binary_and_metadata", str(archive), exists, self.revision,
            size, True, True, True, False, True,
            ("Original author 32x32 CIFAR binary and CSV with exact split/cifar_index join",),
        )

    def plan(self, limit: int, max_bytes: int, cursor: str | None = None) -> PreparationPlan:
        base = CIFARBinaryAdapter.plan(self, limit, max_bytes, cursor)
        required = self._archive().stat().st_size + self._metadata_path().stat().st_size + 6 * self.BATCH_BYTES + 1024
        if required > max_bytes:
            raise ValueError("ArtBench source and prepared output exceed approved byte budget")
        return PreparationPlan(
            self.dataset.id, self.revision, cursor, limit, max_bytes, 0,
            6 * self.BATCH_BYTES + 1024,
            ("verify both author files; extract six binary batches; validate every CSV-index/style join",),
        )

    def prepare(self, approved_plan: PreparationPlan) -> PreparedSource:
        if _sha256(self._archive()) != self.config["archive_sha256"]:
            raise ValueError("ArtBench binary archive differs from pinned SHA-256")
        metadata_path = self._metadata_path()
        if _sha256(metadata_path) != self.config["metadata_sha256"]:
            raise ValueError("ArtBench metadata differs from pinned SHA-256")
        source = CIFARBinaryAdapter.prepare(self, approved_plan)
        classes = (self._prepared() / "batches.meta.txt").read_text().splitlines()
        binary = [(self._prepared() / f"data_batch_{i}.bin").read_bytes() for i in range(1, 6)]
        binary.append((self._prepared() / "test_batch.bin").read_bytes())
        # The generic CIFAR preparation may reuse existing same-sized files.
        # Verify all pixels against this exact pinned ArtBench archive too.
        with tarfile.open(self._archive(), "r:gz") as original:
            for index, name in enumerate([*(f"data_batch_{i}.bin" for i in range(1, 6)), "test_batch.bin"]):
                member = original.getmember("artbench-10-batches-bin/" + name)
                if not member.isfile() or member.size != self.BATCH_BYTES:
                    raise ValueError("ArtBench binary member differs from author layout")
                stream = original.extractfile(member)
                if stream is None or stream.read(self.BATCH_BYTES + 1) != binary[index]:
                    raise ValueError("ArtBench prepared binary differs from pinned archive")
        metadata: dict[tuple[str, int], dict[str, str]] = {}
        with metadata_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            required = {"name", "artist", "url", "is_public_domain", "length", "width",
                        "label", "split", "cifar_index"}
            if set(reader.fieldnames or []) != required:
                raise ValueError("ArtBench metadata schema differs from author CSV")
            for row in reader:
                split = row["split"]
                if split not in {"train", "test"}:
                    raise ValueError("ArtBench metadata has invalid split")
                try:
                    index = int(row["cifar_index"])
                    width, height = int(row["width"]), int(row["length"])
                except ValueError as exc:
                    raise ValueError("ArtBench metadata has non-integer index or geometry") from exc
                if not 0 <= index < (50_000 if split == "train" else 10_000):
                    raise ValueError("ArtBench metadata index is outside binary split")
                if width <= 0 or height <= 0 or row["is_public_domain"] not in {"True", "False"}:
                    raise ValueError("ArtBench metadata has invalid source attributes")
                key = (split, index)
                if key in metadata:
                    raise ValueError("ArtBench metadata has duplicate binary index")
                batch = index // 10_000 if split == "train" else 5
                offset = index % 10_000 if split == "train" else index
                label_index = binary[batch][offset * 3073]
                if label_index > 9 or classes[label_index] != row["label"]:
                    raise ValueError("ArtBench metadata style differs from binary label")
                metadata[key] = row
        if len(metadata) != 60_000:
            raise ValueError(f"ArtBench metadata has {len(metadata)} rows, expected 60,000")
        source.charge(metadata_path.stat().st_size)
        self._artwork_metadata = metadata
        return source

    def iter_records(self, source: PreparedSource, cursor: str | None = None,
                     limit: int | None = None) -> RecordBatch:
        if not hasattr(self, "_artwork_metadata"):
            raise ValueError("ArtBench adapter must be prepared before pagination")
        batch = CIFARBinaryAdapter.iter_records(self, source, cursor, limit)
        for record in batch.records:
            split, index = record.source["split"], record.source["index"]
            metadata = self._artwork_metadata[(split, index)]
            record.source.update({
                "artwork_name": metadata["name"], "artist": metadata["artist"],
                "source_url": metadata["url"],
                "author_public_domain_flag": metadata["is_public_domain"] == "True",
                "original_width": int(metadata["width"]),
                "original_height": int(metadata["length"]),
                "author_metadata": metadata,
            })
        return batch
