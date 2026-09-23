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
`remote-parquet-live.json`. FineVision's separate LLaVA representation completed 157,710 rows; the original LLaVA release has 157,712. Both are indexed separately and their previews passed live image checks.

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
- The latest recorded full Python suite passed 347 tests (one optional local-archive check skipped after deliberate source retirement), including native TSV, RAVEL,
  EMNIST and multi-archive preparation. All 22 frontend tests and all
  34 browser checks passed in one opt-in run, including real analysis and local image send.
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

## Further native populations and gated access

The next acquisition batch completed full native populations: original LLaVA (157,712),
its FineVision representation (157,710), Aircraft (10,000), COCO-QA (117,684), OK-VQA
(14,055), VSR (16,023 overlapping split/configuration memberships), Medical Multimodal
Evaluation Data (17,303), HallusionBench (1,129), MMBench (21,990 circular-evaluation
rows), CausalGym (17,400), RAVEL (11,839 native entity/control rows), What's Up (4,958),
Food-101 (101,000), CIFAR-100-C (950,000), EMNIST (2,255,710 configuration memberships)
and its Letters subset (145,600). HADES is indexed from its pinned native release.

Caltech101 has 9,144 images with 8,677 native object-outline annotations, including
native per-image quality values. Its 467 background images have no released object
outlines. DreamBooth retains all 158 reference images across 30 subjects and the native
class, prompt-template and attribution files. GVIL has 3,302 native VQA, visual-grounding
and raw-annotation records, with 1,600 explicitly joined evaluation pairs. IllusoryVQA
contains all 26,121 records across its eight native configurations; the separately
identified IllusionMNIST subset has 5,069. Targets differ by image condition; declared
no-illusion cases do not acquire fabricated counterparts.

Agent Security Bench retains 843 native input rows, including one explicitly labelled
raw HTML document committed by its authors under a JSONL filename. That malformed
source file is not counted as a functioning agent task. HQH retains all 4,000 questions,
joined to author image metadata and original Visual Genome archive members.

PHANTOM access was authorized by the user and verified using the existing local HF
credential. Its pinned native release contains 47,524 conversations in turn JSONL,
47,512 in grouped attack JSON, and 7,826 behaviours. The full index retains all 55,350
conversation/behaviour records and both native forms; the 747 native Child Safety
intents are also browsable as their own subset. 11,508 source-listed image paths are
absent from the pinned repository, affecting 2,031 records. Missing media remains
explicit, while 56,854 valid distinct image references are checksum-pinned for access
on demand. No adversarial prompt was executed, and no PHANTOM content was sent to a
model. The release remains gated, with no public redistribution approval.

Live preview receipts are `preview-media-batch2` through `preview-media-batch7-20260923.json`.
The first IllusoryVQA audit and three batch-2 checks were interrupted by a workbench
restart; the subsequent retry receipts preserve that history. MMBench initially exposed
an API error for opaque TSV asset identifiers; the route was fixed and all 100 preview
images subsequently passed. `native-diversity-media-20260923.json` records additional
full-population configuration probes when completed; it does not assert that every
image payload has been downloaded.

Local source objects can now be registered by SHA-256 and reused independently of the
evictable download cache. This prevented large retained originals from being downloaded
again when a smaller preparation evicted their cache entries. Nested TAR members in the
original Caltech ZIP are repacked into bounded, checksummed member-addressable derivatives.


Visual Genome completed 116,367 records: 108,077 images with all eleven source annotation
tables, plus 8,290 orphan QA-region mapping records. 131,261 mappings lacked a released QA;
those with a released region still join through that region. 55,989 lacked a released
region; those with a released QA still join through that QA. The 8,290 with neither are
retained without an invented image. All 19,561 paragraph rows survive, including ten
repeated image IDs. The streaming join used a bounded SQLite derivative, included in the
output budget and receipt. Its 100 preview images passed on the updated workbench;
the first pre-restart attempt hit the old server's missing adapter dispatch and is
retained separately. T2I-CompBench retains all 17,861 native text-list memberships,
including overlapping lists and its explicitly named object vocabulary.


HOD completed all 10,631 native images with original CSV metadata, YOLO annotations,
XML annotations, category/difficulty and reference URLs. Its all/ and class/ copies
match for all 31,893 image/annotation Git-blob pairs and are represented once per native
metadata image; alternate paths remain in the records. All 100 preview images passed.
Aircraft's updated source scope now explicitly states that the official 2013b archive
omits images_size.txt; source_size is null and original boxes remain unchanged. The
corrected immutable version and its 100 preview images passed after increasing the
bounded repack output allowance to 5 GB.

## Native perceptual, restoration and paired-question releases

The next implementation batch preserves native variant relationships instead of
flattening them into unrelated images:

- BAPPS: 197,344 judgement records (151,400 2AFC train, 36,344 2AFC validation,
  9,600 JND validation), with 582,432 original patches. Fractional human judgements,
  reference/p0/p1 roles and all eleven native distortion/task groups remain distinct.
  The files named `.tar.gz` are uncompressed TARs; their original hashes are recorded.
- MME: 2,374 original yes/no questions, with the 2,114-question perception component
  also available under its existing catalogue entry. Native question pairs share
  their original image identity without sharing record identity.
- MM-SafetyBench: 1,680 annotated questions with SD, SD_TYPO and TYPO image conditions,
  plus five native image groups without released questions. All 5,055 images survive
  in 1,685 records. Condition-specific questions remain source data; none were run.
- Set5 and Set14: all 114 files in the pinned SelfExSR benchmark representation,
  grouped into five and fourteen image identities. Scale-specific HR crops and LR
  images are separate assets. Byte equivalence to the first historical distribution
  is not established and is not claimed.

All preview images for those five catalogue sources plus the MME perception entry
passed live decoding. BAPPS, MME and MM-SafetyBench also have deterministic probes
covering every native task/category/scenario, including unannotated image groups.
Receipts: `preview-media-batch11-20260923.json`, `preview-media-batch12-20260923.json`,
`preview-media-batch13-20260923.json` and `native-diversity-media-batch2-20260923.json`.
Batch 13 completed Set5, Set14 and DIV2K. CINIC-10 and SUN397 subsequently completed in their separate native preview receipts.

DIV2K's 900 published train/validation identities have a complete index over all 22
author ZIPs. Training preserves all four wild realizations (14 total HR/LR assets
per image); validation has one wild realization (11 assets per image). Test HR
images are not published at the author download page. Remote archive consistency
uses strong ETags and member CRCs; full archive SHA-256 was not computed. All 1,400 original preview image variants passed live decoding in the batch-13 receipt.

Repeated local ZIP reads now reuse verified directory metadata. Remote ZIP reads
coalesce adjacent local-header and small-payload requests into bounded 64 KiB ranges.
This changes request overhead without changing original asset bytes or identities.
Focused inspection names native conditions and roles, and labels an image-specific
question separately from the record question. The complete browser suite passed
34 checks, including real local analysis and image transmission to the local VLM.


## Original-quality previews and bounded storage

SUN397 now has all 108,754 images and ten native evaluation-fold memberships indexed;
its 100 sampled previews preserve the original JPEG bytes. CINIC-10 has all 270,000
native train/valid/test images, with CIFAR/ImageNet origin identifiers retained.
NRC-VAD has 74,772 versioned terms across v1 and v2.1, including native translations
and scale exports; its noncommercial license does not authorize public redistribution.
Each has a native source audit and completed live preview receipt.

The storage pass now fits within the requested 50–150 GB range, including configured
model weights and the current vLLM compilation cache. The exact, timestamped footprint
is `storage-footprint-retained-20260923.json`; 100 GB remains the target.
SHA-verified duplicate acquired copies were hard-linked, unused versions were pruned,
and verified native ZIP/TAR access replaced large retained archives. VQA v2 and POPE
were retired together because they share COCO val2014 media. Frozen snapshots remain.

Aircraft's 10,000 images have 9,900 AVIF copies and 100 byte-exact preview originals.
GQA's complete validation-balanced image population has 10,234 distinct images,
including 82 distinct originals serving its existing 100-record preview. Other large
populations retain partial bulk conversions plus original preview pins; remaining
images are compressed on inspection through a shared bounded cache. They are not
claimed to be completely transcoded offline. Model inputs always resolve originals.

`retained-media-live-verification.json` verifies all 582 distinct preview images
across GQA, SUN397, complete CLEVR, VQA v2, POPE and DOCCI after original retirement,
plus 18 late-population original/display pairs. One SUN397 source image retained its
original representation because AVIF conversion was unsuitable. Native ZIP/TAR cold
range probes and VHD image/video after-retirement checks have separate receipts.
`docs/storage.md` documents bounded encoding, original retrieval, retirement checks,
shared preparation admission and the limits of application-level quota enforcement.
