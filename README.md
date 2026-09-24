# Dataset Atlas

Browse evidence-linked datasets, inspect real records, save reproducible selections, and attach optional local analysis. The same React frontend runs as a static site or with a loopback Python workbench.

The workbench and static browser are implemented, with **333 catalogue entries, 167 prepared local previews (16,246 records), and 162 canonical full-scope indices**. Full-scope indices describe their acquired populations; some have partial media. This is **not a completed v1 release** of [SPEC.md](SPEC.md): 166 entries have no preview. All 64 paper mention inventories have been checked against the full text, but exact release identity and dataset coverage remain incomplete. See the [remaining roadmap](ROADMAP.md), [latest native verification](reports/native-expansion-20260924.md), [corpus coverage](reports/corpus_coverage.md), [dataset coverage](reports/dataset_coverage.csv), [source access](reports/source_access_report.md), and [release evidence](reports/release_evidence.md). Paper mention evidence does not by itself resolve a dataset release. Metadata-only entries are not browsable datasets.

## Run locally

Python 3.12 and Node 22+ are used for development. `uv.lock` and `apps/web/package-lock.json` pin the resolved environments.

```bash
uv sync --extra development --extra projection
cd apps/web
npm ci
npm run build
cd ../..
uv run atlas serve
```

Use **Prepare full data** on a dataset to review its pinned source plan, set budgets, and start or resume local preparation. See [on-demand preparation](docs/on-demand-preparation.md) and [implementation evidence](reports/on-demand-implementation.md).

For large collections, [the storage policy](docs/storage.md) preserves original-quality, full-resolution previews and compresses other images on demand into a bounded AVIF cache. Original bytes remain available for inspection and model inputs. The local 2026-09-24 storage pass measured 147.60 GB, within the requested 150 GB ceiling and above the 100 GB target, including configured model weights, pinned Cauldron preview originals, and newly registered native archives. See [the storage receipt](reports/storage-footprint-20260924.json) for accounting limits.

Open **http://127.0.0.1:8765/?mode=workbench**. The default browser route is static mode and makes no privileged localhost connection. Local preview packs live under `work/packs/`; to install the redistributable demonstration packs into a fresh checkout:

```bash
mkdir -p work/packs
cp -R examples/approved-packs/. work/packs/
```

Static mode needs no Python or models. Build it with `npm run build` in `apps/web`, or use `npm run dev` during development. The catalogue and approved previews are generated into `apps/web/public/data` by the explicit publication command. No backend is needed after building.

## The interface

One shell carries every screen: navigation on the left, the examples in the centre, and a single contextual panel on the right that shows the inspected sample or, on request, dataset details, analysis setup or a model conversation.

- **Catalogue** — thumbnail-led dataset cards over real prepared media, with faceted filters for coverage, modality, task, access and annotations, and a compact list alternative.
- **Dataset** — a compact header, then **Samples** (the default) and **Overview**. Overview computes label distributions over the population the filter matched, in preview or complete scope, and states that population.
- **Browsing** — Grid, Table, Map and Compare share one population, one selection and one set of filters. Both grid and table are virtualized and page in as you scroll; media is fetched only for what is on screen.
- **Inspection** — clicking a record inspects it and never selects it; ticking its checkbox selects it and never changes what is inspected. Focused inspection takes the centre with prev/next, fit/actual size, overlay toggles and a filmstrip labelled as browsing order rather than similarity.
- **Compare** — two equally weighted media panels above aligned evidence, with a differences-only toggle that compares only values present on both sides with the same type.

Coverage claims are per deployment: the public build says what *it* can show, and an entry prepared locally but not published reads "Metadata only here". A metadata-only dataset explains its access, adapter, complete-data and publication states instead of showing an empty grid, and says plainly that an unimplemented adapter is an implementation gap rather than a source restriction. See [interface architecture](docs/interface.md).

## Reproducible workflows

```bash
# All corpus originals remain read-only; configure your own path.
uv run atlas corpus scan --papers-dir "$PAPERS" --output work/corpus
uv run atlas corpus extract --manifest work/corpus/corpus_manifest.json
uv run atlas corpus resolve --mentions work/corpus/dataset_mentions.jsonl --registry registry
uv run atlas datasets validate --all
uv run atlas datasets prepare --dataset clevr --preview-size 100 --max-bytes 30000000 --dry-run
uv run atlas doctor

# Index an already acquired full source with an exact verified count.
uv run atlas datasets index --dataset mnist --expected-count 70000 --max-bytes 100000000

# Only configured allowlist entries can enter static publication.
uv run atlas publish validate --profile public
uv run atlas publish build --profile public
```

`resolve` preserves review uncertainty. Preparation uses bounded source plans, and a dry run performs no acquisition. Do not use unknown size as permission to download a complete collection.

Save a selection in the workbench before running:

```bash
uv run atlas analyze --selection SELECTION_ID --processor quality.basic --config CONFIG.json
uv run atlas export selection SELECTION_ID --output work/exports/selection
```

The CLI waits for its job coordinator to finish; the API returns a durable job immediately. Failed, cancelled, skipped and completed items remain distinct. A completed detector output with no boxes is different from a failed detector.

## Optional computation

Base browsing does not install CUDA or model frameworks. Extras are `datasets` (SciPy for SVHN MAT files), `vision`, `embeddings`, `projection`, `remote-storage`, and `development`. The prepared workspace includes real CLEVR and COCO detector, embedding and projection demonstrations; see [release evidence](reports/release_evidence.md). Detector and embedding recipes require explicitly prepared local model files and verified revisions/checksums. They do not silently download weights. See [processors](docs/adding-processors.md) and [model connections](docs/model-connections.md).

Provider capabilities start unknown and are probed independently. Context preview shows the exact outgoing record scope; sending requires explicit provider and context approval. Evaluation mode excludes source labels and computed predictions. A text-only request never claims to see image pixels. No model service is bundled or automatically started.

## Development and distribution

```bash
prek run --all-files
uv run pytest -q
cd apps/web && npm test && npm run build
cd ../..
uv run python scripts/generate_contracts.py
uv run python scripts/build_release.py
```

The `prek` configuration runs pinned `ty` checks over the storage, preview sampling
and NRC-VAD modules. This is an incremental type-checking boundary, not a claim
that the older untyped code passes a repository-wide check. Use `uv run --no-sync`
with an intentionally provisioned optional model environment to preserve its
Torch/CUDA build; validate dependency upgrades in an isolated environment first.

The release builder embeds the built frontend in the wheel. Install the resulting wheel to run `atlas serve` without Node. Dataset previews are separately portable; full datasets, paper PDFs, caches, credentials, and full extracted text are excluded from the distribution.

- [Interface architecture](docs/interface.md): the shell, the interaction contract, and the honesty rules the components enforce.
- [Shared contracts](docs/contracts.md): Pydantic is the schema source of truth; TypeScript is generated.
- [Adding datasets](docs/adding-datasets.md): reusable mappings, coverage, and evidence.
- [Remote workbench](docs/remote-workbench.md): existing mounts and SSH tunnelling.
- [Publication](docs/publication.md): explicit rights and media allowlists.

Tests use synthetic fixtures only where isolation is necessary. Production previews retain real source identity, sampling and rights receipts. GitHub Pages deployment is an explicit workflow action; implementation does not automatically publish anything.
