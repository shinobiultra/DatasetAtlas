"""Build 100 original IconQA question/media examples across all nine sections."""
from __future__ import annotations

import argparse
from pathlib import Path

from dataset_atlas.adapters import build_preview, get_adapter
from dataset_atlas.adapters.core import _write_rooted_atomic
from dataset_atlas.models import Pack
from dataset_atlas.registry import Registry


MAX_BYTES = 3_000_000_000


def prepare(root: Path) -> Pack:
    root = root.resolve()
    dataset = Registry(root).dataset("iconqa")
    output = root / "work/packs/iconqa"
    base = build_preview(dataset, output, limit=100, max_bytes=MAX_BYTES)
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(100, MAX_BYTES))
    counts = adapter._index()["counts"]
    records = []
    sections = []
    offset = 0
    for section, population in sorted(counts.items()):
        quota = 12 if section == "train:choose_img" else 11
        batch = adapter.iter_records(source, str(offset), quota)
        split, task = section.split(":")
        if len(batch.records) != quota or any(
            row.source["split"] != split or row.source["subtask"] != task
            for row in batch.records
        ):
            raise ValueError(f"IconQA section {section} differs from pinned source")
        records.extend(batch.records)
        sections.append({"section": section, "source_offset": offset,
                         "population_count": population, "selected_count": quota})
        offset += population
    if len(records) != 100 or len({row.id for row in records}) != 100:
        raise ValueError("IconQA preview IDs are not distinct and complete")
    checksums: dict[str, str] = {}
    for record in records:
        if not record.assets or record.assets[0].metadata["role"] != "diagram":
            raise ValueError("IconQA preview row lacks source diagram")
        for asset in record.assets:
            original = asset.uri
            if not original:
                raise ValueError("IconQA source image has no ZIP member reference")
            handle = adapter.resolve_asset(source, original)
            _write_rooted_atomic(output / "media", original, handle.data)
            relative = "media/" + original
            asset.uri = relative
            asset.sha256 = handle.sha256
            asset.metadata["source_zip_member"] = original
            checksums[relative] = handle.sha256
    pack = Pack.model_validate(base.model_dump(mode="json") | {
        "records": [row.model_dump(mode="json") for row in records],
        "checksums": checksums,
        "sampling": {
            "method": "first_11_per_split_subtask_plus_one_train_image_choice",
            "unit": "example", "population": dataset.adapter_config["population"],
            "sections": sections, "requested_count": 100, "returned_count": 100,
            "source_revision": dataset.release, "bytes_read": source.bytes_read,
            "note": "Near-equal coverage of nine original sections; not population weighted. Original diagrams and all image choices copied from the pinned author ZIP.",
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
    print(f"IconQA preview: {len(pack.records)} original questions, {len(pack.checksums)} original PNGs")
