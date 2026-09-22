"""Joined DOCCI source identity, pagination, media, and archive boundaries."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

from PIL import Image
import pytest

from dataset_atlas.adapters.docci import DocciAdapter
from dataset_atlas.models import Dataset


def _fixture(tmp_path: Path, *, bad_member: str | None = None, missing: bool = False) -> DocciAdapter:
    tmp_path.mkdir(parents=True, exist_ok=True)
    descriptions = tmp_path / "docci_descriptions.jsonlines"
    rows = [
        {"example_id": "qual_dev_00000", "split": "qual_dev", "image_file": "qual_dev_00000.jpg",
         "description": "A small green square."},
        {"example_id": "test_00001", "split": "test", "image_file": "test_00001.jpg",
         "description": "A different blue square."},
    ]
    descriptions.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    pixels = io.BytesIO()
    Image.new("RGB", (3, 2), (20, 140, 40)).save(pixels, format="JPEG")
    archive = tmp_path / "docci_images.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        directory = tarfile.TarInfo("images")
        directory.type = tarfile.DIRTYPE
        output.addfile(directory)
        for row in rows[:1] if missing else rows:
            data = pixels.getvalue()
            member = tarfile.TarInfo("images/" + row["image_file"])
            member.size = len(data)
            output.addfile(member, io.BytesIO(data))
        if bad_member:
            member = tarfile.TarInfo(bad_member)
            member.type = tarfile.SYMTYPE
            member.linkname = "../../outside.jpg"
            output.addfile(member)
    dataset = Dataset(
        id="docci", name="DOCCI", release="test-joined-sources", snapshot_id="test-snapshot",
        adapter="docci", adapter_config={
            "path": str(descriptions), "format": "jsonl",
            "sha256": hashlib.sha256(descriptions.read_bytes()).hexdigest(),
            "images_archive": str(archive),
            "images_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "prepared_root": str(tmp_path / "prepared"), "expected_records": 2,
            "mapping": {"id": "example_id", "text": "description", "media": "image_file"},
        },
    )
    return DocciAdapter(dataset)


def test_docci_joined_full_pagination_and_original_media(tmp_path: Path):
    adapter = _fixture(tmp_path)
    with pytest.raises(ValueError, match="byte budget"):
        adapter.prepare(adapter.plan(2, 1))
    source = adapter.prepare(adapter.plan(2, 100_000))
    first = adapter.iter_records(source, None, 1)
    second = adapter.iter_records(source, first.next_cursor, 1)
    assert first.next_cursor == "1" and second.next_cursor is None
    assert len({row.id for row in first.records + second.records}) == 2
    assert first.records[0].text == "A small green square."
    assert first.records[0].source["image_file"] == first.records[0].assets[0].uri
    assert second.records[0].source["split"] == "test"
    for record in first.records + second.records:
        handle = adapter.resolve_asset(source, record.assets[0].uri)
        assert handle.media_type == "image/jpeg"
        assert Image.open(io.BytesIO(handle.data)).size == (3, 2)
        assert hashlib.sha256(handle.data).hexdigest() == handle.sha256
    # A prepared copy is reused only after both pinned source hashes and the
    # complete filename join have been checked again.
    adapter.prepare(adapter.plan(2, 100_000))
    with pytest.raises(ValueError, match="invalid DOCCI image reference"):
        adapter.resolve_asset(source, "../../outside.jpg")
    image = tmp_path / "prepared/images/qual_dev_00000.jpg"
    image.write_bytes(b"changed")
    with pytest.raises(ValueError, match="differs from pinned archive"):
        adapter.resolve_asset(source, "qual_dev_00000.jpg")


def test_docci_rejects_missing_and_symlinked_archive_members(tmp_path: Path):
    missing = _fixture(tmp_path / "missing", missing=True)
    with pytest.raises(ValueError, match="lacks 1 description images"):
        missing.prepare(missing.plan(2, 100_000))
    linked = _fixture(tmp_path / "linked", bad_member="images/escape.jpg")
    with pytest.raises(ValueError, match="unexpected DOCCI archive member"):
        linked.prepare(linked.plan(2, 100_000))
