"""Moving a finished array-backed run from another workspace (a cluster's, say) into this one, verified end to end."""
from __future__ import annotations

import shutil
import sqlite3

import numpy as np
import pytest

from dataset_atlas.jobs import JobManager
from dataset_atlas.models import Record, Selection
from dataset_atlas.storage import arrays as store
from test_columnar_runs import BLOBS, MISSING, PER, run, settled, world  # noqa: F401  (world is a fixture, used by name)
from test_model_server_runs import server  # noqa: F401


@pytest.fixture
def finished(world):
    manager, run_record, artifact, directory = run(world, "project.pca", dimensions=3)
    return manager, run_record, artifact, directory


def rows(manager, run_id):
    with sqlite3.connect(manager.db_path) as db:
        return db.execute("SELECT record_id,item_key,status,error_json,output_bytes FROM run_items WHERE run_id=? ORDER BY record_id", (run_id,)).fetchall()


def test_an_array_run_moves_to_another_workspace_byte_for_byte(finished, tmp_path):
    source, run_record, artifact, directory = finished
    destination = JobManager(tmp_path / "destination")
    imported = destination.import_completed_run(source.work_dir, run_record.id)
    assert imported.id == run_record.id and imported.artifact_ids == run_record.artifact_ids
    copy = destination.get_artifact(artifact.id)
    assert copy.model_dump(mode="json") == artifact.model_dump(mode="json")
    target = destination.artifact_dir / artifact.data["bulk"]["dir"]
    assert sorted(path.name for path in target.iterdir()) == sorted(path.name for path in directory.iterdir())
    for path in directory.iterdir():
        assert (target / path.name).read_bytes() == path.read_bytes()
    bulk = copy.data["bulk"]
    assert store.read_ids(target, bulk) == store.read_ids(directory, bulk)
    assert np.array_equal(store.read_array(target, bulk["arrays"]["coords"], verify=True), store.read_array(directory, bulk["arrays"]["coords"], verify=True))
    # Every record's outcome came across, including the ones that had no vector.
    assert rows(destination, run_record.id) == rows(source, run_record.id)
    assert sum(1 for row in rows(destination, run_record.id) if row[2] == "not_applicable") == MISSING
    assert len(destination.list_runs()) == 1 and len(destination.list_artifacts()) == 1
    destination.close()


def test_importing_twice_changes_nothing(finished, tmp_path):
    source, run_record, artifact, _ = finished
    destination = JobManager(tmp_path / "destination")
    first = destination.import_completed_run(source.work_dir, run_record.id)
    second = destination.import_completed_run(source.work_dir, run_record.id)
    assert first.id == second.id and len(destination.list_runs()) == len(destination.list_artifacts()) == 1
    assert len(rows(destination, run_record.id)) == BLOBS * PER + MISSING
    destination.close()


def broken(finished, tmp_path, name):
    source, run_record, artifact, _ = finished
    copy = tmp_path / name
    shutil.copytree(source.work_dir, copy)
    return copy, run_record, artifact


def untouched(destination, artifact):
    assert destination.list_runs() == [] and destination.list_artifacts() == []
    arrays = destination.artifact_dir / "arrays"
    assert not arrays.exists() or list(arrays.iterdir()) == [], "a refused import leaves no bundle and no temporary files"


def test_a_changed_array_is_refused_and_leaves_nothing_behind(finished, tmp_path):
    copy, run_record, artifact = broken(finished, tmp_path, "tampered")
    victim = copy / "artifacts" / artifact.data["bulk"]["dir"] / artifact.data["bulk"]["arrays"]["coords"]["file"]
    data = bytearray(victim.read_bytes())
    data[-1] ^= 0xFF
    victim.write_bytes(bytes(data))
    destination = JobManager(tmp_path / "destination")
    with pytest.raises(ValueError, match="checksum"):
        destination.import_completed_run(copy, run_record.id)
    untouched(destination, artifact)
    destination.close()


def test_a_symbolic_link_in_the_bundle_is_refused(finished, tmp_path):
    copy, run_record, artifact = broken(finished, tmp_path, "linked")
    victim = copy / "artifacts" / artifact.data["bulk"]["dir"] / artifact.data["bulk"]["arrays"]["coords"]["file"]
    outside = tmp_path / "outside.npy"
    victim.rename(outside)
    victim.symlink_to(outside)
    destination = JobManager(tmp_path / "destination")
    with pytest.raises(ValueError, match="symbolic|escapes"):
        destination.import_completed_run(copy, run_record.id)
    untouched(destination, artifact)
    destination.close()


def test_receipts_that_disagree_with_the_run_are_refused(finished, tmp_path):
    destination = JobManager(tmp_path / "destination")
    copy, run_record, artifact = broken(finished, tmp_path, "keys")
    with sqlite3.connect(copy / "jobs.sqlite3") as db:
        db.execute("UPDATE run_items SET item_key='x'||substr(item_key,2) WHERE run_id=? AND rowid=(SELECT min(rowid) FROM run_items WHERE run_id=?)", (run_record.id, run_record.id))
    with pytest.raises(ValueError, match="item key"):
        destination.import_completed_run(copy, run_record.id)
    copy, run_record, artifact = broken(finished, tmp_path, "statuses")
    with sqlite3.connect(copy / "jobs.sqlite3") as db:
        db.execute("UPDATE run_items SET status='completed' WHERE run_id=? AND status='not_applicable'", (run_record.id,))
    with pytest.raises(ValueError, match="receipts|rows"):
        destination.import_completed_run(copy, run_record.id)
    copy, run_record, artifact = broken(finished, tmp_path, "skipped")
    skipped = copy / "artifacts" / artifact.data["bulk"]["dir"] / "skipped.json"
    skipped.write_text(skipped.read_text().replace("not_applicable", "failed", 1))
    with pytest.raises(ValueError, match="skipped"):
        destination.import_completed_run(copy, run_record.id)
    untouched(destination, artifact)
    destination.close()


def test_a_run_that_is_not_finished_or_is_a_different_run_is_refused(finished, world, tmp_path):
    source, run_record, artifact, _ = finished
    destination = JobManager(tmp_path / "destination")
    copy, _, _ = broken(finished, tmp_path, "cancelled")
    with sqlite3.connect(copy / "jobs.sqlite3") as db:
        db.execute("UPDATE runs SET cancel_requested=1 WHERE id=?", (run_record.id,))
    with pytest.raises(ValueError, match="completed"):
        destination.import_completed_run(copy, run_record.id)
    with pytest.raises(KeyError):
        destination.import_completed_run(source.work_dir, "no-such-run")
    with pytest.raises(ValueError, match="differ"):
        source.import_completed_run(source.work_dir, run_record.id)
    untouched(destination, artifact)
    destination.close()


def test_a_run_of_model_answers_arrives_with_its_text_columns_and_summary(server, tmp_path):
    ids = [f"q{i}" for i in range(7)]
    records = [Record(id=identity, dataset_id="d", release_id="r", snapshot_id="s", question="What color is it?" if i % 2 == 0 else "How many?") for i, identity in enumerate(ids)]
    selection = Selection(id="answers", ids=ids, unit="example", snapshot_ids=["s"], dataset_ids=["d"], created_at="2026-01-01T00:00:00Z")
    source = JobManager(tmp_path / "cluster")
    created = source.create(selection, records, "vlm.answer", {"provider": server.provider, "use_images": False, "storage": "arrays", "resource_class": "network"})
    finished = settled(source, created.id)
    assert finished.status == "completed", finished.errors
    artifact = source.get_artifact(finished.artifact_ids[0])
    assert artifact.data["bulk"]["texts"]["answer"]["count"] == 7
    destination = JobManager(tmp_path / "laptop")
    destination.import_completed_run(source.work_dir, finished.id)
    copy = destination.get_artifact(artifact.id)
    target = destination.artifact_dir / copy.data["bulk"]["dir"]
    assert store.read_texts(target, copy.data["bulk"]["texts"]["answer"]) == ["Red.", "two", "Red.", "two", "Red.", "two", "Red."]
    assert copy.data["summary"]["completed"] == 7 and copy.data["summary"]["not_completed"] == 0
    source.close()
    destination.close()


def test_the_command_line_imports_a_run_from_another_workspace(finished, tmp_path, capsys):
    import json
    from dataset_atlas.cli import main
    source, run_record, artifact, _ = finished
    workspace = tmp_path / "laptop"
    (workspace / "work").mkdir(parents=True)
    # The other workspace may be named by its folder or by its work/ folder.
    parent = tmp_path / "cluster-workspace"
    parent.mkdir()
    shutil.copytree(source.work_dir, parent / "work")
    for named in (parent, parent / "work"):
        assert main(["--root", str(workspace), "runs", "import", str(named), run_record.id]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["run_id"] == run_record.id and report["artifact_ids"] == [artifact.id] and report["processor_id"] == "project.pca"
    destination = JobManager(workspace / "work")
    assert [run.id for run in destination.list_runs()] == [run_record.id]
    assert (destination.artifact_dir / artifact.data["bulk"]["dir"] / "manifest.json").is_file()
    destination.close()
    assert main(["--root", str(workspace), "runs", "import", str(tmp_path / "nowhere"), run_record.id]) == 1
    assert "No finished runs" in capsys.readouterr().err
