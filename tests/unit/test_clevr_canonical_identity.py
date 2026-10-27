"""Synthetic identity checks for canonical CLEVR and its existing validation preview."""
import pytest

from dataset_atlas.adapters.clevr_full import CLEVRFullAdapter
from dataset_atlas.models import Dataset, stable_id


def adapter(mode=None):
    config = {} if mode is None else {"validation_identity": mode}
    return CLEVRFullAdapter(Dataset(id="clevr", name="CLEVR", release="CLEVR_v1.0",
                                   snapshot_id="synthetic-full", adapter="clevr_full",
                                   adapter_config=config))


def native(split):
    return {"split": split, "question_index": 7, "image_filename": f"CLEVR_{split}_000001.png",
            "question": "Synthetic fixture question", "program": [{"function": "scene", "inputs": []}],
            "image_index": 1, "native_extra": {"retained": True}}


def test_default_identity_keeps_existing_full_release_namespacing():
    row = native("val")
    record = adapter()._record(row)
    assert record.id == stable_id("clevr", "CLEVR_v1.0", "example", "val:7")
    assert record.asset_ids == [stable_id("clevr", "CLEVR_v1.0", "asset", "images/val/CLEVR_val_000001.png")]
    assert record.source == row


def test_canonical_validation_matches_legacy_preview_ids_without_changing_source():
    row = native("val")
    record = adapter("question_index")._record(row)
    assert record.id == stable_id("clevr", "CLEVR_v1.0", "example", "7")
    assert record.asset_ids == [stable_id("clevr", "CLEVR_v1.0", "asset", row["image_filename"])]
    assert record.assets[0].uri == "images/val/CLEVR_val_000001.png"
    assert record.source == row and record.snapshot_id == "synthetic-full"


def test_canonical_splits_do_not_collide_and_keep_every_native_annotation():
    reader = adapter("question_index")
    rows = [native(split) for split in ("train", "val", "test")]
    records = [reader._record(row) for row in rows]
    assert len({record.id for record in records}) == 3
    assert len({record.asset_ids[0] for record in records}) == 3
    for row, record in zip(rows, records):
        assert record.source == row
        assert record.dataset_id == "clevr"
        assert record.assets[0].dataset_id == "clevr"
    assert records[0].id == stable_id("clevr", "CLEVR_v1.0", "example", "train:7")
    assert records[2].id == stable_id("clevr", "CLEVR_v1.0", "example", "test:7")


def test_unrecognized_validation_identity_is_rejected():
    with pytest.raises(ValueError, match="validation_identity"):
        adapter("unrecognized")._record(native("val"))
