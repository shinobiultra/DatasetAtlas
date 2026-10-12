"""Colouring a whole map by a dataset field: one value per point, in the result's own row order."""
from __future__ import annotations

import json
import time
from urllib.parse import unquote

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, FieldDescriptor, Record
from dataset_atlas.queries.parquet import ParquetSnapshot, build_parquet_snapshot
from dataset_atlas.storage import arrays as store

HEADERS = {"X-Atlas-Request": "1"}
COUNT = 5000
FIELDS = [FieldDescriptor(id="source.label", name="Label", dtype="category"), FieldDescriptor(id="source.score", name="Score", dtype="number"),
          FieldDescriptor(id="source.flag", name="Flag", dtype="boolean"), FieldDescriptor(id="source.note", name="Note", dtype="string")]


def records():
    out = []
    for i in range(COUNT):
        source = {"label": "ABCDE"[i % 5] if i % 7 else None, "score": float(i) if i % 10 else None, "flag": i % 2 == 0, "note": f"n{i % 3}"}
        out.append(Record(id=f"r{i}", dataset_id="fixture", release_id="r1", snapshot_id="s1", unit="example", text=f"t{i}", source={k: v for k, v in source.items() if v is not None}))
    return out


@pytest.fixture
def snapshot(tmp_path):
    directory = tmp_path / "snap"
    build_parquet_snapshot(records(), FIELDS, directory, root=tmp_path, dataset_id="fixture", release_id="r1", snapshot_id="s1", expected_count=COUNT, population_scope="complete")
    return ParquetSnapshot(tmp_path, directory)


def test_a_category_is_coded_per_id_in_the_order_asked(snapshot):
    order = [f"r{i}" for i in (4, 0, 3, 7, 999999, 14)]  # r0, r7, r14 have no label; the last-but-one is not in the snapshot
    answer = snapshot.column_values(order, "source.label")
    names = [category["value"] for category in answer["categories"]]
    assert answer["kind"] == "category" and set(names) == {"D", "E"}  # the categories are those among the ids asked for
    decoded = [names[code] if code >= 0 else None for code in answer["codes"]]
    assert decoded == ["E", None, "D", None, None, None]
    assert answer["missing"] == 4 and answer["other"] == 0 and answer["codes"].dtype == np.int16


def test_values_beyond_the_most_frequent_share_an_other_code(snapshot):
    ids = [f"r{i}" for i in range(COUNT)]
    answer = snapshot.column_values(ids, "source.label", top=2)
    assert len(answer["categories"]) == 2 and answer["categories"][0]["count"] >= answer["categories"][1]["count"]
    assert answer["other"] == sum(1 for i in range(COUNT) if i % 7 and "ABCDE"[i % 5] not in {c["value"] for c in answer["categories"]})
    assert set(np.unique(answer["codes"])) == {-1, 0, 1, 2}
    assert int((answer["codes"] == 2).sum()) == answer["other"]


def test_numbers_come_back_as_floats_with_nan_for_missing(snapshot):
    ids = ["r3", "r10", "r11", "nope"]
    answer = snapshot.column_values(ids, "source.score")
    assert answer["kind"] == "number" and answer["values"].dtype == np.float32
    assert np.allclose(answer["values"][[0, 2]], [3.0, 11.0]) and np.isnan(answer["values"][[1, 3]]).all()
    assert (answer["missing"], answer["min"], answer["max"]) == (2, 3.0, 11.0)


def test_booleans_and_strings_are_categories(snapshot):
    ids = [f"r{i}" for i in range(6)]
    flags = snapshot.column_values(ids, "source.flag")
    assert [flags["categories"][code]["value"] for code in flags["codes"]] == ["true", "false", "true", "false", "true", "false"]
    notes = snapshot.column_values(ids, "source.note")
    assert [notes["categories"][code]["value"] for code in notes["codes"]] == ["n0", "n1", "n2", "n0", "n1", "n2"]


def test_unknown_and_structured_fields_and_bad_widths_are_refused(snapshot):
    with pytest.raises(ValueError, match="Unknown field"):
        snapshot.column_values(["r1"], "source.nothing")
    with pytest.raises(ValueError, match="category count"):
        snapshot.column_values(["r1"], "source.label", top=0)


def test_the_endpoint_colours_every_row_of_an_array_result(workspace, pack):
    snapshots = workspace / "work/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    build_parquet_snapshot(records(), FIELDS, snapshots / "fixture", root=snapshots, dataset_id="fixture", release_id="r1", snapshot_id="s1", expected_count=COUNT, population_scope="complete")
    ids = [f"r{i}" for i in range(COUNT - 1, -1, -1)]  # the result's order is its own, not the snapshot's
    with TestClient(create_app(workspace)) as client:
        jobs = client.app.state.jobs
        directory = jobs.artifact_dir / "arrays" / "proj"
        manifest = store.write_bundle(directory, ids, {"coords": np.zeros((COUNT, 3), dtype=np.float32)})
        artifact = Artifact(id="proj-colour", kind="project.pca", run_id="x", snapshot_ids=["s1"], unit="example", ids=[], data={"bulk": {"dir": "arrays/proj", **manifest}})
        with jobs._db() as db:
            db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
        started = time.perf_counter()
        response = client.get("/api/v1/datasets/fixture/column/proj-colour", params={"field_id": "source.label", "snapshot_id": "s1"})
        assert response.status_code == 200, response.text
        assert time.perf_counter() - started < 10
        meta = json.loads(unquote(response.headers["X-Atlas-Column"]))
        codes = np.frombuffer(response.content, dtype=response.headers["X-Atlas-Dtype"])
        assert response.headers["X-Atlas-Shape"] == str(COUNT) and len(codes) == COUNT
        names = [category["value"] for category in meta["categories"]]
        row = ids.index("r2")
        assert names[codes[row]] == "C" and codes[ids.index("r7")] == -1 and meta["kind"] == "category"
        numbers = client.get("/api/v1/datasets/fixture/column/proj-colour", params={"field_id": "source.score", "snapshot_id": "s1"})
        values = np.frombuffer(numbers.content, dtype="float32")
        assert values[ids.index("r13")] == 13.0 and np.isnan(values[ids.index("r10")]) and json.loads(unquote(numbers.headers["X-Atlas-Column"]))["max"] == COUNT - 1
        wrong = client.get("/api/v1/datasets/fixture/column/proj-colour", params={"field_id": "source.label", "snapshot_id": "other"})
        assert wrong.status_code == 422 and "different snapshots" in wrong.text
