"""Build a 100-image local ArtBench-10 preview, five per style and split."""
from __future__ import annotations

import argparse
from pathlib import Path

from dataset_atlas.adapters import build_preview, get_adapter
from dataset_atlas.adapters.core import _write_rooted_atomic
from dataset_atlas.models import Pack
from dataset_atlas.registry import Registry


MAX_BYTES = 500_000_000


def prepare(root: Path) -> Pack:
    root = root.resolve()
    dataset = Registry(root).dataset("artbench")
    output = root / "work/packs/artbench"
    base = build_preview(dataset, output, limit=100, max_bytes=MAX_BYTES)
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(100, MAX_BYTES))
    styles = (adapter._prepared() / "batches.meta.txt").read_text().splitlines()
    if len(styles) != 10 or len(set(styles)) != 10:
        raise ValueError("ArtBench author style list differs from expected release")
    records = []
    sections = []
    for split, start in (("train", 0), ("test", 50_000)):
        per_style = {style: 0 for style in styles}
        offset = start
        scanned = 0
        while any(count < 5 for count in per_style.values()):
            batch = adapter.iter_records(source, str(offset), 100)
            if not batch.records or any(rec.source["split"] != split for rec in batch.records):
                raise ValueError(f"ArtBench {split} source ended before balanced sample")
            for record in batch.records:
                style = record.source["class_name"]
                if per_style[style] < 5:
                    records.append(record)
                    per_style[style] += 1
            offset += len(batch.records)
            scanned += len(batch.records)
        sections.append({"split": split, "scanned_source_rows": scanned,
                         "selected_per_style": 5, "selected_count": 50})
    if len(records) != 100 or len({record.id for record in records}) != 100:
        raise ValueError("ArtBench preview IDs are not unique and complete")
    checksums: dict[str, str] = {}
    for record in records:
        asset = record.assets[0]
        original = asset.uri
        if not original:
            raise ValueError("ArtBench source row has no lossless image reference")
        handle = adapter.resolve_asset(source, original)
        _write_rooted_atomic(output / "media", original, handle.data)
        relative = "media/" + original
        asset.uri = relative
        asset.sha256 = handle.sha256
        checksums[relative] = handle.sha256
    pack = Pack.model_validate(base.model_dump(mode="json") | {
        "records": [record.model_dump(mode="json") for record in records],
        "checksums": checksums,
        "sampling": {
            "method": "first_5_per_style_per_split",
            "unit": "example", "population": dataset.adapter_config["population"],
            "sections": sections, "requested_count": 100, "returned_count": 100,
            "source_revision": dataset.release, "bytes_read": source.bytes_read,
            "note": "Class- and split-balanced local preview; PNGs are lossless encodings of author 32x32 CIFAR RGB pixels, not original-resolution artworks.",
        },
    })
    staged = output / "pack.json.part"
    staged.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    staged.replace(output / "pack.json")
    return pack


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    pack = prepare(args.root)
    print(f"ArtBench-10 32px preview: {len(pack.records)} real examples")
