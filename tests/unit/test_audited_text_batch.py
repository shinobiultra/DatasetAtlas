"""Pinned real-source checks for six audited local releases."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from dataset_atlas.adapters import get_adapter
from dataset_atlas.registry import Registry

ROOT = Path(__file__).parents[2]
EXPECTED = {
    "anthropic-red-teaming-prompts": 38_961,
    "jailbreakv-28k": 28_000,
    "tdc2023": 100,
    "bbq": 58_492,
    "halueval": 34_507,
    "omnisafebench-mm": 1_500,
}


@pytest.mark.parametrize("dataset_id,count", EXPECTED.items())
def test_pinned_preview_and_full_source_pagination(dataset_id: str, count: int):
    registry = Registry(ROOT)
    dataset = registry.dataset(dataset_id)
    source_path = Path(dataset.adapter_config["path"])
    if not source_path.is_file():
        pytest.skip(f"{dataset_id} source is absent")
    assert sum(1 for _ in source_path.open(encoding="utf-8")) == count
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == dataset.adapter_config["sha256"]
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(101, 160_000_000))
    first = adapter.iter_records(source, limit=101)
    last = adapter.iter_records(source, cursor=str(count - 1), limit=101)
    assert len(first.records) == min(101, count)
    assert len(last.records) == 1 and last.next_cursor is None
    assert last.records[0].id not in {record.id for record in first.records[:-1]}
    pack = registry.pack(dataset_id)
    assert len(pack.records) == 100
    assert len({record.id for record in pack.records}) == 100
    assert all(record.snapshot_id == dataset.snapshot_id for record in pack.records)
    assert dataset.coverage.total_count == count
    receipt = json.loads((ROOT / "reports" / f"{dataset_id}-source.json").read_text())
    assert hashlib.sha256((ROOT / receipt["preview_pack"]).read_bytes()).hexdigest() == receipt["preview_sha256"]
    assert receipt["derived"]["rows"] == count
    for item in receipt["original_files"]:
        original = ROOT / item["file"]
        assert original.stat().st_size == item["bytes"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == item["sha256"]


def test_tdc_released_dev_and_test_are_both_present():
    pack = Registry(ROOT).pack("tdc2023")
    assert Counter(record.source["split"] for record in pack.records) == {"dev": 50, "test": 50}
    assert len({record.source["source_id"] for record in pack.records}) == 100
    for split, offset in (("dev", 0), ("test", 50)):
        originals = json.loads((ROOT / f"work/sources/tdc2023/{split}_behaviors.json").read_text())
        assert [record.source["behavior"] for record in pack.records[offset:offset + 50]] == originals


def test_jailbreakv_preview_only_references_released_distinct_media():
    registry = Registry(ROOT)
    dataset = registry.dataset("jailbreakv-28k")
    files = json.loads((ROOT / "work/sources/jailbreakv-28k/available_images.json").read_text())["files"]
    pack = registry.pack("jailbreakv-28k")
    refs = [record.assets[0].uri for record in pack.records]
    assert len(refs) == len(set(refs)) == 100
    assert all(ref in files for ref in refs)
    assert pack.sampling["method"] == "first_available_distinct_media_source_order"
    assert dataset.coverage.complete_data == "partial_media"
    source = get_adapter(dataset).prepare(get_adapter(dataset).plan(1, 2_000_000))
    first = get_adapter(dataset).iter_records(source, limit=1).records[0]
    assert first.source["image_path"] and first.assets == []  # source references a missing public file


def test_balanced_bbq_halueval_and_omnisafe_previews():
    registry = Registry(ROOT)
    bbq = registry.pack("bbq")
    assert len({record.source["category"] for record in bbq.records}) == 11
    assert all(len(record.choices) == 3 and record.source["label"] in {0, 1, 2} for record in bbq.records)
    halueval = registry.pack("halueval")
    assert Counter(record.source["task"] for record in halueval.records) == {
        "dialogue": 25, "general": 25, "qa": 25, "summarization": 25}
    omni = registry.pack("omnisafebench-mm")
    assert len({record.source["main_category"] for record in omni.records}) == 9
    assert all(len(record.assets) == 1 and record.assets[0].uri.startswith("images/") for record in omni.records)
    official_files = json.loads((ROOT / "work/sources/omnisafebench-mm/available_images.json").read_text())["files"]
    all_rows = [json.loads(line) for line in (ROOT / "work/sources/omnisafebench-mm/records.jsonl").open()]
    assert len(official_files) == len(all_rows) == 1_500
    assert {row["media_path"] for row in all_rows} == set(official_files)
