# Full populations and selective original media — 2026-09-23

This is implementation and live verification evidence, not a completed v1 declaration.
The current moving totals are generated in `on-demand-preparation.json` and
`dataset_coverage.csv`. Dataset revisions and paper-used subsets remain separate.

## Completed populations in this batch

| Dataset | Indexed records | Exact scope |
| --- | ---: | --- |
| TextVQA | 45,336 | Original 0.5.1 train, validation and test questions; test answers absent in that source |
| VizWiz VQA | 32,842 | Original train/validation and 8,000 test questions with the authors' April 2026 public test-answer release |
| ChartQA | 32,719 | Author first-version human and augmented questions across train/validation/test; bounding-box variant separate |
| HatefulIllusion | 2,160 | Digits, hate slangs and hate symbols; illusion and condition images preserved |
| OmniSpatial | 8,431 | Official full archive, with category-scoped question IDs and original options/answers |
| PMC-VQA | 228,948 | V1 train/test plus a separately identified 2,000-row `test_clean` evaluation subset; noncompound V2 separate |
| Flowers-102 | 8,189 | All original class IDs and train/validation/test membership |
| CUB-200-2011 | 11,788 | Original train/test, classes, boxes, 15 parts and 312 attributes per image |
| CIFAR-10-C | 950,000 | All 19 corruption types, five severities and original test labels |
| SocialCounterfactuals | 170,832 | All 61 pinned source shards; full annotations indexed through bounded ranges |
| TweetEval | 200,785 | Native task configurations and train/validation/test partitions; per-shard class meanings preserved |
| MMStar | 1,500 | Original author release, image and question records |
| COCO 2014 | 164,062 | All train/validation/test images; all published captions, instances and person keypoints; test annotations absent |

Recipes pin the annotation/source checksums. ZIP-hosted images remain in their original
archives and are fetched on inspection through strict HTTPS ranges. Every annotation
reference is checked against the archive directory before activation. Individual
ChartQA/HatefulIllusion images are checked against a pinned Git-blob/SHA-256 inventory.
Strong ETags bind range consistency; they are **not** a claim that a full remote ZIP was
downloaded and SHA-256 checked. Original image bytes get their own SHA-256 on retrieval.
No new media is approved for public redistribution by this work.

Primary sources: [TextVQA](https://textvqa.org/),
[VizWiz](https://vizwiz.org/tasks-and-datasets/vqa/),
[ChartQA](https://github.com/vis-nlp/ChartQA),
[HatefulIllusion](https://huggingface.co/datasets/yiting/HatefulIllusion_Dataset),
[OmniSpatial](https://huggingface.co/datasets/qizekun/OmniSpatial),
[PMC-VQA](https://huggingface.co/datasets/xmcmic/PMC-VQA),
[Flowers](https://www.robots.ox.ac.uk/~vgg/data/flowers/102/),
[CUB](https://data.caltech.edu/records/65de6-vp158),
[CIFAR-C](https://zenodo.org/records/2535967).

The Caltech file endpoint returned Cloudflare error 1010 from this host. The CUB archive
was acquired from a pinned mirror and verified against Caltech's published MD5 plus the
mirror's SHA-256. Exact mirror revision and URL are in the recipe. This does not merge
ambiguous `cub`/`cub200` mentions with the known CUB-200-2011 release.

## Selective Parquet indexing

A new preparation mode indexes all annotation columns across a pinned repository's native
Parquet shards while deferring embedded image bytes. The original shard sizes are shown
separately from the approved transfer upper bound. Only the bounded range cache and
prepared output need local disk. Row-group media reads have transfer and decoded-size
caps; unsupported layouts or missing bytes are explicit errors. Source-provided full-file
SHA-256 values remain provenance, not locally verified hashes of unread bytes.

SocialCounterfactuals completed all 170,832 records across 61 shards, fetching 6,132,809
metadata/annotation bytes from 27.22 GB of remote shards. All 100 preview images and three
reproducible full-population images from distinct shards passed decoding. See
`remote-parquet-live.json`. FineVision's separate LLaVA representation is still indexing
at this checkpoint; a ready plan or test fixture is not real dataset coverage.

Small Parquet columns are coalesced only when their byte intervals touch; image columns
are excluded from metadata prefetch. The 1,000-row real-shard benchmark used 948,782 fetched
bytes in 13.97 seconds; it is a mixed-cache measurement, not a cold whole-release benchmark.
See `remote-metadata-benchmark.json`.

## Checks and fixes

- Original-image API checks beyond previews: `selective-media-live.json`,
  `native-vision-live.json`; train/validation/test TextVQA and VizWiz checks retained in
  `vqa-live-verification.json`.
- A full decode/hash check of the new 100-record previews writes its completed dataset
  results incrementally to `preview-media-20260923.json`; unfinished entries are omitted.
- The rebuilt model panel sent an approved COCO image to the local vLLM instance and saved
  the response and context digest. The linked selection survived export/import. Fresh
  detector and embedding browser runs passed. Receipts: `browser-linked-journey.json` and
  `browser-analysis-journey.json`. This validates routing, not answer accuracy.
- The latest recorded full Python suite passed 292 tests, including native TSV, RAVEL,
  EMNIST and multi-archive preparation. All 22 frontend tests and all
  30 browser checks passed in one opt-in run, including real analysis and local image send.
- Browsing now explicitly chooses result snapshots instead of attaching every historical
  run. A 40-run regression verifies that source browsing works, older results remain
  selectable, and the 32-run query bound stays enforced.
- LM Studio's actual headless server passed original-image and text conversations. Empty
  or truncated provider outputs are now saved as errors, including finish-reason evidence;
  failed evaluations remain pending. See `lmstudio-live-verification.json`.
- Catalogue thumbnails now follow active prepared versions, including datasets that never
  had a legacy preview directory. Source/access/publication reviews remain registry-owned.
- Pruning traces retained versions' source dependencies transitively, keeps running
  preparations and avoids double-counting hard-linked files.
- Native TAR datasets can be copied losslessly to a derived stored ZIP within the approved
  output budget, so late-image inspection does not decompress the full archive repeatedly.

No sub-agents, paid APIs, external model transmission, or writes to corpus originals were
used. The local source/model downloads were bounded; the application remains incomplete
until accessible catalogue-wide acquisition and exact release reconciliation are finished.
