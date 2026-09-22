"""Acquire pinned public VLMBias synthetic Parquet files for local inspection.

This script never fetches the gated original SBBench benchmark or ViSU-Text.
All transfers have exact byte limits, resumable range checks, and SHA-256 pins.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import requests


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "work" / "sources" / "vlmbias"
SOURCES = {
    "sbbench-synthetic-gender-crop-false": {
        "repo": "vlmbias/sbbench_synthetic_gender_crop_False",
        "revision": "b3f53090f541bfcdb491217dfec7aa639289ad8a",
        "count": 206,
        "shards": [
            ("data/train-00000-of-00001.parquet", 237029151,
             "ada6735e59d70c98b812ca95cbce379b79340d224e1e86382a6d3ccdd620aeae"),
        ],
    },
    "sbbench-synthetic-age-crop-false": {
        "repo": "vlmbias/sbbench_synthetic_age_crop_False",
        "revision": "95ac0c3020ff710295a6ed5c0216718f03383151",
        "count": 333,
        "shards": [
            ("data/train-00000-of-00001.parquet", 430967656,
             "827f8c928bc1942a03eb93f2e8ea5a2198a4c9fd09465c16dcf3749da735e5e8"),
        ],
    },
    "sbbench-synthetic-gender-crop-true": {
        "repo": "vlmbias/sbbench_synthetic_gender_crop_True",
        "revision": "a7679386395cf29e9640757f16923f823d6251ef",
        "count": 406,
        "shards": [
            ("data/train-00000-of-00001.parquet", 496951911,
             "735bea2e42b4be933c4687170bce19e8738c096176d21807d94dbbdf4e439599"),
        ],
    },
    "sbbench-synthetic-age-crop-true": {
        "repo": "vlmbias/sbbench_synthetic_age_crop_True",
        "revision": "43769ef07d9388ebb4c3dc74b548eea615d0c93b",
        "count": 511,
        "combined_sha256": "41701bca3742c6151dc7b666a95eeb545bf8890c3d15f9149e5ca973ba6c1926",
        "shards": [
            ("data/train-00000-of-00002.parquet", 343041741,
             "cb8ac573bcf8c0b29e3164e90e144c3fac86eabf73961c1d18f6477f4dc63f1e"),
            ("data/train-00001-of-00002.parquet", 342276597,
             "c83a2c053cb877c41a6137086deacf2e251185317555643e84c37442203bfdd7"),
        ],
    },
}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _acquire(session: requests.Session, repo: str, revision: str,
             filename: str, size: int, digest: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == size and _digest(dest) == digest:
        return
    part = dest.with_name(dest.name + ".part")
    offset = part.stat().st_size if part.exists() else 0
    if offset > size:
        part.unlink()
        offset = 0
    url = f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{filename}"
    headers = {"Range": f"bytes={offset}-{size - 1}"}
    with session.get(url, headers=headers, stream=True, timeout=(20, 120)) as response:
        response.raise_for_status()
        parsed = urlparse(response.url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "huggingface.co", "us.aws.cdn.hf.co", "cdn-lfs-us-1.hf.co", "cdn-lfs.hf.co"
        }:
            raise ValueError("Unexpected download redirect destination")
        expected_range = f"bytes {offset}-{size - 1}/{size}"
        if response.status_code != 206 or response.headers.get("Content-Range") != expected_range:
            raise ValueError("Source did not honor pinned byte range")
        with part.open("ab") as target:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                if target.tell() + len(chunk) > size:
                    raise ValueError("Source exceeded declared size")
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    if part.stat().st_size != size or _digest(part) != digest:
        raise ValueError(f"Pinned size or SHA-256 mismatch for {repo}/{filename}")
    os.replace(part, dest)
    directory = os.open(dest.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _combine(shards: list[Path], output: Path, expected_sha256: str) -> None:
    if output.exists() and _digest(output) == expected_sha256:
        return
    temp = output.with_suffix(".parquet.part")
    if temp.exists():
        temp.unlink()
    base_schema = pq.ParquetFile(shards[0]).schema_arrow
    schema = base_schema.append(pa.field("source_shard", pa.string())).append(
        pa.field("source_row", pa.int64()))
    with pq.ParquetWriter(temp, schema, compression="zstd") as writer:
        for shard in shards:
            reader = pq.ParquetFile(shard)
            row = 0
            for batch in reader.iter_batches(batch_size=8):
                n = batch.num_rows
                table = pa.Table.from_batches([batch]).append_column(
                    "source_shard", pa.array([shard.name] * n)).append_column(
                    "source_row", pa.array(range(row, row + n), type=pa.int64()))
                writer.write_table(table)
                row += n
    if _digest(temp) != expected_sha256:
        raise ValueError("Consolidated source differs from pinned local transformation")
    with temp.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(temp, output)
    directory = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main() -> None:
    session = requests.Session()
    receipt = {"schema_version": "1.0", "scope": "local public synthetic VLMBias files only",
               "sources": []}
    for dataset_id, config in SOURCES.items():
        folder = DEST / dataset_id
        files = []
        for name, size, digest in config["shards"]:
            target = folder / Path(name).name
            _acquire(session, config["repo"], config["revision"], name, size, digest, target)
            files.append(target)
        if len(files) == 1:
            data_path = files[0]
        else:
            data_path = folder / "records.parquet"
            _combine(files, data_path, config["combined_sha256"])
        rows = pq.read_metadata(data_path).num_rows
        if rows != config["count"]:
            raise ValueError(f"Unexpected row count for {dataset_id}: {rows}")
        receipt["sources"].append({
            "dataset_id": dataset_id, "repo": config["repo"],
            "revision": config["revision"], "rows": rows,
            "source_shards": [{"path": str(path.relative_to(ROOT)), "bytes": size,
                               "sha256": digest}
                              for path, (_, size, digest) in zip(files, config["shards"])],
            "adapter_file": str(data_path.relative_to(ROOT)),
            "adapter_sha256": _digest(data_path),
            "publication": "metadata_only; dataset cards have no license text",
        })
        print(json.dumps({"dataset_id": dataset_id, "rows": rows, "path": str(data_path)}), flush=True)
    path = ROOT / "work" / "sources" / "vlmbias-acquisition.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
