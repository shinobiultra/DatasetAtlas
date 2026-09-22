"""Real, pinned source and media checks for three small visual benchmarks."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from PIL import Image

from dataset_atlas.adapters import get_adapter
from dataset_atlas.registry import Registry

ROOT = Path(__file__).parents[2]
EXPECTED = {"vibeeval": 269, "visualpuzzle": 1_168, "whoops": 500}


@pytest.mark.parametrize("dataset_id,count", EXPECTED.items())
def test_full_pagination_pinned_originals_and_real_media(dataset_id: str, count: int):
    registry = Registry(ROOT)
    dataset = registry.dataset(dataset_id)
    source_file = Path(dataset.adapter_config["path"])
    if not source_file.is_file():
        pytest.skip(f"pinned {dataset_id} source is absent")
    receipt = json.loads((ROOT / "reports" / f"{dataset_id}-source.json").read_text())
    assert receipt["derived"]["rows"] == count
    assert sum(1 for _ in source_file.open(encoding="utf-8")) == count
    for item in receipt["original_files"]:
        original = ROOT / item["file"]
        assert original.stat().st_size == item["bytes"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == item["sha256"]
    adapter = get_adapter(dataset)
    prepared = adapter.prepare(adapter.plan(101, 20_000_000))
    first = adapter.iter_records(prepared, limit=101)
    last = adapter.iter_records(prepared, cursor=str(count - 1), limit=101)
    assert len(first.records) == 101
    assert len(last.records) == 1 and last.next_cursor is None
    assert all(record.assets and record.assets[0].modality == "image" for record in first.records)
    pack = registry.pack(dataset_id)
    assert len(pack.records) == len({record.assets[0].uri for record in pack.records}) == 100
    assert receipt["preview_sha256"] == hashlib.sha256((ROOT / receipt["preview_pack"]).read_bytes()).hexdigest()
    for record in (pack.records[0], pack.records[-1]):
        media = adapter.resolve_asset(adapter.prepare(adapter.plan(1, 10_000_000)), record.assets[0].uri)
        assert media.sha256 == record.source["image_sha256"]
        Image.open(BytesIO(media.data)).verify()


def test_vibeeval_and_visualpuzzle_source_fields_preserve_official_rows():
    registry = Registry(ROOT)
    for dataset_id, filename, fields in (
        ("vibeeval", "vibe-eval.v1.parquet", ("example_id", "category", "prompt", "reference", "media_url")),
        ("visualpuzzle", "train-00000-of-00001.parquet", ("id", "question", "options", "answer", "category", "difficulty")),
    ):
        original = pq.ParquetFile(ROOT / "work/sources" / dataset_id / filename)
        source_file = Path(registry.dataset(dataset_id).adapter_config["path"])
        first = json.loads(source_file.open(encoding="utf-8").readline())
        upstream = next(original.iter_batches(batch_size=1)).to_pylist()[0]
        assert all(first[field] == upstream[field] for field in fields)
        assert hashlib.sha256(upstream["image"]["bytes"]).hexdigest() == first["image_sha256"]
    vibe = registry.pack("vibeeval")
    assert Counter(record.source["category"] for record in vibe.records) == {
        "difficulty-normal": 50, "difficulty-hard": 50}
    puzzle = registry.pack("visualpuzzle")
    assert set(Counter(record.source["category"] for record in puzzle.records).values()) == {20}
    assert all(record.source["answer"] and
               (record.source["options"] is None or isinstance(record.source["options"], list))
               for record in puzzle.records)


def test_whoops_source_arrays_and_image_population():
    registry = Registry(ROOT)
    dataset = registry.dataset("whoops")
    rows = [json.loads(line) for line in Path(dataset.adapter_config["path"]).open(encoding="utf-8")]
    with (ROOT / "work/sources/whoops/whoops_dataset.csv").open(encoding="utf-8-sig", newline="") as handle:
        original = list(csv.DictReader(handle))
    assert len(rows) == len(original) == 500
    assert all(row["image_id"] == source["image_id"] and row["selected_caption"] == source["selected_caption"]
               for row, source in zip(rows, original))
    assert sum(len(row["crowd_captions"]) for row in rows) == 2_500
    assert sum(len(row["crowd_explanations"]) for row in rows) == 2_500
    assert sum(len(row["crowd_underspecified_captions"]) for row in rows) == 2_500
    assert sum(len(row["question_answering_pairs"]) for row in rows) == 3_362
    assert len({row["media_path"] for row in rows}) == 500
