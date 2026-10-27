# Getting started

Dataset Atlas has an approved sample browser and an optional local workbench. The
sample is the fastest way to explore the interface. The workbench adds your own
source data, preparation, saved runs and optional analysis.

## Open the samples

Install uv and Node.js 26 (or 22.12+), then:

```bash
git clone --depth 1 https://github.com/shinobiultra/DatasetAtlas.git
cd DatasetAtlas
./start.sh
```

Setup installs locked base dependencies, validates the publication allowlist and
builds the interface. The browser includes 100 original examples each from CLEVR,
EuroSAT and PAIRS, their approved media and annotations, plus catalogue guides.
It needs no GPU or model. After setup the included examples work offline.
Use `--no-open` to print the loopback URL without opening a browser, or `--port 8768`
to choose a port. Reuse the same port to keep browser-saved selections available.

The portable sample ZIP needs only Python 3.11+:

```bash
python3 OPEN_ATLAS.py --check
python3 OPEN_ATLAS.py
```

The portable launcher has also been checked on Python 3.15.2. The checkout and
workbench currently support Python 3.11–3.14; use 3.14.10 for the latest supported
patch. [Development](development.md) records the binary-wheel compatibility limit.

Download the [sample ZIP](https://github.com/shinobiultra/DatasetAtlas/releases/latest/download/dataset-atlas-samples.zip), extract it and open its `dataset-atlas-sample` folder first.
See [sharing](sharing.md) for checksums and Windows commands.

## Open a workbench

```bash
./start.sh --workbench
```

Or install the release wheel without Node or a source checkout:

```bash
uv tool install ./dataset_atlas-1.0.0-py3-none-any.whl
atlas init ~/atlas
cd ~/atlas
atlas serve
```

The workbench supports Python 3.11–3.14 on Linux and macOS; use WSL on Windows.
It listens on loopback. For a remote machine, use an SSH tunnel as described in
[remote workbench](remote-workbench.md). One coordinator owns a workspace at a
time; separate workspaces can run independently.

A new workspace contains the catalogue and no fetched data. Local availability
is shown separately from source coverage. Open a dataset and choose **Get preview**
or **Prepare full data** to review its source, transfer and output requirements.
Nothing downloads until you start the plan within explicit budgets.

```bash
atlas previews status
atlas previews fetch --dataset mnist                 # plan only
atlas previews fetch --dataset mnist --execute       # execute the bounded plan
atlas doctor
```

A source can require an account, accepted terms or a larger transfer budget.
Atlas does not accept agreements or bypass source gates. A complete index covers
the declared native partition; a preview remains a bounded sample. FineVision and
the SmolLM2 training mixture offer budgeted sampling from pinned whole-source populations without a
complete local query index. See [preparation](on-demand-preparation.md) and the
[coverage matrix](../reports/dataset_coverage.csv).

Use **Add dataset** for local folders, CSV/Parquet tables or Hugging Face datasets.
Your original files remain in place. See [your own datasets](adding-your-own-datasets.md).

## Optional analysis

Browsing requires no analysis extras, GPU, model weights or provider. To install CPU
analysis and source-format support from a checkout:

```bash
uv sync --frozen --extra vision --extra embeddings --extra projection --extra datasets --extra remote-storage
uv run --no-sync atlas models status
uv run --no-sync atlas models fetch                 # review pinned files and sizes
uv run --no-sync atlas models fetch --execute       # download and checksum explicitly
```

`uv sync` installs exactly the extras named in that command. Keep the same extras
when resynchronizing, or use `--inexact` to retain an intentionally provisioned
environment. CUDA acceleration is optional; select compatible GPU dependencies
only when you need them. A configured local provider is separate from these model
files. See [model connections](model-connections.md) and [analysis at scale](analysis-at-scale.md).

Select records and open **Analyze**. Results retain the selection, snapshot and
processor provenance, and become fields, filters or map colours. Model context
preview shows the explicit outgoing content before approval. No external model
is connected automatically.

## Keep your workspace

Back up `local-config/`, saved selections and any originals you supplied. Prepared
versions, source objects and protected previews carry reproducibility dependencies;
use the storage tools and inspect their plans before cleanup. See [storage](storage.md).
To update the shipped catalogue after installing a new wheel:

```bash
atlas init --update ~/atlas
```

Current release counts and verification live in [release evidence](../reports/release_evidence.md).
Dataset rights and historical paper-use qualifications are recorded separately in
[source qualifications](../reports/limitations.md).
