from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time

import pytest

from dataset_atlas.jobs import JobManager
from dataset_atlas.models import Asset, Record, Selection


def fixture_records():
    selection = Selection(id="frozen", ids=["a", "b"], unit="example", snapshot_ids=["snapshot"],
                          dataset_ids=["dataset"], created_at="2026-01-01T00:00:00Z")
    records = [Record(id=record_id, dataset_id="dataset", release_id="release", snapshot_id="snapshot",
                      source={"left": index, "right": index + 1}) for index, record_id in enumerate(selection.ids)]
    return selection, records


def completed(manager, run_id, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = manager.get_run(run_id)
        if run.status not in ("queued", "running"):
            return run
        time.sleep(0.05)
    pytest.fail("run did not settle")


def test_frozen_selection_and_immutable_artifact(tmp_path):
    manager = JobManager(tmp_path)
    selection, records = fixture_records()
    with pytest.raises(ValueError, match="match the frozen selection"):
        manager.create(selection, records[:1], "compare.fields", {})
    config = {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab",
              "asset_roots": [str(tmp_path / "private")], "model_path": str(tmp_path / "private" / "model")}
    run = manager.create(selection, records, "compare.fields", config)
    config["left_field"] = "source.changed"
    records[0].source["left"] = 999
    run = completed(manager, run.id)
    assert run.status == "completed"
    assert run.config["left_field"] == "source.left"
    assert run.progress["completed"] == 2
    artifact = manager.get_artifact(run.artifact_ids[0])
    assert artifact.data["points"][0]["left"] == 0
    assert artifact.coverage["status"] == "completed"
    assert "asset_roots" not in artifact.provenance["config"]
    assert "model_path" not in artifact.provenance["config"]
    assert (tmp_path / "artifacts" / artifact.files["manifest"]).is_file()
    manager.close()


def test_successful_items_reused_and_recovered(tmp_path, monkeypatch):
    selection, records = fixture_records()
    config = {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab"}
    manager = JobManager(tmp_path)
    first = completed(manager, manager.create(selection, records, "compare.fields", config).id)
    assert first.status == "completed"
    manager.close()

    import dataset_atlas.jobs.manager as module
    def no_worker(*args, **kwargs):
        raise AssertionError("successful work was recomputed")
    monkeypatch.setattr(module.subprocess, "Popen", no_worker)
    recovered = JobManager(tmp_path)
    second = completed(recovered, recovered.create(selection, records, "compare.fields", config).id)
    assert second.status == "completed"
    assert second.progress["completed"] == 2
    recovered.close()


def test_stage_validation_rejects_wrong_record_id(tmp_path):
    selection, records = fixture_records()
    manager = JobManager(tmp_path, auto_recover=False)
    # Simulate a crash with a foreign staged item; only validated shards may be promoted.
    run = manager.create(selection, records, "compare.fields",
                         {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab"})
    completed(manager, run.id)
    with sqlite3.connect(manager.db_path) as db:
        key = db.execute("SELECT item_key FROM run_items WHERE run_id=? AND record_id='a'", (run.id,)).fetchone()[0]
    stage = tmp_path / "jobs" / run.id / "a.json"
    stage.write_text(json.dumps({"key": key, "record_id": "a", "result": {"items": [{"id": "intruder", "status": "completed"}]}}))
    with manager._db() as db:
        manager._import_staged(db, run.id)
    assert not stage.exists()
    assert stage.with_suffix(".invalid").exists()
    assert manager.item_statuses(run.id)["a"] == "completed"
    manager.close()


def test_cancelled_queued_run_retries_without_losing_frozen_inputs(tmp_path, monkeypatch):
    selection, records = fixture_records()
    config = {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab"}
    manager = JobManager(tmp_path)
    launch = manager._launch
    monkeypatch.setattr(manager, "_launch", lambda run_id: None)
    queued = manager.create(selection, records, "compare.fields", config)
    assert queued.status == "queued"
    cancelled = manager.cancel(queued.id)
    assert cancelled.status == "cancelled"
    assert cancelled.progress["completed"] == 0
    manager.close()

    recovered = JobManager(tmp_path)
    assert recovered.get_run(queued.id).status == "cancelled"
    retry = recovered.retry(queued.id)
    assert completed(recovered, retry.id).status == "completed"
    recovered.close()


def test_restart_recovers_queued_frozen_run(tmp_path, monkeypatch):
    selection, records = fixture_records()
    manager = JobManager(tmp_path)
    monkeypatch.setattr(manager, "_launch", lambda run_id: None)
    queued = manager.create(selection, records, "compare.fields",
                            {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab"})
    assert queued.status == "queued"
    manager.close()
    recovered = JobManager(tmp_path)
    assert completed(recovered, queued.id).status == "completed"
    recovered.close()


def test_estimate_reports_shared_assets_and_unknown_footprint(tmp_path):
    selection, records = fixture_records()
    shared = Asset(id="shared", dataset_id="dataset", release_id="release", modality="image",
                   uri="shared.png", metadata={"size_bytes": 123})
    for record in records:
        record.assets = [shared]
    manager = JobManager(tmp_path)
    preview = manager.estimate(selection, records, "quality.basic", {})
    assert preview["selected_count"] == 2
    assert preview["asset_references"] == 2
    assert preview["unique_assets"] == 1
    assert preview["known_input_bytes"] == 123
    assert preview["expected_download_bytes"] == preview["model_download_bytes"] == 0
    assert preview["output_bytes_status"] == "unknown"
    assert len(preview["estimate_digest"]) == 64
    assert manager.list_runs() == []
    manager.close()


def test_asset_worker_batches_repeated_asset_once(tmp_path, monkeypatch):
    from dataset_atlas.jobs import worker
    import dataset_atlas.processors as processors

    selection, records = fixture_records()
    shared = Asset(id="shared", dataset_id="dataset", release_id="release", modality="image", uri="shared.png")
    for record in records:
        record.assets = [shared]
    calls = []
    def fake_run(processor_id, batch, config):
        calls.append([record["id"] for record in batch])
        return {"items": [{"id": record["id"], "status": "completed", "output": {"asset_id": "shared"}}
                          for record in batch]}
    monkeypatch.setattr(processors, "run_processor", fake_run)
    plan = {"processor_id": "detect.nudenet", "batching": "assets", "config": {},
            "items": [{"key": str(index) * 64, "record": record.model_dump(mode="json")}
                      for index, record in enumerate(records, 1)]}
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(plan))
    monkeypatch.setattr(sys, "argv", ["worker", str(input_path)])
    assert worker.main() == 0
    assert calls == [["a", "b"]]
    staged = list(tmp_path.glob("group-*.json"))
    assert len(staged) == 1
    assert {item["id"] for item in json.loads(staged[0].read_text())["result"]["items"]} == set(selection.ids)


def test_subprocess_cancel_preserves_partial_and_retry(tmp_path):
    from PIL import Image

    image = tmp_path / "source.png"
    Image.new("RGB", (512, 512), color=(18, 36, 54)).save(image)
    ids = [f"r{index:04d}" for index in range(1000)]
    selection = Selection(id="many", ids=ids, unit="example", snapshot_ids=["snapshot"],
                          dataset_ids=["dataset"], created_at="2026-01-01T00:00:00Z")
    records = [Record(id=record_id, dataset_id="dataset", release_id="release", snapshot_id="snapshot",
                      assets=[Asset(id=f"asset-{record_id}", dataset_id="dataset", release_id="release",
                                    modality="image", uri=str(image))]) for record_id in ids]
    manager = JobManager(tmp_path / "work")
    run = manager.create(selection, records, "quality.basic", {"asset_roots": [str(tmp_path)]})
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        progress = manager.get_run(run.id).progress
        if 0 < progress["completed"] < len(ids):
            break
        time.sleep(0.01)
    else:
        pytest.fail("actual worker did not expose partial progress")
    manager.cancel(run.id)
    cancelled = completed(manager, run.id)
    assert cancelled.status == "cancelled"
    assert 0 < cancelled.progress["completed"] < len(ids)
    assert cancelled.progress["queued"] > 0
    partial = manager.get_artifact(cancelled.artifact_ids[0])
    assert partial.coverage["status"] == "cancelled"
    assert len(partial.data["items"]) == len(ids)
    assert {item["status"] for item in partial.data["items"]} == {"completed", "queued"}
    done = cancelled.progress["completed"]
    manager.close()

    resumed = JobManager(tmp_path / "work")
    finished = completed(resumed, resumed.retry(run.id).id, timeout=60)
    assert finished.status == "completed"
    assert finished.progress["completed"] == len(ids)
    assert len(resumed.get_artifact(finished.artifact_ids[0]).data["items"]) == len(ids)
    assert done < finished.progress["completed"]
    resumed.close()


def test_output_budget_rejects_oversized_stage(tmp_path):
    selection, records = fixture_records()
    manager = JobManager(tmp_path)
    run = manager.create(selection, records, "compare.fields",
                         {"left_field": "source.left", "right_field": "source.right",
                          "kind": "crosstab", "max_output_bytes": 1})
    result = completed(manager, run.id)
    assert result.status == "failed"
    assert result.progress["completed"] == 0
    assert result.progress["max_output_bytes"] == 1
    assert result.artifact_ids == []
    assert {error["type"] for error in result.errors} == {"OutputBudgetExceeded"}
    assert not list((tmp_path / "jobs" / run.id).glob("*.tmp"))
    manager.close()


def test_import_completed_run_checks_receipts_and_is_idempotent(tmp_path):
    selection, records = fixture_records()
    config = {"left_field": "source.left", "right_field": "source.right", "kind": "crosstab"}
    source = JobManager(tmp_path / "source")
    run = completed(source, source.create(selection, records, "compare.fields", config).id)
    assert run.status == "completed"
    destination = JobManager(tmp_path / "destination")
    first = destination.import_completed_run(source.work_dir, run.id)
    second = destination.import_completed_run(source.work_dir, run.id)
    assert first.id == second.id == run.id
    assert len(destination.list_runs()) == len(destination.list_artifacts()) == 1
    assert destination.get_artifact(first.artifact_ids[0]).data["items"] == source.get_artifact(run.artifact_ids[0]).data["items"]

    tampered = tmp_path / "tampered"
    shutil.copytree(source.work_dir, tampered)
    with sqlite3.connect(tampered / "jobs.sqlite3") as db:
        key = db.execute("SELECT item_key FROM run_items WHERE run_id=? LIMIT 1", (run.id,)).fetchone()[0]
    item = tampered / "artifacts" / "items" / f"{key}.json"
    item.write_bytes(item.read_bytes() + b" ")
    clean = JobManager(tmp_path / "clean")
    with pytest.raises(ValueError, match="canonical JSON|SHA-256"):
        clean.import_completed_run(tampered, run.id)
    assert clean.list_runs() == clean.list_artifacts() == []
    source.close()
    destination.close()
    clean.close()


def test_import_completed_run_rejects_symlinked_item(tmp_path):
    selection, records = fixture_records()
    source = JobManager(tmp_path / "source")
    run = completed(source, source.create(selection, records, "compare.fields",
                                          {"left_field": "source.left", "right_field": "source.right",
                                           "kind": "crosstab"}).id)
    with sqlite3.connect(source.db_path) as db:
        key = db.execute("SELECT item_key FROM run_items WHERE run_id=? LIMIT 1", (run.id,)).fetchone()[0]
    item = source.artifact_dir / "items" / f"{key}.json"
    outside = tmp_path / "outside.json"
    item.rename(outside)
    item.symlink_to(outside)
    destination = JobManager(tmp_path / "destination")
    with pytest.raises(ValueError, match="Symlink|symlink|root|symbolic"):
        destination.import_completed_run(source.work_dir, run.id)
    assert destination.list_runs() == []
    source.close()
    destination.close()
