from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from dataset_atlas.processors import engines
from dataset_atlas.storage import arrays

CUDA = engines.backend_available("torch")
HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None
needs_cuda = pytest.mark.skipif(not CUDA, reason="no CUDA device with PyTorch")
needs_sklearn = pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn not installed")


def blobs(per=60, dim=16, centers=3, seed=0, spread=0.05):
    rng = np.random.default_rng(seed)
    means = rng.normal(size=(centers, dim)) * 4
    data = np.concatenate([means[i] + rng.normal(size=(per, dim)) * spread for i in range(centers)]).astype(np.float32)
    truth = np.repeat(np.arange(centers), per)
    return data, truth


def same_partition(left, right):
    pairs = {(int(a), int(b)) for a, b in zip(left, right)}
    return len(pairs) == len(set(left.tolist())) == len(set(right.tolist()))


# --- array bundles ---------------------------------------------------------

def test_bundle_round_trips_and_detects_tampering(tmp_path):
    ids = [f"r{i}" for i in range(5)]
    values = np.arange(10, dtype=np.float32).reshape(5, 2)
    manifest = arrays.write_bundle(tmp_path, ids, {"coords": values, "cluster": np.arange(5, dtype=np.int32)})
    assert manifest["count"] == 5 and manifest["arrays"]["coords"]["shape"] == [5, 2]
    assert arrays.read_ids(tmp_path, manifest) == ids
    loaded = arrays.read_array(tmp_path, manifest["arrays"]["coords"], verify=True)
    assert isinstance(loaded, np.memmap) and np.array_equal(loaded, values)
    (tmp_path / "coords.npy").write_bytes((tmp_path / "coords.npy").read_bytes()[:-4] + b"\0\0\0\0")
    with pytest.raises(ValueError, match="checksum"):
        arrays.read_array(tmp_path, manifest["arrays"]["coords"], verify=True)


def test_bundle_rejects_bad_names_shapes_and_non_finite_values(tmp_path):
    with pytest.raises(ValueError, match="rows"):
        arrays.write_bundle(tmp_path, ["a", "b"], {"x": np.zeros((3, 2), dtype=np.float32)})
    with pytest.raises(ValueError, match="Array name"):
        arrays.write_array(tmp_path, "../escape", np.zeros(2, dtype=np.float32))
    with pytest.raises(ValueError, match="non-finite"):
        arrays.write_array(tmp_path, "x", np.array([1.0, np.nan], dtype=np.float32))
    with pytest.raises(ValueError, match="dtype"):
        arrays.write_array(tmp_path, "x", np.array(["a"]))
    with pytest.raises(ValueError, match="unique"):
        arrays.write_bundle(tmp_path, ["a", "a"], {})


# --- PCA -------------------------------------------------------------------

def reference_pca(matrix, k):
    centered = matrix.astype(np.float64) - matrix.astype(np.float64).mean(0)
    u, s, _ = np.linalg.svd(centered, full_matrices=False)
    return u[:, :k] * s[:k], (s ** 2)[:k] / (s ** 2).sum()


def test_pca_matches_svd_on_cpu():
    data, _ = blobs()
    coords, explained, backend = engines.pca(data, 3, "cpu")
    expected, variance = reference_pca(data, 3)
    assert backend == "cpu" and coords.shape == (180, 3)
    assert np.allclose(np.abs(coords), np.abs(expected), atol=1e-3)
    assert np.allclose(explained, variance, atol=1e-6)


@needs_cuda
def test_pca_on_gpu_agrees_with_cpu():
    data, _ = blobs()
    cpu, explained_cpu, _ = engines.pca(data, 3, "cpu")
    gpu, explained_gpu, backend = engines.pca(data, 3, "torch")
    assert backend == "torch" and np.allclose(gpu, cpu, atol=1e-3) and np.allclose(explained_gpu, explained_cpu, atol=1e-6)


# --- k-means ---------------------------------------------------------------

@pytest.mark.parametrize("backend", ["cpu", pytest.param("torch", marks=needs_cuda)])
def test_kmeans_recovers_separated_blobs_and_is_repeatable(backend):
    data, truth = blobs()
    first = engines.kmeans(data, 3, seed=1, backend=backend)
    again = engines.kmeans(data, 3, seed=1, backend=backend)
    assert first["backend"] == backend and same_partition(first["labels"], truth)
    assert np.array_equal(first["labels"], again["labels"])
    assert first["centers"].shape == (3, 16) and first["inertia"] > 0


def test_kmeans_cosine_normalises_and_validates():
    data, truth = blobs()
    assert same_partition(engines.kmeans(data, 3, metric="cosine", backend="cpu")["labels"], truth)
    with pytest.raises(ValueError, match="within"):
        engines.kmeans(data, 0, backend="cpu")
    with pytest.raises(ValueError, match="metric"):
        engines.kmeans(data, 3, metric="manhattan", backend="cpu")


def test_kmeans_handles_duplicate_rows_without_empty_cluster_failures():
    data = np.repeat(np.eye(4, dtype=np.float32), 10, axis=0)
    result = engines.kmeans(data, 4, backend="cpu")
    assert len(set(result["labels"].tolist())) == 4


# --- nearest neighbours ----------------------------------------------------

def brute_force(matrix, k, metric):
    x = matrix.astype(np.float64)
    if metric == "cosine":
        x = x / np.linalg.norm(x, axis=1, keepdims=True)
        distance = 1 - x @ x.T
    else:
        distance = np.sqrt(np.maximum(((x[:, None] - x[None]) ** 2).sum(2), 0))
    np.fill_diagonal(distance, np.inf)
    return np.sort(distance, axis=1)[:, :k]


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
@pytest.mark.parametrize("backend", ["cpu", pytest.param("torch", marks=needs_cuda)])
def test_knn_matches_brute_force(metric, backend):
    data, _ = blobs(per=40, spread=0.5)
    result = engines.knn(data, 5, metric, backend)
    assert result["indices"].shape == (120, 5) and not (result["indices"] == np.arange(120)[:, None]).any()
    assert np.allclose(result["distances"], brute_force(data, 5, metric), atol=2e-3)


def test_knn_cpu_row_limit_and_argument_checks():
    data, _ = blobs()
    with pytest.raises(ValueError, match="limited"):
        engines.knn(data, 3, "cosine", "cpu", max_cpu_rows=10)
    with pytest.raises(ValueError, match="neighbors"):
        engines.knn(data, 500, "cosine", "cpu")
    with pytest.raises(ValueError, match="nonzero"):
        engines.knn(np.zeros((6, 3), dtype=np.float32), 2, "cosine", "cpu")


# --- backends --------------------------------------------------------------

def test_backend_choice_is_explicit_and_explains_a_missing_one(monkeypatch):
    assert engines.choose_backend("kmeans", "cpu") == "cpu"
    with pytest.raises(ValueError, match="supports the backends"):
        engines.choose_backend("umap", "torch")
    monkeypatch.setattr(engines, "backend_available", lambda name: name == "cpu")
    assert engines.choose_backend("umap", "auto") == "cpu"
    with pytest.raises(ValueError, match="gpu extra"):
        engines.choose_backend("umap", "cuml")


# --- clustering ------------------------------------------------------------

@needs_sklearn
def test_hdbscan_finds_the_blobs_and_labels_stragglers_noise():
    data, truth = blobs(per=80, spread=0.05)
    outlier = np.full((1, 16), 50.0, dtype=np.float32)
    result = engines.hdbscan_cluster(np.vstack([data, outlier]), min_cluster_size=10, metric="euclidean", backend="cpu")
    assert result["labels"][-1] == -1 and same_partition(result["labels"][:-1], truth)
    assert result["probabilities"].shape == (241,)


@needs_sklearn
def test_agglomerative_exact_and_two_stage_agree_on_blobs():
    data, truth = blobs(per=100)
    exact = engines.agglomerative(data, 3)
    staged = engines.agglomerative(data, 3, exact_limit=10, micro_clusters=20, backend="cpu")
    assert not exact["two_stage"] and staged["two_stage"] and staged["micro_clusters"] == 20
    assert same_partition(exact["labels"], truth) and same_partition(staged["labels"], truth)


def test_cluster_summaries_report_size_exemplars_and_noise():
    data, truth = blobs(per=30)
    labels = truth.copy()
    labels[:3] = -1
    summary = engines.cluster_summaries(data, labels, metric="euclidean", exemplars=4)
    sizes = {row["cluster"]: row["size"] for row in summary["clusters"]}
    assert sizes == {0: 27, 1: 30, 2: 30} and summary["noise"] == 3
    assert all(len(row["exemplar_rows"]) == 4 for row in summary["clusters"])
    assert all(labels[row] == cluster["cluster"] for cluster in summary["clusters"] for row in cluster["exemplar_rows"])
    assert summary["centroids"].shape == (3, 16)


def test_silhouette_is_high_for_separated_and_none_for_one_cluster():
    data, truth = blobs()
    assert engines.silhouette_sample(data, truth, metric="euclidean") > 0.9
    assert engines.silhouette_sample(data, np.zeros(len(data), dtype=int)) is None
