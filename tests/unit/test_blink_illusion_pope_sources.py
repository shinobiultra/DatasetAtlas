"""Real pinned release checks for BLINK, IllusionVQA, and POPE COCO v1."""
from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from PIL import Image

from dataset_atlas.adapters import resolve_dataset_asset
from dataset_atlas.registry import Registry

ROOT = Path(__file__).parents[2]
COUNTS = {"blink": 3807, "illusionvqa": 1435, "pope": 9000}


@pytest.mark.parametrize("dataset_id,count", COUNTS.items())
def test_complete_pinned_snapshot_preview_and_real_media(dataset_id, count):
    registry = Registry(ROOT)
    dataset = registry.dataset(dataset_id)
    if not Path(dataset.adapter_config["path"]).is_file():
        pytest.skip(f"{dataset_id} author source is not installed")
    receipt = json.loads((ROOT / "reports" / f"{dataset_id}-source.json").read_text())
    assert receipt["derived"]["rows"] == count
    assert dataset.coverage.total_count == count
    assert hashlib.sha256(Path(dataset.adapter_config["path"]).read_bytes()).hexdigest() == receipt["derived"]["sha256"]
    for item in receipt["original_files"]:
        path = ROOT / item["file"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    snapshot = ROOT / "work/snapshots" / dataset_id
    manifest = json.loads((snapshot / "manifest.json").read_text())
    table = pq.read_table(snapshot / "records.parquet", columns=["id", "record_json"])
    assert manifest["record_count"] == table.num_rows == count
    final = json.loads(table.column("record_json")[-1].as_py())
    assert final["assets"] and all(asset["uri"] for asset in final["assets"])
    pack = registry.pack(dataset_id)
    assert len(pack.records) == len({row.assets[0].id for row in pack.records}) == 100
    assert receipt["preview_sha256"] == hashlib.sha256((ROOT / receipt["preview_pack"]).read_bytes()).hexdigest()
    for record in (pack.records[0], pack.records[-1]):
        for asset in record.assets:
            media = resolve_dataset_asset(dataset, asset.uri, workspace_root=ROOT)
            with Image.open(BytesIO(media.data)) as image:
                image.verify()
            assert hashlib.sha256(media.data).hexdigest() == media.sha256


def test_blink_and_illusion_task_scopes_remain_distinct(require_local_files):
    require_local_files('work/packs/blink/pack.json', 'work/packs/illusionvqa/pack.json')
    registry = Registry(ROOT)
    blink = registry.pack("blink")
    strata = Counter((row.source["task"], row.source["split"]) for row in blink.records)
    assert len(strata) == 28 and sorted(strata.values()) == [3] * 12 + [4] * 16
    assert all(1 <= len(row.assets) <= 4 for row in blink.records)
    assert all(row.source["answer"] == "hidden" for row in blink.records if row.source["split"] == "test")
    illusion = registry.pack("illusionvqa")
    assert Counter(row.source["task"] for row in illusion.records) == {
        "comprehension": 50, "soft-localization": 50}
    assert all(row.source["split"] == "test" and len(row.assets) == 1 for row in illusion.records)
    source = json.loads((ROOT / "reports/illusionvqa-source.json").read_text())
    assert source["derived"]["task_counts"] == {"comprehension": 435, "soft-localization": 1000}


def test_pope_three_strategy_labels_and_exact_coco_image_references(require_local_files):
    require_local_files('work/sources/pope/records.jsonl')
    rows = [json.loads(line) for line in (ROOT / "work/sources/pope/records.jsonl").open()]
    assert len(rows) == 9000
    assert Counter(row["strategy"] for row in rows) == {
        "adversarial": 3000, "popular": 3000, "random": 3000}
    assert Counter((row["strategy"], row["label"]) for row in rows) == {
        (strategy, label): 1500 for strategy in ("adversarial", "popular", "random")
        for label in ("yes", "no")}
    assert len({row["source_image_name"] for row in rows}) == 500
    assert all(row["media_path"] == "val2014/" + row["source_image_name"] for row in rows)
    preview = Registry(ROOT).pack("pope")
    assert Counter(row.source["strategy"] for row in preview.records) == {
        "adversarial": 34, "popular": 33, "random": 33}
    assert Counter(row.source["label"] for row in preview.records) == {"yes": 50, "no": 50}


def test_zerobench_fresh_install_reports_the_gate_without_content(tmp_path):
    directory = tmp_path / 'registry/datasets'
    directory.mkdir(parents=True)
    shutil.copyfile(ROOT / 'registry/datasets/zerobench.yaml', directory / 'zerobench.yaml')
    registry = Registry(tmp_path)
    dataset = registry.dataset("zerobench")
    receipt = json.loads((ROOT / "reports/zerobench-source.json").read_text())
    assert dataset.coverage.access == "gated" and dataset.coverage.preview_count == 0
    assert receipt["access_check"]["status"] == 401 and receipt["downloaded_content"] is False
    with pytest.raises(FileNotFoundError):
        registry.pack('zerobench')


def test_authorized_zerobench_preserves_the_gate_and_publication_restrictions():
    registry = Registry(ROOT)
    if registry.active_directory('zerobench') is None:
        pytest.skip('authorized ZeroBench source is not installed')
    dataset = registry.dataset('zerobench')
    assert dataset.coverage.access == 'gated'
    assert dataset.coverage.preview_count == len(registry.pack('zerobench').records) == 100
    assert dataset.coverage.total_count == 100
    assert dataset.coverage.publication == 'metadata_only'
    assert any('answers' in message and 'publicly' in message for message in dataset.coverage.blockers)
    assert not any('unauthenticated pinned Parquet HEAD' in message for message in dataset.coverage.blockers)
