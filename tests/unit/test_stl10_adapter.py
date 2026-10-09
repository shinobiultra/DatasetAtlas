"""STL-10 binary row, split, media geometry and archive boundary contracts."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile

import numpy as np
from PIL import Image
import pytest

from dataset_atlas.adapters.stl10 import STL10BinaryAdapter
from dataset_atlas.models import Dataset


class TinySTL10(STL10BinaryAdapter):
    COUNTS = {"train": 2, "test": 1, "unlabeled": 1}
    MEMBER_SIZES = {"train_X.bin": 2 * 3 * 96 * 96, "train_y.bin": 2,
                    "test_X.bin": 3 * 96 * 96, "test_y.bin": 1,
                    "unlabeled_X.bin": 3 * 96 * 96}
    MEMBER_MD5: dict[str, str] = {}


def _fixture(tmp_path: Path, *, symlink: bool = False) -> tuple[TinySTL10, np.ndarray]:
    rgb = np.zeros((96, 96, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.arange(96, dtype=np.uint8)[None, :]
    rgb[:, :, 1] = np.arange(96, dtype=np.uint8)[:, None]
    rgb[:, :, 2] = 121
    raw = rgb.transpose(2, 1, 0).tobytes()
    members = {"train_X.bin": raw + raw, "train_y.bin": bytes([1, 10]),
               "test_X.bin": raw, "test_y.bin": bytes([4]), "unlabeled_X.bin": raw,
               "class_names.txt": b"airplane\nbird\ncar\ncat\ndeer\ndog\nhorse\nmonkey\nship\ntruck\n",
               "fold_indices.txt": (b"0 1\n" * 10)}
    TinySTL10.MEMBER_MD5 = {key: hashlib.md5(value, usedforsecurity=False).hexdigest()
                            for key, value in members.items() if key in TinySTL10.MEMBER_SIZES}
    archive = tmp_path / "stl10_binary.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name, data in members.items():
            info = tarfile.TarInfo("stl10_binary/" + name)
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
        if symlink:
            info = tarfile.TarInfo("stl10_binary/escape")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../elsewhere"
            bundle.addfile(info)
    dataset = Dataset(id="stl-10", name="STL-10", release="test-pinned-binary",
                      snapshot_id="test-snapshot", adapter="stl10",
                      adapter_config={"root": str(tmp_path),
                                      "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                                      "archive_md5": hashlib.md5(archive.read_bytes(), usedforsecurity=False).hexdigest()})
    return TinySTL10(dataset), rgb


def test_stl10_bounded_archive_split_identity_and_pixel_geometry(tmp_path: Path):
    adapter, expected_rgb = _fixture(tmp_path)
    with pytest.raises(ValueError, match="requires at least"):
        adapter.plan(4, 1_000_000)
    source = adapter.prepare(adapter.plan(4, 3_000_000))
    first = adapter.iter_records(source, None, 2)
    assert [row.source["label"] for row in first.records] == [1, 10]
    assert [row.source["class_name"] for row in first.records] == ["airplane", "truck"]
    assert first.records[0].source["fold_memberships"] == list(range(10))
    assert first.next_cursor == "2"
    final = adapter.iter_records(source, first.next_cursor, 2)
    assert [(row.source["split"], row.source["label"], row.source["label_status"]) for row in final.records] == [
        ("test", 4, "source_labeled"), ("unlabeled", None, "unlabeled_by_source")]
    assert final.next_cursor is None
    assert len({row.id for row in first.records + final.records}) == 4
    handle = adapter.resolve_asset(source, first.records[0].assets[0].uri)
    assert handle.media_type == "image/png" and hashlib.sha256(handle.data).hexdigest() == handle.sha256
    image = np.asarray(Image.open(io.BytesIO(handle.data)).convert("RGB"))
    np.testing.assert_array_equal(image, expected_rgb)
    with pytest.raises(ValueError, match="outside split"):
        adapter.resolve_asset(source, "test/000001.png")


def test_stl10_rejects_symlink_archive_member(tmp_path: Path):
    adapter, _ = _fixture(tmp_path, symlink=True)
    with pytest.raises(ValueError, match="Unsafe STL-10 archive member"):
        adapter.prepare(adapter.plan(4, 3_000_000))


def test_stl10_retains_exact_pixels_and_checks_every_member_after_archive_removal(tmp_path):
    adapter,expected=_fixture(tmp_path)
    source=adapter.prepare(adapter.plan(4,3_000_000))
    original=adapter.resolve_asset(source,'unlabeled/000000.png').data
    adapter._archive().unlink()
    source=adapter.prepare(adapter.plan(4,3_000_000))
    assert adapter.resolve_asset(source,'unlabeled/000000.png').data==original
    np.testing.assert_array_equal(np.asarray(Image.open(io.BytesIO(original))),expected)
    (adapter._prepared()/'unlabeled_X.bin').write_bytes(b'x'*adapter.IMAGE_BYTES)
    with pytest.raises(ValueError,match='retained member checksum changed'):
        adapter.prepare(adapter.plan(4,3_000_000))
