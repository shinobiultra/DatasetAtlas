# Implementation evidence

This workspace implements the browser, local workbench, source adapters, durable analysis, model integration, and publication pipeline described in `SPEC.md`. **It is not yet a completed v1 release:** exact source identity and previews across the entire paper-derived inventory remain incomplete. Current counts and exact acquired populations are generated in [the preparation report](on-demand-preparation.json). Some indexed populations retain partial media; an index is not automatically a complete original release. See [the remaining roadmap](../ROADMAP.md). An unavailable adapter is an implementation gap, not an external access restriction.

## Reproduce the running application

From the repository root, run `.venv/bin/atlas serve --port 8765` and open `http://127.0.0.1:8765/?mode=workbench`. The default route uses the approved static bundle. Local datasets and model weights are stored under ignored `work/`; provider settings and saved model conversations are under ignored `local-config/`.

## Evidence and its scope

| Requirement | Evidence | Limits |
| --- | --- | --- |
| Complete paper inventory | [Corpus coverage](corpus_coverage.md): 83 original files, 64 paper inventories checked by agents against full text and page evidence | Source identities and particular extraction uncertainties remain separate; no human approval is asserted |
| Honest dataset coverage | [Coverage CSV](dataset_coverage.csv), [source access](source_access_report.md), versioned registry YAMLs | Candidate entries are not advertised as browsable; publication restrictions do not prohibit local inspection |
| Complete local queries | Immutable Parquet indices under `work/snapshots`; each manifest gives its verified expected record count | Each index names its release and exact population; these are not all datasets in the inventory |
| Real analysis | [CLEVR receipt](analysis-demo-clevr-100.json): ten completed 100-example runs; [COCO receipt](analysis-demo-coco-100.json): fourteen completed 100-example runs, including both detectors and embedding spaces | Detector counts are predictions, not benchmark accuracy; all source labels remain separate |
| Local model integration | `work/model-server/proof-summary.json`, capability probe, independent-batch receipts and saved conversations | The local Qwen2.5-VL-3B produced incorrect CLEVR answers; integration success is not answer accuracy or a SOTA claim |
| Export and static publication | `work/demo-analysis/portable-pack`; approved CLEVR, PAIRS, and EuroSAT source packs under `examples/approved-packs`, with six CLEVR derived artifacts | Explicit media/artifact allowlists; no remote publication performed |
| Query performance | [Measured timings](query-performance.json), reproduced by `scripts/benchmark_queries.py` | OS caches were not flushed; this measures exact count and first-page retrieval, not arbitrary filters or browser rendering |
| Query cancellation | [Full CLEVR cancellation](query-cancellation.json), reproduced by `scripts/benchmark_query_cancellation.py`; 999,968-record reader remained usable after interruption | Native DuckDB memory setting is not a process RSS cap; the default 30-second query timer bounds SQL work, not source indexing or model jobs |
| Browser acceptance | [Browser verification](browser-verification.md); durable Playwright static CLEVR flow, live linked COCO image conversation/export journey, geometry and video checks, and separate mocked 10,000-point map test | Synthetic performance fixtures are not real dataset coverage; timing is one reference-machine run |
| Base installation | [Clean installation receipt](installation-verification.json) for the built wheel outside the checkout | Browser/API work without model dependencies; optional model stack is tested separately in this development environment |
| Independent review | [Review report](independent_review.md) and adversarial API/storage/job tests | Open findings remain release work; passing tests alone is insufficient |

## Validation discipline

Run `.venv/bin/python -m pytest -q`, then `npm test --prefix apps/web` and `npm run build --prefix apps/web`. Generated contracts are checked against Pydantic models. Publication validation scans paths, secrets, rights, artifacts and actual bytes. Runtime tests distinguish failed/missing detector results from completed zero detections, reject changed selection/run inputs, and exercise cancelled jobs, resumed transfers, immutable result joins, traversal and chunked-body limits.

`scripts/build_release.py` builds the frontend and distribution. Installation and browser walkthrough receipts are recorded separately when executed; an unexecuted check must not be inferred from this document.

No paid model API was used. Dataset pixels were sent only to the explicitly configured local model server. Models and datasets were acquired under the user's explicit local-download authorization.

## Earlier closeout validation (historical)

180 Python tests and 15 frontend tests passed. The final Playwright run passed 11 checks; the optional additional model-send test was skipped because its real saved conversation is already recorded in [the linked journey receipt](browser-linked-journey.json). Browser re-export/import was rerun successfully. Generated contracts were byte-identical. [All 64 registered local previews](final-preview-verification.json) passed record-count, snapshot-identity, and file-checksum verification. Registry validation passed 336/336. The public bundle contains only the three approved 100-record previews and is about 30.4 MB including frontend assets.

The wheel and source archive were rebuilt, scanned, and the wheel installed with base dependencies in a fresh Python 3.12 environment. A real HTTP server outside the checkout served the catalogue, all three packs and representative images, JavaScript, and API capabilities without Torch, Transformers, NudeNet, scikit-learn, UMAP, or LanceDB. See [the refreshed installation receipt](installation-verification.json). No remote deployment was performed.

## Rebuilt interface closeout

The earlier UI evidence above is superseded by [the UI closeout](ui-closeout.md): 191 Python tests, 22 frontend tests, and all 27 browser checks pass. The rebuilt panels now have real local image-send and detector/embedding-run receipts, explicit result refresh, and 390 px / 820 px browser coverage. No model-send skip remains in the live closeout run.

## Current acquisition and provider work

The 2026-09-23 expansion and its precise limits are documented in
[selective acquisition](selective-acquisition-20260923.md). Live preparation status remains
separate from verified coverage. The latest counts and test checkpoint are in
[final-status.json](final-status.json); older counts above are historical receipts.

The current implementation has not received a new independent review. PR #3's review
covers its earlier changes only. Source acquisition does not approve redistribution;
public media remain limited to CLEVR, PAIRS and EuroSAT.

## Full-resolution previews and bounded retained storage

The 2026-09-23 storage checkpoint retains original preview pixels and serves
full-dimension AVIF browsing copies for other images, with originals available
on demand. The measured footprint, including explicitly configured local model
weights and the active vLLM compilation cache, is below 150 GB; see
[the timestamped storage scan](storage-footprint-retained-20260923.json).
This measures the current 131-preview workspace, not a prediction that every
remaining collection's metadata will fit. Admission checks enforce the configured
ceiling for new preparations, subject to the documented filesystem caveats.

After retiring verified acquired archives, all 600 preview records across GQA,
SUN397, CLEVR full, VQA v2, POPE and DOCCI passed original-byte checks (582 distinct
images). Eighteen late-population original/display pairs also passed. Separate
VHD11K checks passed 100 original preview images, three non-preview image pairs,
and three original videos. Receipts are in `retained-media-live-verification.json`,
`vhd11k-images-after-source-eviction.json`, and
`vhd11k-video-after-source-eviction.json`. Aircraft has its own earlier receipt.

Validation: 347 Python tests passed, with one optional local-archive test skipped
because that original is now served on demand; targeted retirement and type-fix
tests passed afterward. All 22 frontend tests and 34 browser checks passed,
including real local detector, embedding and vLLM image-send journeys. The new
storage modules pass the pinned `ty` check through `prek`. Current archive and
base-only installation receipts are recorded separately. Catalogue coverage
remains incomplete: 202 of 333 entries still lack a preview.

## Native populations, visual masks and bounded remote indexing

The next 2026-09-23 checkpoint has **143 prepared previews / 14,032 records and
138 full-population indices**, with 190 of 333 entries still lacking a preview.
Newly verified populations are Resume Corpus (29,783 native text/label pairs),
SAD (127,173 unrendered samples and three trials), Bias in Bios (396,189 rows),
ScienceQA-IMG (10,332 image-bearing questions), six Pathways populations (4,955
rows), TextVQA-X (18,096 explanations), and FOIL (594,536 caption examples).

The exact releases and limitations matter: Bias in Bios uses the identified
LabHC/Ravfogel derivative, Pathways follows the pinned available author transform,
and FOIL uses the author's corrected October 2018 release. Historical paper-used
revision equivalence is not inferred. SAD's templates are not executed or rendered,
and its question/answer text is excluded from committed receipts. See
[native text verification](native-text-live-verification.json),
[ScienceQA/Bios verification](scienceqa-bios-live-verification.json),
[Pathways verification](pathways-live-verification.json),
[TextVQA-X verification](textvqa-x-live-verification.json), and
[FOIL verification](foil-live-verification.json).

TextVQA-X retains exact native boolean NumPy masks, a lossless PNG view, explanations
and original TextVQA photographs. All native explanations/splits were checked;
103 image/mask/array triplets passed live checks. The browser downloads the exact
native array and labels the lossless mask view. Deflated storage reduces the
13.84 GB decoded native mask members to a 28 MB random-access ZIP without changing
member bytes. The worker independently bounds encoded output and decoded work.

Food101 now has a deterministic random 100-record preview. Retirement of its
verified native archive freed 4,996,278,331 bytes; its separate derived ZIP remains.
All 100 new preview originals and three later original/display pairs passed live
checks after retirement. The latest [storage scan](storage-footprint-native-20260923.json)
measured 137.4 GB including configured local model weights, before FOIL's index.
This is a timestamped measurement, not a promise that all remaining full metadata
will fit. Corpus originals remain untouched.

Cauldron is still running and is excluded from completed coverage. A real native
record exceeded the default 2 MB bound; the explicit recipe now permits up to
16 MB per record. Query pages stop at 32 MB of encoded record/result payload and
continue without skipping the next record. Remote shard prefetch buffers are
bounded, cancellation closes producers, and worker failure explicitly closes
its iterators. Persistent range connections halve elapsed time in one recorded
cold-client-cache trial; that is not a controlled global throughput estimate.

Validation: 372 Python tests passed (one optional retired-local-archive skip),
370 passed on fresh Python 3.14 (three optional dependency/source skips), 22 frontend
tests and 36 browser checks passed. The browser run includes real local detectors,
embeddings, vLLM image send, native mask download and 304/390/820 px layouts.
Pinned `ty`/`prek`, wheel/sdist scanning and base-only installed HTTP checks passed;
receipts identify their exact artifacts. No new independent review is claimed.

## Nocaps, PHASE and author Shapes recipes

The next checkpoint reaches **148 previews / 14,532 records and 143 full-population
indices**, leaving 185 of 333 entries without a preview. Nocaps includes all 15,100
native image records with all 45,000 public validation captions and explicitly
unpublished test labels. Its legacy Figure Eight URLs fail; exact Open Images IDs
join to the official CVDF V4/V5 image distribution. All 103 inspected files match
the benchmark's recorded dimensions, which are capped at 1024 pixels upstream;
Atlas does not resize them or claim original Flickr full resolution. See
[nocaps verification](nocaps-live-verification.json).

PHASE retains all 18,889 native images, 35,347 annotated regions, aggregated human
perceptions and individual annotator votes. Every annotation field was checked
against the author release; 103 live images match original ZIP member bytes.
Auxiliary annotator information and the research-only-use notice remain in the
native annotation archive. These are source annotations, not inferred personal
attributes. See [PHASE verification](phase-live-verification.json).

Shapes Recognition, Localization and Relations each contain 400 images reconstructed
with the authors' released generator. The source revision, seed, Python/Pillow
versions, 1024-pixel rendering parameters, generated-file hashes and paired sample
relations are recorded. All 1,200 images and native fields matched the upstream
pure functions; 309 live originals passed checks. These are explicitly labelled
author-recipe reconstructions, not archived historical experiment images or test
fixtures. See [Shapes verification](shapes-live-verification.json).

Food101's redundant repacked ZIP was also retired after all 101,008 native members,
202,000 image references in retained snapshots and pinned preview originals passed
verification. Fresh original retrieval probes passed before removing the extra
5,139,003,823-byte copy. The original preview/late-image live checks passed again
after deletion. See [the retirement receipt](food101-repacked-retention.json).
The [new storage scan](storage-footprint-expanded-20260923.json) measured **135.6 GB**,
including configured external model weights and active staging, with no scan errors.

Validation: 380 Python tests passed (one optional source skip), and 378 passed on
Python 3.14 (three optional dependency/source skips). Subsequent focused retention
and generator-budget checks passed. The earlier 22 frontend and 36 browser checks
remain the UI checkpoint; this batch changed no frontend code. Native media and
query checks above ran against the current workbench. Pinned type checks passed.
Cauldron remains in progress and is excluded from these completed counts.
