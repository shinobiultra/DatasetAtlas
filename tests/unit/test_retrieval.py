"""Retrieval for chat with a dataset: model-server text queries, query/document prefixes, and population-scale eligibility."""
from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.models import Artifact, Record
from dataset_atlas.processors import encode_text_query, run_processor
from dataset_atlas.processors.vlm import encode_api_query
from dataset_atlas.queries.parquet import build_parquet_snapshot
from dataset_atlas.storage import arrays as store
from test_model_server_runs import FakeServer, server  # noqa: F401  (the fixture is used by name)

HEADERS = {"X-Atlas-Request": "1"}


def digit_embedding(text: str, index: int) -> list[float]:
    """A vector that points at the last digit of the text, so which record a query should find is known."""
    return [1.0 if text.strip()[-1:] == str(k) else 0.05 for k in range(4)]


def wait(client, run_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        state = client.get(f"/api/v1/runs/{run_id}").json()
        if state["status"] not in ("queued", "running"):
            return state
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_a_query_is_embedded_like_the_stored_vectors_with_its_own_prefix(server):
    server.embedding = digit_embedding
    records = [Record(id=f"r{i}", dataset_id="d", release_id="r", snapshot_id="s", text=f"Text {i}") for i in range(4)]
    plain = run_processor("embed.api", records, {"provider": server.provider, "storage": "arrays", "representation": "text"})
    prefixed = run_processor("embed.api", records, {"provider": server.provider, "storage": "arrays", "representation": "text", "document_prefix": "passage: ", "query_prefix": "query: "})
    assert "document_prefix" not in plain["provenance"]["recipe"] and "query_prefix" not in plain["provenance"]["recipe"]
    recipe = prefixed["provenance"]["recipe"]
    assert recipe["document_prefix"] == "passage: " and recipe["query_prefix"] == "query: "
    # Documents are embedded with the document prefix, so that prefix is part of the space; the query prefix is not.
    assert plain["provenance"]["embedding_space_id"] != prefixed["provenance"]["embedding_space_id"]
    only_query = run_processor("embed.api", records, {"provider": server.provider, "storage": "arrays", "representation": "text", "query_prefix": "q: "})
    assert only_query["provenance"]["embedding_space_id"] == plain["provenance"]["embedding_space_id"]
    assert any(body["input"][0].startswith("passage: ") for _, body in server.requests if "input" in body)
    vector = encode_api_query(server.provider, recipe, "Text 2")
    assert server.requests[-1][1]["input"] == ["query: Text 2"]
    assert np.isclose(np.linalg.norm(vector), 1) and int(np.argmax(vector)) == 2


def test_a_query_is_refused_when_the_server_changed_or_the_vector_does_not_fit(server):
    recipe = {"model_id": "fake-model", "dimension": 4}
    assert len(encode_api_query(server.provider, recipe, "hello")) == 4
    with pytest.raises(ValueError, match="different model"):
        encode_api_query({**server.provider, "model": "other"}, recipe, "hello")
    with pytest.raises(ValueError, match="different dimension"):
        encode_api_query(server.provider, {**recipe, "dimension": 7}, "hello")
    server.always_status = 500
    with pytest.raises(ValueError, match="could not embed"):
        encode_api_query(server.provider, recipe, "hello")


def test_a_model_server_space_needs_its_provider_to_be_queried_by_text():
    artifact = Artifact(id="a", kind="embed.api", run_id="x", snapshot_ids=["s"], unit="example", ids=["r0"],
                        provenance={"processor_provenance": {"recipe": {"model_id": "m", "dimension": 4}}})
    with pytest.raises(ValueError, match="model server is unavailable"):
        encode_text_query(artifact, {}, "hello")


def test_chat_retrieval_through_the_api_finds_the_nearest_record_with_the_query_prefix(workspace, server):
    server.embedding = digit_embedding
    (workspace / "local-config").mkdir(exist_ok=True)
    with TestClient(create_app(workspace)) as client:
        added = client.post("/api/v1/providers", headers=HEADERS, json={"id": "fake", "base_url": server.provider["base_url"], "model": "fake-model", "max_output_tokens": 64})
        assert added.status_code == 200, added.text
        ids = [row["id"] for row in client.post("/api/v1/queries/fixture", headers=HEADERS, json={"snapshot_id": "s1", "population_scope": "preview", "unit": "example", "limit": 10}).json()["records"]]
        selection = client.post("/api/v1/selections", headers=HEADERS, json={"id": "", "name": "t", "ids": ids, "unit": "example", "snapshot_ids": ["s1"], "dataset_ids": ["fixture"], "created_at": "2026-01-01T00:00:00Z"}).json()
        config = {"provider_id": "fake", "representation": "text", "document_prefix": "passage: ", "query_prefix": "query: "}
        estimate = client.post("/api/v1/runs/estimate", headers=HEADERS, json={"selection_id": selection["id"], "processor_id": "embed.api", "config": config}).json()
        run = client.post("/api/v1/runs", headers=HEADERS, json={"selection_id": selection["id"], "processor_id": "embed.api", "config": config, "estimate_digest": estimate["estimate_digest"]})
        assert run.status_code == 200, run.text
        state = wait(client, run.json()["id"])
        assert state["status"] == "completed", state.get("errors")
        artifact_id = state["artifact_ids"][0]
        query = {"snapshot_id": "s1", "population_scope": "preview", "unit": "example"}
        found = client.post("/api/v1/similarity/fixture", headers=HEADERS, json={"artifact_id": artifact_id, "text": "Text 2", "query": query, "limit": 3})
        assert found.status_code == 200, found.text
        body = found.json()
        assert body["results"][0]["id"] == "r2" and 0 <= body["results"][0]["distance"] < 1e-6  # an exact match is zero away, never negative
        assert body["population_scope"] == "preview" and body["coverage"]["embedded_eligible_records"] == len(ids)
        assert server.requests[-1][1]["input"] == ["query: Text 2"]
        both = client.post("/api/v1/similarity/fixture", headers=HEADERS, json={"artifact_id": artifact_id, "record_id": "r1", "text": "x", "query": query})
        assert both.status_code == 422 and "exactly one" in both.text
        # If the provider id now serves another model, the stored space is not queried with it.
        client.post("/api/v1/providers", headers=HEADERS, json={"id": "fake", "base_url": server.provider["base_url"], "model": "another-model", "max_output_tokens": 64})
        sent = len(server.requests)
        changed = client.post("/api/v1/similarity/fixture", headers=HEADERS, json={"artifact_id": artifact_id, "text": "Text 2", "query": query})
        assert changed.status_code == 422 and "different model" in changed.text and len(server.requests) == sent


COUNT = 12_000


def test_retrieval_over_a_whole_population_resolves_ids_in_one_scan(workspace, pack):
    snapshots = workspace / "work/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    records = [Record(id=f"r{i}", dataset_id="fixture", release_id="r1", snapshot_id="s1", unit="example", text=f"record {i}", source={"label": "A" if i % 3 == 0 else "B"}) for i in range(COUNT)]
    build_parquet_snapshot(records, pack.fields, snapshots / "fixture", root=snapshots, dataset_id="fixture", release_id="r1", snapshot_id="s1",
                           expected_count=COUNT, population_scope="complete")
    ids = [f"r{i}" for i in range(COUNT)]
    vectors = np.random.default_rng(1).normal(size=(COUNT, 8)).astype(np.float32)
    with TestClient(create_app(workspace)) as client:
        jobs = client.app.state.jobs
        directory = jobs.artifact_dir / "arrays" / "emb"
        manifest = store.write_bundle(directory, ids, {"vector": vectors})
        artifact = Artifact(id="emb", kind="embed.siglip2", run_id="upstream", snapshot_ids=["s1"], unit="example", ids=ids,
                            provenance={"processor_provenance": {"embedding_space_id": "space:test", "embedding_space": {"metric": "cosine"}}}, data={"bulk": {"dir": "arrays/emb", **manifest}})
        with jobs._db() as db:
            db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
        everything = {"snapshot_id": "s1", "population_scope": "complete", "unit": "example"}
        started = time.perf_counter()
        whole = client.post("/api/v1/similarity/fixture", headers=HEADERS, json={"artifact_id": "emb", "record_id": "r7", "query": everything, "limit": 5})
        assert whole.status_code == 200, whole.text
        assert time.perf_counter() - started < 20
        assert whole.json()["coverage"] == {"filtered_records": COUNT, "embedded_eligible_records": COUNT - 1} and whole.json()["population_scope"] == "complete"
        unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        expected = [f"r{i}" for i in np.argsort(-(unit @ unit[7]))[1:6]]
        assert [row["id"] for row in whole.json()["results"]] == expected
        # A filtered knowledge base only searches its own members.
        only_a = client.post("/api/v1/similarity/fixture", headers=HEADERS, json={"artifact_id": "emb", "record_id": "r7", "limit": 5,
                             "query": {**everything, "filter": {"field_id": "source.label", "op": "eq", "value": "A"}}})
        assert only_a.status_code == 200, only_a.text
        assert only_a.json()["coverage"]["filtered_records"] == COUNT // 3
        assert all(int(row["id"][1:]) % 3 == 0 for row in only_a.json()["results"])


def test_a_cosine_distance_is_never_negative_even_for_the_query_itself(tmp_path):
    from dataset_atlas.queries.similarity import similar_records_bulk
    ids = [f"r{i}" for i in range(300)]
    vectors = np.random.default_rng(3).normal(size=(300, 7)).astype(np.float32)
    directory = tmp_path / "arrays" / "emb"
    manifest = store.write_bundle(directory, ids, {"vector": vectors})
    artifact = Artifact(id="emb-negative", kind="embed.siglip2", run_id="x", snapshot_ids=["s"], unit="example", ids=ids,
                        provenance={"processor_provenance": {"embedding_space_id": "space:t", "embedding_space": {"metric": "cosine"}}}, data={"bulk": {"dir": "arrays/emb", **manifest}})
    norms = np.linalg.norm(vectors, axis=1)
    # The same arithmetic as the search, without the clamp: how far each vector is from itself.
    unclamped = [float((1 - (vectors @ vectors[row]) / (norms * np.linalg.norm(vectors[row])))[row]) for row in range(300)]
    assert min(unclamped) < 0, "the data must actually trigger the rounding problem for this test to mean anything"
    seen = []
    for row in range(300):
        found = similar_records_bulk(artifact, None, ids, 1, tmp_path, query_vector=vectors[row].tolist())
        seen.append(found["results"][0]["distance"])
        assert found["results"][0]["id"] == f"r{row}"
    assert min(seen) >= 0


def test_a_reused_artifact_id_never_serves_another_artifacts_vectors(tmp_path):
    from dataset_atlas.queries.similarity import similar_records_bulk

    def artifact_with(vectors, ids, folder):
        manifest = store.write_bundle(tmp_path / "arrays" / folder, ids, {"vector": vectors})
        return Artifact(id="same-id", kind="embed.siglip2", run_id="x", snapshot_ids=["s"], unit="example", ids=ids,
                        provenance={"processor_provenance": {"embedding_space_id": "space:t", "embedding_space": {"metric": "cosine"}}}, data={"bulk": {"dir": f"arrays/{folder}", **manifest}})

    first = artifact_with(np.array([[1, 0], [0, 1]], dtype=np.float32), ["a", "b"], "one")
    second = artifact_with(np.array([[0, 1], [1, 0], [1, 1]], dtype=np.float32), ["x", "y", "z"], "two")
    assert [row["id"] for row in similar_records_bulk(first, "a", ["a", "b"], 2, tmp_path)["results"]] == ["b"]
    answer = similar_records_bulk(second, "x", ["x", "y", "z"], 3, tmp_path)
    assert [row["id"] for row in answer["results"]] == ["z", "y"]
