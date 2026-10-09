import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
import zipfile

import pytest

from dataset_atlas.adapters import build_preview, get_adapter, resolve_dataset_asset
from dataset_atlas.models import Dataset


def dataset(tmp_path: Path, adapter: str, config: dict) -> Dataset:
    return Dataset(id="fixture", name="Fixture", release="v1", snapshot_id="sha256-pinned-fixture",
                   adapter=adapter, adapter_config=config)


@pytest.mark.parametrize("kind", ["json", "jsonl", "csv", "parquet"])
def test_structured_records_and_pagination(tmp_path: Path, kind: str):
    rows = [{"key": str(i), "text": f"text {i}", "label": "x"} for i in range(130)]
    path = tmp_path / f"rows.{kind}"
    if kind == "json":
        path.write_text(json.dumps({"items": rows}))
    elif kind == "jsonl":
        path.write_text("\n".join(json.dumps(x) for x in rows))
    elif kind == "csv":
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    else:
        pa = pytest.importorskip("pyarrow")
        import pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pylist(rows), path)
    item = dataset(tmp_path, "structured", {"path": str(path), "format": kind,
                   "records_key": "items" if kind == "json" else None,
                   "mapping": {"id": "key", "text": "text"}})
    adapter = get_adapter(item)
    plan = adapter.plan(80, 1_000_000)
    assert plan.expected_download_bytes == 0
    prepared = adapter.prepare(plan)
    first = adapter.iter_records(prepared, limit=80)
    second = adapter.iter_records(prepared, cursor=first.next_cursor, limit=80)
    assert len(first.records) == 80 and len(second.records) == 50
    assert len({r.id for r in first.records + second.records}) == 130
    assert first.records[0].id == adapter.iter_records(prepared, limit=1).records[0].id
    assert first.records[0].source["label"] == "x"


def test_asset_identity_and_safe_resolution(tmp_path: Path):
    root = tmp_path / "media"; root.mkdir()
    (root / "a.png").write_bytes(b"first")
    path = tmp_path / "records.jsonl"
    path.write_text('\n'.join(json.dumps(x) for x in [
        {"id": "q1", "image": "a.png", "question": "One?"},
        {"id": "q2", "image": "a.png", "question": "Two?"},
    ]))
    item = dataset(tmp_path, "jsonl", {"path": str(path), "media_root": str(root),
                  "mapping": {"id": "id", "media": "image", "question": "question"},
                  "fields": {"image": {"dtype": "string", "description": "source name"}}})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(2, 1_000))
    records = adapter.iter_records(source).records
    assert records[0].id != records[1].id
    assert records[0].asset_ids == records[1].asset_ids
    assert records[0].source["image"] == "a.png"
    assert adapter.resolve_asset(source, "a.png").data == b"first"
    with pytest.raises(ValueError, match="unsafe"):
        adapter.resolve_asset(source, "../outside.png")


def test_pinned_source_row_identity_preserves_duplicate_native_ids(tmp_path: Path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    rows = [{"native_id": 7, "text": "synthetic first"},
            {"native_id": 7, "text": "synthetic second"}]
    path = tmp_path / "duplicate-ids.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=1)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    config = {"path": str(path), "sha256": sha, "record_identity": "source_row",
              "mapping": {"id": "native_id", "text": "text"}}
    adapter = get_adapter(dataset(tmp_path, "parquet", config))
    source = adapter.prepare(adapter.plan(2, 10_000))
    records = list(adapter.iter_sequential(source))
    assert len({record.id for record in records}) == 2
    assert [record.source["native_id"] for record in records] == [7, 7]
    assert [record.source["_atlas_origin"]["row"] for record in records] == [0, 1]
    assert all(record.source["_atlas_origin"]["source_sha256"] == sha for record in records)
    assert adapter.iter_records(source, cursor="1", limit=1).records[0] == records[1]
    unpinned = get_adapter(dataset(tmp_path, "parquet", {**config, "sha256": None}))
    with pytest.raises(ValueError, match="pinned source checksum"):
        unpinned.iter_records(unpinned.prepare(unpinned.plan(2, 10_000)))
    other_path = tmp_path / "other-source.parquet"
    pq.write_table(pa.Table.from_pylist(rows[::-1]), other_path)
    other_sha = hashlib.sha256(other_path.read_bytes()).hexdigest()
    other = get_adapter(dataset(tmp_path, "parquet", {**config, "path": str(other_path), "sha256": other_sha}))
    other_records = list(other.iter_sequential(other.prepare(other.plan(2, 10_000))))
    assert {record.id for record in records}.isdisjoint(record.id for record in other_records)


def test_parquet_cursor_seeks_past_prior_row_groups(tmp_path: Path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    path = tmp_path / "rows.parquet"
    pq.write_table(pa.Table.from_pylist([{"key": str(i)} for i in range(130)]),
                   path, row_group_size=17)
    real_file = pq.ParquetFile
    groups_read = []

    class SpyParquetFile:
        def __init__(self, filename):
            self.delegate = real_file(filename)
            self.metadata = self.delegate.metadata

        def iter_batches(self, **kwargs):
            groups_read.extend(kwargs.get("row_groups", []))
            return self.delegate.iter_batches(**kwargs)

    monkeypatch.setattr(pq, "ParquetFile", SpyParquetFile)
    item = dataset(tmp_path, "parquet", {"path": str(path), "mapping": {"id": "key"}})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(20, 10_000))
    batch = adapter.iter_records(source, cursor="100", limit=20)
    assert [r.source["key"] for r in batch.records] == [str(i) for i in range(100, 120)]
    assert batch.next_cursor == "120"
    assert groups_read[0] == 5 and min(groups_read) >= 5
    final = adapter.iter_records(source, cursor="120", limit=20)
    assert len(final.records) == 10 and final.next_cursor is None


def test_local_media_does_not_follow_symlinks(tmp_path: Path):
    from dataset_atlas.adapters.core import _write_rooted_atomic

    root = tmp_path / "media"; root.mkdir()
    outside = tmp_path / "outside.png"; outside.write_bytes(b"outside")
    (root / "link.png").symlink_to(outside)
    rows = tmp_path / "rows.jsonl"; rows.write_text('{"id":"one"}\n')
    item = dataset(tmp_path, "jsonl", {"path": str(rows), "media_root": str(root)})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(1, 1000))
    with pytest.raises(ValueError, match="root|read"):
        adapter.resolve_asset(source, "link.png")
    (root / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        _write_rooted_atomic(root, "escape/other.png", b"cached")
    assert not (tmp_path / "other.png").exists()
    _write_rooted_atomic(root, "nested/cached.png", b"cached")
    assert (root / "nested/cached.png").read_bytes() == b"cached"


def test_archive_members_and_traversal(tmp_path: Path):
    path = tmp_path / "media.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.png", b"ok")
        archive.writestr("../unsafe.png", b"bad")
    item = dataset(tmp_path, "archive", {"path": str(path)})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(10, 100))
    with pytest.raises(ValueError, match="unsafe"):
        adapter.iter_records(source)
    with pytest.raises(ValueError, match="unsafe"):
        adapter.resolve_asset(source, "../unsafe.png")


def test_archive_folder_labels_and_balanced_preview_order(tmp_path: Path):
    path = tmp_path / "images.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for label in ("class-a", "class-b"):
            for i in range(3):
                archive.writestr(f"release/train/{label}/{i}.png", b"image")
        archive.writestr("release/README.txt", "metadata")
    item = dataset(tmp_path, "archive", {"path": str(path),
                   "path_regex": r"release/(?P<split>train|val)/(?P<label>class-[a-z]+)/\d+\.png",
                   "order": "round_robin_label", "label_names": {"class-a": "Class A", "class-b": "Class B"},
                   "label_indices": {"class-a": 0, "class-b": 1},
                   "label_index_field": "class_index_2",
                   "label_index_maps": {"class_index_parent": {"class-a": 9, "class-b": 13}},
                   "fields": {"label": {"dtype": "category", "values": ["class-a", "class-b"]}}})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(6, 1000))
    batch = adapter.iter_records(source, limit=6)
    assert [r.source["label"] for r in batch.records] == ["class-a", "class-b"] * 3
    assert batch.records[0].source["split"] == "train"
    assert batch.records[0].source["class_name"] == "Class A"
    assert [r.source["class_index_2"] for r in batch.records] == [0, 1] * 3
    assert [r.source["class_index_parent"] for r in batch.records] == [9, 13] * 3
    assert len(build_preview(item, tmp_path / "pack", 4, 1000).records) == 4


def test_archive_integer_folder_labels(tmp_path: Path):
    path = tmp_path / "images.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("release/37/a.jpg", b"image")
    item = dataset(tmp_path, "archive", {"path": str(path),
                   "path_regex": r"release/(?P<label>\d+)/[^/]+\.jpg",
                   "field_types": {"label": "integer"},
                   "constant_fields": {"variant": "MatchedFrequency"}})
    adapter = get_adapter(item)
    source = adapter.prepare(adapter.plan(1, 1000))
    assert adapter.iter_records(source).records[0].source["label"] == 37
    assert adapter.iter_records(source).records[0].source["variant"] == "MatchedFrequency"


def test_svo_pairs_attach_only_verified_local_media(tmp_path: Path):
    media_root = tmp_path / "media"; (media_root / "images").mkdir(parents=True)
    (media_root / "images/1.png").write_bytes(b"local-image")
    csv_path = tmp_path / "svo.csv"
    csv_path.write_text("sentence,pos_image_id,pos_url,neg_image_id,neg_url\n"
                        "A sentence,1,https://example.org/positive.png,2,http://example.org/negative.png\n")
    source_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest = tmp_path / "media.json"
    manifest.write_text(json.dumps({"source_revision": "v1", "source_sha256": source_sha,
                                    "images": {"1": {"status": "verified", "path": "images/1.png",
                                                     "sha256": hashlib.sha256(b"local-image").hexdigest(),
                                                     "url_sha256": hashlib.sha256(b"https://example.org/positive.png").hexdigest()}}}))
    item = dataset(tmp_path, "svo_probes", {"path": str(csv_path), "format": "csv",
                   "sha256": source_sha, "media_root": str(media_root),
                   "media_manifest": str(manifest), "mapping": {"text": "sentence"}})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(1, 1000))
    record = adapter.iter_records(source).records[0]
    assert record.text == "A sentence" and len(record.assets) == 1
    assert record.assets[0].metadata["pair_role"] == "pos"
    assert adapter.resolve_asset(source, record.assets[0].uri).data == b"local-image"
    assert record.source["neg_url"] == "http://example.org/negative.png"


def test_overlay_join_reports_missing_and_duplicate_keys(tmp_path: Path):
    base = tmp_path / "base.jsonl"; overlay = tmp_path / "overlay.jsonl"
    base.write_text('\n'.join(json.dumps(x) for x in [{"id": "a"}, {"id": "b"}]))
    overlay.write_text('\n'.join(json.dumps(x) for x in [
        {"id": "a", "label": 1}, {"id": "a", "label": 2}, {"id": "z", "label": 3},
    ]))
    item = dataset(tmp_path, "overlay", {
        "base": {"path": str(base), "format": "jsonl", "mapping": {"id": "id"}},
        "overlay": {"path": str(overlay), "format": "jsonl"},
        "join_base_key": "id", "join_overlay_key": "id", "mapping": {"id": "id"},
    })
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(10, 1000))
    report = adapter.validate(source)
    assert report.unmatched_overlay_ids == ("z",)
    assert report.multiply_matched_overlay_ids == ("a",)
    batch = adapter.iter_records(source)
    assert len(batch.records) == 2
    assert len(batch.records[0].source["overlay"]) == 2
    assert batch.records[1].source["overlay"] == []
    assert len(batch.warnings) == 2


def test_overlay_reports_duplicate_base_and_missing_join_keys(tmp_path: Path):
    base = tmp_path / "base.jsonl"; overlay = tmp_path / "overlay.jsonl"
    base.write_text('{"id":"a"}\n{"id":"a"}\n{"other":1}\n')
    overlay.write_text('{"id":"a","label":1}\n{"other":2}\n')
    item = dataset(tmp_path, "overlay", {
        "base": {"path": str(base), "format": "jsonl", "mapping": {"id": "id"}},
        "overlay": {"path": str(overlay), "format": "jsonl"},
        "join_base_key": "id", "join_overlay_key": "id", "mapping": {"id": "id"},
    })
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(10, 1000))
    report = adapter.validate(source)
    assert report.duplicate_source_ids == ("a",)
    assert report.errors == ("overlay row 1 lacks join key id", "base row 2 lacks join key id")
    assert len(adapter.iter_records(source).warnings) == 3


def test_preview_scope_and_distinct_assets(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    rows = [{"id": f"q{i}", "image": f"img{i//2}.png"} for i in range(120)]
    path.write_text("\n".join(json.dumps(x) for x in rows))
    item = dataset(tmp_path, "jsonl", {"path": str(path),
                  "population": "test split", "mapping": {"id": "id", "media": "image"}})
    pack = build_preview(item, tmp_path / "pack", limit=50, max_bytes=50_000,
                         distinct_assets=True)
    assert len(pack.records) == 50
    assert len({a for r in pack.records for a in r.asset_ids}) == 50
    assert pack.population_scope == "preview"
    assert pack.sampling["method"] == "first_per_asset_source_order"
    assert pack.sampling["population"] == "test split"
    assert pack.dataset.adapter_config == {}


def test_preview_preserves_numeric_category_values(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    path.write_text('{"label": 1}\n{"label": 0}\n')
    item = dataset(tmp_path, "jsonl", {"path": str(path),
                   "fields": {"label": {"dtype": "category", "values": [0, 1]}}})
    pack = build_preview(item, tmp_path / "pack", limit=2, max_bytes=1000)
    assert pack.fields[0].dtype == "category"
    assert pack.fields[0].values == [0, 1]
    assert isinstance(pack.fields[0].values[0], int)


def test_byte_budget_stops_reads(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    path.write_text(json.dumps({"id": "one", "text": "x" * 1000}) + "\n")
    item = dataset(tmp_path, "jsonl", {"path": str(path), "mapping": {"id": "id"}})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(1, 100))
    with pytest.raises(ValueError, match="budget"):
        adapter.iter_records(source)


def test_json_plan_rejects_whole_file_over_budget(tmp_path: Path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps([{"id": "one", "text": "x" * 1000}]))
    item = dataset(tmp_path, "json", {"path": str(path), "mapping": {"id": "id"}})
    with pytest.raises(ValueError, match="entire file"):
        get_adapter(item).plan(1, 100)


def test_hf_rows_requires_explicit_live_source_opt_in(tmp_path: Path):
    item = dataset(tmp_path, "huggingface", {"repository": "owner/repo",
                   "config": "default", "split": "train", "revision": "deadbeef"})
    with pytest.raises(ValueError, match="live"):
        get_adapter(item).plan(100, 1000)


def test_idx_full_record_and_lossless_media(tmp_path: Path):
    root = tmp_path / "idx"; root.mkdir()
    config = {"root": str(root), "counts": {"train": 2, "test": 1},
              "preparation_budget_bytes": 20_000, "splits": {}}
    for split, count in config["counts"].items():
        pixels = b"".join(bytes([i + 1]) * 784 for i in range(count))
        images = struct.pack(">IIII", 2051, count, 28, 28) + pixels
        labels = struct.pack(">II", 2049, count) + bytes(range(count))
        files = {}
        for key, data in [("images", images), ("labels", labels)]:
            name = f"{split}-{key}.gz"
            (root / name).write_bytes(gzip.compress(data))
            files[key] = name
            files[f"{key}_md5"] = hashlib.md5((root / name).read_bytes(), usedforsecurity=False).hexdigest()
        config["splits"][split] = files
    item = dataset(tmp_path, "idx", config)
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(3, 20_000))
    first = adapter.iter_records(source, limit=2)
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=2)
    assert [r.source["split"] for r in first.records + second.records] == ["train", "train", "test"]
    handle = resolve_dataset_asset(item, first.records[0].assets[0].uri)
    assert handle.media_type == "image/png" and handle.data.startswith(b"\x89PNG")


def test_idx_pinned_character_mapping_and_upright_transpose(tmp_path: Path):
    from PIL import Image
    root = tmp_path / "emnist"; root.mkdir()
    pixels = bytearray(784); pixels[1] = 255  # source coordinate (1, 0)
    blobs = {"images": struct.pack(">IIII", 2051, 1, 28, 28) + pixels,
             "labels": struct.pack(">II", 2049, 1) + bytes([1])}
    files = {}
    for key, blob in blobs.items():
        name = f"train-{key}.gz"; compressed = gzip.compress(blob)
        (root / name).write_bytes(compressed)
        files[key] = name
        files[f"{key}_md5"] = hashlib.md5(compressed, usedforsecurity=False).hexdigest()
    mapping = b"0 65\n1 66\n"
    (root / "mapping.txt").write_bytes(mapping)
    item = dataset(tmp_path, "idx", {"root": str(root), "counts": {"train": 1},
                   "splits": {"train": files}, "mapping_file": "mapping.txt", "class_count": 2,
                   "mapping_sha256": hashlib.sha256(mapping).hexdigest(),
                   "pixel_transform": "transpose"})
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(1, 10_000))
    record = adapter.iter_records(source).records[0]
    assert record.source["label"] == 1 and record.source["character"] == "B"
    assert record.source["ascii_code"] == 66
    assert record.assets[0].metadata["display_transform"] == "transpose"
    data = adapter.resolve_asset(source, record.assets[0].uri).data
    with Image.open(io.BytesIO(data)) as image:
        assert image.getpixel((0, 1)) == 255 and image.getpixel((1, 0)) == 0


def test_cifar_binary_archive_reader(tmp_path: Path, monkeypatch):
    from dataset_atlas.adapters.binary import CIFARBinaryAdapter
    monkeypatch.setattr(CIFARBinaryAdapter, "BATCH_BYTES", 2 * 3073)
    archive_path = tmp_path / "cifar.tar.gz"
    row = bytes([3]) + bytes(range(256)) * 12
    files = {f"data_batch_{i}.bin": row * 2 for i in range(1, 6)}
    files["test_batch.bin"] = row * 2
    files["batches.meta.txt"] = "\n".join(f"class{i}" for i in range(10)).encode() + b"\n"
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo("cifar-10-batches-bin/" + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    item = dataset(tmp_path, "cifar_binary", {
        "archive": str(archive_path), "prepared_root": str(tmp_path / "prepared"),
        "archive_md5": hashlib.md5(archive_path.read_bytes(), usedforsecurity=False).hexdigest(),
        "preparation_budget_bytes": 100_000,
    })
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(2, 100_000))
    batch = adapter.iter_records(source, limit=2)
    assert len(batch.records) == 2 and batch.records[0].source["class_name"] == "class3"
    media = adapter.resolve_asset(source, batch.records[0].assets[0].uri)
    assert media.data.startswith(b"\x89PNG")


def test_cifar100_binary_preserves_both_labels(tmp_path: Path, monkeypatch):
    from dataset_atlas.adapters.binary import CIFAR100BinaryAdapter
    monkeypatch.setattr(CIFAR100BinaryAdapter, "TRAIN_COUNT", 2)
    monkeypatch.setattr(CIFAR100BinaryAdapter, "TEST_COUNT", 1)
    archive_path = tmp_path / "cifar100.tar.gz"
    row = bytes([4, 37]) + bytes(range(256)) * 12
    files = {"train.bin": row * 2, "test.bin": row,
             "coarse_label_names.txt": ("\n".join(f"coarse{i}" for i in range(20)) + "\n").encode(),
             "fine_label_names.txt": ("\n".join(f"fine{i}" for i in range(100)) + "\n").encode()}
    with tarfile.open(archive_path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo("cifar-100-binary/" + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    item = dataset(tmp_path, "cifar100_binary", {
        "archive": str(archive_path), "prepared_root": str(tmp_path / "prepared"),
        "archive_md5": hashlib.md5(archive_path.read_bytes(), usedforsecurity=False).hexdigest(),
        "preparation_budget_bytes": 30_000,
    })
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(3, 30_000))
    records = adapter.iter_records(source, limit=2).records + adapter.iter_records(source, "2", 2).records
    assert len(records) == 3
    assert [r.source["split"] for r in records] == ["train", "train", "test"]
    assert records[0].source["coarse_label"] == 4 and records[0].source["fine_label"] == 37
    assert records[0].source["coarse_class_name"] == "coarse4"
    assert records[0].source["fine_class_name"] == "fine37"
    assert adapter.resolve_asset(source, records[0].assets[0].uri).data.startswith(b"\x89PNG")


def test_full_clevr_zip_streams_questions_and_selects_media(tmp_path: Path):
    archive_path = tmp_path / "CLEVR_v1.0.zip"
    counts = {"train": 110, "val": 10, "test": 5}
    with zipfile.ZipFile(archive_path, "w") as archive:
        for split, count in counts.items():
            rows = [{"question_index": i, "image_filename": f"CLEVR_{split}_{i:06d}.png",
                     "question": f"Question {i}?", "answer": "yes", "program": []}
                    for i in range(count)]
            archive.writestr(f"CLEVR_v1.0/questions/CLEVR_{split}_questions.json",
                             json.dumps({"info": {"release": "v1"}, "questions": rows}))
            for i in range(count):
                archive.writestr(f"CLEVR_v1.0/images/{split}/CLEVR_{split}_{i:06d}.png",
                                 b"\x89PNG\r\n\x1a\nfixture")
    item = dataset(tmp_path, "clevr_full", {
        "archive": str(archive_path), "prepared_root": str(tmp_path / "prepared"),
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    })
    adapter = get_adapter(item)
    source = adapter.prepare(adapter.plan(120, 100_000))
    first = adapter.iter_records(source, limit=100)
    later = adapter.iter_records(source, cursor=first.next_cursor, limit=25)
    assert len(first.records) == 100 and len(later.records) == 25
    assert first.records[0].source["image_filename"] == "CLEVR_train_000000.png"
    assert later.records[10].source["split"] == "val"
    assert adapter.iter_records(source, cursor="124", limit=10).records[0].source["split"] == "test"
    media = adapter.resolve_asset(source, later.records[10].assets[0].uri)
    assert media.data.startswith(b"\x89PNG") and media.source_ref.startswith("images/val/")
    with pytest.raises(ValueError, match="invalid CLEVR asset"):
        adapter.resolve_asset(source, "../images/val/CLEVR_val_000000.png")


def test_vqa_v2_joins_original_answers_and_coco_2014_images(tmp_path: Path):
    questions_zip = tmp_path / "questions.zip"
    annotations_zip = tmp_path / "annotations.zip"
    images_zip = tmp_path / "val2014.zip"
    questions = [{"question_id": i, "image_id": 10 if i < 3 else 11,
                  "question": f"Question {i}?"} for i in (1, 2, 3)]
    annotations = [{"question_id": q["question_id"], "image_id": q["image_id"],
                    "question_type": "what", "answer_type": "other",
                    "multiple_choice_answer": "cat",
                    "answers": [{"answer_id": j, "answer": "cat", "answer_confidence": "yes"}
                                for j in range(1, 11)]} for q in questions]
    with zipfile.ZipFile(questions_zip, "w") as archive:
        archive.writestr("v2_OpenEnded_mscoco_val2014_questions.json",
                         json.dumps({"data_subtype": "val2014", "questions": questions}))
    with zipfile.ZipFile(annotations_zip, "w") as archive:
        archive.writestr("v2_mscoco_val2014_annotations.json",
                         json.dumps({"data_subtype": "val2014", "annotations": annotations}))
    with zipfile.ZipFile(images_zip, "w") as archive:
        for image_id in (10, 11):
            archive.writestr(f"val2014/COCO_val2014_{image_id:012d}.jpg", b"\xff\xd8\xffimage")
    item = dataset(tmp_path, "vqa_v2", {
        "questions_archive": str(questions_zip), "annotations_archive": str(annotations_zip),
        "images_archive": str(images_zip), "prepared_root": str(tmp_path / "prepared"),
        "questions_sha256": hashlib.sha256(questions_zip.read_bytes()).hexdigest(),
        "annotations_sha256": hashlib.sha256(annotations_zip.read_bytes()).hexdigest(),
        "images_sha256": hashlib.sha256(images_zip.read_bytes()).hexdigest(),
        "expected_questions": 3,
    })
    adapter = get_adapter(item); source = adapter.prepare(adapter.plan(2, 100_000))
    first = adapter.iter_records(source, limit=2)
    second = adapter.iter_records(source, cursor=first.next_cursor, limit=2)
    assert len(first.records) == 2 and len(second.records) == 1
    assert first.records[0].asset_ids == first.records[1].asset_ids
    assert first.records[0].source["multiple_choice_answer"] == "cat"
    assert len(first.records[0].source["answers"]) == 10
    assert adapter.resolve_asset(source, second.records[0].assets[0].uri).media_type == "image/jpeg"
    assert json.loads((tmp_path / "prepared" / "index.json").read_text())["join_report"]["unmatched_annotations"] == 0


def _vqa_fixture(tmp_path: Path, remote: bool):
    questions_zip, annotations_zip, images_zip = tmp_path / "q.zip", tmp_path / "a.zip", tmp_path / "val2014.zip"
    questions = [{"question_id": i, "image_id": 10 if i < 3 else 11, "question": f"Question {i}?"} for i in (1, 2, 3)]
    annotations = [{"question_id": q["question_id"], "image_id": q["image_id"], "question_type": "what", "answer_type": "other",
                    "multiple_choice_answer": "cat", "answers": [{"answer_id": j, "answer": "cat", "answer_confidence": "yes"} for j in range(1, 11)]}
                   for q in questions]
    with zipfile.ZipFile(questions_zip, "w") as archive:
        archive.writestr("v2_OpenEnded_mscoco_val2014_questions.json", json.dumps({"data_subtype": "val2014", "questions": questions}))
    with zipfile.ZipFile(annotations_zip, "w") as archive:
        archive.writestr("v2_mscoco_val2014_annotations.json", json.dumps({"data_subtype": "val2014", "annotations": annotations}))
    with zipfile.ZipFile(images_zip, "w") as archive:
        for image_id in (10, 11):
            archive.writestr(f"val2014/COCO_val2014_{image_id:012d}.jpg", b"\xff\xd8\xff" + f"original {image_id}".encode())
    config = {"questions_archive": str(questions_zip), "annotations_archive": str(annotations_zip), "prepared_root": str(tmp_path / "prepared"),
              "questions_sha256": hashlib.sha256(questions_zip.read_bytes()).hexdigest(),
              "annotations_sha256": hashlib.sha256(annotations_zip.read_bytes()).hexdigest(), "expected_questions": 3}
    if remote:
        config.update(remote_images={"url": f"https://example.com/{tmp_path.name}/val2014.zip", "bytes": images_zip.stat().st_size,
                                     "etag": '"fixture-etag"', "allowed_hosts": ["example.com"]},
                      remote_cache_root=str(tmp_path / "remote-cache"))
    else:
        config.update(images_archive=str(images_zip), images_sha256=hashlib.sha256(images_zip.read_bytes()).hexdigest())
    return config, images_zip


class _FakeRange:
    """Stands in for an ETag-bound HTTPS range reader over a local ZIP, counting what it is asked for."""
    def __init__(self, path: Path, requested: list):
        self._stream, self.size, self.requested = path.open("rb"), path.stat().st_size, requested
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self._stream.tell()
    def seek(self, offset, whence=0): return self._stream.seek(offset, whence)
    def read(self, size=-1):
        start = self._stream.tell(); data = self._stream.read(size); self.requested.append((start, len(data))); return data
    def close(self): self._stream.close()
    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def test_vqa_v2_reads_images_by_range_when_the_archive_is_not_local(tmp_path: Path, monkeypatch):
    from dataset_atlas.adapters.remote_media import RemoteZip
    config, images_zip = _vqa_fixture(tmp_path, remote=True)
    requested: list = []
    monkeypatch.setattr(RemoteZip, "reader", lambda self, budget: _FakeRange(images_zip, requested))
    adapter = get_adapter(dataset(tmp_path, "vqa_v2", config))
    assert adapter.probe().exists  # no local image archive is required
    source = adapter.prepare(adapter.plan(3, 100_000))
    batch = adapter.iter_records(source, limit=3)
    assert len(batch.records) == 3 and batch.records[0].source["question"] == "Question 1?"
    assert batch.records[0].assets[0].metadata["media_access"] == "remote_zip_range"
    assert batch.records[0].assets[0].metadata["source_etag"] == '"fixture-etag"'
    media = adapter.resolve_asset(source, batch.records[2].assets[0].uri)
    assert media.data == b"\xff\xd8\xfforiginal 11" and media.media_type == "image/jpeg"
    # The index records that the images were bound by ETag rather than by a whole-file hash.
    index = json.loads((tmp_path / "prepared" / "index.json").read_text())
    assert index["source_sha256"]["images"] == 'remote-etag:"fixture-etag"' and index["join_report"]["missing_images"] == 0
    assert requested, "images must be read through the range reader"


def test_remote_and_local_images_give_identical_records(tmp_path: Path, monkeypatch):
    """Where the archive lives must not change record identity: colleagues share selections with the maintainer."""
    from dataset_atlas.adapters.remote_media import RemoteZip
    local_dir, remote_dir = tmp_path / "local", tmp_path / "remote"
    local_dir.mkdir(); remote_dir.mkdir()
    local_config, _ = _vqa_fixture(local_dir, remote=False)
    remote_config, images_zip = _vqa_fixture(remote_dir, remote=True)
    monkeypatch.setattr(RemoteZip, "reader", lambda self, budget: _FakeRange(images_zip, []))
    ids = []
    for directory, config in ((local_dir, local_config), (remote_dir, remote_config)):
        adapter = get_adapter(dataset(directory, "vqa_v2", config))
        source = adapter.prepare(adapter.plan(3, 100_000))
        ids.append([(r.id, r.asset_ids, r.source["question"]) for r in adapter.iter_records(source, limit=3).records])
    assert ids[0] == ids[1]


def test_remote_images_without_a_pinned_etag_are_refused(tmp_path: Path):
    config, _ = _vqa_fixture(tmp_path, remote=True)
    del config["remote_images"]["etag"]
    adapter = get_adapter(dataset(tmp_path, "vqa_v2", config))
    with pytest.raises(ValueError, match="strong ETag"):
        adapter.plan(1, 1000)


def test_full_clevr_reads_questions_and_media_by_range_with_identical_records(tmp_path: Path, monkeypatch):
    from dataset_atlas.adapters.remote_media import RemoteZip
    archive_path = tmp_path / "CLEVR_v1.0.zip"
    counts = {"train": 110, "val": 10, "test": 5}
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for split, count in counts.items():
            rows = [{"question_index": i, "image_filename": f"CLEVR_{split}_{i:06d}.png", "question": f"Question {i}?", "answer": "yes", "program": []}
                    for i in range(count)]
            archive.writestr(f"CLEVR_v1.0/questions/CLEVR_{split}_questions.json", json.dumps({"info": {"release": "v1"}, "questions": rows}))
            for i in range(count):
                archive.writestr(f"CLEVR_v1.0/images/{split}/CLEVR_{split}_{i:06d}.png", b"\x89PNG\r\n\x1a\nfixture " + f"{split}{i}".encode())
    local = get_adapter(dataset(tmp_path, "clevr_full", {
        "archive": str(archive_path), "prepared_root": str(tmp_path / "prepared-local"),
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest()}))
    local_source = local.prepare(local.plan(120, 100_000))
    local_rows = local.iter_records(local_source, limit=125).records

    class Range:
        def __init__(self): self._s, self.size = archive_path.open("rb"), archive_path.stat().st_size
        def readable(self): return True
        def seekable(self): return True
        def tell(self): return self._s.tell()
        def seek(self, o, w=0): return self._s.seek(o, w)
        def read(self, n=-1): return self._s.read(n)
        def close(self): self._s.close()
        def __enter__(self): return self
        def __exit__(self, *e): self.close()
    monkeypatch.setattr(RemoteZip, "reader", lambda self, budget: Range())
    remote = get_adapter(dataset(tmp_path, "clevr_full", {
        "remote_archive": {"url": f"https://example.com/{tmp_path.name}/CLEVR_v1.0.zip", "bytes": archive_path.stat().st_size,
                           "etag": '"clevr-etag"', "allowed_hosts": ["example.com"]},
        "remote_cache_root": str(tmp_path / "remote-cache"), "prepared_root": str(tmp_path / "prepared-remote")}))
    assert remote.probe().exists
    remote_source = remote.prepare(remote.plan(120, 100_000))
    remote_rows = remote.iter_records(remote_source, limit=125).records
    assert [(r.id, r.asset_ids, r.source["split"], r.question) for r in local_rows] == [(r.id, r.asset_ids, r.source["split"], r.question) for r in remote_rows]
    assert json.loads((tmp_path / "prepared-remote" / "questions-index.json").read_text())["archive_sha256"] == 'remote-etag:"clevr-etag"'
    assert remote.resolve_asset(remote_source, remote_rows[112].assets[0].uri).data == b"\x89PNG\r\n\x1a\nfixture val2"


def test_structured_archive_reads_media_by_range_when_the_archive_is_not_local(tmp_path: Path, monkeypatch):
    from dataset_atlas.adapters.remote_media import RemoteZip
    archive_path = tmp_path / "val2014.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("val2014/COCO_val2014_000000000001.jpg", b"\xff\xd8\xfforiginal one")
    records = tmp_path / "records.jsonl"
    records.write_text(json.dumps({"source_id": "a:1", "question": "Is there a cat?", "media_path": "val2014/COCO_val2014_000000000001.jpg"}) + "\n")
    class Range:
        def __init__(self): self._s, self.size = archive_path.open("rb"), archive_path.stat().st_size
        def readable(self): return True
        def seekable(self): return True
        def tell(self): return self._s.tell()
        def seek(self, o, w=0): return self._s.seek(o, w)
        def read(self, n=-1): return self._s.read(n)
        def close(self): self._s.close()
        def __enter__(self): return self
        def __exit__(self, *e): self.close()
    monkeypatch.setattr(RemoteZip, "reader", lambda self, budget: Range())
    item = dataset(tmp_path, "structured_archive", {
        "path": str(records), "format": "jsonl", "mapping": {"id": "source_id", "question": "question", "media": "media_path"},
        "remote_media_archive": {"url": f"https://example.com/{tmp_path.name}/val2014.zip", "bytes": archive_path.stat().st_size,
                                 "etag": '"val2014-etag"', "allowed_hosts": ["example.com"]},
        "remote_cache_root": str(tmp_path / "remote-cache")})
    adapter = get_adapter(item)
    source = adapter.prepare(adapter.plan(1, 100_000))
    record = adapter.iter_records(source, limit=1).records[0]
    media = adapter.resolve_asset(source, record.assets[0].uri)
    assert media.data == b"\xff\xd8\xfforiginal one" and media.media_type == "image/jpeg"
    with pytest.raises(ValueError):
        adapter.resolve_asset(source, "../val2014/COCO_val2014_000000000001.jpg")
