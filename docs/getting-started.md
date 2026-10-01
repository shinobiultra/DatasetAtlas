# Getting started

Dataset Atlas is a local tool for exploring datasets, mostly multimodal ones: a searchable catalogue, real examples with their annotations, filters, saved selections, and optional analysis on the same samples. Everything runs on your machine. Your data and your own datasets stay there.

## Install

You need Python 3.11–3.14. Node is only needed if you build the interface yourself.

**From a release wheel** (no Node, no checkout):

```bash
uv tool install ./dataset_atlas-0.2.0-py3-none-any.whl      # or: pip install ./dataset_atlas-0.2.0-py3-none-any.whl
atlas init ~/atlas                                          # creates a workspace from the catalogue in the wheel
cd ~/atlas
atlas serve                                                 # then open http://127.0.0.1:8765/
```

**From a repository checkout:**

```bash
uv sync
npm --prefix apps/web ci && npm --prefix apps/web run build    # once; needs Node 22
uv run atlas serve
```

The server listens on loopback only. To use it on another machine, run it there and tunnel the port: `ssh -L 8765:127.0.0.1:8765 host` (see [remote workbench](remote-workbench.md)).

Optional analysis (detectors, embeddings, maps) needs extras: `uv sync --extra vision --extra embeddings --extra projection` or `pip install "dataset-atlas[vision,embeddings,projection]"`. Browsing needs none of them, and never needs a GPU.

`atlas doctor` reports what is installed and whether the interface is available.

## What a fresh workspace contains

The catalogue: 333 datasets and benchmarks with their provenance, access and rights state. It does **not** contain the data. Each dataset says plainly what you can do with it:

| State | Meaning |
| --- | --- |
| **Preview available** | 100 real examples (or all, if fewer) are on this machine. |
| **Preview on request** | A preview is recorded for this dataset and can be fetched from its original source. Nothing downloads until you approve the plan. |
| **Metadata only** | No adapter or pinned source exists yet, or access is gated. The dataset page says which, and whether it is a gap in Atlas or a restriction by the source. |

Metadata-only entries are never presented as browsable, and a preview is never presented as the whole dataset: every view states its scope (preview or complete index) and how its examples were sampled.

## Get previews

In the interface, open a dataset and choose **Get preview**. You see the source, the size and the free space before anything is fetched. Or from the command line:

```bash
atlas previews status                                  # what this workspace holds; offline
atlas previews status --plan                           # also checks each dataset's source and cost (reads metadata only)
atlas previews fetch                                   # dry run: plans everything, downloads nothing
atlas previews fetch --execute --total-download-bytes 10000000000
atlas previews fetch --execute --dataset mnist --dataset wmdp     # just these
```

`fetch` plans every dataset first, then fetches the cheapest first within the total budget you give it, and writes a receipt to `work/previews/`. It resumes where it stopped: finished previews are skipped, and verified partial downloads are reused. Sources are the datasets' own publishers; Atlas does not use a mirror of its own. A dataset whose source needs a login or an agreement is reported, never bypassed.

Previews are small by design, but some sources only publish large archives. The plan states that size, and the budget you set is a hard limit. Fetching one preview never starts a full download of a large release.

## Add more of a dataset

A preview is 100 samples. **Prepare full data** on a dataset's page plans a complete index (all records, exact counts, filtering over the whole population) within download and storage budgets you set. Media for very large releases stays at its source and is fetched when you inspect an example.

## Add your own datasets

Folders of images, tables, Parquet files and Hugging Face datasets can be added from the **Add dataset** button on the catalogue, or with `atlas datasets add`. See [adding your own datasets](adding-your-own-datasets.md).

## Enable the analysis tools

Detectors (NudeNet, a person/object detector), image/text embeddings, maps, clustering and outliers are optional and need extra libraries and model weights. Browsing needs neither.

```bash
uv tool install './dataset_atlas-0.2.0-py3-none-any.whl[vision,embeddings,projection]'    # or: pip install "dataset-atlas[vision,embeddings,projection]"
atlas models status                       # which pinned models are installed and configured
atlas models fetch                        # dry run: lists files and sizes (about 1.7 GB in total, mostly SigLIP 2)
atlas models fetch --execute              # downloads, verifies every file's SHA-256, and configures the processors
```

Each model is a public third-party artifact pinned by revision and checksum in `registry/models/`; Atlas never downloads one without your `--execute`, refuses a file that does not match its checksum, and never overwrites settings you changed in `local-config/recipes.json` (use `--reconfigure` to reset them). `atlas doctor` reports what is installed. Then select records in the interface and choose **Analyze**; results appear as fields, map colours and filters on the same examples. Connecting a model server for conversations is separate; see [model connections](model-connections.md).

## Where things live

| Path | Contents | Safe to delete? |
| --- | --- | --- |
| `registry/`, `schemas/` | The shipped catalogue. Replaced by `atlas init --update`. | Yes, but it is regenerated. |
| `local-config/registry/` | Datasets you added. | Back it up. |
| `local-config/` | Provider settings, saved conversations. | Back it up. |
| `work/prepared/`, `work/packs/` | Fetched data and indexes. | Yes; they can be fetched again. |
| `work/media-cache/`, `work/download-cache/` | Caches. | Yes. |

Your source files are never modified, moved or uploaded.

## Updating

Install the new wheel, then refresh the catalogue in your workspace. Your datasets, fetched data and settings are untouched:

```bash
uv tool install --reinstall ./dataset_atlas-<new>-py3-none-any.whl
atlas init --update ~/atlas
```

## Storage

`atlas storage status` measures what the workspace uses. Preparation plans are checked against free space and, when you configure one with `atlas storage configure`, against a workspace-wide ceiling. See [storage](storage.md).

## Models and privacy

Nothing is sent to any model or service unless you connect a provider and approve an explicit context. See [model connections](model-connections.md). Dataset text, images and annotations are treated as untrusted content.
