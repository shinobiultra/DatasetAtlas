"""Columnar ("arrays") runs: vectors by reference in, array-backed artifacts out, through the real worker."""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import pytest

from dataset_atlas.jobs import JobManager
from dataset_atlas.models import Artifact, Record, Selection
from dataset_atlas.storage import arrays as store

needs_sklearn = pytest.mark.skipif(importlib.util.find_spec("sklearn") is None, reason="scikit-learn not installed")
needs_umap = pytest.mark.skipif(importlib.util.find_spec("umap") is None, reason="umap-learn not installed")
PER, DIM, BLOBS, MISSING = 60, 16, 3, 5


def settled(manager, run_id, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = manager.get_run(run_id)
        if run.status not in ("queued", "running"):
            return run
        time.sleep(0.05)
    pytest.fail("run did not settle")


@pytest.fixture
def world(tmp_path):
    """A manager, a registered array-backed embedding artifact, and a selection that includes records without vectors."""
    manager = JobManager(tmp_path / "work")
    rng = np.random.default_rng(3)
    means = rng.normal(size=(BLOBS, DIM)) * 5
    vectors = np.concatenate([means[i] + rng.normal(size=(PER, DIM)) * 0.1 for i in range(BLOBS)]).astype(np.float32)
    truth = np.repeat(np.arange(BLOBS), PER)
    embedded = [f"r{i:03d}" for i in range(len(vectors))]
    # The selection interleaves unembedded records with embedded ones, and is not in the bundle's order.
    selection_ids = list(reversed(embedded)) + [f"x{i}" for i in range(MISSING)]
    bundle = manager.artifact_dir / "arrays" / "embedding"
    manifest = store.write_bundle(bundle, embedded, {"vector": vectors})
    artifact = Artifact(id="embedding", kind="embed.siglip2", run_id="upstream", snapshot_ids=["snapshot"], unit="example", ids=embedded,
                        provenance={"processor_provenance": {"embedding_space_id": "space:test"}}, data={"bulk": {"dir": "arrays/embedding", **manifest}})
    with manager._db() as db:
        db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
    selection = Selection(id="selection", ids=selection_ids, unit="example", snapshot_ids=["snapshot"], dataset_ids=["dataset"], created_at="2026-01-01T00:00:00Z")
    records = [Record(id=record_id, dataset_id="dataset", release_id="release", snapshot_id="snapshot") for record_id in selection_ids]
    config = {"storage": "arrays", "backend": "cpu", "embedding_space_id": "space:test", "embedding_run_id": "upstream",
              "vector_source": {"dir": str(bundle), "array": "vector", "manifest": {key: manifest[key] for key in ("count", "ids", "arrays")}}}
    return manager, selection, records, config, embedded, truth, bundle


def run(world, processor, **extra):
    manager, selection, records, config, *_ = world
    created = manager.create(selection, records, processor, {**config, **extra})
    finished = settled(manager, created.id)
    assert finished.status == "completed", finished.errors
    artifact = manager.get_artifact(finished.artifact_ids[0])
    directory = manager.artifact_dir / artifact.data["bulk"]["dir"]
    return manager, finished, artifact, directory


def load(artifact, directory, name):
    bulk = artifact.data["bulk"]
    return store.read_array(directory, {**bulk["arrays"], **bulk.get("extras", {})}[name], verify=True)


def same_partition(left, right):
    pairs = {(int(a), int(b)) for a, b in zip(left, right)}
    return len(pairs) == len(set(left.tolist())) == len(set(right.tolist()))


def test_pca_run_yields_an_array_artifact_in_selection_order(world):
    from dataset_atlas.processors import engines
    manager, finished, artifact, directory = run(world, "project.pca", dimensions=3)
    embedded = world[4]
    ids = store.read_ids(directory, artifact.data["bulk"])
    # Rows follow the selection's order (reversed here), skipping records that have no vector.
    assert ids == [i for i in world[1].ids if i in set(embedded)] and len(ids) == BLOBS * PER
    coords = load(artifact, directory, "coords")
    assert coords.shape == (BLOBS * PER, 3) and coords.dtype == np.float32
    # Each id's coordinates equal a direct PCA of the original matrix, whatever order the rows were stored in.
    vectors = store.read_array(world[6], world[3]["vector_source"]["manifest"]["arrays"]["vector"])
    expected, _, _ = engines.pca(np.asarray(vectors), 3, "cpu")
    direct = dict(zip(embedded, expected))
    assert np.allclose(coords, np.array([direct[i] for i in ids]), atol=1e-3)
    assert "points" not in artifact.data and "items" not in artifact.data
    assert artifact.provenance["storage"] == "arrays" and artifact.provenance["processor_id"] == "project.pca"
    assert artifact.provenance["processor_provenance"]["population_count"] == len(world[1].ids)
    assert "fitted_ids" not in artifact.provenance["processor_provenance"]
    skipped = artifact.data["skipped"]
    assert skipped["count"] == MISSING and skipped["by_status"] == {"not_applicable": MISSING}
    assert not (manager.artifact_dir / "shards" / finished.id).exists(), "shards are removed after a completed run"
    assert finished.progress["completed"] == BLOBS * PER and finished.progress["not_applicable"] == MISSING


def test_kmeans_labels_line_up_with_ids_and_carry_summaries(world):
    _, _, artifact, directory = run(world, "cluster.kmeans", clusters=3, seed=1)
    embedded, truth = world[4], world[5]
    ids = store.read_ids(directory, artifact.data["bulk"])
    labels = load(artifact, directory, "cluster")
    by_id = dict(zip(embedded, truth))
    assert same_partition(labels, np.array([by_id[i] for i in ids]))
    summary = artifact.data["summary"]
    assert summary["cluster_count"] == 3 and sorted(c["size"] for c in summary["clusters"]) == [PER] * 3
    assert all(by_id[e] == by_id[ids[list(labels).index(c["cluster"])]] for c in summary["clusters"] for e in c["exemplar_ids"])
    assert load(artifact, directory, "centroids").shape == (3, DIM)
    assert summary["silhouette_sample"] > 0.9


@needs_sklearn
def test_hdbscan_and_knn_outlier_runs(world):
    _, _, artifact, directory = run(world, "cluster.hdbscan", min_cluster_size=10, metric="euclidean")
    labels = load(artifact, directory, "cluster")
    assert len(set(labels.tolist()) - {-1}) == BLOBS and load(artifact, directory, "probability").shape == labels.shape
    _, _, outliers, odir = run(world, "outlier.knn", neighbors=3, metric="euclidean")
    scores = load(outliers, odir, "outlier_score")
    assert scores.shape == (BLOBS * PER,) and (scores >= 0).all()


@needs_umap
def test_umap_run_in_three_dimensions(world):
    _, _, artifact, directory = run(world, "project.umap", dimensions=3, neighbors=10)
    assert load(artifact, directory, "coords").shape == (BLOBS * PER, 3)
    assert artifact.provenance["processor_provenance"]["backend"] == "cpu"
    assert artifact.provenance["processor_provenance"]["parameters"]["n_components"] == 3


def test_a_changed_vector_file_fails_the_run_instead_of_analysing_it(world):
    manager, selection, records, config, *_, bundle = world
    path = bundle / "vector.npy"
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF
    path.write_bytes(bytes(data))
    created = manager.create(selection, records, "project.pca", {**config, "dimensions": 2})
    finished = settled(manager, created.id)
    assert finished.status == "failed" and any("checksum" in json.dumps(error) for error in finished.errors)


def test_a_tampered_shard_is_not_imported(world, tmp_path):
    manager, selection, records, config, *_ = world
    created = manager.create(selection, records, "project.pca", {**config, "dimensions": 2})
    settled(manager, created.id)
    # Build a second run's shard by hand, corrupt one array, and import it directly.
    other = manager.create(selection, records, "cluster.kmeans", {**config, "clusters": 2})
    settled(manager, other.id)
    stage = manager.stage_dir / "synthetic"
    stage.mkdir()
    with manager._db() as db:
        keys = dict(db.execute("SELECT record_id,item_key FROM run_items WHERE run_id=?", (other.id,)))
        db.execute("UPDATE run_items SET status='queued' WHERE run_id=?", (other.id,))
    from dataset_atlas.jobs.worker import _write_shard
    from dataset_atlas.processors.bulk import BulkResult
    ids = list(keys)[:2]
    result = {"bulk": BulkResult(ids=ids, arrays={"cluster": np.array([0, 1], dtype=np.int32)}, provenance={},
                                 skipped={record_id: {"status": "not_applicable"} for record_id in list(keys)[2:]}),
              "provenance": {}, "coverage": {}, "processor_id": "cluster.kmeans", "unit": "example"}
    _write_shard(stage, "bad", keys, result, 1 << 20)
    shard = stage / "shard-bad"
    (shard / "cluster.npy").write_bytes((shard / "cluster.npy").read_bytes()[:-1] + b"\x07")
    with manager._db() as db:
        manager._import_shard(db, other.id, shard)
        states = dict(db.execute("SELECT status,count(*) FROM run_items WHERE run_id=? GROUP BY status", (other.id,)))
    assert states.get("failed") == len(keys) and (stage / "shard-bad.invalid").is_dir()


def test_array_budget_is_enforced_and_storage_is_validated(world):
    manager, selection, records, config, *_ = world
    with pytest.raises(ValueError, match="storage must be"):
        manager.estimate(selection, records, "project.pca", {**config, "storage": "parquet"})
    estimate = manager.estimate(selection, records, "project.pca", {**config, "dimensions": 2})
    assert estimate["storage"] == "arrays" and estimate["resource_limits"]["max_cpu_seconds"] > 3600
    created = manager.create(selection, records, "project.pca", {**config, "dimensions": 2, "max_output_bytes": 100})
    finished = settled(manager, created.id)
    assert finished.status in {"failed", "partial"}


def test_a_partial_run_keeps_its_finished_shards_and_a_retry_assembles_all_of_them(world):
    """Shards survive a partial run; once the rest arrive, the final artifact has every row in selection order."""
    from dataset_atlas.jobs.worker import _write_shard
    from dataset_atlas.processors.bulk import BulkResult
    manager, selection, records, config, embedded, *_ = world
    manager._launch = lambda run_id: None  # drive the coordinator by hand: no worker is started
    run = manager.create(selection, records, "cluster.kmeans", {**config, "clusters": 2})
    with manager._db() as db:
        keys = dict(db.execute("SELECT record_id,item_key FROM run_items WHERE run_id=?", (run.id,)))
    stage = manager.stage_dir / run.id
    stage.mkdir(exist_ok=True)
    order = [record_id for record_id in selection.ids if record_id in set(embedded)]
    halves = [order[: len(order) // 2], order[len(order) // 2:]]

    def shard(name, ids, labels, skipped=()):
        keys_here = {record_id: keys[record_id] for record_id in [*ids, *skipped]}
        result = {"bulk": BulkResult(ids=list(ids), arrays={"cluster": np.array(labels, dtype=np.int32)}, provenance={"method": "test"},
                                     skipped={record_id: {"status": "not_applicable"} for record_id in skipped}),
                  "provenance": {"method": "test"}, "coverage": {}, "processor_id": "cluster.kmeans", "unit": "example"}
        _write_shard(stage, name, keys_here, result, 1 << 20)
        return stage / f"shard-{name}"

    missing = [record_id for record_id in selection.ids if record_id not in set(embedded)]
    with manager._db() as db:
        manager._import_shard(db, run.id, shard("first", halves[0], [0] * len(halves[0]), skipped=missing))
        partial = manager._refresh(db, run.id, final=True, exit_code=1)
        first = manager._register_bulk_artifact(db, run.id, partial)
    assert partial.status == "partial" and first.artifact_ids
    partial_artifact = manager.get_artifact(first.artifact_ids[0])
    assert partial_artifact.data["bulk"]["count"] == len(halves[0])
    assert (manager.artifact_dir / "shards" / run.id).is_dir(), "finished shards are kept for a retry"
    with manager._db() as db:
        manager._import_shard(db, run.id, shard("second", halves[1], [1] * len(halves[1])))
        done = manager._refresh(db, run.id, final=True)
        final = manager._register_bulk_artifact(db, run.id, done)
    assert done.status == "completed"
    artifact = manager.get_artifact(final.artifact_ids[0])
    assert artifact.id != partial_artifact.id and artifact.data["bulk"]["count"] == len(order)
    directory = manager.artifact_dir / artifact.data["bulk"]["dir"]
    assert store.read_ids(directory, artifact.data["bulk"]) == order
    labels = load(artifact, directory, "cluster")
    assert labels[: len(halves[0])].tolist() == [0] * len(halves[0]) and labels[len(halves[0]):].tolist() == [1] * len(halves[1])
