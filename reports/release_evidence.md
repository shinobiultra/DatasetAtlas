# Current release evidence — 2026-10-09

The current working release has **231 catalogue entries, 220 native previews, 21,532 preview records and 218 complete indices for declared native populations**. **11 entries have no prepared preview** and `full_v1_complete` remains false. Public implementation gaps, exact paper identities, effective gates and unreleased data are recorded separately in [ROADMAP](../ROADMAP.md), [remaining coverage](remaining-native-coverage-audit-20261007.json) and [authorization links](../docs/dataset-authorization.md).

Current software verification: **1,028 Python tests pass, one optional skip; 26 frontend tests pass; all 69 browser checks pass**. The separate Python 3.14.2 environment passes **1,025 tests with four optional skips**; three concern missing LanceDB/UMAP dependencies and one concerns unretained native VHD11K archives. Pinned `ty`/`prek` checks pass. The real local linked journey verifies filters, projection reuse, detector/outlier fields, exactly approved original-image context, conversation receipt, export/import and prediction-column retention. Native audio/video checks prove muted playback and seeking, with their original/display representation limits. These functional checks do not establish scientific model accuracy or human acceptance.

The [six-source integrity receipt](native-six-source-integrity-20261007.json) covers complete indices and all retained originals for Open Images, MIT-States, UCF101, FFHQ, EmoSet and Spoken Wikipedia. [Exhaustive value parity](ffhq-emoset-exhaustive-native-parity-20261007.json) covers all 188,102 FFHQ/EmoSet native metadata objects. Mirror byte equality and historical paper subsets remain unverified. Full preview/index HTTP checks are in [media smoke](preview-media-smoke-final-20261007.json) and [complete-index smoke](complete-index-smoke-factoid-attested-20261007.json). Fresh source reproduction is current-recipe bound: **84 successful fresh acquisitions remain bound to the current recipe SHA** (79 current verified classifications and five matching historical proofs under other current planning classifications), distinct from all 218 previews having acquisition paths.

[The authorized independent 6.1 Sol review](independent-limitations-review-20261007.md) covers code, synthetic failures and aggregate receipts. Reproduced cancellation, retention, transfer-accounting and CIFAR-C retirement defects were repaired and retested. The reviewer did not independently inspect native records or media; the report discloses its one embedded-excerpt scope deviation. Review recommendations do not constitute human acceptance.

EmoSet, PHASE and both CIFAR-C acquired archive bodies were removed only after canonical membership, protected-original, complete-source/index and bounded cold retrieval verification. [Post-retirement JPEGs](native-post-retirement-originals-20261007.json) and [CIFAR-C RGB/PNG checks](cifar-native-post-retirement-originals-20261007.json) verify live original access after deletion. Superseded versions, isolated reproduction workspaces and unpinned caches were separately audited. Corpus originals, active/frozen canonical records, protected original previews and required weights remain available. Final configured-root accounting, source hashes, wheel/sdist identity and clean-install checks are bound in [final status](final-status.json); each receipt retains its execution time and precise scope.

The rebuilt static bundle contains only the approved CLEVR, PAIRS and EuroSAT packs; current [publication validation](publication-validation-release-20261007.json) reports zero errors. No remote deployment, paid model API, external model send or cluster job was performed. Basic installation/browsing is checked without optional model dependencies. Model-stack and base-Python tests are separate evidence.

The dated sections below preserve historical checkpoints. They do not certify later source code, native coverage or a newer distribution hash.

The resumed FACTOID integration preserves all **4,150 native user rows and 17,288,900 source cells**, exact DataFrame metadata and the unchanged original gzip without executing pickle globals. Exhaustive canonical-record, 83,000 materialized-field and search parity passed; a separately downloaded empty workspace reproduced the same snapshot and preview IDs. [Native parity](factoid-native-population-verification-20261007.json) and [fresh-source proof](factoid-empty-workspace-preparation-20261007.json) retain their scopes. The compact preview pack changes JSON whitespace only. Its exact native user envelope is available locally; missing Reddit text is not hydrated. Paper membership and publication/privacy rights remain unresolved.

Wide ordinary queries now sort compact keys before bounded native payload batches; durable cancellation survives between statements. Sixteen generated query tests include the reproduced memory and cancellation failures. The default FACTOID complete page returns 53 records, an exact 4,150 count and a cursor under the 32 MB record budget in **6.04 seconds**. This does not meet the ordinary two-second filter target; wide stratified sampling retains its prior window/envelope path and can explicitly refuse its memory budget. [Page repair](factoid-complete-ui-page-repair-20261007.json) records the measurement. Both current Python suites, 26 frontend tests, 69 browser checks and the independently reviewed query regressions pass. The final browser run uses the available **local Ollama image model**; the removed disposable vLLM environment is not currently running. Screenshots, traces and video are disabled in that run.

The main environment was accidentally replaced during isolated-Python verification, then restored from the existing locked cache. All required optional imports pass and the host confirms CUDA is available with Torch 2.14.0+cu130. A temporary package-cache extraction quota failure and both restoration receipts are retained. The lead also accidentally read a native-class filter audit containing 24 excluded labels and row ordinals; [the scope deviation](lead-native-audit-read-deviation-20261007.json) records this. It was not sent to the independent reviewer; this resumed pass cannot claim zero dataset-content exposure to the lead assistant. No FACTOID user/post contents or media were read into the assistant context.

Fresh FACTOID reproduction bodies and unused standalone conversions were retired only after original-hash, canonical membership and same-snapshot proofs. Primary native originals, active/frozen indices, protected previews, required runtime and model weights remain. Final configured-root savings, exact distribution hashes, two clean-install checks and source parity are in [final status](final-status.json). All earlier receipts retain their original timestamps; the whole SPEC remains incomplete.


---

# Implementation evidence

## Current deadline closeout, 2026-10-06 approximately 19:00 JST

Current measured coverage: **333 catalogue entries, 212 prepared previews, 20,732 real preview records, 209 indices for declared native populations, 121 entries without previews**. `full_v1_complete` remains false. All 64 paper inputs have outcomes; mention candidates and native release identities are not independently reviewed paper populations.

Current verification passes **884 Python tests with 1 optional skip** (882 passed, 3 skipped on a base-only Python 3.14.2 environment; logs `work/python-final-all-20261007.log` and `work/python314-final-all-20261007.log`), **26 frontend tests** and **56 browser checks with 4 skips** (both from 2026-10-06 18:56; the 2026-10-07 changes touched no frontend file), scoped `ty`/`prek` and generated-contract parity. All 333 catalogue entries validate. The wheel and sdist were rebuilt on 2026-10-07 (wheel SHA-256 `1ca7066f0da747e24adaea41f0345ac7705787e094e42be429a171e13ec5ac45`, 39,358,170 bytes; sdist `a1454ebdd2620032d4e4a815d29a428d863bccafa0f2ab88578dcf608fb3f1b0`, 39,291,989 bytes); that wheel passed archive inspection and was installed in clean base-only Python 3.12.14 and 3.14.2 environments outside the checkout (the receipt holds the last, 3.14.2). The earlier 2026-10-06 3.14.7 installation checked the previous wheel. The installed server serves the catalogue, interface, original assets from the three approved static packs, capabilities and missing-optional-reader preflight. See[installation receipt](installation-verification.json).

The real local CLEVR journey proves 9 existing analysis artifacts remain connected to filtering, 16 → 1 → 16 projection changes, detector colour fields, original-image context, a saved local model reply and selection export/import. Explicit thinking control and the provider timeout are recorded; previous 60/120 second failed calls remain in the local ledger. This is functional integration evidence, not answer accuracy or scientific evaluation. See[browser journey](browser-runtime-linked-journey-20261006.json).

New native receipts verify TID2013's 3,000 distorted/reference pairs, all 3,025 BMP hashes and 17 exact score tables; VOC2011's 14,961 JPEG/XML records and 102 image-set tables; Places365's 36,500 validation originals; original LAION400M first-shard **12,933,524** native annotations; COCO-GB's 244,242 variant-scoped records preserve 1,214,755 native sentence objects and exact whitespace. See the individual parity receipts and[post-cleanup native verification](native-after-final-cleanup-20261006.json), which checks 624 retained original memberships through the live API with zero source acquisition or external-model requests. TID's paired BMP reference also renders in the browser.

Fresh source reproduction is recipe-bound: **57 current recipes verified**, with **142 entries carrying historical proof** separately. Feasibility includes untried planned recipes and is not a count of verified fresh previews. TID,Places and the repaired COCO-GB were fetched in fresh workspaces; their disposable bodies/indices were subsequently retired with full file inventories and verification receipts preserved. See[reproducibility](preview-reproducibility.md).

Allocated storage was **121.56 GB** at the 2026-10-06 closeout and is **129.18 GB** after the 2026-10-07 re-preparation of `oasis`, `zerobench`, `mvbench-scene-qa` and `mit-adobe-5k` (superseded prepared versions of about 5.4 GB are retained, not deleted; [current footprint](storage-footprint-current-20261007.json)), including the three explicitly configured external roots, with **20.82 GB** under the 150 GB ceiling. It remains above the 100 GB target. Cleanup removes unreferenced failed/superseded versions, verified duplicate staging, disposable fresh/installation workspaces, idle caches and frontend dependencies; corpus originals, active and saved frozen snapshots, protected original previews, source retrieval indices, model weights and failure evidence remain. `npm ci` restores frontend developer dependencies. The running workbench and release archives remain usable. A real write and fsync pass. See[current footprint](storage-footprint-current-20261006.json) and[write proof](closeout-storage-write-verification-20261006.json).

Spoken Wikipedia remains text-only in the active snapshot. Complete native Dutch and English TAR/member hashes and seek indices are checkpointed; German acquisition, all-language audio joins and real preview/playback evidence remain implementation work. Whole parent ZIP SHA-256 is not asserted.

The independent review uses one authorized **gpt-6.1-sol/xhigh** reviewer restricted to code, synthetic tests and aggregate receipts. Reproduced integrity/resource/cancellation defects were fixed and rerun; native content was not sent to that reviewer or external models. The[limitations report](independent-limitations-review-20261006.md) retains failed intermediate findings and final scope limits. No cluster jobs, paid model APIs or remote deployment were used. See[final status](final-status.json),[roadmap](../ROADMAP.md), and[authorization links](../docs/dataset-authorization.md) for remaining acceptance work.

This workspace implements the browser, local workbench, source adapters, durable analysis, model integration, and publication pipeline described in `SPEC.md`. **It is not yet a completed v1 release:** exact source identity and previews across the entire paper-derived inventory remain incomplete. Current counts and exact acquired populations are generated in [the preparation report](on-demand-preparation.json). Some indexed populations retain partial media; an index is not automatically a complete original release. See [the remaining roadmap](../ROADMAP.md). An unavailable adapter is an implementation gap, not an external access restriction.

## Reproduce the running application

From the repository root, run `.venv/bin/atlas serve --port 8765` and open `http://127.0.0.1:8765/?mode=workbench`. The default route on a local workbench opens the workbench; a static host serves the approved public bundle. Local datasets and model weights are stored under ignored `work/`; provider settings and saved model conversations are under ignored `local-config/`.

## Evidence and its scope

| Requirement | Evidence | Limits |
| --- | --- | --- |
| Complete paper inventory | [Corpus coverage](corpus_coverage.md): 83 original files, 64 paper inventories checked by agents against full text and page evidence | Source identities and particular extraction uncertainties remain separate; no human approval is asserted |
| Honest dataset coverage | [Coverage CSV](dataset_coverage.csv), [source access](source_access_report.md), versioned registry YAMLs | Candidate identities stay explicit; a distinct pinned native population may have a real local preview without resolving the paper subset. Publication restrictions do not prohibit local inspection |
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

The 2026-09-24 continuation added the pinned native MLLMU-Bench Full_Set/Test_Set,
both SBBench synthetic age/gender variants and the exact seven-file Figshare v1
stimulus release. [Native verification](native-expansion-20260924.md)
compares complete annotations and paths with author releases, then checks original
images from previews and later records; all seven Figshare images/videos passed
original-byte media routes. The eLife source-data workbooks also pass independent
parity on all 1,229 native nonempty cells and 135 formulas, plus seven original
XLSX routes. The 2026-09-24 morning checkpoint was 162 previews, 157 complete-population
indices and 171 entries without a preview. Cauldron is still indexing and is
excluded. Python 3.12 passed 410 tests with one optional skip; Python 3.14
passed 408 with three optional skips. All 22 frontend tests and the pinned
`prek` checks passed. The built wheel and sdist passed archive inspection,
and the reinstalled base-only wheel passed an HTTP smoke test outside the checkout.
The 38 browser checks were completed at the earlier 2026-09-23 checkpoint; no
frontend behavior changed in this continuation. [Storage accounting](storage-footprint-20260924.json)
measured 141.82 GB at that checkpoint while Cauldron was still running, below the 150 GB ceiling
but above the 100 GB target.
Checksum-identical immutable source, derived ZIP and Parquet copies were linked
without changing their paths or bytes. [Visual Genome derivatives](derived-archive-dedup-20260924.json),
[COCO snapshots](coco-snapshot-dedup-20260924.json),
[Waterbirds source](waterbirds-source-dedup-20260924.json), and
[four smaller pairs](secondary-dedup-20260924.json) recovered about 3 GB
of allocated space; direct source-media and representative snapshot reads passed
after relinking.

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

## Native archive and caption checkpoint, 2026-09-23

The next verified checkpoint reaches **157 previews / 15,432 records and 152
full-population indices**, leaving 176 of 333 entries without previews. Nine new
populations and their exact scope are documented in
[native-expansion-20260923.md](native-expansion-20260923.md). This remains incomplete.

Multipart HTTPS ZIP reads now preserve SEED's native images/ordered frames without
assembling its large source archives. A bounded parsed-directory cache avoids
reparsing the same large ZIP for each frame while preserving native header/CRC
validation. FairFace retains both native crop variants, VQA-Constraints retains
all released image candidates and exact Unicode joins, and RSICD retains all
54,605 captions including repeated strings. FIND code and weights remain passive
source data; no untrusted benchmark code or pickle was executed.

Preparation now honors declared remote Parquet cache roots/budgets. Verified
registered source files can be reused through same-filesystem hard links, with
admission accounting reflecting reuse. A failed planned link or missing registered
object fails explicitly rather than silently downloading an unreserved copy.

Validation: **406 Python passed, one optional source skip; Python 3.14: 404 passed,
three optional skips; 22 frontend tests; 38 browser checks**. The browser suite
includes local detector/embedding runs and actual vLLM image transmission. Its
small-source preparation test now requests a 50 MB budget instead of requiring
an unnecessary 2 GB default reservation. `prek`, wheel/sdist inspection and the
installed base-only HTTP smoke test passed. Receipts and exact logs are referenced
in `reports/final-status.json` and `reports/installation-verification.json`.

The timestamped storage scan measured **143.47 GB**, including configured external
models. The user requested a graceful stop. Cauldron was cancelled at 725,000 of
1,880,992 rows and remains excluded from coverage. The workbench and task-owned
vLLM server were stopped. See [STOP_20260923.md](../STOP_20260923.md) before resuming.

The subsequent SafeBench expansion adds a complete 2,300-group native index and
100 original-quality preview records, making **163 previews / 15,846 records,
158 full-population indices, and 170 entries without previews**. All 6,971
archive members and all native text/image prompt rows were independently
verified; 300 preview media and three later original files passed HTTP reads.
The 4.7 GB local archive was retired after both image and audio previews were
pinned, and original media remain available through checksum-checked remote
multipart reads. [Native receipt](safebench-live-verification.json),
[retirement receipt](safebench-retirement-20260924.json), and
[browser check](safebench-browser-20260924.json). The measured footprint is
139.44 GB, including configured models and the still-running Cauldron plan.
The Python 3.12 suite passed 414 tests with one optional skip; Python 3.14 passed 412 with three optional skips. The 22 frontend tests, 26 default browser checks, one live SafeBench browser check, and `prek` passed.

On 2026-09-24, ROCO and Cauldron raised local coverage to **165 prepared previews / 16,046 records, 160 full-population indices, and 168 entries without previews**. ROCO's 87,927 original annotation rows passed complete 36-table and indexed-row parity checks; its 100 preview images were verified against current PMC version MD5s and pinned locally. Historical FTP-image byte equality is not claimed, and `NO-CC CODE` among sampled licences excludes ROCO from public packs. [ROCO receipt](roco-live-verification.json).

Cauldron's 1,880,992-row complete annotation index passed its local SHA-256 and unique-ID checks. The pinned author release spans 50 configurations and 938 remote Parquet shards; their source SHA-256s remain author metadata rather than whole-shard local verification. Some source images contain only a path. A deterministic 250-candidate pool excluded five unavailable records, selected 100 records, verified and pinned all 109 original images, and passed all 109 live HTTP decode/hash checks. Three later non-preview originals from separate shards and the focused browser view passed. The remaining media are on-demand and unverified, and the paper's selected 72,000 pairs are unidentified. [Cauldron receipt](cauldron-live-verification-20260924.json).

The Python 3.12 suite passed 418 tests with one optional skip; the live Cauldron browser test, production frontend build and `prek` passed. The subsequent six native preparations for CIFAR-10, CIFAR-100, ImageNet-A, ImageNet-R, ImageNet-V2 MatchedFrequency and IconQA migrated previously counted indices into reproducible prepared versions. They passed complete native label, member or question/media-reference parity checks and 716 live preview media comparisons; the two CIFAR source archives contain raw planar pixels, so those 200 comparisons check exact pixels in lossless PNG renderings. [Native receipts](native-expansion-20260924.md). The 22 frontend tests and 26 default browser tests passed. [Storage accounting](storage-footprint-20260924.json) measured **145.94 GB** including configured external model roots, below the 150 GB ceiling but above the 100 GB target. This remains an incomplete implementation of [SPEC.md](../SPEC.md), principally because 168 catalogue entries still have no local preview and source/rights/release reconciliation is incomplete.

The QAVA author repository contributes the pinned 32-image × 50-question VQA v2 setting: all 1,600 native question and answer rows join exactly, all 32 original images are pinned and checksum-checked, and the 100-record preview covers every distinct image. The live focused browser check passed. Other m+n settings and publication rights remain unresolved. [QAVA receipt](qava-live-verification-20260924.json). This raises measured local coverage to **166 previews / 16,146 records, 161 full-population indices, and 167 entries without previews**. The Python 3.12 suite passed 422 tests with one optional skip. [Storage accounting](storage-footprint-20260924.json) measured **145.95 GB** including configured external model roots, leaving about 4.05 GB under the 150 GB ceiling. This is still not a completed [SPEC.md](../SPEC.md) v1.

The depositor's COVID-19 Radiography Kaggle v5 adds all 21,165 native radiograph/mask pairs. The four source tables join exactly to the native image and mask filenames; all 42,330 PNGs decode. Atlas pinned the 200 full-resolution preview assets, and all 200 plus a later pair passed byte-exact live HTTP checks and a focused browser check. The native XLSX tables say `256*256` for radiographs whose original PNGs are 299×299; masks are 256×256. The prepared source preserves that statement as `source_table_size` without assigning false asset dimensions. [Native receipt](covid-radiography-live-verification-20260924.json). Coverage is now **167 previews / 16,246 records, 162 full-population indices, and 166 entries without previews**. The Python 3.12 suite passed 424 tests with one optional skip; registry validation reported zero errors and `prek` passed. [Storage accounting](storage-footprint-20260924.json) measured **147.60 GB** including configured model roots. Medical image publication rights and the cited paper's exact evaluated subset are unverified; SPEC.md remains incomplete.

ObjectNet 1.0 adds a complete 50,273-image filename/class index from the official 197.05 GB encrypted ZIP through ETag-pinned HTTP ranges. Its 100 hash-ranked preview originals (412,243,274 bytes) are locally protected, decoded, and checked for the original red border. Three non-preview images passed byte-exact source-to-live-API comparison, and focused browser inspection passed. [Native receipt](objectnet-live-verification-20260924.json). The entire archive checksum and every non-preview image have not been verified; no images enter the public pack under the source's restrictions. Measured coverage is **168 previews / 16,346 records, 163 full-population indices, and 165 entries without previews**. The Python 3.12 suite passed 425 tests with one optional skip, 22 frontend tests passed, registry validation reported zero errors, and `prek` passed. [Storage accounting](storage-footprint-20260924.json) measured **148.02 GB** including configured model roots, leaving 1.98 GB under the 150 GB ceiling. SPEC.md remains incomplete.

Visual6502 adds the complete 3,510-transistor table from commit `d8ecc129b34e0eaf320e0400fcf33329475bdb1e`: every native ID, node, bounding box and geometry value matches the immutable index, with a 100-record preview, ten live complete-query records and a focused browser check. [Native receipt](visual6502-live-verification-20260924.json). The source says 6502 revD while the cited paper describes a 6507 input; it remains a candidate identity, and file-specific redistribution rights remain unreviewed. Measured local coverage is **169 previews / 16,446 records, 164 full-population indices, and 164 entries without previews**. [Storage accounting](storage-footprint-20260924.json) measured **148.03 GB** including configured model roots. SPEC.md remains incomplete.


## Native portability and cleanup checkpoint, 2026-10-05

The workspace has **333 catalogue entries, 176 prepared previews, 17,146 preview
records and 169 indices for explicitly declared native populations**. Full v1
remains incomplete: **157 entries lack previews**, and many exact paper-used
identities remain unresolved. [Coverage](dataset_coverage.csv),
[reproducibility](preview-reproducibility.md) and [the roadmap](../ROADMAP.md)
separate implementation gaps, access restrictions, unavailable releases and
budgets. The reproducibility table retains execution dates for earlier checks;
175 sources are verified under its default planning budget, while SUN397 needs
a larger transfer budget. All 176 maintainer previews have acquisition paths.

[Native expansion receipts](native-expansion-20261005.json) cover AudioSet's
2,084,320 weak-label rows, Recap's 1,000-row author preview split, LingoQA's 1,000
evaluation answer rows and 500 original frames, VizWiz-Priv's 13,571 annotation
rows and distinct source conditions, and one 532,229-row DataComp metadata shard.
Missing audio, linked third-party images, eight absent VizWiz image IDs and
unprepared larger releases remain explicit. FineVision adds 100 sampled records
from the pinned 25,243,243-row release after all 9,499 shard footers were read,
using 2,902,318,210 transfer bytes within the approved 3 GB cap. Its 58 original
images pass HTTP hash/decode checks. No complete FineVision index, exact paper
subset or blanket publication permission is inferred.

Native DOCCI, SVHN, VHD11K and controversial-stimulus acquisition paths and
bounded native Parquet readers now reproduce previews outside the maintainer
workspace. Optional source readers are checked before downloading. Sampled
Parquet previews serve their retained original files locally, with whole-file
checksums, configured roots, MIME detection and traversal/swap protections;
they no longer fetch the same remote images again for inspection.

The complete Python run passes **633 tests with one optional skip**. Frontend
unit tests pass **22**. The final browser and clean-installation results are
recorded in [final status](final-status.json) and
[installation verification](installation-verification.json). The full Python
suite uses the existing Python 3.12 ML environment; the separate base-only wheel
installation uses Python 3.14.7 and fresh current dependencies. Three optional
live model/analysis browser integrations are outside this pass. Historical real
model receipts remain evidence for those earlier runs, not a current model
retest. No paid API, external model send or cluster job was run in this pass.

[Storage accounting](storage-footprint-20261005.json) measures the workspace
and explicitly configured external model roots. Caches, completed duplicate
verification versions, isolated installation/model test environments, and
checksum-identical immutable duplicates were removed or linked. Native archives
were retired only after source identity, member parity, protected previews and
cold original routes were verified; sources without a stable remote identity
remain local. [Retirement](storage-retirement-20261005.json) and
[live original checks](native-retirement-live-20261005.json) preserve the evidence.
Original paper files, native canonical indices, frozen selection dependencies,
protected preview originals, model weights and failed-attempt receipts remain.
Hard links are counted once; reflink sharing and unconfigured external caches
limit interpretation of the measured allocated blocks.

The public bundle is rebuilt locally with only the three approved packs (CLEVR,
EuroSAT and PAIRS). No remote deployment or new media publication approval is
claimed. [Authorization links](../docs/dataset-authorization.md) provide the
publisher forms and gated repositories requested by the user; no access request,
agreement acceptance or purchase was made on their behalf.


## 2026-10-07 closeout addendum (Claude pass)

After the Codex pass's final checkpoint (2026-10-06 18:57 JST) the tree was quiet and this pass continued in it. Changes and evidence:

- Sixteen further recipes were verified from an empty workspace (twelve in a first batch, then `celeba`, `mit-adobe-5k`, `oasis` and `zerobench`; `mvbench-scene-qa` again under its final recipe). Three of them first failed and exposed defects, now fixed with regression tests: the `mit-adobe-5k` plan understated its preview-original transfer (`preview_media_transfer_bytes`), `zerobench` could not be rebuilt because `auto` planning chose a complete download that refuses its large embedded images (`auto_source_mode: selective`), and the `oasis` preview carried no images because its converter did not map the media reference. See `ROADMAP.md` items 9 to 12.
- Snapshot IDs from an empty workspace equal the maintainer's for `oasis`, `zerobench`, `celeba`, `mit-adobe-5k` and `mvbench-scene-qa`; `oasis`, `zerobench`, `mit-adobe-5k` and `mvbench-scene-qa` were re-prepared here for that, because their recipe files changed and the recipe hash is part of a snapshot ID. The `mit-adobe-5k` preview was also compared record for record (100 record IDs, 100 original TIFF SHA-256 values) before the re-preparation and was identical.
- The preview media smoke over the live route covers 212 datasets and 489 assets with no failure (163 datasets with media, 49 metadata-only): `preview-media-smoke-20261007.json`. The complete-index smoke also passed.
- The Codex reviewer's five findings against this pass's files were repaired with regression tests (see `review-brief-20261006.md`).
- Not done: a review of the 2026-10-07 changes by anyone other than their author, a re-run of the browser suites (the frontend dependencies were removed at the last closeout and `npm ci` restores them), and the four live specs that send an image to a local model.
- The disposable empty-workspace verification directories (about 17 GB) and the Python 3.14.2 test environment were deleted after their results were recorded in `preview-reproducibility.json`; the proof records carry the snapshot IDs, byte counts and recipe checksums.
