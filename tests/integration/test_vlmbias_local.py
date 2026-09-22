"""Real pinned source checks; skipped when optional local data are absent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from dataset_atlas.adapters import get_adapter
from dataset_atlas.models import Query
from dataset_atlas.queries.parquet import ParquetSnapshot
from dataset_atlas.registry import Registry


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "work/sources/vlmbias-acquisition.json"
COUNTS = {
    "sbbench-synthetic-gender-crop-false": 206,
    "sbbench-synthetic-age-crop-false": 333,
    "sbbench-synthetic-gender-crop-true": 406,
    "sbbench-synthetic-age-crop-true": 511,
}


@pytest.mark.parametrize("dataset_id,expected", COUNTS.items())
def test_pinned_real_synthetic_source_preview_and_index(dataset_id: str, expected: int) -> None:
    if not RECEIPT.is_file():
        pytest.skip("Optional public VLMBias source files were not acquired")
    source_entry = next(
        x for x in json.loads(RECEIPT.read_text())["sources"] if x["dataset_id"] == dataset_id
    )
    path = ROOT / source_entry["adapter_file"]
    if not path.is_file():
        pytest.skip("Optional source file is absent")
    assert source_entry["rows"] == expected == pq.read_metadata(path).num_rows
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source_entry["adapter_sha256"]

    dataset = Registry(ROOT).dataset(dataset_id)
    assert dataset.adapter == "embedded_parquet"
    assert dataset.coverage.complete_data == "supported"
    assert dataset.coverage.publication == "metadata_only"
    assert dataset.coverage.total_count == expected
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(2, 15_000_000))
    first = adapter.iter_records(source, None, 1).records[0]
    last = adapter.iter_records(source, str(expected - 1), 1).records[0]
    assert first.id != last.id
    assert first.source["label"] in {0, 1}
    assert first.source["image"]["bytes"] > 0
    assert first.asset_ids and first.assets[0].sha256
    media = adapter.resolve_asset(source, first.assets[0].uri)
    assert media.media_type == "image/png"
    assert media.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(media.data).hexdigest() == first.assets[0].sha256

    pack = Registry(ROOT).pack(dataset_id)
    assert len(pack.records) == 100
    assert pack.sampling["source_revision"] == dataset.release
    assert b"\x89PNG" not in (ROOT / "work/packs" / dataset_id / "pack.json").read_bytes()
    index = ROOT / "work/snapshots" / dataset_id
    manifest = json.loads((index / "manifest.json").read_text())
    assert manifest["record_count"] == expected
    assert manifest["snapshot_id"] == dataset.snapshot_id
    indexed = pq.read_table(index / "records.parquet", columns=["id"]).column("id").to_pylist()
    assert len(indexed) == expected == len(set(indexed))
    snapshot = ParquetSnapshot(ROOT / "work/snapshots", index)
    zero = snapshot.query(Query(population_scope="complete", snapshot_id=dataset.snapshot_id,
                                filter={"field_id": "source.label", "op": "eq", "value": 0},
                                limit=3))
    one = snapshot.query(Query(population_scope="complete", snapshot_id=dataset.snapshot_id,
                               filter={"field_id": "source.label", "op": "eq", "value": 1},
                               limit=3))
    assert zero.matched_count + one.matched_count == expected


def test_visu_text_is_gated_metadata_only() -> None:
    dataset = Registry(ROOT).dataset("visu-text")
    assert dataset.coverage.access == "gated"
    assert dataset.coverage.preview == "none"
    assert dataset.coverage.complete_data == "externally_blocked"
    assert "Unsafe vision images" in " ".join(dataset.coverage.blockers)
