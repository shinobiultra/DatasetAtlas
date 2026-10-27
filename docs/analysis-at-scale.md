# Analysis at scale

Analysis runs freeze their input selection, snapshot and processor configuration.
Results join the same records as fields, filters and map colours. Install optional
libraries and pinned weights explicitly; browsing and querying need no GPU.

## Computation

| Analysis | Controls | Available backends |
| --- | --- | --- |
| SigLIP 2 / MiniLM embeddings | Representation, precision, batching | PyTorch CPU or CUDA |
| PCA / UMAP projections | 2D or 3D, metric, neighbourhood, seed | PCA on CPU or torch; UMAP on CPU or optional cuML |
| k-means / HDBSCAN / agglomerative | Cluster parameters, metric, seed | CPU, torch or optional cuML as supported by the method |
| Neighbour-distance outliers | Neighbours and metric | Exact CPU or torch computation |

Automatic backend choice considers the operation and input size. A missing backend
is reported with setup guidance, and the backend actually used is stored in
provenance. `atlas doctor` reports the local capability state. GPU acceleration
must respect other workloads; hardware availability does not authorize starting a
model service or reserving every GPU.

```bash
uv sync --frozen --extra vision --extra embeddings --extra projection --extra datasets --extra remote-storage
uv run --no-sync atlas models status
```

The optional `gpu` extra adds the platform-constrained cuML dependency declared in
`pyproject.toml`. Choose it explicitly on a compatible CUDA system. `uv sync` keeps
only named extras unless `--inexact` is used for an intentionally provisioned
environment. See [model setup](model-connections.md).

## Array-backed results

Large runs use checksummed `.npy` arrays and an ordered `ids.json`, registered as one
artifact. Vector inputs are read by reference from the verified bundle. Workers
commit completed shards atomically, account for failed or skipped records, and
avoid repeating image-only computation when examples share the same original.

The API serves array bytes with dtype and shape headers. Scalar and text results
join records as `prediction.<artifact>.<field>`. Projections, clustering and outlier
runs retain their embedding-space identity; equal vector dimensions alone do not
establish compatibility. Recolouring and filtering a map do not refit it.

Exact similarity scores eligible vectors in bounded chunks and returns deterministic
top-k results. Source filters define eligibility before retrieval. Cached mappings
have explicit byte and entry bounds; a very wide record or array may require a
larger approved budget or an explicit refusal.

## Whole populations and maps

**Select all matching** resolves matches on the server. Large selections store
identities beside the workspace database and return a size summary to the browser.
Analysis can consume that frozen population without moving every record through
the browser. Portable selection exchange has a separate size limit.

Maps retain the fitted population while filters determine the eligible points.
Selection includes only eligible points; an unloaded point is resolved with its
inspected snapshot identity. A pending or invalid membership mask does not select
unrelated points. Structured fields cannot become scalar colour values. Categorical
legends retain explicit missing and other-value counts.

A full local index permits whole-population queries over its declared native
partition. Whole-source sampled releases retain sample scope; their global source
totals never become local index or projection counts.

## Measure a workload

Use `scripts/bench_analysis.py` for explicitly synthetic vectors and
`scripts/bench_embeddings.py` with explicitly prepared local weights for embeddings.
Choose a bounded size and backend, then record the hardware, shape, dtype, concurrent
load, cold/warm state, setup time and algorithm time. Include checksum validation
and result registration when reporting end-to-end latency.

The browser suite separately measures synthetic 10,000-point rendering and
selection latency, and bounded DOM/media behavior for long grids and tables. These
engineering fixtures are not real dataset coverage or scientific results. The
[current release evidence](../reports/release_evidence.md) records the actual checks
performed for a release; performance on another workload or machine must be measured.
