import json
from pathlib import Path
import pytest
from dataset_atlas.adapters.seed_bench import SeedBenchAdapter
from dataset_atlas.models import Dataset


def adapter(tmp_path, version, rows):
    path = tmp_path / "native.json"
    path.write_text(
        json.dumps(
            {
                "questions": rows,
                "question_type": {
                    "attributes": 3,
                    "text": 9,
                    "action": 10,
                    "action-v2": 20,
                },
            }
        )
    )
    d = Dataset(
        id="seed",
        name="Fixture",
        adapter="seed_bench",
        release="r",
        snapshot_id="s",
        adapter_config={
            "annotations_path": str(path),
            "seed_version": version,
            "identity_fields": ["question_id", "question_type_id"],
            "annotations": [
                {
                    "path_key": "annotations_path",
                    "records_key": "questions",
                    "split": "test",
                    "choices_columns": ["choice_a", "choice_b", "choice_c", "choice_d"],
                }
            ],
            "mapping": {"question": "question", "choices": "_atlas_choices"},
        },
    )
    return SeedBenchAdapter(d)


def question(**fields):
    return {
        "question_id": "native-id",
        "question_type_id": 3,
        "question": "native question",
        "choice_a": "A content",
        "choice_b": "B content",
        "choice_c": "C content",
        "choice_d": "D content",
        "answer": "B ",
        "data_id": "photo",
        "data_type": "image",
        **fields,
    }


def test_v1_duplicate_native_ids_across_tasks_survive_and_frames_keep_order(tmp_path):
    native = [
        question(),
        question(question_type_id=9),
        question(
            question_id="v1",
            question_type_id=10,
            data_type="video",
            data_id="native.webm",
        ),
    ]
    a = adapter(tmp_path, 1, native)
    rows = a.iter_records(a.prepare(a.plan(10, 100000))).records
    assert len({r.id for r in rows}) == 3
    assert rows[0].assets[0].id == rows[1].assets[0].id
    assert rows[0].source["answer"] == "B " and rows[0].choices == [
        "A content",
        "B content",
        "C content",
        "D content",
    ]
    assert [r.uri for r in rows[2].assets] == [
        f"zip/video/v1_video/task10/ssv2_8_frame/v1/{i}.png" for i in range(1, 9)
    ]
    assert rows[2].source["data_id"] == "native.webm"
    assert rows[2].assets[7].metadata["condition"] == "frame 8/8"


def test_v2_explicit_paths_and_choice_strings_are_not_rewritten(tmp_path):
    native = [
        question(
            data_source="SEED-Bench v2",
            data_type="Multiple Images",
            data_id=["task17/2.png", "task17/1.png"],
        )
    ]
    a = adapter(tmp_path, 2, native)
    row = a.iter_records(a.prepare(a.plan(10, 100000))).records[0]
    assert [x.uri for x in row.assets] == [
        "zip/images/SEED-Bench-2-image/task17/2.png",
        "zip/images/SEED-Bench-2-image/task17/1.png",
    ]
    assert all(row.source[k] == v for k, v in native[0].items())
    native[0]["data_id"] = ["../../escape.png"]
    with pytest.raises(ValueError):
        adapter(tmp_path, 2, native)._rows()
    native[0].update(data_id=["task20/1.png"], data_type="Video", question_type_id=20)
    with pytest.raises(ValueError, match="eight"):
        adapter(tmp_path, 2, native)._rows()
