"""Bounded original-space and map analyses over explicit upstream vectors."""
from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any

import numpy as np
from dataset_atlas.models import Record, content_id
from .core import package_version


def _matrix(records: list[Record], config: dict[str, Any]) -> tuple[list[str], np.ndarray, list[str]]:
    vectors = config.get("vectors")
    if not isinstance(vectors, dict):
        raise ValueError("Analysis requires vectors keyed by stable record ID")
    if not config.get("embedding_space_id") or not config.get("embedding_run_id"):
        raise ValueError("Analysis requires embedding_space_id and embedding_run_id")
    if config.get('embedding_snapshot_ids') is not None and any(record.snapshot_id not in config['embedding_snapshot_ids'] or record.unit != config.get('embedding_unit') for record in records):
        raise ValueError('Embedding artifact snapshot or sample unit is incompatible')
    ids = [record.id for record in records if record.id in vectors]
    missing = [record.id for record in records if record.id not in vectors]
    if not ids:
        raise ValueError("No selected records have vectors")
    if len(ids) > 100_000:
        raise ValueError("Analysis exceeds 100000-vector bound")
    first = vectors[ids[0]]
    if not isinstance(first, (list, tuple)) or not 1 <= len(first) <= 4096:
        raise ValueError("Vectors must be bounded numeric sequences")
    dimension = len(first)
    if len(ids) * dimension > 2_000_000 or any(not isinstance(vectors[item_id], (list, tuple)) or len(vectors[item_id]) != dimension for item_id in ids):
        raise ValueError("Vectors have inconsistent dimension or exceed two million values")
    array = np.asarray([vectors[item_id] for item_id in ids], dtype=np.float64)
    if array.ndim != 2 or array.shape[1] == 0 or array.shape[1] > 4096 or not np.isfinite(array).all():
        raise ValueError("Vectors must have one consistent finite dimension at most 4096")
    if array.size > 2_000_000:
        raise ValueError("Analysis exceeds two million numeric values")
    return ids, array, missing


def _base_provenance(records: list[Record], config: dict[str, Any], ids: list[str], matrix: np.ndarray) -> dict[str, Any]:
    snapshots = sorted({record.snapshot_id for record in records})
    return {"embedding_space_id": config["embedding_space_id"], "embedding_run_id": config["embedding_run_id"],
            **({'embedding_artifact_id': config['embedding_artifact_id']} if config.get('embedding_artifact_id') else {}),
            "snapshot_ids": snapshots, "population_ids": [record.id for record in records],
            "fitted_ids": ids, "original_dimension": matrix.shape[1], "sample_unit": records[0].unit,
            "input_digest": content_id({"ids": ids, "vectors": matrix.tolist()}, "vectors:")}


def pca(matrix: np.ndarray, n_components: int = 2) -> tuple[np.ndarray, list[float]]:
    if matrix.shape[0] < 2 or matrix.shape[1] < n_components:
        raise ValueError("PCA needs at least two rows and enough input dimensions")
    centered = matrix - matrix.mean(axis=0)
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    coords = np.zeros((matrix.shape[0], n_components), dtype=np.float64)
    available = min(n_components, singular.size)
    coords[:, :available] = u[:, :available] * singular[:available]
    # Fix SVD's arbitrary signs for reproducible serialization.
    for col in range(available):
        pivot = np.argmax(np.abs(coords[:, col]))
        if coords[pivot, col] < 0:
            coords[:, col] *= -1
    variance = singular ** 2
    explained = (variance[:available] / variance.sum()).tolist() if variance.sum() else [0.0] * available
    return coords, explained + [0.0] * (n_components - available)


def kmeans(matrix: np.ndarray, clusters: int, seed: int, max_iter: int = 100) -> tuple[np.ndarray, np.ndarray, int]:
    if clusters < 1 or clusters > len(matrix):
        raise ValueError("clusters must be within 1..population size")
    rng = np.random.default_rng(seed)
    centers = matrix[rng.choice(len(matrix), size=clusters, replace=False)].copy()
    labels = np.zeros(len(matrix), dtype=np.int64)
    for iteration in range(max_iter):
        distances = ((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        if iteration > 0 and np.array_equal(labels, new_labels):
            return labels, centers, iteration
        labels = new_labels
        for cluster in range(clusters):
            members = matrix[labels == cluster]
            if len(members):
                centers[cluster] = members.mean(axis=0)
            else:
                # Empty clusters are deterministically reseeded to a poorly fitted row.
                farthest = np.argmax(np.min(distances, axis=1))
                centers[cluster] = matrix[farthest]
    return labels, centers, max_iter


def knn_outlier(matrix: np.ndarray, neighbors: int, metric: str = "cosine") -> np.ndarray:
    n = len(matrix)
    if n < 2 or neighbors < 1 or neighbors >= n:
        raise ValueError("neighbors must be within 1..population size minus one")
    if n > 5_000:
        raise ValueError("Exact pairwise outlier analysis limited to 5000 rows")
    if metric == "cosine":
        norms = np.linalg.norm(matrix, axis=1)
        if (norms == 0).any():
            raise ValueError("Cosine distance requires nonzero vectors")
        normalized = matrix / norms[:, None]
        distances = 1.0 - np.clip(normalized @ normalized.T, -1, 1)
    elif metric == "euclidean":
        norms2 = (matrix * matrix).sum(axis=1)
        distances = np.sqrt(np.maximum(0, norms2[:, None] + norms2[None, :] - 2 * matrix @ matrix.T))
    else:
        raise ValueError("metric must be cosine or euclidean")
    np.fill_diagonal(distances, np.inf)
    return np.partition(distances, neighbors - 1, axis=1)[:, neighbors - 1]


def _field(record: Record, field_id: str):
    namespace, _, key = field_id.partition(".")
    if namespace not in {"source", "prediction", "human", "record"} or not key:
        raise ValueError("Comparison field must be namespace.key")
    if namespace == "record":
        if key not in {"id", "text", "question", "unit"}:
            raise ValueError("Unsupported record comparison field")
        return getattr(record, key)
    return getattr(record, namespace).get(key)


def compare(records: list[Record], config: dict[str, Any]) -> dict[str, Any]:
    left = str(config.get("left_field", ""))
    right = str(config.get("right_field", ""))
    kind = str(config.get("kind", ""))
    pairs = [(_field(record, left), _field(record, right)) for record in records]
    complete = [(a, b) for a, b in pairs if a is not None and b is not None]
    base = {"left_field": left, "right_field": right, "kind": kind, "sample_unit": records[0].unit if records else "example",
            "population_scope": str(config.get("population_scope", "selection")), "selected": len(records),
            "paired": len(complete), "missing_left": sum(a is None for a, _ in pairs),
            "missing_right": sum(b is None for _, b in pairs),
            "snapshot_ids": sorted({r.snapshot_id for r in records}), "selection_ids": [r.id for r in records]}
    if config.get("source_artifact_id"):
        base["source_artifact_id"] = str(config["source_artifact_id"])
    if kind == "correlation":
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for pair in complete for v in pair):
            raise ValueError("Correlation fields must be finite numeric values")
        if len(complete) < 2:
            base["pearson_r"] = None
        else:
            array = np.asarray(complete, dtype=np.float64)
            base["pearson_r"] = float(np.corrcoef(array[:, 0], array[:, 1])[0, 1]) if np.std(array[:, 0]) and np.std(array[:, 1]) else None
    elif kind == "crosstab":
        if any(not isinstance(v, (str, int, float, bool)) or (isinstance(v, float) and not math.isfinite(v)) for pair in complete for v in pair):
            raise ValueError("Crosstab fields must be scalar categories")
        def category(value):
            return (type(value).__name__, repr(value))
        values = {category(value): value for pair in complete for value in pair}
        counts = Counter((category(a), category(b)) for a, b in complete)
        base["cells"] = [{"left": values[a], "right": values[b], "left_type": a[0], "right_type": b[0], "count": count} for (a, b), count in sorted(counts.items())]
    elif kind == "grouped_numeric":
        groups: dict[tuple[str, str], list[float]] = defaultdict(list)
        categories = {}
        for a, b in complete:
            if not isinstance(a, (str, int, float, bool)) or (isinstance(a, float) and not math.isfinite(a)) or isinstance(b, bool) or not isinstance(b, (int, float)) or not math.isfinite(b):
                raise ValueError("Grouped numeric needs scalar categories and finite numeric values")
            key=(type(a).__name__, repr(a));categories[key]=a
            groups[key].append(float(b))
        base["groups"] = [{"group": categories[key], "group_type": key[0], "count": len(values), "mean": float(np.mean(values)),
                            "median": float(np.median(values)), "minimum": min(values), "maximum": max(values)}
                           for key, values in sorted(groups.items())]
    else:
        raise ValueError("kind must be correlation, crosstab, or grouped_numeric")
    return base


def run_analysis(processor_id: str, records: list[Record], config: dict[str, Any]):
    if processor_id == "compare.fields":
        summary = compare(records, config)
        items = []
        for record in records:
            left, right = _field(record, config["left_field"]), _field(record, config["right_field"])
            items.append({"id": record.id, "status": "completed", "output": {"left": left, "right": right, "left_type": type(left).__name__, "right_type": type(right).__name__}}
                         if left is not None and right is not None else
                         {"id": record.id, "status": "not_applicable", "output": None})
        return items, {"comparison": summary}
    ids, matrix, missing = _matrix(records, config)
    provenance = _base_provenance(records, config, ids, matrix)
    outputs: dict[str, dict[str, Any]] = {}
    if processor_id == "project.pca":
        coordinates, explained = pca(matrix)
        provenance.update({"method": "centered SVD PCA", "explained_variance_ratio": explained, "parameters": {"n_components": 2}, "numpy_version": np.__version__})
        outputs = {item_id: {"x": float(x), "y": float(y)} for item_id, (x, y) in zip(ids, coordinates)}
    elif processor_id == "project.umap":
        import umap
        seed = int(config.get("seed", 42))
        neighbors = int(config.get("neighbors", 15))
        if neighbors < 2 or neighbors >= len(ids):
            raise ValueError("UMAP neighbors must be within 2..population size minus one")
        metric = str(config.get("metric", "cosine"))
        if metric not in {"cosine", "euclidean"}:
            raise ValueError("Unsupported UMAP metric")
        min_dist = float(config.get("min_dist", 0.1))
        if not 0 <= min_dist <= 1:
            raise ValueError("UMAP min_dist must be within 0..1")
        coordinates = umap.UMAP(n_components=2, n_neighbors=neighbors, min_dist=min_dist, metric=metric,
                                random_state=seed, n_jobs=1).fit_transform(matrix)
        provenance.update({"method": "UMAP", "implementation_version": package_version("umap-learn"),
                           "parameters": {"n_components": 2, "neighbors": neighbors, "min_dist": min_dist, "metric": metric, "seed": seed, "n_jobs": 1}})
        outputs = {item_id: {"x": float(x), "y": float(y)} for item_id, (x, y) in zip(ids, coordinates)}
    elif processor_id == "cluster.kmeans":
        clusters = int(config.get("clusters", 8))
        seed = int(config.get("seed", 42))
        labels, centers, iterations = kmeans(matrix, clusters, seed)
        provenance.update({"method": "Lloyd k-means", "space": "original embedding", "metric": "squared euclidean",
                           "parameters": {"clusters": clusters, "seed": seed, "max_iter": 100}, "iterations": iterations,
                           "centers": centers.tolist(), "numpy_version": np.__version__})
        outputs = {item_id: {"cluster": int(label)} for item_id, label in zip(ids, labels)}
    elif processor_id == "outlier.knn":
        neighbors = int(config.get("neighbors", 5))
        metric = str(config.get("metric", "cosine"))
        distances = knn_outlier(matrix, neighbors, metric)
        provenance.update({"method": "distance to kth nearest other selected item", "space": "original embedding",
                           "parameters": {"neighbors": neighbors, "metric": metric}, "numpy_version": np.__version__})
        outputs = {item_id: {"outlier_score": float(score)} for item_id, score in zip(ids, distances)}
    else:
        raise ValueError("Unknown analysis processor")
    provenance["fit_id"] = content_id({"processor": processor_id, "input": provenance["input_digest"],
                                        "parameters": provenance["parameters"]}, "fit:")
    items = [{"id": record.id, "status": "completed", "output": outputs[record.id]} if record.id in outputs
             else {"id": record.id, "status": "not_applicable", "output": None} for record in records]
    return items, provenance


def exact_lancedb_search(table: Any, vector: list[float], eligible_ids: list[str], limit: int,
                         *, metric: str = "cosine") -> list[dict[str, Any]]:
    """Exact, prefiltered search over already-resolved eligible identities.

    The caller opens the optional LanceDB table. SQL identifiers are fixed; values
    are escaped, and large eligible sets must use a validated search snapshot.
    """
    if not eligible_ids or limit < 1:
        return []
    if len(eligible_ids) > 1000:
        # The global top-k must be among each disjoint partition's top-k.
        # Each partition remains a prefiltered exact LanceDB scan.
        unique=list(dict.fromkeys(eligible_ids))
        best=[]
        for start in range(0,len(unique),1000):
            best.extend(exact_lancedb_search(table,vector,unique[start:start+1000],limit,metric=metric))
            best=sorted(best,key=lambda row:(row['_distance'],row['id']))[:limit]
        return best
    if metric not in {"cosine", "l2"}:
        raise ValueError("Unsupported retrieval metric")
    query = np.asarray(vector, dtype=np.float32)
    if query.ndim != 1 or not query.size or not np.isfinite(query).all():
        raise ValueError("Query vector must be finite and nonempty")
    unique = list(dict.fromkeys(eligible_ids))
    literals = ",".join("'" + value.replace("'", "''") + "'" for value in unique)
    search = table.search(query.tolist(), vector_column_name="vector").where(f"id IN ({literals})", prefilter=True)
    rows = search.distance_type(metric).bypass_vector_index().limit(min(limit, len(unique))).to_list()
    eligible = set(unique)
    if any(row.get("id") not in eligible for row in rows):
        raise ValueError("LanceDB returned an ineligible row")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("LanceDB table contains duplicate eligible IDs")
    return rows
