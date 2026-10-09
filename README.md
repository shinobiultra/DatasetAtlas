# Dataset Atlas

One place to explore datasets, mostly multimodal ones: a searchable catalogue of the datasets and benchmarks in a paper corpus, real examples with their annotations, reproducible filters and selections, optional analysis on the same samples, and your own datasets alongside them. It runs on your machine; the same React interface also builds as a static site.

## Quick start

```bash
uv tool install ./dataset_atlas-0.2.0-py3-none-any.whl     # a release wheel; no Node, no checkout
atlas init ~/atlas && cd ~/atlas                           # a workspace with the 287-entry catalogue
atlas serve                                                # open http://127.0.0.1:8765/
atlas previews fetch --execute --total-download-bytes 10000000000    # optional: fetch many previews at once
```

Everything is explained in **[Getting started](docs/getting-started.md)**; to browse your own folders, tables or Hugging Face datasets see **[Adding your own datasets](docs/adding-your-own-datasets.md)**. From a repository checkout instead: `uv sync && npm --prefix apps/web ci && npm --prefix apps/web run build && uv run atlas serve`.

A fresh workspace holds the catalogue but no data. Each dataset says what you can do with it: **Preview available** (100 real examples are here), **Preview on request** (fetch it from the original publisher after reviewing the size), or **Metadata only** (no acquisition path yet, or gated; the page says which). Nothing downloads until you approve a plan, and previews are never presented as whole datasets.

## Status

This is a working release; full v1 of [SPEC.md](SPEC.md) remains incomplete. Measured on 2026-10-09 ([coverage matrix](reports/dataset_coverage.csv); the [reproducibility report](reports/preview-reproducibility.md) is dated 2026-10-07 and predates BBQ-V and MultiTrust):

- **287 catalogue entries**, real datasets named in the 64 corpus papers (aliases and views of other datasets are not listed; [why](registry/candidate_dispositions.yaml)), with **220 prepared previews**, **21,532 preview records** and **218 indices for explicitly declared native populations**. Exact paper-used release identities remain open for many entries ([dataset coverage](reports/dataset_coverage.csv)).
- Every prepared preview has an acquisition path from the catalogue. Fresh-workspace results, remaining budgets and failed attempts are recorded per dataset in the reproducibility report. A sampled preview is distinct from a complete population index.
- 2026-10-09 added BBQ-V (54,414 rows, images kept remote) and MultiTrust (11,512 query rows over 50 member tasks, images kept remote), both gated and read with the researcher's own accepted terms, and a [GitHub Pages edition](docs/github-pages.md) plan (not deployed). 2026-10-07 additions include Open Images validation annotations, the pinned MIT-States and UCF101 mirrors, all FFHQ metadata, the author-linked EmoSet-118K population, and whole-article Spoken Wikipedia audio. All have native membership/original verification; mirror equality, historical paper subsets and publication rights retain their explicit limits. Earlier native coverage includes AudioSet annotations, the Recap preview split, LingoQA evaluation rows and frames, VizWiz-Priv source conditions, one DataComp metadata shard, and a sampled FineVision preview from its pinned release. Their receipts distinguish missing audio/images, absent source files, and unprepared shards; these do not imply complete coverage of a larger release.
- **67 entries still lack a prepared preview.** Remaining public acquisition implementations, unresolved identities, unavailable releases and gated sources are listed separately. [Authorization links](docs/dataset-authorization.md) explain where to request the licensed or gated data you do not currently hold.

Paper mention evidence does not by itself resolve a dataset release. Metadata-only entries are not browsable datasets.

## Run from a checkout

Python 3.12 and Node 22+ are used for development. `uv.lock` and `apps/web/package-lock.json` pin the resolved environments.

```bash
uv sync --extra development --extra projection
npm --prefix apps/web ci && npm --prefix apps/web run build
uv run atlas serve
```

Use **Get preview** or **Prepare full data** on a dataset to review its pinned source plan, set budgets, and start or resume local preparation. See [on-demand preparation](docs/on-demand-preparation.md) and [implementation evidence](reports/on-demand-implementation.md). The default browser route on a workbench is the workbench; a static host serves the public build, which makes no privileged localhost connection.

For large collections, [the storage policy](docs/storage.md) preserves original-quality, full-resolution previews and compresses other images on demand into a bounded AVIF cache. Original bytes remain available for inspection and model inputs. Use `atlas storage clean` to review removable caches, duplicate immutable bytes and isolated test environments, then `atlas storage clean --execute` to reclaim them. See [the current storage receipt](reports/storage-footprint-final-20261007.json) for measured allocated blocks and accounting limits.

Static mode needs no Python or models. Build it with `npm run build` in `apps/web`, or use `npm run dev` during development. The catalogue and approved previews are generated into `apps/web/public/data` by the explicit publication command. Only the redistributable demonstration packs (CLEVR, PAIRS, EuroSAT) are approved for it; to install them into a workspace:

```bash
mkdir -p work/packs
cp -R examples/approved-packs/. work/packs/
```

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
- [Getting started](docs/getting-started.md): install, fetch previews, where things live, updating.
- [Adding your own datasets](docs/adding-your-own-datasets.md): folders, tables and Hugging Face datasets, from the interface or the CLI.
- [Adding catalogue datasets](docs/adding-datasets.md): adapters, recipes, mappings, coverage and evidence.
- [Remote workbench](docs/remote-workbench.md): existing mounts and SSH tunnelling.
- [Publication](docs/publication.md): explicit rights and media allowlists.

Tests use synthetic fixtures only where isolation is necessary. Production previews retain real source identity, sampling and rights receipts. GitHub Pages deployment is an explicit workflow action; implementation does not automatically publish anything.
