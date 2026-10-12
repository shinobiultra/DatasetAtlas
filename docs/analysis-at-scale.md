# Analysis at scale

Embeddings, projections, clusterings and neighbour scores run on a GPU when one is usable, store their results as
binary arrays when a run is large, and show up in a rotatable 3D map. This page says what runs where, what the
numbers were when it was measured, and the limits that remain.

## What you can run

| Analysis | Options | Backends |
| --- | --- | --- |
| Embeddings (SigLIP 2, MiniLM) | precision (`auto` is bf16 on a GPU), result storage | PyTorch CUDA or CPU |
| Projection: PCA, UMAP | 2D or 3D, neighbours, minimum distance, distance | PCA on torch or CPU; UMAP on RAPIDS cuML or CPU (umap-learn) |
| Clustering: k-means, HDBSCAN, agglomerative | clusters, restarts, smallest cluster, linkage, distance | k-means on torch or CPU; HDBSCAN on cuML or CPU (scikit-learn); agglomerative on CPU |
| Neighbour distance (outliers) | neighbours, distance | exact, on torch or CPU |

`Compute: Automatic` uses a GPU only when the work is large enough to repay starting one (about five million
numbers), and the CPU otherwise. Naming a backend that is not installed is an error that says how to install it;
the backend used is always recorded in the result's provenance. `atlas doctor` shows which backend each method
would pick on your machine.

Cluster results carry a summary (sizes, the examples nearest each centre, a sampled silhouette score). HDBSCAN labels
points that belong to no dense group as noise. Cosine k-means and HDBSCAN run as Euclidean on unit-length vectors.
Above 20,000 rows, agglomerative clustering clusters k-means micro-clusters instead of the points and says so.

## Install

`uv sync` makes the environment match exactly what you name, so a plain `uv sync` removes the extras. Use
`uv sync --all-extras`, or list what you want in one command. The `gpu` extra is RAPIDS cuML for CUDA 13 (published by
NVIDIA; needs driver 580.65.06 or newer, Linux x86-64, Python below 3.14) and is several gigabytes; without an NVIDIA
GPU leave it out:

```bash
uv sync --extra vision --extra embeddings --extra projection --extra datasets --extra remote-storage
```

## How large runs are stored

A run over thousands of records used to write one JSON file per record and keep every vector inside the run
configuration, which capped analysis at 100,000 vectors and two million numbers (about 2,600 vectors at 768
dimensions). A run with `storage: arrays` (chosen automatically above 5,000 records, or by the form) instead:

- reads vectors **by reference** from a checksummed array bundle, memory-mapped, never parsed;
- writes results as `.npy` arrays beside an `ids.json`, registered as one artifact whose `data.bulk` lists each
  array's dtype, shape and SHA-256, with no `data.items`;
- workers write each batch as a shard directory that is renamed into place atomically, so a killed worker leaves
  nothing the coordinator would trust, and a retry keeps finished shards;
- embeds each distinct image once however many records point at it.

The API serves arrays as raw bytes (`GET /api/v1/artifacts/{id}/arrays/{name}`, shape and dtype in headers) and ids
as JSON (`/ids`). Artifact ids are content digests, so both are cacheable forever. Array results still join onto
records as ordinary `prediction.<artifact>.<key>` fields for columns, filters and colours, and exact similarity
search reads the memory-mapped matrix directly. Array-backed runs cannot be imported from another workspace yet,
and publication excludes them unless explicitly allowlisted.

## Measured

Synthetic clustered vectors, 214,354 x 768 (the example count of VQA v2 at SigLIP 2's width), through the real job
path (`scripts/bench_analysis.py`), on an RTX 5090 Laptop GPU shared with other applications. "Run" includes starting
the worker, verifying the 658 MB input, the algorithm and registering the artifact.

| Analysis | Create | Run | Total |
| --- | ---: | ---: | ---: |
| PCA, 3 components (torch) | 3.8 s | 7.9 s | 11.7 s |
| k-means, 60 clusters (torch) | 3.5 s | 9.8 s | 13.2 s |
| UMAP, 3D (cuML) | 3.6 s | 15.7 s | 19.2 s |
| Exact 10 nearest neighbours (torch) | 3.5 s | 15.8 s | 19.4 s |
| Agglomerative, 60 clusters | 3.3 s | 23.1 s | 26.4 s |
| HDBSCAN (cuML, full 768 dimensions) | 3.2 s | 31.6 s | 34.8 s |

Algorithm time alone: PCA 0.6 s, k-means 0.7 s, UMAP 5.8 s, HDBSCAN 19 s (4.6 s on a 50-dimension PCA reduction).
For comparison, CPU umap-learn took 24 s for only 20,000 of those points, and the previous exact-SVD PCA took 5.7 s
for 20,000.

Embeddings (`scripts/bench_embeddings.py`, pinned local weights, bf16 on the same GPU): SigLIP 2 images about
1,360 per second, MiniLM about 29,000 sentences per second. The legacy path measured 4.7 images and 79 sentences per
second because it reloaded and re-verified the model for every group of 16 records. Columnar fp32 vectors match the
legacy path exactly (cosine 1.000000); bf16 stays above 0.9997. `torch.compile` gave +20% for a 7 s compile and
`max-autotune` no more for 38 s, so it is not enabled: it only pays back above roughly 45,000 images.

## Whole populations

"Select all matching" on a complete index no longer moves ids through the browser. Above 5,000 matches the server
resolves the ids with one scan of the snapshot (`POST /api/v1/selections/population`), freezes them as a selection whose
ids live in a side file (`work/selection-ids/`), and returns a summary with `size`. Analyze runs on it directly; the
per-record actions (save, compare, ask a model, export) are disabled for it, and portable export stays limited to
10,000 records. Records are resolved in one batched scan rather than one query each, and a columnar projection or
clustering over a population never reads record content at all.

On the real VQA v2 index (214,354 questions, nothing downloaded), through the API on the same GPU:

| Step | Time |
| --- | ---: |
| Select all 214,354 on the server | 0.14 s |
| MiniLM embeddings of every question (bf16), estimate to artifact | 57 s |
| 3D UMAP (cuML), estimate to artifact | 31 s |
| k-means, 60 clusters | 23 s |
| HDBSCAN (71 clusters) | 32 s |

The 3D map then draws all 214,354 points in the browser, coloured by cluster.

## Limits

- Portable selection export is limited to 10,000 records; use the CLI for larger packs.
- The 3D map draws every point of an array-backed projection, but colours by a dataset field only for records loaded
  in the page. Colouring by cluster or score covers every point.
- Records of a whole population are read once per estimate and cached for five minutes between estimate and run; a
  very large selection of wide records needs the memory to hold them.
- NudeNet runs on the CPU (onnxruntime has no CUDA provider here).
