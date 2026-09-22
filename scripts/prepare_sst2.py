"""Convert the pinned GLUE SST-2 ZIP to a split-preserving local Parquet table.

Only the three GLUE TSV members are read. The original archive remains unchanged,
and the derived table keeps every source sentence, original split, and label status.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
from pathlib import Path
import zipfile

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_SHA256 = "d67e16fb55739c1b32cdce9877596db1c127dc322d93c082281f64057c16deaa"
COUNTS = {"train": 67349, "dev": 872, "test": 1821}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(root: Path) -> tuple[Path, dict[str, int]]:
    directory = root / "work/sources/sst2"
    archive = directory / "SST-2.zip"
    output = directory / "glue-sst2.parquet"
    if sha256(archive) != SOURCE_SHA256:
        raise ValueError("GLUE SST-2 source archive differs from pinned SHA-256")
    columns = {name: [] for name in
               ("source_id", "sentence", "label", "label_status", "split", "source_index", "source_member")}
    with zipfile.ZipFile(archive) as zf:
        for split, expected in COUNTS.items():
            member = f"SST-2/{split}.tsv"
            info = zf.getinfo(member)
            if info.file_size > 5_000_000:
                raise ValueError(f"GLUE TSV member exceeds 5 MB: {member}")
            with zf.open(info) as stream:
                raw = stream.read(5_000_001)
            if len(raw) != info.file_size:
                raise ValueError(f"GLUE TSV member length mismatch: {member}")
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter="\t")
            required = ["index", "sentence"] if split == "test" else ["sentence", "label"]
            if reader.fieldnames != required:
                raise ValueError(f"Unexpected GLUE {split} fields: {reader.fieldnames}")
            count = 0
            for index, row in enumerate(reader):
                if not isinstance(row["sentence"], str) or not row["sentence"].strip():
                    raise ValueError(f"Empty GLUE sentence at {split}:{index}")
                if split == "test":
                    if row["index"] != str(index):
                        raise ValueError("GLUE test source index is not sequential")
                    label = None
                else:
                    if row["label"] not in {"0", "1"}:
                        raise ValueError(f"Invalid GLUE label at {split}:{index}")
                    label = int(row["label"])
                columns["source_id"].append(f"{split}:{index}")
                columns["sentence"].append(row["sentence"])
                columns["label"].append(label)
                columns["label_status"].append("withheld_by_glue" if label is None else "source_labeled")
                columns["split"].append(split)
                columns["source_index"].append(index)
                columns["source_member"].append(member)
                count += 1
            if count != expected:
                raise ValueError(f"GLUE {split} count {count} differs from expected {expected}")
    if len(set(columns["source_id"])) != sum(COUNTS.values()):
        raise ValueError("GLUE source IDs are not unique")
    schema = pa.schema([
        ("source_id", pa.string()), ("sentence", pa.string()), ("label", pa.int8()),
        ("label_status", pa.string()), ("split", pa.string()), ("source_index", pa.int32()),
        ("source_member", pa.string()),
    ], metadata={b"source_archive_sha256": SOURCE_SHA256.encode(),
                 b"source_release": b"GLUE SST-2 ZIP as hosted 2020-09-03",
                 b"transformation": b"lossless TSV row to Parquet, split and withheld labels preserved"})
    table = pa.Table.from_pydict(columns, schema=schema)
    staged = output.with_suffix(".parquet.part")
    pq.write_table(table, staged, compression="zstd", row_group_size=1024)
    if output.exists() and sha256(output) != sha256(staged):
        staged.unlink(missing_ok=True)
        raise ValueError("Existing derived SST-2 table differs from regenerated source")
    staged.replace(output)
    return output, COUNTS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    output, counts = prepare(args.root.resolve())
    print(f"{output} SHA-256={sha256(output)} rows={sum(counts.values())} splits={counts}")


if __name__ == "__main__":
    main()
