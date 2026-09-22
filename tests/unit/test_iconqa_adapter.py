"""IconQA question/media joins, all three tasks, and unsafe ZIP boundaries."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest

from dataset_atlas.adapters.iconqa import IconQAAdapter
from dataset_atlas.models import Dataset


def _fixture(tmp_path: Path, *, extra_media: bool = False, broken_choice: bool = False) -> IconQAAdapter:
    tmp_path.mkdir(parents=True, exist_ok=True)
    image = io.BytesIO()
    Image.new("RGB", (3, 2), (31, 80, 200)).save(image, format="PNG")
    archive = tmp_path / "iconqa_data.zip"
    counts = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("iconqa_data/LICENSE.md", "Creative Commons Attribution-NonCommercial-ShareAlike 4.0")
        output.writestr("iconqa_data/metadata.json", json.dumps({"version": "v1", "license": "CC BY-NC-SA 4.0"}))
        for split in ("train", "val", "test"):
            for task in ("choose_img", "choose_txt", "fill_in_blank"):
                prefix = f"iconqa_data/iconqa/{split}/{task}/1/"
                data = {"question": "What is shown?", "ques_type": task,
                        "grade": "grade1", "label": "L1"}
                if task == "choose_img":
                    data.update({"choices": ["choice_0.png", "choice_1.png"], "answer": 0})
                    output.writestr(prefix + "choice_0.png", image.getvalue())
                    if not broken_choice:
                        output.writestr(prefix + "choice_1.png", image.getvalue())
                elif task == "choose_txt":
                    data.update({"choices": ["one", "two"], "answer": 1})
                else:
                    data["answer"] = "one"
                output.writestr(prefix + "image.png", image.getvalue())
                output.writestr(prefix + "data.json", json.dumps(data))
                counts[f"{split}:{task}"] = 1
        if extra_media:
            output.writestr("iconqa_data/iconqa/train/choose_txt/1/choice_9.png", image.getvalue())
    dataset = Dataset(
        id="iconqa", name="IconQA", release="test-v1", snapshot_id="test-snapshot",
        adapter="iconqa", adapter_config={
            "archive": str(archive), "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "prepared_root": str(tmp_path / "prepared"), "expected_records": 9,
            "expected_counts": counts,
        },
    )
    return IconQAAdapter(dataset)


def test_iconqa_question_assets_and_full_pagination(tmp_path: Path):
    adapter = _fixture(tmp_path)
    with pytest.raises(ValueError, match="byte budget"):
        adapter.plan(9, 1)
    source = adapter.prepare(adapter.plan(9, 100_000))
    rows = []
    cursor = None
    while True:
        batch = adapter.iter_records(source, cursor, 2)
        rows.extend(batch.records)
        cursor = batch.next_cursor
        if not cursor:
            break
    assert len(rows) == len({row.id for row in rows}) == 9
    assert {row.source["subtask"] for row in rows} == {"choose_img", "choose_txt", "fill_in_blank"}
    image_choice = next(row for row in rows if row.source["subtask"] == "choose_img")
    assert len(image_choice.assets) == 3
    assert image_choice.choices == ["choice_0.png", "choice_1.png"]
    assert image_choice.source["answer"] == 0
    assert len(next(row for row in rows if row.source["subtask"] == "choose_txt").assets) == 1
    assert isinstance(next(row for row in rows if row.source["subtask"] == "fill_in_blank").source["answer"], str)
    handle = adapter.resolve_asset(source, image_choice.assets[1].uri)
    assert handle.media_type == "image/png" and Image.open(io.BytesIO(handle.data)).size == (3, 2)
    adapter.prepare(adapter.plan(9, 100_000))
    with pytest.raises(ValueError, match="invalid IconQA media reference"):
        adapter.resolve_asset(source, "../choice_0.png")


@pytest.mark.parametrize("change", ["extra_media", "broken_choice"])
def test_iconqa_rejects_unjoined_media(tmp_path: Path, change: str):
    adapter = _fixture(tmp_path, **{change: True})
    with pytest.raises(ValueError, match="unreferenced PNGs|image is absent"):
        adapter.prepare(adapter.plan(9, 100_000))
