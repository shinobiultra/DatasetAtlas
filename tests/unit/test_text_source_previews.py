"""Real, pinned local text source access; skips when source files are absent."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from dataset_atlas.adapters import get_adapter
from dataset_atlas.registry import Registry


ROOT = Path(__file__).parents[2]


def _source(name: str):
    registry = Registry(ROOT)
    dataset = registry.dataset(name)
    path = ROOT / dataset.adapter_config.get("path", "missing")
    if not path.is_file():
        pytest.skip(f"pinned {name} source file is not present locally")
    return registry, dataset, path


def test_maliciousinstruct_original_lines_and_complete_preview():
    registry, dataset, path = _source("maliciousinstruct")
    original = ROOT / dataset.adapter_config["source_path"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == dataset.adapter_config["source_sha256"]
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(100, 1_000_000))
    first = adapter.iter_records(source, limit=60)
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=60)
    assert len(first.records) == 60 and len(second.records) == 40
    assert second.next_cursor is None
    assert len({record.id for record in first.records + second.records}) == 100
    assert [record.source["prompt"] for record in first.records + second.records] == [
        line.rstrip("\r\n") for line in original.open(encoding="utf-8")
    ]
    pack = registry.pack("maliciousinstruct")
    assert len(pack.records) == 100
    assert [record.id for record in pack.records] == [record.id for record in first.records + second.records]


def test_realtoxicityprompts_full_pagination_and_flagged_preview():
    registry, dataset, path = _source("realtoxicityprompts")
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(1000, 100_000_000))
    first = adapter.iter_records(source, limit=101)
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=101)
    final = adapter.iter_records(source, cursor="99441", limit=10)
    assert len(first.records) == len(second.records) == 101
    assert len(final.records) == 1 and final.next_cursor is None
    assert len({record.id for record in first.records + second.records + final.records}) == 203
    assert all(record.source.keys() >= {"filename", "begin", "end", "challenging", "prompt", "continuation"}
               for record in first.records)
    pack = registry.pack("realtoxicityprompts")
    assert len(pack.records) == 100
    assert len({record.id for record in pack.records}) == 100
    assert all(record.source["challenging"] is True for record in pack.records)
    assert pack.sampling["method"] == "first_challenging_source_order"


def test_sorrybench_is_gated_without_a_fake_pack():
    registry = Registry(ROOT)
    dataset = registry.dataset("sorrybench")
    assert dataset.coverage.access == "gated"
    assert dataset.coverage.preview_count == 0
    assert dataset.coverage.complete_data == "externally_blocked"
    with pytest.raises(FileNotFoundError):
        registry.pack("sorrybench")
