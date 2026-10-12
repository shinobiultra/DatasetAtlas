"""Selecting a whole population on the server, past the old 10,000-id cap, and analysing it."""
from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Record
from dataset_atlas.queries.parquet import build_parquet_snapshot
from dataset_atlas.storage import arrays as store

HEADERS = {"X-Atlas-Request": "1"}
COUNT = 12_000


@pytest.fixture
def client(workspace, pack):
    snapshots = workspace / "work/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    records = [Record(id=f"r{i}", dataset_id="fixture", release_id="r1", snapshot_id="s1", unit="example", text=f"record {i}",
                      source={"label": "A" if i % 3 == 0 else "B", "score": i}) for i in range(COUNT)]
    build_parquet_snapshot(records, pack.fields, snapshots / "fixture", root=snapshots, dataset_id="fixture", release_id="r1",
                           snapshot_id="s1", expected_count=COUNT, population_scope="complete")
    with TestClient(create_app(workspace)) as client:
        yield client


def query(**extra):
    return {"snapshot_id": "s1", "population_scope": "complete", "unit": "example", **extra}


def test_a_population_is_selected_on_the_server_and_listed_without_its_ids(client):
    response = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query()})
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["size"] == COUNT and summary["ids"] == [] and summary["method"] == "population"
    assert summary["snapshot_ids"] == ["s1"] and summary["dataset_ids"] == ["fixture"]
    listed = [row for row in client.get("/api/v1/selections").json() if row["id"] == summary["id"]]
    assert listed[0]["ids"] == [] and listed[0]["size"] == COUNT
    assert client.get(f"/api/v1/selections/{summary['id']}").json()["ids"] == []
    ids = client.app.state.selection_ids(summary["id"])
    assert len(ids) == COUNT and ids[0] == "r0" and ids[-1] == f"r{COUNT - 1}"


def test_a_filtered_population_matches_the_filter_and_keeps_snapshot_order(client):
    body = {"dataset_id": "fixture", "name": "label A", "query": query(filter={"field_id": "source.label", "op": "eq", "value": "A"})}
    summary = client.post("/api/v1/selections/population", headers=HEADERS, json=body).json()
    assert summary["size"] == COUNT // 3 and summary["name"] == "label A"
    ids = client.app.state.selection_ids(summary["id"])
    assert ids[:3] == ["r0", "r3", "r6"] and all(int(identity[1:]) % 3 == 0 for identity in ids)


def test_empty_samples_and_oversized_populations_are_refused(client):
    refused = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query(filter={"field_id": "source.label", "op": "eq", "value": "none"})})
    assert refused.status_code == 422 and "no records" in refused.text
    sampled = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query(sample={"method": "random", "size": 5})})
    assert sampled.status_code == 422 and "sampled" in sampled.text
    capped = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query(), "limit": 100})
    assert capped.status_code == 422 and "more than 100" in capped.text


def test_records_resolve_in_one_scan_and_in_the_requested_order(client):
    summary = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query()}).json()
    selection = client.app.state.selection_by_id(summary["id"])
    started = time.perf_counter()
    records = client.app.state.selection_records(selection, prepare_media=False)
    assert time.perf_counter() - started < 20
    assert [record.id for record in records] == selection.ids and records[5].source["score"] == 5
    reordered = selection.model_copy(update={"ids": list(reversed(selection.ids[:1000]))})
    assert [record.id for record in client.app.state.selection_records(reordered, prepare_media=False)][:2] == ["r999", "r998"]


def test_export_of_a_large_selection_is_refused_not_attempted(client):
    summary = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query()}).json()
    response = client.get(f"/api/v1/selections/{summary['id']}/export")
    assert response.status_code == 422 and "limited" in response.text


def test_a_whole_population_can_be_projected_and_clustered(client):
    jobs = client.app.state.jobs
    ids = [f"r{i}" for i in range(COUNT)]
    vectors = np.random.default_rng(0).normal(size=(COUNT, 8)).astype(np.float32)
    directory = jobs.artifact_dir / "arrays" / "emb"
    manifest = store.write_bundle(directory, ids, {"vector": vectors})
    artifact = Artifact(id="emb", kind="embed.siglip2", run_id="upstream", snapshot_ids=["s1"], unit="example", ids=ids,
                        provenance={"processor_provenance": {"embedding_space_id": "space:test"}}, data={"bulk": {"dir": "arrays/emb", **manifest}})
    with jobs._db() as db:
        db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
    summary = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query()}).json()
    for processor, extra in (("project.pca", {"dimensions": 3}), ("cluster.kmeans", {"clusters": 5})):
        config = {"embedding_artifact_id": "emb", "backend": "cpu", **extra}
        started = time.perf_counter()
        estimate = client.post("/api/v1/runs/estimate", headers=HEADERS, json={"selection_id": summary["id"], "processor_id": processor, "config": config})
        assert estimate.status_code == 200, estimate.text
        assert estimate.json()["selected_count"] == COUNT and estimate.json()["storage"] == "arrays"
        run = client.post("/api/v1/runs", headers=HEADERS, json={"selection_id": summary["id"], "processor_id": processor, "config": config, "estimate_digest": estimate.json()["estimate_digest"]})
        assert run.status_code == 200, run.text
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            state = client.get(f"/api/v1/runs/{run.json()['id']}").json()
            if state["status"] not in ("queued", "running"):
                break
            time.sleep(0.1)
        assert state["status"] == "completed", state.get("errors")
        result = client.get(f"/api/v1/artifacts/{state['artifact_ids'][0]}").json()
        assert result["data"]["bulk"]["count"] == COUNT
        assert time.perf_counter() - started < 60


def test_array_results_list_as_fields_and_filter_the_complete_index_without_a_row_join(client):
    """Listing a dataset's fields must not join every array result row by row, and a filter on one must work."""
    jobs = client.app.state.jobs
    ids = [f"r{i}" for i in range(COUNT)]
    labels = np.arange(COUNT, dtype=np.int32) % 7
    directory = jobs.artifact_dir / "arrays" / "labels"
    manifest = store.write_bundle(directory, ids, {"cluster": labels, "probability": np.linspace(0, 1, COUNT, dtype=np.float32)})
    artifact = Artifact(id="labels", kind="cluster.kmeans", run_id="x", snapshot_ids=["s1"], unit="example", ids=ids, data={"bulk": {"dir": "arrays/labels", **manifest}})
    with jobs._db() as db:
        db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
    fields = {field["id"]: field for field in client.get("/api/v1/datasets/fixture/complete").json()["fields"]}
    assert {"prediction.labels.cluster", "prediction.labels.probability", "prediction.labels.status"} <= set(fields)
    assert fields["prediction.labels.cluster"]["dtype"] == "number" and "gt" in fields["prediction.labels.cluster"]["query_ops"]
    assert fields["prediction.labels.status"]["dtype"] == "string"
    answer = client.post("/api/v1/queries/fixture", headers=HEADERS, json=query(result_snapshot_ids=["labels"], filter={"field_id": "prediction.labels.cluster", "op": "eq", "value": 3}, limit=5))
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["matched_count"] == len([i for i in range(COUNT) if i % 7 == 3])
    # A result join orders by id as text, as ever, so the first page is r10, r100, r1000, ...
    assert [row["id"] for row in body["records"]] == sorted(f"r{i}" for i in range(COUNT) if i % 7 == 3)[:5]
    assert all(row["prediction"]["labels.cluster"] == 3 for row in body["records"])
    summary = client.post("/api/v1/selections/population", headers=HEADERS, json={"dataset_id": "fixture", "query": query(result_snapshot_ids=["labels"], filter={"field_id": "prediction.labels.cluster", "op": "eq", "value": 3})}).json()
    assert summary["size"] == body["matched_count"]
