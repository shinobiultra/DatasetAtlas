"""Numeric engines for projection, clustering and neighbours, on a GPU when one is usable.

Each method has an ordered list of backends: ``cuml`` (RAPIDS), ``torch`` (CUDA) and
``cpu``. ``auto`` takes the first one that is installed and has a device; naming a
backend that is missing is an error that says how to install it, never a silent
fallback, because the backend is part of how a result was produced and is recorded
in its provenance. PCA, k-means and exact kNN run on NumPy alone, so they need no extra.
"""
from __future__ import annotations

import importlib
import importlib.util
import math
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np

CHUNK_BYTES = 128 * 1024 * 1024
BACKENDS = {
    "pca": ("torch", "cpu"),
    "kmeans": ("torch", "cpu"),
    "knn": ("torch", "cpu"),
    "umap": ("cuml", "cpu"),
    "hdbscan": ("cuml", "cpu"),
    "agglomerative": ("cpu",),
}
_GPU_HELP = {"torch": "install the vision or embeddings extra for CUDA PyTorch (`uv sync --all-extras`)",
             "cuml": "install the gpu extra (`uv sync --all-extras`; RAPIDS cuML needs CUDA 13, driver 580.65.06 or newer)"}


def _have(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def gpu_hint() -> bool:
    """Cheap, import-free hint that an NVIDIA driver is present (the API process never imports torch)."""
    return Path("/proc/driver/nvidia").exists() or shutil.which("nvidia-smi") is not None


def cuda_ready() -> bool:
    """True when this process can run CUDA work. Imports torch (or cupy), so call it in a worker."""
    if _have("torch"):
        torch = importlib.import_module("torch")
        return bool(torch.cuda.is_available())
    if _have("cupy"):
        try:
            return int(importlib.import_module("cupy").cuda.runtime.getDeviceCount()) > 0
        except Exception:
            return False
    return False


def backend_available(name: str) -> bool:
    if name == "cpu":
        return True
    if name == "torch":
        return _have("torch") and cuda_ready()
    if name == "cuml":
        return _have("cuml") and cuda_ready()
    return False


def choose_backend(method: str, requested: str = "auto") -> str:
    options = BACKENDS[method]
    if requested == "auto":
        return next(name for name in options if backend_available(name))
    if requested not in options:
        raise ValueError(f"{method} supports the backends {', '.join(options)}, not {requested}")
    if not backend_available(requested):
        raise ValueError(f"Backend {requested} is not usable here for {method}: {_GPU_HELP.get(requested, 'no device found')}")
    return requested


def _rows_per_chunk(width: int, itemsize: int = 4) -> int:
    return max(1024, CHUNK_BYTES // max(1, width * itemsize))


def _float32(chunk: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(chunk, dtype=np.float32)


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    out = np.empty(matrix.shape, dtype=np.float32)
    step = _rows_per_chunk(matrix.shape[1])
    for start in range(0, len(matrix), step):
        block = _float32(matrix[start:start + step])
        norms = np.linalg.norm(block, axis=1, keepdims=True)
        if (norms == 0).any():
            raise ValueError("Cosine distance requires nonzero vectors")
        out[start:start + step] = block / norms
    return out


# --- PCA -------------------------------------------------------------------

def pca(matrix: np.ndarray, n_components: int = 2, backend: str = "auto") -> tuple[np.ndarray, list[float], str]:
    """Exact PCA from the covariance eigendecomposition, streamed in row chunks.

    Equivalent to centred SVD up to sign (fixed below) and rounding, but never holds
    more than one chunk beyond the data, so it scales to hundreds of thousands of rows.
    Returns coordinates (float32), explained variance ratios and the backend used.
    """
    n, d = matrix.shape
    if n < 2 or d < n_components:
        raise ValueError("PCA needs at least two rows and enough input dimensions")
    backend = choose_backend("pca", backend)
    step = _rows_per_chunk(d, 8)
    if backend == "torch":
        torch = importlib.import_module("torch")
        device = torch.device("cuda")
        total = torch.zeros(d, dtype=torch.float64, device=device)
        for start in range(0, n, step):
            total += torch.from_numpy(_float32(matrix[start:start + step])).to(device).double().sum(0)
        mean = total / n
        cov = torch.zeros((d, d), dtype=torch.float64, device=device)
        for start in range(0, n, step):
            block = torch.from_numpy(_float32(matrix[start:start + step])).to(device).double() - mean
            cov += block.T @ block
        values, vectors = torch.linalg.eigh(cov)
        order = torch.argsort(values, descending=True)
        values, vectors = values[order].clamp_min(0), vectors[:, order[:n_components]]
        coords = np.empty((n, n_components), dtype=np.float32)
        for start in range(0, n, step):
            block = torch.from_numpy(_float32(matrix[start:start + step])).to(device).double() - mean
            coords[start:start + step] = (block @ vectors).float().cpu().numpy()
        values = values.cpu().numpy()
    else:
        mean = np.zeros(d, dtype=np.float64)
        for start in range(0, n, step):
            mean += matrix[start:start + step].astype(np.float64).sum(0)
        mean /= n
        cov = np.zeros((d, d), dtype=np.float64)
        for start in range(0, n, step):
            block = matrix[start:start + step].astype(np.float64) - mean
            cov += block.T @ block
        values, vectors = np.linalg.eigh(cov)
        order = np.argsort(values)[::-1]
        values, vectors = np.maximum(values[order], 0), vectors[:, order[:n_components]]
        coords = np.empty((n, n_components), dtype=np.float32)
        for start in range(0, n, step):
            coords[start:start + step] = ((matrix[start:start + step].astype(np.float64) - mean) @ vectors).astype(np.float32)
    # The eigenvector sign is arbitrary; fix it so serialisation is reproducible.
    for column in range(n_components):
        pivot = int(np.argmax(np.abs(coords[:, column])))
        if coords[pivot, column] < 0:
            coords[:, column] *= -1
    total_variance = float(values.sum())
    explained = (values[:n_components] / total_variance).tolist() if total_variance > 0 else [0.0] * n_components
    return coords, explained, backend


# --- k-means ---------------------------------------------------------------

def _group_sums(block: np.ndarray, labels: np.ndarray, sums: np.ndarray, counts: np.ndarray) -> None:
    order = np.argsort(labels, kind="stable")
    sorted_labels = labels[order]
    starts = np.flatnonzero(np.r_[True, sorted_labels[1:] != sorted_labels[:-1]])
    sums[sorted_labels[starts]] += np.add.reduceat(block[order], starts, axis=0)
    counts[sorted_labels[starts]] += np.diff(np.r_[starts, len(sorted_labels)])


def _kmeans_numpy(matrix: np.ndarray, k: int, rng: np.random.Generator, max_iter: int, tol: float):
    n, d = matrix.shape
    step = _rows_per_chunk(max(d, k))
    centers = _float32(matrix[[int(rng.integers(n))]])
    nearest = np.full(n, np.inf, dtype=np.float32)
    for index in range(1, k):  # k-means++ seeding
        for start in range(0, n, step):
            block = _float32(matrix[start:start + step])
            gap = ((block - centers[-1]) ** 2).sum(1)
            nearest[start:start + step] = np.minimum(nearest[start:start + step], gap)
        weights = nearest.astype(np.float64)
        pick = int(rng.choice(n, p=weights / weights.sum())) if weights.sum() > 0 else int(rng.integers(n))
        centers = np.vstack([centers, _float32(matrix[[pick]])])
    labels = np.zeros(n, dtype=np.int32)
    inertia = math.inf
    for iteration in range(1, max_iter + 1):
        sums = np.zeros((k, d), dtype=np.float64)
        counts = np.zeros(k, dtype=np.int64)
        csq = (centers ** 2).sum(1)
        inertia, worst, worst_gap = 0.0, 0, -1.0
        for start in range(0, n, step):
            block = _float32(matrix[start:start + step])
            d2 = (block ** 2).sum(1)[:, None] - 2 * block @ centers.T + csq[None, :]
            chunk_labels = d2.argmin(1).astype(np.int32)
            gap = np.maximum(d2[np.arange(len(block)), chunk_labels], 0)
            labels[start:start + step] = chunk_labels
            inertia += float(gap.sum())
            if gap.max() > worst_gap:
                worst, worst_gap = start + int(gap.argmax()), float(gap.max())
            _group_sums(block.astype(np.float64), chunk_labels, sums, counts)
        updated = centers.copy()
        full = counts > 0
        updated[full] = (sums[full] / counts[full, None]).astype(np.float32)
        if (~full).any():  # empty clusters restart at the worst-fitted row, deterministically
            updated[np.flatnonzero(~full)[0]] = _float32(matrix[[worst]])[0]
        shift = float(((updated - centers) ** 2).sum())
        centers = updated
        if shift <= tol * max(1.0, float((centers ** 2).sum())):
            break
    return labels, centers, inertia, iteration


def _kmeans_torch(matrix: np.ndarray, k: int, seed: int, max_iter: int, tol: float):
    torch = importlib.import_module("torch")
    device = torch.device("cuda")
    n, d = matrix.shape
    free, _ = torch.cuda.mem_get_info()
    if n * d * 4 > free * 0.6:
        raise ValueError("The vectors do not fit in GPU memory; use backend cpu or reduce the dimension first")
    x = torch.empty((n, d), dtype=torch.float32, device=device)
    step = _rows_per_chunk(d)
    for start in range(0, n, step):
        x[start:start + step] = torch.from_numpy(_float32(matrix[start:start + step])).to(device)
    xsq = (x * x).sum(1)
    gen = torch.Generator(device=device).manual_seed(seed)
    rows = max(1024, (256 * 1024 * 1024) // (4 * max(k, 1)))
    centers = x[torch.randint(n, (1,), generator=gen, device=device)].clone()
    nearest = torch.full((n,), float("inf"), device=device)
    for _ in range(1, k):
        nearest = torch.minimum(nearest, ((x - centers[-1]) ** 2).sum(1))
        total = nearest.sum()
        pick = torch.multinomial(nearest / total, 1, generator=gen) if total > 0 else torch.randint(n, (1,), generator=gen, device=device)
        centers = torch.cat([centers, x[pick]])
    labels = torch.zeros(n, dtype=torch.int64, device=device)
    inertia = math.inf
    for iteration in range(1, max_iter + 1):
        csq = (centers * centers).sum(1)
        gaps = torch.empty(n, device=device)
        for start in range(0, n, rows):
            d2 = xsq[start:start + rows, None] - 2 * x[start:start + rows] @ centers.T + csq[None, :]
            best, chosen = d2.min(1)
            labels[start:start + rows], gaps[start:start + rows] = chosen, best.clamp_min(0)
        inertia = float(gaps.sum())
        sums = torch.zeros((k, d), device=device).index_add_(0, labels, x)
        counts = torch.bincount(labels, minlength=k)
        updated = torch.where(counts[:, None] > 0, sums / counts.clamp_min(1)[:, None], centers)
        empty = torch.nonzero(counts == 0).flatten()
        if len(empty):
            updated[empty[0]] = x[gaps.argmax()]
        shift = float(((updated - centers) ** 2).sum())
        centers = updated
        if shift <= tol * max(1.0, float((centers ** 2).sum())):
            break
    return labels.int().cpu().numpy(), centers.cpu().numpy(), inertia, iteration


def kmeans(matrix: np.ndarray, clusters: int, seed: int = 42, *, max_iter: int = 100, n_init: int = 1,
           tol: float = 1e-6, metric: str = "euclidean", backend: str = "auto") -> dict[str, Any]:
    """Lloyd k-means with k-means++ seeding and ``n_init`` restarts; cosine means unit-length rows."""
    n = len(matrix)
    if clusters < 1 or clusters > n:
        raise ValueError("clusters must be within 1..population size")
    if metric not in {"euclidean", "cosine"}:
        raise ValueError("k-means metric must be euclidean or cosine")
    backend = choose_backend("kmeans", backend)
    data = _normalize_rows(matrix) if metric == "cosine" else matrix
    best = None
    for restart in range(max(1, n_init)):
        if backend == "torch":
            run = _kmeans_torch(data, clusters, seed + restart, max_iter, tol)
        else:
            run = _kmeans_numpy(data, clusters, np.random.default_rng(seed + restart), max_iter, tol)
        if best is None or run[2] < best[2]:
            best = run
    labels, centers, inertia, iterations = best
    return {"labels": labels, "centers": centers, "inertia": float(inertia), "iterations": int(iterations), "backend": backend}


# --- nearest neighbours ----------------------------------------------------

def knn(matrix: np.ndarray, k: int, metric: str = "cosine", backend: str = "auto", *, max_cpu_rows: int = 60_000) -> dict[str, Any]:
    """Exact k nearest *other* rows by brute force: distances (n, k) float32 and indices (n, k) int32."""
    n, d = matrix.shape
    if n < 2 or k < 1 or k >= n:
        raise ValueError("neighbors must be within 1..population size minus one")
    if metric not in {"cosine", "euclidean"}:
        raise ValueError("metric must be cosine or euclidean")
    backend = choose_backend("knn", backend)
    if backend == "cpu" and n > max_cpu_rows:
        raise ValueError(f"Exact neighbours on the CPU are limited to {max_cpu_rows} rows; use a GPU backend or a smaller selection")
    data = _normalize_rows(matrix) if metric == "cosine" else None
    distances = np.empty((n, k), dtype=np.float32)
    indices = np.empty((n, k), dtype=np.int32)
    if backend == "torch":
        torch = importlib.import_module("torch")
        device = torch.device("cuda")
        free, _ = torch.cuda.mem_get_info()
        if n * d * 4 > free * 0.5:
            raise ValueError("The vectors do not fit in GPU memory; use backend cpu or reduce the dimension first")
        x = torch.empty((n, d), dtype=torch.float32, device=device)
        source = data if data is not None else matrix
        for start in range(0, n, _rows_per_chunk(d)):
            x[start:start + _rows_per_chunk(d)] = torch.from_numpy(_float32(source[start:start + _rows_per_chunk(d)])).to(device)
        xsq = (x * x).sum(1)
        rows = max(256, min(4096, int(free * 0.15 // (4 * n))))
        # Full fp32, not TF32: the |x|^2 - 2x.y + |y|^2 expansion cancels badly at TF32's 10-bit mantissa.
        for start in range(0, n, rows):
            stop = min(n, start + rows)
            d2 = xsq[start:stop, None] - 2 * x[start:stop] @ x.T + xsq[None, :]
            d2[torch.arange(stop - start, device=device), torch.arange(start, stop, device=device)] = float("inf")
            best, where = torch.topk(d2, k, dim=1, largest=False)
            best = best.clamp_min(0)
            distances[start:stop] = (best / 2 if metric == "cosine" else best.sqrt()).cpu().numpy()
            indices[start:stop] = where.int().cpu().numpy()
    else:
        source = data if data is not None else _float32(matrix)
        sq = (source * source).sum(1)
        rows = max(64, min(2048, CHUNK_BYTES // (4 * n)))
        for start in range(0, n, rows):
            stop = min(n, start + rows)
            d2 = sq[start:stop, None] - 2 * source[start:stop] @ source.T + sq[None, :]
            d2[np.arange(stop - start), np.arange(start, stop)] = np.inf
            where = np.argpartition(d2, k - 1, axis=1)[:, :k]
            best = np.take_along_axis(d2, where, axis=1)
            order = np.argsort(best, axis=1)
            best, where = np.take_along_axis(best, order, axis=1), np.take_along_axis(where, order, axis=1)
            best = np.maximum(best, 0)
            distances[start:stop] = best / 2 if metric == "cosine" else np.sqrt(best)
            indices[start:stop] = where
    # For unit rows squared euclidean = 2 - 2 cos, so cosine distance (1 - cos) is half of it.
    return {"distances": distances, "indices": indices, "backend": backend, "metric": metric}


# --- UMAP, HDBSCAN, agglomerative -----------------------------------------

def umap_embed(matrix: np.ndarray, *, n_components: int = 2, n_neighbors: int = 15, min_dist: float = 0.1,
               metric: str = "cosine", seed: int = 42, backend: str = "auto") -> dict[str, Any]:
    backend = choose_backend("umap", backend)
    if backend == "cuml":
        umap = importlib.import_module("cuml.manifold").UMAP
        model = umap(n_components=n_components, n_neighbors=n_neighbors, min_dist=min_dist, metric=metric,
                     random_state=seed, output_type="numpy")
        coords = np.asarray(model.fit_transform(_float32(matrix)), dtype=np.float32)
        library = importlib.import_module("cuml").__version__
    else:
        umap = importlib.import_module("umap")
        # A fixed random_state makes umap-learn single-threaded, which is the reproducible choice.
        model = umap.UMAP(n_components=n_components, n_neighbors=n_neighbors, min_dist=min_dist, metric=metric,
                          random_state=seed, n_jobs=1)
        coords = np.asarray(model.fit_transform(_float32(matrix)), dtype=np.float32)
        library = umap.__version__
    return {"coords": coords, "backend": backend, "library_version": library}


def hdbscan_cluster(matrix: np.ndarray, *, min_cluster_size: int = 15, min_samples: int | None = None,
                    metric: str = "cosine", backend: str = "auto", max_cpu_cells: int = 400_000_000) -> dict[str, Any]:
    """Density clustering; label -1 is noise. Cosine runs as euclidean on unit-length rows."""
    n, d = matrix.shape
    backend = choose_backend("hdbscan", backend)
    if backend == "cpu" and n * d > max_cpu_cells:
        raise ValueError("HDBSCAN on the CPU is too slow at this size: use the GPU backend, or run it on a PCA or UMAP reduction")
    data = _normalize_rows(matrix) if metric == "cosine" else _float32(matrix)
    if metric not in {"cosine", "euclidean"}:
        raise ValueError("HDBSCAN metric must be cosine or euclidean")
    if backend == "cuml":
        cluster = importlib.import_module("cuml.cluster").HDBSCAN
        model = cluster(min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean", output_type="numpy")
        model.fit(data)
        library = importlib.import_module("cuml").__version__
    else:
        sklearn_cluster = importlib.import_module("sklearn.cluster")
        model = sklearn_cluster.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, metric="euclidean", n_jobs=-1, copy=False)
        model.fit(data)
        library = importlib.import_module("sklearn").__version__
    return {"labels": np.asarray(model.labels_, dtype=np.int32), "probabilities": np.asarray(model.probabilities_, dtype=np.float32),
            "backend": backend, "library_version": library}


def agglomerative(matrix: np.ndarray, clusters: int, *, linkage: str = "ward", seed: int = 42, exact_limit: int = 20_000,
                  micro_clusters: int = 2000, backend: str = "auto") -> dict[str, Any]:
    """Hierarchical clustering. Above ``exact_limit`` rows it clusters k-means micro-clusters instead
    (a two-stage tree, so memory stays bounded) and says so in the result."""
    n = len(matrix)
    if clusters < 1 or clusters > n:
        raise ValueError("clusters must be within 1..population size")
    sklearn_cluster = importlib.import_module("sklearn.cluster")
    if n <= exact_limit:
        labels = sklearn_cluster.AgglomerativeClustering(n_clusters=clusters, linkage=linkage).fit_predict(_float32(matrix))
        return {"labels": labels.astype(np.int32), "two_stage": False, "micro_clusters": None}
    micro = min(max(micro_clusters, clusters), n)
    stage = kmeans(matrix, micro, seed, backend=backend)
    tree = sklearn_cluster.AgglomerativeClustering(n_clusters=clusters, linkage=linkage).fit_predict(stage["centers"])
    return {"labels": tree[stage["labels"]].astype(np.int32), "two_stage": True, "micro_clusters": int(micro), "backend": stage["backend"]}


# --- cluster summaries -----------------------------------------------------

def cluster_summaries(matrix: np.ndarray, labels: np.ndarray, *, metric: str = "cosine", exemplars: int = 5) -> dict[str, Any]:
    """Per-cluster size, centroid, compactness and the rows closest to the centroid.

    Noise (label -1) is counted but gets no centroid. Rows are returned as indices so the
    caller maps them to record ids.
    """
    n, d = matrix.shape
    ids = sorted(int(value) for value in np.unique(labels) if value >= 0)
    sums = {label: np.zeros(d, dtype=np.float64) for label in ids}
    counts = {label: 0 for label in ids}
    step = _rows_per_chunk(d)
    for start in range(0, n, step):
        block = _float32(matrix[start:start + step])
        if metric == "cosine":
            block = block / np.maximum(np.linalg.norm(block, axis=1, keepdims=True), 1e-12)
        for label in np.unique(labels[start:start + step]):
            if label >= 0:
                chosen = labels[start:start + step] == label
                sums[int(label)] += block[chosen].astype(np.float64).sum(0)
                counts[int(label)] += int(chosen.sum())
    centroids = np.zeros((len(ids), d), dtype=np.float32)
    for row, label in enumerate(ids):
        mean = sums[label] / max(counts[label], 1)
        centroids[row] = (mean / max(np.linalg.norm(mean), 1e-12) if metric == "cosine" else mean).astype(np.float32)
    best: dict[int, list[tuple[float, int]]] = {label: [] for label in ids}
    spread = {label: 0.0 for label in ids}
    position = {label: row for row, label in enumerate(ids)}
    for start in range(0, n, step):
        block = _float32(matrix[start:start + step])
        if metric == "cosine":
            block = block / np.maximum(np.linalg.norm(block, axis=1, keepdims=True), 1e-12)
        for label in np.unique(labels[start:start + step]):
            if label < 0:
                continue
            chosen = np.flatnonzero(labels[start:start + step] == label)
            gap = ((block[chosen] - centroids[position[int(label)]]) ** 2).sum(1)
            spread[int(label)] += float(np.sqrt(gap).sum())
            order = np.argsort(gap)[:exemplars]
            best[int(label)] = sorted(best[int(label)] + [(float(gap[i]), start + int(chosen[i])) for i in order])[:exemplars]
    return {"labels": ids, "centroids": centroids,
            "clusters": [{"cluster": label, "size": counts[label], "mean_distance_to_centroid": spread[label] / max(counts[label], 1),
                          "exemplar_rows": [row for _, row in best[label]]} for label in ids],
            "noise": int((labels < 0).sum())}


def silhouette_sample(matrix: np.ndarray, labels: np.ndarray, *, sample: int = 4000, seed: int = 42, metric: str = "cosine") -> float | None:
    """Mean silhouette over a seeded subsample (noise excluded); None when fewer than two clusters remain."""
    keep = np.flatnonzero(labels >= 0)
    if len(keep) < 3 or len(np.unique(labels[keep])) < 2:
        return None
    rng = np.random.default_rng(seed)
    if len(keep) > sample:
        keep = np.sort(rng.choice(keep, sample, replace=False))
    x = _float32(matrix[keep])
    if metric == "cosine":
        x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
    y = labels[keep]
    sq = (x * x).sum(1)
    dist = np.sqrt(np.maximum(sq[:, None] - 2 * x @ x.T + sq[None, :], 0))
    scores = []
    for index in range(len(keep)):
        own = y == y[index]
        if own.sum() < 2:
            continue
        a = dist[index, own].sum() / (own.sum() - 1)
        b = min(dist[index, y == other].mean() for other in np.unique(y) if other != y[index])
        scores.append((b - a) / max(a, b, 1e-12))
    return float(np.mean(scores)) if scores else None


def thread_hint() -> int:
    return os.cpu_count() or 1
