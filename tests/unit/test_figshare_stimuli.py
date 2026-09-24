"""Pinned media inventory must never resolve unlisted or modified files."""

import hashlib

import pytest

from dataset_atlas.adapters.core import PreparationPlan, get_adapter
from dataset_atlas.models import Dataset


def test_figshare_v1_inventory_and_media_integrity(tmp_path):
    files = []
    config = {}
    for number in range(7):
        name = f"stimulus-{number}.{'mp4' if number < 2 else 'jpg'}"
        path = tmp_path / name
        payload = f"original-{number}".encode()
        path.write_bytes(payload)
        key = f"file_{number}"
        config[key] = str(path)
        files.append({"figshare_file_id": number, "name": name,
                      "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                      "md5": hashlib.md5(payload).hexdigest(),
                      "modality": "video" if number < 2 else "image", "path_key": key})
    config["media_files"] = files
    dataset = Dataset(id="stimuli", name="Stimuli", release="figshare-5483680-v1",
                      snapshot_id="s1", adapter="figshare_stimuli", adapter_config=config)
    adapter = get_adapter(dataset)
    plan = PreparationPlan(dataset.id, dataset.release, None, 7, 10_000, 0, 10_000)
    source = adapter.prepare(plan)
    batch = adapter.iter_records(source, limit=7)
    assert len(batch.records) == 7 and batch.next_cursor is None
    assert {record.unit for record in batch.records} == {"asset"}
    assert {record.source["figshare_file_id"] for record in batch.records} == set(range(7))
    assert adapter.resolve_asset(source, files[0]["name"]).data == b"original-0"
    with pytest.raises(ValueError, match="absent"):
        adapter.resolve_asset(source, "other.jpg")
    (tmp_path / files[0]["name"]).write_bytes(b"changed!!")
    with pytest.raises(ValueError, match="checksum"):
        adapter.resolve_asset(source, files[0]["name"])
