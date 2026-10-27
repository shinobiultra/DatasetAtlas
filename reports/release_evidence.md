# Dataset Atlas release evidence

Release 1.0.0; full_v1_complete: true.

**202 catalogue entries, 202 prepared previews, 19,779 preview records, 200 complete local indices.**

Counts come from the active runtime registry, structural preview counts and index metadata. No dataset record values are decoded or inspected by this report generator. A source's total population is distinct from its locally indexed population.

Catalogue SHA-256: `ba6c177064b0b7c23c64cbd2baae9904b2403ac0e340af3054296268fd86e508`.
Release source SHA-256: `347db588b133120cf024b4b096b5f98aabc378d2bf99ea2e23e2ae469e8afbf1`.

The current verification proof passed every required software release gate. Its checksum is `21092efc7462d1d1bbadecfd20ef862ab821cff572d5e01cdbba76f6e923e793`. Automated verification does not confer human, scientific or publication acceptance.

| Check | Result | Evidence |
| --- | --- | --- |
| python tests | passed | 1735 passed; one optional whole-archive test skipped, with original-on-demand access verified separately. |
| frontend tests | passed | 72 frontend tests passed on the current stable dependency stack. |
| browser tests | passed | 88 browser cases passed; two optional local-VLM journeys skipped because no server was running. CPU analysis and frozen selection exchange passed. |
| frontend build | passed | TypeScript and Vite production builds passed; approved-static documentation screenshots refreshed. |
| publication validation | passed | 202 catalogue guides; only the three approved packs and 300 original media files published. Archive privacy checks passed. |
| catalogue validation | passed | 202 resolved declared source identities and tested adapters. A cold workspace has zero local rows, 202 previews and 200 complete indices on request; two whole-source samplers remain distinct. |
| native index checks | passed | All 200 complete local indices returned exact declared counts and snapshot-bound native records; all 202 previews opened. |
| preview media checks | passed | 459 sampled asset checks: 458 successful originals and one explicitly declared source absence; 49 datasets have no media. No failed dataset checks. |
| distribution build | passed | Final wheel and source archive pass inspection and exact source-member parity; no model weights or private workspace data included. |
| clean install | passed | Final wheel installed outside the checkout on Python 3.12 and 3.14.10; 202-entry catalogue and approved samples served with no optional model packages. Fresh source startup passed. |
| portable sample bundle | passed | 29.31 MB checksummed ZIP; 300 original examples, standalone file verification and HTTP startup passed on Python 3.15.2, including hostile Host rejection. |
| acceptance traceability | passed | All 16 acceptance areas passed their named checks; zero traceability problems or recorded software gaps. |
| analysis runtime | passed | Nine local processors completed on 16 frozen native CLEVR records; exported analysis pack roundtrip passed. CPU detector/SigLIP browser runs and frozen selection reimport passed. Historical model evidence stays explicitly historical. |
| cold source preparation | passed | 13 seeded-source preparations preserve 115801 native records; four additional built-in HF routes plan at pinned revisions. New lazy image access preserves originals. A real private normal-activation and media HTTP check passed. |
| storage cleanup | passed | 3007758336 duplicate allocated bytes eliminated with all data/proof paths and hashes preserved. Eight obsolete local and six merged remote branches retired with verified Git-bundle recovery; no extra worktrees remain. |
| independent review | passed | Independent source, identity, resource-budget, frozen lookup, publication and final metadata reviews found no remaining actionable issue in the reviewed scope; this is engineering evidence, not human or scientific acceptance. |

[Coverage](dataset_coverage.csv) · [Pinned sources](catalogue-sources.json) · [Source and rights qualifications](limitations.md).
