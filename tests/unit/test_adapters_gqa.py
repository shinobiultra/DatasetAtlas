import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from dataset_atlas.adapters import get_adapter
from dataset_atlas.models import Dataset


def _fixture(tmp_path: Path, *, missing_image: bool = False) -> Dataset:
    questions = tmp_path / "questions.zip"
    images = tmp_path / "images.zip"
    source = {f"{i:08d}": {"imageId": str(i), "question": f"What is {i}?",
                            "answer": "test", "isBalanced": True,
                            "types": {"structural": "query"},
                            "semantic": [{"operation": "query", "argument": "name"}]}
              for i in range(125)}
    with zipfile.ZipFile(questions, "w") as archive:
        archive.writestr("val_balanced_questions.json", json.dumps(source))
    with zipfile.ZipFile(images, "w") as archive:
        for i in range(125 - int(missing_image)):
            archive.writestr(f"images/{i}.jpg", b"\xff\xd8\xff" + str(i).encode())
    return Dataset(id="fixture", name="Fixture", release="gqa-v1.2-val-balanced",
                   snapshot_id="test-snapshot", adapter="gqa_balanced",
                   adapter_config={
                       "questions_archive": str(questions),
                       "questions_sha256": hashlib.sha256(questions.read_bytes()).hexdigest(),
                       "images_archive": str(images),
                       "images_sha256": hashlib.sha256(images.read_bytes()).hexdigest(),
                       "prepared_root": str(tmp_path / "prepared"),
                       "expected_questions": 125})


def test_gqa_original_ids_fields_pagination_and_selective_image(tmp_path: Path):
    adapter = get_adapter(_fixture(tmp_path))
    plan = adapter.plan(100, 200_000)
    assert plan.expected_download_bytes == 0
    source = adapter.prepare(plan)
    first = adapter.iter_records(source, limit=100)
    later = adapter.iter_records(source, cursor=first.next_cursor, limit=100)
    assert len(first.records) == 100 and len(later.records) == 25
    assert later.next_cursor is None
    assert later.records[0].source["question_id"] == "00000100"
    assert later.records[0].source["semantic"][0]["operation"] == "query"
    assert later.records[0].question == "What is 100?"
    assert first.records[0].asset_ids[0] != first.records[1].asset_ids[0]
    media = adapter.resolve_asset(source, later.records[0].assets[0].uri)
    assert media.data == b"\xff\xd8\xff100" and media.media_type == "image/jpeg"
    assert adapter._index()["join_report"]["missing_images"] == 0


def test_gqa_fails_when_question_image_is_missing(tmp_path: Path):
    adapter = get_adapter(_fixture(tmp_path, missing_image=True))
    with pytest.raises(ValueError, match="no original image"):
        adapter.prepare(adapter.plan(100, 100_000))


def test_gqa_selected_preview_keeps_full_questions_and_marks_unavailable_media(tmp_path: Path):
    item = _fixture(tmp_path, missing_image=True)
    item.adapter_config["media_scope"] = "selected_preview"
    item.adapter_config["minimum_available_images"] = 124
    adapter = get_adapter(item)
    source = adapter.prepare(adapter.plan(100, 100_000))
    last = adapter.iter_records(source, cursor="124", limit=1).records[0]
    assert last.source["imageId"] == "124"
    assert last.source["media_available"] is False
    assert last.assets == []
    assert adapter._index()["join_report"]["missing_images"] == 1


def test_gqa_rejects_unsafe_asset_reference(tmp_path: Path):
    adapter = get_adapter(_fixture(tmp_path))
    source = adapter.prepare(adapter.plan(1, 100_000))
    with pytest.raises(ValueError, match="invalid GQA image reference"):
        adapter.resolve_asset(source, "../images/0.jpg")


class _FakeRange:
    """Local stand-in for an ETag-bound range reader; records every ranged read."""
    def __init__(self, path: Path, log: list):
        self._stream, self.size, self.log = path.open("rb"), path.stat().st_size, log
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self._stream.tell()
    def seek(self, offset, whence=0): return self._stream.seek(offset, whence)
    def read(self, size=-1):
        data = self._stream.read(size); self.log.append(len(data)); return data
    def close(self): self._stream.close()
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def _remote_fixture(tmp_path: Path, monkeypatch, *, missing_image: bool = False):
    from dataset_atlas.adapters.remote_media import RemoteZip
    item = _fixture(tmp_path, missing_image=missing_image)
    config = item.adapter_config
    paths = {"q": Path(config["questions_archive"]), "i": Path(config["images_archive"])}
    unique = tmp_path.name
    for key in ("questions", "images"):
        path = paths["q" if key == "questions" else "i"]
        config[f"remote_{key}"] = {"url": f"https://example.com/{unique}/{key}.zip", "bytes": path.stat().st_size,
                                   "etag": f'"{key}-etag"', "allowed_hosts": ["example.com"]}
        del config[f"{key}_archive"], config[f"{key}_sha256"]
    config["remote_cache_root"] = str(tmp_path / "remote-cache")
    log: list = []
    monkeypatch.setattr(RemoteZip, "reader", lambda self, budget: _FakeRange(paths["q" if self.spec["url"].endswith("/questions.zip") else "i"], log))
    return item, log


def test_gqa_reads_questions_and_images_by_range_without_any_local_archive(tmp_path: Path, monkeypatch):
    item, log = _remote_fixture(tmp_path, monkeypatch)
    item.adapter_config["media_scope"] = "on_demand_unverified"
    adapter = get_adapter(item)
    assert adapter.probe().exists
    source = adapter.prepare(adapter.plan(100, 200_000))
    batch = adapter.iter_records(source, cursor="100", limit=25)
    assert len(batch.records) == 25 and batch.records[0].question == "What is 100?"
    media = adapter.resolve_asset(source, batch.records[0].assets[0].uri)
    assert media.data == b"\xff\xd8\xff100"
    index = adapter._index()
    assert index["source_sha256"] == {"questions": 'remote-etag:"questions-etag"', "images": 'remote-etag:"images-etag"'}
    assert index["join_report"]["missing_images"] == 0 and log


def test_gqa_remote_join_still_fails_when_a_question_image_is_absent(tmp_path: Path, monkeypatch):
    item, _ = _remote_fixture(tmp_path, monkeypatch, missing_image=True)
    item.adapter_config["media_scope"] = "on_demand_unverified"
    adapter = get_adapter(item)
    with pytest.raises(ValueError, match="no original image"):
        adapter.prepare(adapter.plan(100, 100_000))


def test_gqa_remote_specification_must_pin_a_strong_etag(tmp_path: Path, monkeypatch):
    item, _ = _remote_fixture(tmp_path, monkeypatch)
    del item.adapter_config["remote_images"]["etag"]
    with pytest.raises(ValueError, match="strong ETag"):
        get_adapter(item).plan(1, 1000)
