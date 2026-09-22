"""COCO source joins, stable identities, and selective archive media."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest
import yaml

from dataset_atlas.adapters import build_preview, get_adapter, resolve_dataset_asset
from dataset_atlas.models import Dataset


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, image_count: int = 3) -> Dataset:
    images_zip = tmp_path / "val2017.zip"
    ann_zip = tmp_path / "annotations_trainval2017.zip"
    images = []
    captions = []
    instances = []
    with zipfile.ZipFile(images_zip, "w") as archive:
        for iid in range(1, image_count + 1):
            filename = f"{iid:012d}.jpg"
            images.append({"id": iid, "file_name": filename, "width": 4, "height": 3,
                           "license": 1, "coco_url": f"https://example.test/{filename}"})
            archive.writestr(f"val2017/{filename}", b"\xff\xd8\xffsynthetic-jpeg-bytes\xff\xd9")
            for ordinal in range(2):
                captions.append({"id": iid * 10 + ordinal, "image_id": iid,
                                 "caption": f"Fixture caption {iid} {ordinal}"})
            instances.append({"id": iid * 100, "image_id": iid, "category_id": 1,
                              "bbox": [1, 0, 2, 3], "area": 6, "iscrowd": 0,
                              "segmentation": [[1, 0, 3, 0, 3, 3]]})
    with zipfile.ZipFile(ann_zip, "w") as archive:
        archive.writestr("annotations/captions_val2017.json", json.dumps({
            "info": {"year": 2017}, "licenses": [{"id": 1}],
            "images": images, "annotations": captions}))
        archive.writestr("annotations/instances_val2017.json", json.dumps({
            "info": {"year": 2017}, "licenses": [{"id": 1}],
            "images": images, "annotations": instances,
            "categories": [{"id": 1, "name": "person", "supercategory": "person"}]}))
    return Dataset(id="coco", name="COCO synthetic test fixture", release="2017-val",
                   snapshot_id="test-snapshot", adapter="coco", adapter_config={
                       "images_archive": str(images_zip), "annotations_archive": str(ann_zip),
                       "images_sha256": _sha(images_zip), "annotations_sha256": _sha(ann_zip),
                       "prepared_root": str(tmp_path / "prepared"),
                       "preparation_budget_bytes": 100_000_000,
                       "population": "synthetic fixture only",
                       "fields": {"caption_id": {"dtype": "number"}},
                   })


def test_caption_examples_share_image_and_asset_scoped_boxes(tmp_path: Path):
    dataset = _fixture(tmp_path)
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(10, 100_000_000))
    first = adapter.iter_records(source, limit=2)
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=2)
    assert len(first.records) == len(second.records) == 2
    assert first.records[0].id != first.records[1].id
    assert first.records[0].asset_ids == first.records[1].asset_ids
    assert first.records[0].asset_ids != second.records[0].asset_ids
    assert first.records[0].source["caption"]["id"] == 10
    assert first.records[0].source["category_names"] == ["person"]
    assert first.records[0].source["instances"][0]["segmentation"] == [[1, 0, 3, 0, 3, 3]]
    box = first.records[0].annotations[0]
    assert box.subject_id == first.records[0].asset_ids[0]
    assert box.subject_unit == "asset"
    assert box.value["bbox"] == [1, 0, 2, 3]
    assert box.value["category"]["name"] == "person"
    assert any(link.object_id == first.records[1].id for link in first.records[0].relations)
    assert adapter.iter_records(source, limit=1).records[0].id == first.records[0].id
    assert adapter.iter_records(source, cursor="5", limit=10).next_cursor is None


def test_preview_distinct_images_and_bounded_zip_media(tmp_path: Path):
    dataset = _fixture(tmp_path)
    pack = build_preview(dataset, tmp_path / "pack", limit=3,
                         max_bytes=100_000_000, distinct_assets=True)
    assert len(pack.records) == 3
    assert len({record.asset_ids[0] for record in pack.records}) == 3
    assert pack.dataset.adapter_config == {}
    assert pack.records[0].assets[0].uri == "val2017/000000000001.jpg"
    media = resolve_dataset_asset(dataset, pack.records[0].assets[0].uri)
    assert media.data.startswith(b"\xff\xd8\xff")
    assert media.media_type == "image/jpeg"
    with pytest.raises(ValueError, match="invalid COCO"):
        resolve_dataset_asset(dataset, "../val2017/000000000001.jpg")


def test_changed_archive_rejected(tmp_path: Path):
    dataset = _fixture(tmp_path)
    with zipfile.ZipFile(dataset.adapter_config["annotations_archive"], "a") as archive:
        archive.writestr("tampered.txt", "x")
    adapter = get_adapter(dataset)
    with pytest.raises(ValueError, match="SHA-256"):
        adapter.prepare(adapter.plan(2, 100_000_000))


def test_real_val2017_full_pagination_and_last_record():
    registry_path = Path(__file__).parents[2] / "registry" / "datasets" / "coco.yaml"
    dataset = Dataset.model_validate(yaml.safe_load(registry_path.read_text()))
    if not Path(dataset.adapter_config.get("images_archive", "")).is_file():
        pytest.skip("official COCO val2017 image archive not locally prepared")
    if not Path(dataset.adapter_config.get("annotations_archive", "")).is_file():
        pytest.skip("official COCO annotation archive not locally prepared")
    adapter = get_adapter(dataset)
    source = adapter.prepare(adapter.plan(1000, 2_000_000_000))
    first = adapter.iter_records(source, limit=101)
    later = adapter.iter_records(source, cursor=first.next_cursor, limit=101)
    assert len(first.records) == len(later.records) == 101
    assert first.records[0].id != later.records[0].id
    index = json.loads((Path(dataset.adapter_config["prepared_root"]) / "index.json").read_text())
    assert index["images"] == 5000
    assert index["total"] > 20_000
    final = adapter.iter_records(source, cursor=str(index["total"] - 1), limit=10)
    assert len(final.records) == 1 and final.next_cursor is None
    assert final.records[0].assets[0].uri.startswith("val2017/")
    image = adapter.resolve_asset(source, final.records[0].assets[0].uri)
    assert image.data.startswith(b"\xff\xd8\xff")
