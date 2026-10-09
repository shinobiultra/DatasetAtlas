import csv
import hashlib
import zipfile
from pathlib import Path
import pytest
from dataset_atlas.adapters.vqa_constraints import (
    VQAConstraintsAdapter,
    native_unicode_name,
)
from dataset_atlas.models import Dataset


def fixture(tmp_path):
    csv_path = tmp_path / "labels.csv"
    with csv_path.open("w") as f:
        writer = csv.DictWriter(
            f, fieldnames=["", "question", "main_entity", "image_url"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "": "0",
                "question": "Native question",
                "main_entity": "This person",
                "image_url": "./A photo of José",
            }
        )
    path = tmp_path / "images.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("images/A photo of Jose\u0301/Image_2.jpg", b"2")
        z.writestr("images/A photo of Jose\u0301/Image_1.jpg", b"1")
        z.writestr("images/Unannotated/Image_1.jpg", b"auxiliary")
    d = Dataset(
        id="constraints",
        name="Fixture",
        release="r",
        snapshot_id="s",
        adapter="vqa_constraints",
        adapter_config={
            "annotations_path": str(csv_path),
            "images_path": str(path),
            "source_files": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            ],
            "annotations": [
                {"path_key": "annotations_path", "format": "csv", "split": "known"}
            ],
            "mapping": {"question": "question"},
            "local_archives": {"known": {"path_key": "images_path"}},
            "directory_sources": {"known": {"archive": "known", "prefix": "images"}},
        },
    )
    return VQAConstraintsAdapter(d), path


def test_all_native_candidate_images_and_constraint_text_are_retained(tmp_path):
    a, _ = fixture(tmp_path)
    report = a.validate_media(100000)
    row = a.iter_records(a.prepare(a.plan(10, 100000))).records[0]
    assert (
        row.question == "Native question" and row.source["main_entity"] == "This person"
    )
    assert row.source["image_url"] == "./A photo of José"
    assert row.source["_atlas_native_columns"] == {"": "0"}
    assert [x.metadata["condition"] for x in row.assets] == [
        "Image_1.jpg",
        "Image_2.jpg",
    ]
    assert "Jose\u0301" in row.assets[0].uri
    assert report["unannotated_native_image_directories"] == {
        "known": ["images/Unannotated"]
    }


def test_missing_directory_and_ambiguous_normalization_fail(tmp_path):
    a, path = fixture(tmp_path)
    a.config["directory_sources"]["known"]["prefix"] = "wrong"
    with pytest.raises(ValueError, match="root"):
        a._rows()
    a, path = fixture(tmp_path)
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("images/A photo of José/another.jpg", b"3")
    with pytest.raises(ValueError, match="ambiguous"):
        a._rows()


def test_unflagged_utf8_filename_decoding_is_exact_and_reversible():
    raw = "images/A photo of Jose\u0301/Image_1.jpg".encode("utf-8").decode("cp437")
    info = zipfile.ZipInfo(raw)
    assert native_unicode_name(info) == "images/A photo of José/Image_1.jpg"
    info.flag_bits = 0x800
    assert native_unicode_name(info) == raw


def test_blank_native_csv_header_produces_a_valid_inspectable_preview(tmp_path):
    from dataset_atlas.adapters import build_preview
    a, _ = fixture(tmp_path)
    pack = build_preview(a.dataset, tmp_path/'preview', limit=1, max_bytes=100000, include_media=False)
    assert pack.records[0].source['_atlas_native_columns'] == {'': '0'}
    assert all(field.id != 'source.' for field in pack.fields)
