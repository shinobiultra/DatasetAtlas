# Sharing with colleagues

Give colleagues repository access. They can browse the approved sample without
copying the maintainer's large dataset workspace:

```bash
git clone --depth 1 https://github.com/shinobiultra/DatasetAtlas.git
cd DatasetAtlas
./start.sh
```

This needs uv and Node.js 26 (or 22.12+). It installs the locked base dependencies,
validates the checked-in publication approvals and rebuilds the interface before
opening a local browser. Optional analysis packages already installed in the
environment are retained. Ctrl-C stops the sample server. For an SSH session,
pass `--no-open` and use the printed loopback URL through a tunnel.

The sample uses the stable address `http://127.0.0.1:8767/` so browser-saved
selections remain available across restarts. If that port is occupied, stop your
previous sample server or choose another with `./start.sh --port 8768` (or
`python3 OPEN_ATLAS.py --port 8768`). Reuse the same port for saved selections.

The sample has 100 original examples each from CLEVR, EuroSAT and PAIRS, approved
annotations and any explicitly approved analysis artifacts. Original media bytes
are preserved. Catalogue guides cover the other entries; their data is obtained
from the publisher with the colleague's own access and budgets. The sample is
explicitly a preview, with its original sampling provenance. It does not establish
complete dataset coverage, model accuracy or human acceptance.

## Portable sample ZIP

Download the [sample ZIP](https://github.com/shinobiultra/DatasetAtlas/releases/latest/download/dataset-atlas-samples.zip)
and its [checksum](https://github.com/shinobiultra/DatasetAtlas/releases/latest/download/dataset-atlas-samples.zip.sha256)
from the [latest release](https://github.com/shinobiultra/DatasetAtlas/releases/latest).
Extract the ZIP and open its `dataset-atlas-sample` folder. Run:

```bash
python3 OPEN_ATLAS.py --check     # verify the complete bundle without starting a server
python3 OPEN_ATLAS.py             # verify, serve on loopback, and open the browser
```

Use Python 3.11 or newer; on Windows run `py -3 OPEN_ATLAS.py`. No Node, uv, pip install, model or GPU is
needed for this extracted browser. The included examples and their annotations
work without a network connection. Other catalogue entries can link or request
data from their publishers when selected.

To build it locally:

```bash
uv sync --frozen --inexact
uv run --no-sync python scripts/build_sample_bundle.py
```

The builder regenerates the approved public data from the checked-in packs and
publication profile, uses relative asset paths, compresses the bundle and writes
a manifest of file hashes. It refuses an existing output path and defaults to a
50 MB expanded size limit. A `.zip.sha256` file records the ZIP's own checksum.
The ZIP contains no `work/`, `local-config/`, original
paper corpus, credentials or unapproved dataset packs. Software and dataset
licences remain separate; dataset notices travel with the bundle.

## Full local workbench

Run `./start.sh --workbench`, or install a release wheel and follow
[getting started](getting-started.md). Fetch only the datasets you need using the
plan and budget shown in the interface. The portable sample is a static browser;
it does not include model services or the maintainer's selections and private runs.
For exchanging research results, use selection exports or the verified
`atlas runs import` workflow in [model-server runs](model-server-runs.md).

## Maintainer storage

```bash
uv run --no-sync atlas storage clean --deduplicate-only
uv run --no-sync atlas storage clean --deduplicate-only --execute
```

This mode checks immutable file hashes and shares byte-identical copies through
hard links while preserving all paths. It evicts no caches, source archives,
models or environments. It refuses active coordination/preparation and held
storage locks. Originals and snapshot identity remain intact; an immutable file
must continue to be treated as immutable after sharing it. Inspect the receipt's
actual allocated-byte savings rather than assuming a compression ratio.
