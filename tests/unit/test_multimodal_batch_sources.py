"""Pinned author-source checks for MathVision, MM-Vet v1, and LLaVA-Bench."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from PIL import Image

from dataset_atlas.adapters import get_adapter, resolve_dataset_asset
from dataset_atlas.registry import Registry

ROOT = Path(__file__).parents[2]
EXPECTED = {"mathvision": (3040, 100, 100), "mm-vet": (218, 100, 100),
            "llava-bench": (60, 60, 24)}


@pytest.mark.parametrize("dataset_id,expected", EXPECTED.items())
def test_pinned_complete_source_preview_and_asset(dataset_id, expected):
    count, preview_count, unique_images = expected
    dataset = Registry(ROOT).dataset(dataset_id)
    source = Path(dataset.adapter_config["path"])
    if not source.exists():
        pytest.skip(f"{dataset_id} original source not installed locally")
    receipt = json.loads((ROOT / "reports" / f"{dataset_id}-source.json").read_text())
    assert dataset.coverage.total_count == count
    for original in receipt["original_files"]:
        path = ROOT / original["file"]
        assert path.stat().st_size == original["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original["sha256"]
    adapter = get_adapter(dataset)
    prepared = adapter.prepare(adapter.plan(101, 100_000_000))
    first = adapter.iter_records(prepared, limit=101)
    last = adapter.iter_records(prepared, cursor=str(count - 1), limit=101)
    assert len(first.records) == 101 if count > 101 else len(first.records) == count
    assert len(last.records) == 1 and last.next_cursor is None
    assert last.records[0].assets and last.records[0].assets[0].modality == "image"
    pack = Registry(ROOT).pack(dataset_id)
    assert len(pack.records) == preview_count
    assert len({record.assets[0].id for record in pack.records}) == unique_images
    assert receipt["preview_sha256"] == hashlib.sha256((ROOT / receipt["preview_pack"]).read_bytes()).hexdigest()
    for record in (pack.records[0], pack.records[-1]):
        media = resolve_dataset_asset(dataset, record.assets[0].uri)
        assert hashlib.sha256(media.data).hexdigest() == media.sha256
        with Image.open(BytesIO(media.data)) as image:
            image.verify()


def test_mathvision_full_test_split_and_mini_overlap_are_not_conflated(require_local_files):
    require_local_files('work/packs/mathvision/pack.json')
    dataset = Registry(ROOT).dataset("mathvision")
    full = pq.read_table(dataset.adapter_config["path"], columns=["id", "question", "decoded_image"])
    mini = pq.read_table(ROOT / "work/sources/mathvision/original/data/testmini-00000-of-00001-f8ff70fcb2f29b1d.parquet",
                         columns=["id"])
    assert full.num_rows == 3040 and mini.num_rows == 304
    assert {item.as_py() for item in mini.column("id")} <= {item.as_py() for item in full.column("id")}
    assert all(item is not None and item["bytes"] for item in full.column("decoded_image").to_pylist())
    first = Registry(ROOT).pack("mathvision").records[0]
    assert first.question == full.column("question")[0].as_py()
    assert first.source["answer"] and first.assets[0].uri.startswith("embedded/")


def test_mmvet_v1_source_fields_and_llava_context_join(require_local_files):
    require_local_files('work/packs/mm-vet/pack.json', 'work/packs/llava-bench/pack.json')
    mm = [json.loads(line) for line in (ROOT / "work/sources/mm-vet/records.jsonl").open()]
    assert len(mm) == 218 and len({row["media_path"] for row in mm}) == 200
    assert Counter(row["bard_set"] for row in mm) == {True: 168, False: 50}
    assert all(row["answer"] and row["capability"] and row["imagesource"] for row in mm)
    llava = [json.loads(line) for line in (ROOT / "work/sources/llava-bench/records.jsonl").open()]
    assert len(llava) == 60 and len({row["media_path"] for row in llava}) == 24
    source_questions = [json.loads(line) for line in (ROOT / "work/sources/llava-bench/original/questions.jsonl").open()]
    contexts = {row["image"]: row for row in
                (json.loads(line) for line in (ROOT / "work/sources/llava-bench/original/context.jsonl").open())}
    assert all(row["question_id"] == upstream["question_id"] and row["question"] == upstream["text"]
               and row["context_caption"] == contexts[upstream["image"]]["caption"]
               for row, upstream in zip(llava, source_questions))
