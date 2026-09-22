"""Build the pinned DOCCI image-description preview with 25 rows per split.

The generic source-order preview would show only ``qual_dev`` because that is
the first 100-row block in the author's JSONL. This script keeps the source
file unchanged and records the exact, non-representative sampling rule.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dataset_atlas.adapters import build_preview, get_adapter
from dataset_atlas.adapters.core import _write_rooted_atomic
from dataset_atlas.models import Pack
from dataset_atlas.registry import Registry


SPLIT_OFFSETS = (("qual_dev", 0), ("qual_test", 100), ("test", 200), ("train", 5200))
MAX_BYTES = 20_000_000_000


def prepare(root: Path) -> Pack:
    root = root.resolve()
    dataset = Registry(root).dataset("docci")
    output = root / "work/packs/docci"
    base = build_preview(dataset, output, limit=100, max_bytes=MAX_BYTES)
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(100, MAX_BYTES))
    records = []
    for split, offset in SPLIT_OFFSETS:
        batch = adapter.iter_records(source, str(offset), 25)
        if len(batch.records) != 25 or any(record.source.get("split") != split for record in batch.records):
            raise ValueError(f"DOCCI source split at offset {offset} differs from pinned release: {split}")
        records.extend(batch.records)
    if len({record.id for record in records}) != 100 or len({record.source["image_file"] for record in records}) != 100:
        raise ValueError("DOCCI preview source IDs or image filenames are not unique")
    media_dir = output / "media"
    checksums: dict[str, str] = {}
    for record in records:
        if len(record.assets) != 1 or record.assets[0].uri != record.source["image_file"]:
            raise ValueError("DOCCI preview description and image reference do not join")
        asset = record.assets[0]
        original = asset.uri
        handle = adapter.resolve_asset(source, original)
        _write_rooted_atomic(media_dir, original, handle.data)
        relative = "media/" + original
        asset.uri = relative
        asset.sha256 = handle.sha256
        asset.metadata["source_image_file"] = original
        checksums[relative] = handle.sha256
    sampling = {
        "method": "first_25_per_original_split",
        "unit": "example",
        "population": dataset.adapter_config["population"],
        "sections": [{"split": split, "source_offset": offset, "count": 25} for split, offset in SPLIT_OFFSETS],
        "requested_count": 100,
        "returned_count": 100,
        "source_revision": dataset.release,
        "bytes_read": source.bytes_read,
        "note": "Equal preview allocation across four source splits, not prevalence-weighted; each image is an exact byte copy from the pinned author archive.",
    }
    pack = Pack.model_validate(base.model_dump(mode="json") | {
        "records": [record.model_dump(mode="json") for record in records],
        "sampling": sampling,
        "checksums": checksums,
    })
    target = output / "pack.json"
    staged = output / "pack.json.part"
    staged.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    staged.replace(target)
    return pack


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = prepare(args.root)
    print(f"DOCCI image-description preview: {len(result.records)} records; sampling={result.sampling['method']}")
