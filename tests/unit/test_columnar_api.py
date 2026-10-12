"""Array-backed artifacts over HTTP, in run configuration and in similarity search."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact
from dataset_atlas.queries.similarity import similar_records
from dataset_atlas.storage import arrays as store

VECTORS = np.array([[1, 0], [0.8, 0.6], [0, 1]], dtype=np.float32)
IDS = ["r0", "r1", "r2"]


@pytest.fixture
def client(workspace):
    with TestClient(create_app(workspace)) as client:
        jobs = client.app.state.jobs
        directory = jobs.artifact_dir / "arrays" / "emb"
        manifest = store.write_bundle(directory, IDS, {"vector": VECTORS})
        artifact = Artifact(id="emb", kind="embed.siglip2", run_id="upstream", snapshot_ids=["s1"], unit="example", ids=IDS,
                            provenance={"processor_provenance": {"embedding_space_id": "space:test"}}, data={"bulk": {"dir": "arrays/emb", **manifest}})
        with jobs._db() as db:
            db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
        client.artifact = artifact
        yield client


def test_arrays_are_served_as_raw_immutable_bytes_with_their_shape(client):
    response = client.get("/api/v1/artifacts/emb/arrays/vector")
    assert response.status_code == 200
    assert response.headers["x-atlas-dtype"] == "float32" and response.headers["x-atlas-shape"] == "3,2"
    assert "immutable" in response.headers["cache-control"]
    assert np.array_equal(np.frombuffer(response.content, dtype="<f4").reshape(3, 2), VECTORS)
    assert client.get("/api/v1/artifacts/emb/ids").json() == IDS
    assert client.get("/api/v1/artifacts/emb/arrays/missing").status_code == 404
    assert client.get("/api/v1/artifacts/nothing/arrays/vector").status_code in {404, 500}


def test_a_client_cannot_point_a_run_at_files_of_its_choosing(client):
    config = client.app.state.run_config("project.pca", {"vector_source": {"dir": "/etc", "array": "passwd", "manifest": {}}})
    assert "vector_source" not in config
    config = client.app.state.run_config("project.pca", {"embedding_artifact_id": "emb", "vector_source": {"dir": "/etc"}})
    assert config["vector_source"]["artifact_id"] == "emb" and config["vector_source"]["dir"].endswith("/arrays/emb")
    assert config["storage"] == "arrays" and config["embedding_space_id"] == "space:test" and "vectors" not in config


def test_big_selections_use_arrays_by_default_and_small_ones_do_not(client):
    big = SimpleNamespace(ids=list(range(6000)))
    small = SimpleNamespace(ids=list(range(50)))
    assert client.app.state.run_config("embed.siglip2", {}, big)["storage"] == "arrays"
    assert "storage" not in client.app.state.run_config("embed.siglip2", {}, small)
    assert "storage" not in client.app.state.run_config("detect.nudenet", {}, big), "detectors have no columnar path"
    assert client.app.state.run_config("embed.siglip2", {"storage": "json"}, big)["storage"] == "json", "an explicit choice wins"


def test_similarity_over_an_array_artifact_is_exact(client, tmp_path):
    jobs = client.app.state.jobs
    found = similar_records(client.artifact, "r0", IDS, 2, tmp_path, artifact_dir=jobs.artifact_dir)
    assert found["mode"] == "exact" and [row["id"] for row in found["results"]] == ["r1", "r2"]
    assert found["results"][0]["distance"] == pytest.approx(1 - 0.8, abs=1e-6)
    assert found["eligible_count"] == 2
    only = similar_records(client.artifact, None, ["r1", "r2"], 1, tmp_path, query_vector=[0, 1], artifact_dir=jobs.artifact_dir)
    assert [row["id"] for row in only["results"]] == ["r2"]
    with pytest.raises(ValueError, match="no completed vector"):
        similar_records(client.artifact, "nope", IDS, 2, tmp_path, artifact_dir=jobs.artifact_dir)
    with pytest.raises(ValueError, match="artifact store"):
        similar_records(client.artifact, "r0", IDS, 2, tmp_path)


def test_bundle_directory_cannot_escape_the_artifact_store(client):
    from dataset_atlas.queries.embedding_space import bulk_directory
    jobs = client.app.state.jobs
    outside = client.artifact.model_copy(update={"data": {"bulk": {"dir": "../../etc"}}})
    with pytest.raises(ValueError, match="outside"):
        bulk_directory(outside, jobs.artifact_dir)
    with pytest.raises(ValueError, match="not array-backed"):
        bulk_directory(client.artifact.model_copy(update={"data": {}}), jobs.artifact_dir)


def test_array_results_join_onto_records_like_json_items(client):
    """A projection and a clustering stored as arrays appear as ordinary prediction fields on records."""
    from dataset_atlas.models import Pack
    from dataset_atlas.queries.result_items import result_items
    from dataset_atlas.queries.results import attach_results
    jobs = client.app.state.jobs
    directory = jobs.artifact_dir / "arrays" / "proj"
    manifest = store.write_bundle(directory, ["r0", "r2"], {"coords": np.array([[0.5, 1.5, 2.5], [3.0, 4.0, 5.0]], dtype=np.float32),
                                                             "cluster": np.array([1, -1], dtype=np.int32)})
    (directory / "skipped.json").write_text('{"r1": {"status": "not_applicable"}}')
    artifact = Artifact(id="proj", kind="cluster.hdbscan", run_id="x", snapshot_ids=["s1"], unit="example", ids=["r0", "r1", "r2"],
                        data={"bulk": {"dir": "arrays/proj", **manifest}})
    artifact._store_root = jobs.artifact_dir
    items = list(result_items(artifact))
    assert items[0] == {"id": "r0", "status": "completed", "output": {"cluster": 1, "x": 0.5, "y": 1.5, "z": 2.5}}
    assert {item["id"]: item["status"] for item in items} == {"r0": "completed", "r2": "completed", "r1": "not_applicable"}
    assert [item["id"] for item in result_items(artifact, {"r2"})] == ["r2"]
    pack = Pack.model_validate_json(client.get("/api/v1/datasets/fixture/pack").text)
    pack.dataset = pack.dataset.model_copy(update={"snapshot_id": "s1"})
    joined = attach_results(pack, [artifact])
    record = {r.id: r for r in joined.records}["r0"]
    assert record.prediction["proj.cluster"] == 1 and record.prediction["proj.z"] == 2.5 and record.prediction["proj.status"] == "completed"
    assert {r.id: r for r in joined.records}["r1"].prediction["proj.status"] == "not_applicable"
    assert {"prediction.proj.cluster", "prediction.proj.x", "prediction.proj.z"} <= {f.id for f in joined.fields}
