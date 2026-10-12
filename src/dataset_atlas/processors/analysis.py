"""Bounded original-space and map analyses over explicit upstream vectors.

Vectors reach a processor in one of two ways. Small runs carry them inline as a dict
of lists (the original, JSON path, with its original bounds). Large runs carry a
``vector_source``: a checksummed array bundle written by an embedding run, read
memory-mapped so nothing is parsed per record. With ``storage: arrays`` the result is
columnar too (see ``bulk.BulkResult``). The numeric work is in ``engines``.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
from dataset_atlas.models import Record, content_id
from dataset_atlas.storage import arrays as array_store
from . import engines
from .bulk import BulkResult

MAX_BULK_VECTORS = 2_000_000
MIN_GPU_CELLS = 5_000_000  # below this a GPU costs more to start than it saves


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


def _source_matrix(records: list[Record], config: dict[str, Any]) -> tuple[list[str], np.ndarray, list[str], dict[str, Any]]:
    """Rows of a registered array bundle for the selected records, in selection order."""
    source = config["vector_source"]
    if not config.get("embedding_space_id") or not config.get("embedding_run_id"):
        raise ValueError("Analysis requires embedding_space_id and embedding_run_id")
    if config.get('embedding_snapshot_ids') is not None and any(record.snapshot_id not in config['embedding_snapshot_ids'] or record.unit != config.get('embedding_unit') for record in records):
        raise ValueError('Embedding artifact snapshot or sample unit is incompatible')
    directory = Path(source["dir"])
    manifest = source["manifest"]
    stored = array_store.read_ids(directory, manifest)
    matrix = array_store.read_array(directory, manifest["arrays"][source.get("array", "vector")], mmap=True, verify=True)
    if matrix.ndim != 2 or not 1 <= matrix.shape[1] <= 4096:
        raise ValueError("Stored vectors must be a matrix with at most 4096 columns")
    row = {item_id: index for index, item_id in enumerate(stored)}
    ids = [record.id for record in records if record.id in row]
    missing = [record.id for record in records if record.id not in row]
    if not ids:
        raise ValueError("No selected records have vectors")
    if len(ids) > MAX_BULK_VECTORS:
        raise ValueError(f"Analysis exceeds the {MAX_BULK_VECTORS}-vector bound")
    rows = np.fromiter((row[item_id] for item_id in ids), dtype=np.int64, count=len(ids))
    selected = matrix if len(rows) == len(stored) and np.array_equal(rows, np.arange(len(stored))) else matrix[rows]
    digest = content_id({"source_sha256": manifest["arrays"][source.get("array", "vector")]["sha256"],
                         "ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest()}, "vectors:")
    return ids, selected, missing, {"input_digest": digest, "storage": "array bundle"}


def _base_provenance(records: list[Record], config: dict[str, Any], ids: list[str], matrix: np.ndarray, digest: str | None = None) -> dict[str, Any]:
    snapshots = sorted({record.snapshot_id for record in records})
    base = {"embedding_space_id": config["embedding_space_id"], "embedding_run_id": config["embedding_run_id"],
            **({'embedding_artifact_id': config['embedding_artifact_id']} if config.get('embedding_artifact_id') else {}),
            "snapshot_ids": snapshots, "original_dimension": matrix.shape[1], "sample_unit": records[0].unit,
            "input_digest": digest or content_id({"ids": ids, "vectors": matrix.tolist()}, "vectors:")}
    if config.get("storage") == "arrays":
        # Hundreds of thousands of ids do not belong in provenance; counts and digests identify the populations.
        digest_of = lambda values: hashlib.sha256("\n".join(values).encode()).hexdigest()
        return {**base, "population_count": len(records), "population_ids_sha256": digest_of([record.id for record in records]),
                "fitted_count": len(ids), "fitted_ids_sha256": digest_of(ids)}
    return {**base, "population_ids": [record.id for record in records], "fitted_ids": ids}


def pca(matrix: np.ndarray, n_components: int = 2) -> tuple[np.ndarray, list[float]]:
    coords, explained, _ = engines.pca(matrix, n_components, "cpu")
    return coords.astype(np.float64), explained


def knn_outlier(matrix: np.ndarray, neighbors: int, metric: str = "cosine") -> np.ndarray:
    if len(matrix) > 5_000:
        raise ValueError("Exact pairwise outlier analysis limited to 5000 rows")
    return engines.knn(np.asarray(matrix, dtype=np.float32), neighbors, metric, "cpu")["distances"][:, neighbors - 1]


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


def _int(config: dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    value = config.get(key, default)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{key} must be an integer within {low}..{high}")
    return value


def _backend(method: str, config: dict[str, Any], matrix: np.ndarray) -> str:
    """Honour an explicit backend; otherwise use the GPU only when the work is big enough to repay its start-up."""
    requested = str(config.get("backend", "auto"))
    if requested == "auto" and matrix.size < MIN_GPU_CELLS:
        return "cpu"
    return engines.choose_backend(method, requested)


def _metric(config: dict[str, Any], default: str = "cosine") -> str:
    metric = str(config.get("metric", default))
    if metric not in {"cosine", "euclidean"}:
        raise ValueError("metric must be cosine or euclidean")
    return metric


def _cluster_outputs(ids: list[str], matrix: np.ndarray, labels: np.ndarray, metric: str, seed: int) -> tuple[dict[str, Any], np.ndarray]:
    summary = engines.cluster_summaries(matrix, labels, metric=metric)
    clusters = [{**{k: v for k, v in row.items() if k != "exemplar_rows"}, "exemplar_ids": [ids[i] for i in row["exemplar_rows"]]}
                for row in summary["clusters"]]
    return {"clusters": clusters, "noise": summary["noise"], "cluster_count": len(clusters),
            "silhouette_sample": engines.silhouette_sample(matrix, labels, seed=seed, metric=metric)}, summary["centroids"]


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
    bulk = config.get("storage") == "arrays"
    if config.get("vector_source"):
        ids, matrix, missing, extra = _source_matrix(records, config)
        provenance = _base_provenance(records, config, ids, matrix, extra["input_digest"])
        provenance["vector_storage"] = extra["storage"]
    else:
        ids, matrix, missing = _matrix(records, config)
        provenance = _base_provenance(records, config, ids, matrix)
    arrays: dict[str, np.ndarray] = {}
    extras: dict[str, np.ndarray] = {}
    summary: dict[str, Any] = {}
    seed = int(config.get("seed", 42))
    if processor_id in {"project.pca", "project.umap"}:
        dimensions = _int(config, "dimensions", 2, 2, 3)
        if processor_id == "project.pca":
            coords, explained, backend = engines.pca(matrix, dimensions, _backend("pca", config, matrix))
            provenance.update({"method": "centered covariance PCA", "backend": backend, "explained_variance_ratio": explained,
                               "parameters": {"n_components": dimensions}, "numpy_version": np.__version__})
        else:
            neighbors = _int(config, "neighbors", 15, 2, 200)
            if neighbors >= len(ids):
                raise ValueError("UMAP neighbors must be within 2..population size minus one")
            metric = _metric(config)
            min_dist = float(config.get("min_dist", 0.1))
            if not 0 <= min_dist <= 1:
                raise ValueError("UMAP min_dist must be within 0..1")
            result = engines.umap_embed(matrix, n_components=dimensions, n_neighbors=neighbors, min_dist=min_dist, metric=metric,
                                        seed=seed, backend=_backend("umap", config, matrix))
            coords = result["coords"]
            provenance.update({"method": "UMAP", "backend": result["backend"], "implementation_version": result["library_version"],
                               "parameters": {"n_components": dimensions, "neighbors": neighbors, "min_dist": min_dist, "metric": metric, "seed": seed,
                                              **({"n_jobs": 1} if result["backend"] == "cpu" else {})}})
        arrays["coords"] = np.asarray(coords, dtype=np.float32)
    elif processor_id in {"cluster.kmeans", "cluster.hdbscan", "cluster.agglomerative"}:
        metric = _metric(config, "euclidean" if processor_id == "cluster.kmeans" else "cosine")
        if processor_id == "cluster.kmeans":
            clusters = _int(config, "clusters", 8, 1, 100_000)
            n_init = _int(config, "n_init", 1, 1, 50)
            run = engines.kmeans(matrix, clusters, seed, n_init=n_init, metric=metric, backend=_backend("kmeans", config, matrix))
            labels = run["labels"]
            provenance.update({"method": "Lloyd k-means with k-means++ seeding", "space": "original embedding", "backend": run["backend"],
                               "metric": "squared euclidean" if metric == "euclidean" else "squared euclidean on unit vectors (cosine)",
                               "parameters": {"clusters": clusters, "seed": seed, "n_init": n_init, "max_iter": 100, "metric": metric},
                               "iterations": run["iterations"], "inertia": run["inertia"], "numpy_version": np.__version__})
            if len(run["centers"]) * run["centers"].shape[1] <= 100_000:
                provenance["centers"] = run["centers"].tolist()
        elif processor_id == "cluster.hdbscan":
            min_size = _int(config, "min_cluster_size", 15, 2, 1_000_000)
            min_samples = config.get("min_samples")
            if min_samples is not None:
                min_samples = _int(config, "min_samples", min_size, 1, 1_000_000)
            run = engines.hdbscan_cluster(matrix, min_cluster_size=min_size, min_samples=min_samples, metric=metric,
                                          backend=_backend("hdbscan", config, matrix))
            labels = run["labels"]
            arrays["probability"] = run["probabilities"]
            provenance.update({"method": "HDBSCAN", "space": "original embedding", "backend": run["backend"], "implementation_version": run["library_version"],
                               "metric": "euclidean on unit vectors (cosine)" if metric == "cosine" else "euclidean",
                               "parameters": {"min_cluster_size": min_size, "min_samples": min_samples, "metric": metric}})
        else:
            clusters = _int(config, "clusters", 8, 1, 100_000)
            linkage = str(config.get("linkage", "ward"))
            if linkage not in {"ward", "average", "complete", "single"}:
                raise ValueError("linkage must be ward, average, complete or single")
            run = engines.agglomerative(matrix, clusters, linkage=linkage, seed=seed, backend=_backend("kmeans", config, matrix))
            labels = run["labels"]
            provenance.update({"method": "Agglomerative clustering" + (" over k-means micro-clusters" if run["two_stage"] else ""),
                               "space": "original embedding", "two_stage": run["two_stage"], "micro_clusters": run["micro_clusters"],
                               "parameters": {"clusters": clusters, "linkage": linkage, "seed": seed}})
        arrays["cluster"] = np.asarray(labels, dtype=np.int32)
        summary, centroids = _cluster_outputs(ids, matrix, labels, metric if metric == "cosine" else "euclidean", seed)
        extras["centroids"] = centroids
    elif processor_id == "outlier.knn":
        neighbors = _int(config, "neighbors", 5, 1, 1000)
        metric = _metric(config)
        result = engines.knn(matrix, neighbors, metric, _backend("knn", config, matrix), max_cpu_rows=int(config.get("max_cpu_rows", 60_000)))
        arrays["outlier_score"] = result["distances"][:, neighbors - 1].copy()
        provenance.update({"method": "distance to kth nearest other selected item", "space": "original embedding", "backend": result["backend"],
                           "parameters": {"neighbors": neighbors, "metric": metric}, "numpy_version": np.__version__})
    else:
        raise ValueError("Unknown analysis processor")
    provenance["fit_id"] = content_id({"processor": processor_id, "input": provenance["input_digest"],
                                        "parameters": provenance["parameters"]}, "fit:")
    if summary:
        provenance["summary"] = summary if not bulk else {"stored": "artifact data summary"}
    if bulk:
        skipped = {item_id: {"status": "not_applicable"} for item_id in missing}
        return BulkResult(ids=ids, arrays=arrays, extras=extras, skipped=skipped, summary=summary, provenance=provenance), provenance
    outputs = {item_id: _item_output(processor_id, arrays, row) for row, item_id in enumerate(ids)}
    items = [{"id": record.id, "status": "completed", "output": outputs[record.id]} if record.id in outputs
             else {"id": record.id, "status": "not_applicable", "output": None} for record in records]
    return items, provenance


def _item_output(processor_id: str, arrays: dict[str, np.ndarray], row: int) -> dict[str, Any]:
    if "coords" in arrays:
        return {name: float(value) for name, value in zip("xyz", arrays["coords"][row])}
    if "cluster" in arrays:
        output = {"cluster": int(arrays["cluster"][row])}
        if "probability" in arrays:
            output["probability"] = float(arrays["probability"][row])
        return output
    return {"outlier_score": float(arrays["outlier_score"][row])}


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
