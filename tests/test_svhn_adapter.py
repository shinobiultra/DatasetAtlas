"""Small MAT fixtures verify SVHN labels, pixels, scope and integrity."""
from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from dataset_atlas.adapters.svhn import SVHNAdapter
from dataset_atlas.models import Dataset

scipy = pytest.importorskip("scipy.io")


def _fixture(tmp_path, monkeypatch):
    counts = {"train": 3, "test": 2}
    monkeypatch.setattr(SVHNAdapter, "COUNTS", counts)
    sha = {}
    md5 = {}
    sizes = {}
    originals = {}
    for split, labels in (("train", [10, 5, 1]), ("test", [2, 10])):
        x = np.zeros((32, 32, 3, len(labels)), dtype=np.uint8)
        for index in range(len(labels)):
            x[:, :, :, index] = (index + 1) * 10
            x[0, 0, :, index] = [index + 1, 20, 30]
        originals[split] = x
        path = tmp_path / f"{split}_32x32.mat"
        scipy.savemat(path, {"X": x, "y": np.array(labels, dtype=np.uint8).reshape(-1, 1)},
                      do_compression=True)
        contents = path.read_bytes()
        sizes[split] = len(contents)
        sha[split] = hashlib.sha256(contents).hexdigest()
        md5[split] = hashlib.md5(contents, usedforsecurity=False).hexdigest()
    monkeypatch.setattr(SVHNAdapter, "SOURCE_BYTES", sizes)
    monkeypatch.setattr(SVHNAdapter, "SOURCE_MD5", md5)
    dataset = Dataset(id="svhn", name="SVHN", release="tiny-source-fixture",
                      snapshot_id="tiny-source-fixture-sha", adapter="svhn_cropped_mat",
                      adapter_config={"root": str(tmp_path), "sha256": sha})
    budget = (sum(sizes.values()) + sum(n * (SVHNAdapter.PIXEL_BYTES + 1) for n in counts.values())
              + sum(counts.values()) + 3 * 10_000)
    return SVHNAdapter(dataset), originals, budget


def test_svhn_preserves_raw_ten_and_indexes_pinned_pixels(tmp_path, monkeypatch):
    adapter, originals, budget = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="at least"):
        adapter.plan(3, budget - 1)
    plan = adapter.plan(3, budget)
    assert plan.expected_output_bytes == 5 * (32 * 32 * 3 + 1)
    source = adapter.prepare(plan)
    first = adapter.iter_records(source, limit=3)
    assert len(first.records) == 3
    assert first.next_cursor == "3"
    assert [r.source["raw_label"] for r in first.records] == [10, 5, 1]
    assert [r.source["digit"] for r in first.records] == [0, 5, 1]
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=3)
    assert [r.source["split"] for r in second.records] == ["test", "test"]
    assert [r.source["digit"] for r in second.records] == [2, 0]
    assert second.next_cursor is None
    assert len({r.id for r in first.records + second.records}) == 5
    assert len({r.asset_ids[0] for r in first.records + second.records}) == 5
    media = adapter.resolve_asset(source, first.records[0].assets[0].uri)
    assert media.media_type == "image/png"
    image = np.asarray(Image.open(io.BytesIO(media.data)))
    assert np.array_equal(image, originals["train"][:, :, :, 0])
    assert hashlib.sha256(media.data).hexdigest() == media.sha256
    with pytest.raises(ValueError, match="asset reference"):
        adapter.resolve_asset(source, "../train/000000.png")
    with pytest.raises(ValueError, match="outside release"):
        adapter.resolve_asset(source, "test/999999.png")
    assert adapter.prepare(plan).bytes_read == sum(adapter.SOURCE_BYTES.values())


def test_svhn_rejects_changed_source_and_repairs_prepared_cache(tmp_path, monkeypatch):
    adapter, _, budget = _fixture(tmp_path, monkeypatch)
    plan = adapter.plan(3, budget)
    adapter.prepare(plan)
    prepared = tmp_path / "prepared/train.pixels.bin"
    corrupted = bytearray(prepared.read_bytes())
    corrupted[0] ^= 255
    prepared.write_bytes(corrupted)
    adapter.prepare(plan)
    assert prepared.read_bytes()[0] == 1
    source_path = tmp_path / "train_32x32.mat"
    changed = bytearray(source_path.read_bytes())
    changed[-1] ^= 1
    source_path.write_bytes(changed)
    with pytest.raises(ValueError, match="official MD5 or pinned SHA-256"):
        adapter.prepare(plan)


def test_svhn_requires_pinned_source_hashes(tmp_path, monkeypatch):
    adapter, _, budget = _fixture(tmp_path, monkeypatch)
    adapter.config["sha256"].pop("test")
    with pytest.raises(ValueError, match="pinned SHA-256"):
        adapter.plan(2, budget)
