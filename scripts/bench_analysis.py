"""Time projection, clustering and neighbour runs through the real job path at dataset scale.

Builds a synthetic clustered embedding (no dataset content, nothing downloaded), registers it as an
array-backed embedding artifact in a throwaway workspace, then runs each analysis processor the way
the workbench does: create a run, let the worker subprocess execute it, register the artifact.

    uv run python scripts/bench_analysis.py --rows 214354 --dim 768
    uv run python scripts/bench_analysis.py --rows 50000 --backend cpu --only project.pca cluster.kmeans

The default size is VQA v2's example count (214,354) at SigLIP 2's width (768).
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np

from dataset_atlas.jobs import JobManager
from dataset_atlas.models import Artifact, Record, Selection
from dataset_atlas.storage import arrays as store

RUNS = {
    "project.pca": {"dimensions": 3},
    "project.umap": {"dimensions": 3, "neighbors": 15, "min_dist": 0.1},
    "cluster.kmeans": {"clusters": 60, "n_init": 1},
    "cluster.hdbscan": {"min_cluster_size": 200},
    "cluster.agglomerative": {"clusters": 60},
    "outlier.knn": {"neighbors": 10},
}


def synthetic(rows: int, dim: int, groups: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    means = rng.normal(size=(groups, dim)).astype(np.float32)
    data = means[rng.integers(groups, size=rows)] + 0.6 * rng.normal(size=(rows, dim)).astype(np.float32)
    return data / np.linalg.norm(data, axis=1, keepdims=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, default=214_354)
    parser.add_argument("--dim", type=int, default=768)
    parser.add_argument("--groups", type=int, default=60, help="planted clusters in the synthetic data")
    parser.add_argument("--backend", default="auto", choices=["auto", "cpu", "torch", "cuml"])
    parser.add_argument("--only", nargs="*", choices=sorted(RUNS), help="processors to time (default: all)")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway workspace and print its path")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="atlas-bench-"))
    try:
        started = time.perf_counter()
        manager = JobManager(work / "work")
        vectors = synthetic(args.rows, args.dim, args.groups, 0)
        ids = [f"vqa-v2:example:{index:07d}" for index in range(args.rows)]
        bundle = manager.artifact_dir / "arrays" / "embedding"
        manifest = store.write_bundle(bundle, ids, {"vector": vectors})
        artifact = Artifact(id="embedding", kind="embed.siglip2", run_id="synthetic", snapshot_ids=["snapshot"], unit="example", ids=ids,
                            provenance={"processor_provenance": {"embedding_space_id": "space:synthetic"}}, data={"bulk": {"dir": "arrays/embedding", **manifest}})
        with manager._db() as db:
            db.execute("INSERT INTO artifacts(id,artifact_json) VALUES(?,?)", (artifact.id, artifact.model_dump_json()))
        selection = Selection(id="all", ids=ids, unit="example", snapshot_ids=["snapshot"], dataset_ids=["dataset"], created_at="2026-01-01T00:00:00Z")
        records = [Record(id=item, dataset_id="dataset", release_id="release", snapshot_id="snapshot") for item in ids]
        print(f"{args.rows:,} x {args.dim}: synthetic embedding written in {time.perf_counter() - started:.1f}s ({vectors.nbytes / 1e6:.0f} MB)\n")
        base = {"storage": "arrays", "backend": args.backend, "embedding_space_id": "space:synthetic", "embedding_run_id": "synthetic",
                "vector_source": {"dir": str(bundle), "array": "vector", "manifest": {key: manifest[key] for key in ("count", "ids", "arrays")}}}
        print(f"{'processor':24} {'create':>8} {'run':>8} {'total':>8}  backend / result")
        for processor in args.only or list(RUNS):
            began = time.perf_counter()
            run = manager.create(selection, records, processor, {**base, **RUNS[processor]})
            created = time.perf_counter()
            while (run := manager.get_run(run.id)).status in ("queued", "running"):
                time.sleep(0.1)
            done = time.perf_counter()
            if run.status != "completed":
                print(f"{processor:24} FAILED: {json.dumps(run.errors)[:300]}")
                continue
            artifact = manager.get_artifact(run.artifact_ids[0])
            detail = artifact.provenance["processor_provenance"].get("backend", "cpu")
            summary = artifact.data.get("summary") or {}
            if "cluster_count" in summary:
                detail += f", {summary['cluster_count']} clusters, {summary['noise']} noise, silhouette {summary['silhouette_sample']}"
            print(f"{processor:24} {created - began:7.1f}s {done - created:7.1f}s {done - began:7.1f}s  {detail}")
    finally:
        if args.keep:
            print(f"\nworkspace kept at {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
