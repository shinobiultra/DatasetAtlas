"""Measure real prepared snapshots without claiming cold operating-system caches."""
from pathlib import Path
import json
import platform
import resource
import time

from dataset_atlas.models import Query
from dataset_atlas.queries.parquet import ParquetSnapshot

root = Path(__file__).resolve().parents[1]
receipts = []
for directory in sorted((root / "work/snapshots").iterdir()):
    name = directory.name
    if not (directory / "manifest.json").exists():
        continue
    start = time.perf_counter()
    snapshot = ParquetSnapshot(directory.parent, directory)
    opening = time.perf_counter() - start
    query = Query(snapshot_id=snapshot.snapshot_id, population_scope="complete", limit=48)
    measurements = []
    for _ in range(3):
        start = time.perf_counter()
        result = snapshot.query(query)
        measurements.append(time.perf_counter() - start)
        assert result.matched_count == snapshot.record_count
        assert len(result.records) == min(48, snapshot.record_count)
    receipts.append({"dataset": name, "records": snapshot.record_count,
                     "manifest_and_checksum_seconds": opening,
                     "query_seconds": measurements, "returned": len(result.records),
                     "count_status": result.count_status})
report = {"platform": platform.platform(), "python": platform.python_version(),
          "cache_condition": "New reader per snapshot; existing OS page cache not flushed; three repeated exact-count first-page queries.",
          "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          "duckdb_threads": 2, "duckdb_memory_limit_mb": 256, "measurements": receipts}
output = root / "reports/query-performance.json"
output.write_text(json.dumps(report, indent=2) + "\n")
print(output)

mnist = root / "work/snapshots/mnist"
if mnist.exists():
    snapshot = ParquetSnapshot(mnist.parent, mnist)
    sampling = []
    for method in ("random", "stratified"):
        query = Query(snapshot_id=snapshot.snapshot_id, population_scope="complete", limit=100,
                      sample={"method": method, "seed": 42, "size": 100, "field_id": "source.label"})
        start = time.perf_counter()
        result = snapshot.query(query)
        sampling.append({"method": method, "seconds": time.perf_counter() - start,
                         "matched": result.matched_count, "returned": len(result.records),
                         "labels": {str(label): sum(r.source["label"] == label for r in result.records) for label in range(10)},
                         "first_ids": [r.id for r in result.records[:5]],
                         "cache": "OS caches warm; Arrow-batched deterministic hash"})
    (root / "reports/full-sampling-verification.json").write_text(json.dumps(sampling, indent=2) + "\n")
