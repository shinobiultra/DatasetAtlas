# On-demand preparation implementation

This update implements acquisition and version activation in the workbench and CLI, broadens real dataset coverage, and closes several analysis, media and resource-management gaps. **It does not complete catalogue-wide coverage or SPEC.md.** Current machine-readable counts and outstanding source requirements are in `final-status.json`, `on-demand-preparation.json`, and `preparation-readiness.json`.

## Implemented behavior

- Explicit download/index budgets, metadata-only plans, exact source revisions and checksums, bounded HTTPS transfers with resume, cancellation/retry, persistent status, isolated preparation workers, and atomic activation of completed versions.
- Immutable historical source/snapshot retention for frozen selections. Registry lookups load only the requested active dataset and cache unchanged metadata.
- Native multi-shard Arrow/Parquet reading; schema discovery across every shard; explicit split restrictions; original source filename/row/checksum provenance; selective embedded image reads, including declared base64 images and AVIF.
- Original Oxford Pets/DTD annotations, all ten DTD partitions, and a reusable JSON/JSONL/CSV archive annotation adapter. Task documents retain nested train/test examples, and missing referenced archive media cause explicit failure.
- Complete-scope filtered exact similarity beyond 1,000 eligible records; display-only safe-view derivatives; bounded decoded-original media cache; streaming checksums; worker CPU/wall-time/RSS limits, with verified kernel cgroup memory caps when available.
- A preparation modal, persistent job discovery, download progress, and a responsive dataset header with both side panels open.

## Real source populations

Thirteen additional datasets were acquired and indexed: AlgoPuzzleVQA, IlluChar, WMDP, Oxford Pets, DTD, CounterFact, PuzzleVQA, NaturalBench, Senator Tweets, ConceptARC, MMMU-dev, Waterbirds, and SimpleVQA. Exact counts, source scopes and immutable receipts are in `on-demand-preparation.json`. GQA's existing 132,062 validation-balanced records now resolve against the complete original image archive; other GQA question splits are not part of that snapshot.

These are local datasets. Acquisition grants no public redistribution rights. Only the previously approved CLEVR, PAIRS and EuroSAT media are included in the static distribution.

## Validation and failures resolved

Latest checks: **217 Python tests, 22 frontend tests, and all 29 browser tests passed**, with no skipped browser journeys. The wheel and sdist pass the publication-content audit, and the rebuilt wheel imports successfully in the base-only installation environment.

Unit/integration coverage includes full records beyond previews, complete-scope LanceDB retrieval, historical snapshot resolution, source/recipe drift, cancellation, output limits, archive joins, base64 byte identity, AVIF, resource kills and original-image preservation. Browser evidence includes local model image transmission and real detector/embedding runs, the preparation modal, safe-view and native H.264 playback. `on-demand-live-verification.json` records complete queries and decoded source media beyond the previews.

Live-source testing found and fixed an overly broad MMMU source plan, large integer query precision, SimpleVQA base64/AVIF images, and repeated whole-catalogue metadata parsing that delayed full-index navigation. Tests also caught a decoded-cache commit contract mismatch and a header layout that hid sample controls. Failed intermediate preparations remain recorded; only completed versions were activated.

## Remaining scope

The final readiness audit found executable plans for **81 of 336 catalogue entries** under a 20 GB download / 2 GB output budget. There are **77 local previews and 72 full-population indices**. EXAMS-V preparation was resumed in the background with its pinned 6.44 GB source plan; it is not counted as completed coverage.

Many catalogue entries still have no executable acquisition recipe, and source identity/release reconciliation remains incomplete. A ready plan is not a tested dataset. Gated/unreleased data and missing implementation remain different states in the reports. Multi-terabyte selective remote indexing is not integrated into this workflow. LM Studio is not live-tested, and no remote site deployment has been performed. `ROADMAP.md` remains the explicit list of unfinished work.

No sub-agents, paid APIs, external model transmissions, corpus modifications or new public dataset publication were used for this update.
