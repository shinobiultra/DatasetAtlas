"""End-to-end API regressions for scope and local security boundaries."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dataset_atlas.api import create_app
from dataset_atlas.api.tools import make_tool_backend
from dataset_atlas.models import Artifact, Pack, Run
from dataset_atlas.queries.parquet import build_parquet_snapshot


HEADERS = {"X-Atlas-Request": "1"}


def _complete_workspace(workspace, pack):
    media = workspace / "work/packs/fixture/media/test.png"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"\x89PNG\r\n\x1a\nreview fixture")
    outside_preview = pack.records[0].model_copy(deep=True)
    outside_preview.id = "r4"
    outside_preview.text = "Only in complete snapshot"
    outside_preview.source = {"label": "B", "score": 7}
    snapshots = workspace / "work/snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    build_parquet_snapshot(
        [*pack.records, outside_preview], pack.fields, snapshots / "fixture",
        root=snapshots, dataset_id="fixture", release_id="r1", snapshot_id="s1",
        expected_count=5, population_scope="complete",
    )
    artifact = Artifact(
        id="review-result", kind="review.score", snapshot_ids=["s1"], unit="example",
        ids=["r4"], data={"items": [{"id": "r4", "status": "completed", "output": {"score": 7}}]},
    )
    preview = Pack.model_validate_json((workspace / "work/packs/fixture/pack.json").read_text())
    preview.artifacts.append(artifact)
    (workspace / "work/packs/fixture/pack.json").write_text(preview.model_dump_json())
    return artifact


def test_chunked_request_budget_counts_received_bytes(workspace):
    with TestClient(create_app(workspace)) as client:
        def oversized_body():
            for _ in range(11):
                yield b" " * 1_000_000

        response = client.post(
            "/api/v1/queries/fixture", headers={**HEADERS, "Transfer-Encoding": "chunked"},
            content=oversized_body(),
        )
        assert response.status_code == 413
        assert len(response.content) < 1000

        invalid = client.post("/api/v1/queries/fixture", headers=HEADERS, content=b"sensitive invalid body")
        assert invalid.status_code == 422
        assert b"sensitive invalid body" not in invalid.content


def test_complete_result_join_and_selection_export_scope(workspace, pack):
    artifact = _complete_workspace(workspace, pack)
    with TestClient(create_app(workspace)) as client:
        query = {
            "snapshot_id": "s1", "population_scope": "complete", "unit": "example",
            "result_snapshot_ids": [artifact.id],
            "filter": {"field_id": "prediction.review-result.score", "op": "eq", "value": 7},
        }
        response = client.post("/api/v1/queries/fixture", headers=HEADERS, json=query)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["population_scope"] == "complete"
        assert body["matched_count"] == 1
        assert [row["id"] for row in body["records"]] == ["r4"]
        assert body["records"][0]["prediction"]["review-result.score"] == 7

        fields = client.get("/api/v1/datasets/fixture/fields?population_scope=complete")
        assert fields.status_code == 200
        assert "prediction.review-result.score" in {field["id"] for field in fields.json()}

        selection = {
            "id": "", "name": "Complete result selection", "ids": ["r4"],
            "unit": "example", "snapshot_ids": ["s1"], "dataset_ids": ["fixture"],
            "query": query, "created_at": "2026-09-22T00:00:00Z",
        }
        saved = client.post("/api/v1/selections", headers=HEADERS, json=selection)
        assert saved.status_code == 200, saved.text
        exported = client.get(f"/api/v1/selections/{saved.json()['id']}/export")
        assert exported.status_code == 200, exported.text
        rows = exported.json()["records"]
        assert [row["id"] for row in rows] == ["r4"]
        assert rows[0]["prediction"]["review-result.score"] == 7
        assert rows[0]["assets"][0]["uri"] is None

        no_result = client.post(
            "/api/v1/queries/fixture", headers=HEADERS,
            json={**query, "result_snapshot_ids": []},
        )
        assert no_result.status_code == 422


def test_media_requires_configured_root_and_rejects_swap(workspace, pack, tmp_path, monkeypatch):
    local = workspace / "work/packs/fixture/media/test.png"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(b"\x89PNG\r\n\x1a\ninside")
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"private outside bytes")

    with TestClient(create_app(workspace)) as client:
        response = client.post("/api/v1/queries/fixture", headers=HEADERS, json={"snapshot_id": "s1"})
        assert response.status_code == 200
        uri = response.json()["records"][0]["assets"][0]["uri"]
        assert client.get(uri).content == local.read_bytes()

        from dataset_atlas import storage
        original = storage.read_rooted_file

        def swapped(path, roots, max_bytes):
            local.unlink()
            local.symlink_to(outside)
            return original(path, roots, max_bytes)

        monkeypatch.setattr(storage, "read_rooted_file", swapped)
        blocked = client.get(uri)
        assert blocked.status_code == 422
        assert outside.read_bytes() not in blocked.content

    pack = pack.model_copy(deep=True)
    for record in pack.records:
        record.assets[0].uri = str(outside)
    (workspace / "work/packs/fixture/pack.json").write_text(pack.model_dump_json())
    with TestClient(create_app(workspace)) as client:
        response = client.post("/api/v1/queries/fixture", headers=HEADERS, json={"snapshot_id": "s1"})
        assert response.status_code == 200
        uri = response.json()["records"][0]["assets"][0]["uri"]
        assert client.get(uri).status_code == 422


def test_run_result_tool_uses_requested_ids_within_approved_scope(pack):
    records = {record.id: record for record in pack.records}
    run = Run(
        id="review-run", processor_id="review.score", selection_id="review-selection",
        status="partial", artifact_ids=["review-artifact"], created_at="2026-09-22T00:00:00Z",
    )
    artifact = Artifact(
        id="review-artifact", kind="review.score", run_id=run.id,
        snapshot_ids=["s1"], unit="example", ids=["r0", "r1", "r2"],
        data={"items": [
            {"id": "r0", "status": "completed", "output": {"score": 1}},
            {"id": "r1", "status": "completed", "output": {"score": 2}},
            {"id": "r2", "status": "failed", "error": "held-out fixture"},
        ]},
    )

    class Jobs:
        def get_run(self, run_id):
            assert run_id == run.id
            return run

        def get_artifact(self, artifact_id):
            assert artifact_id == artifact.id
            return artifact

    backend = make_tool_backend(None, records.get, Jobs())
    result = backend(
        "get_run_results", {"run_id": run.id, "record_ids": ["r0"], "limit": 100},
        {"r0", "r1"}, 100,
    )
    assert result.population_scope == "approved_selection"
    assert result.source_refs == ["r0"]
    assert [row["id"] for row in result.rows] == ["r0"]
    assert result.rows[0]["run_id"] == run.id
