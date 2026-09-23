# Acquisition status and remaining work

Updated 2026-09-23. The user authorized bounded public dataset/model acquisition in the tens of GB, without paid APIs or external model transmission. The previous session's 1 GB limit is superseded. This file distinguishes completed preparation from queued or unimplemented work.

## Completed and exercised

The nine new full populations in [selective-acquisition-20260923.md](selective-acquisition-20260923.md) are TextVQA, VizWiz, ChartQA, HatefulIllusion, OmniSpatial, PMC-VQA V1, Flowers-102, CUB-200-2011 and CIFAR-10-C. Their complete 100-record previews have passed actual image decoding through the workbench, including every image slot. See [preview-media-20260923.json](preview-media-20260923.json).

SocialCounterfactuals now has a 170,832-record index spanning all 61 pinned Parquet shards. Index construction fetched 6,132,809 bytes of metadata/annotation ranges from 27.22 GB of remote source shards. Images remain remote and are fetched within per-request limits. Three reproducible full-population samples from distinct shards passed actual image delivery; this does not assert that all 170,832 image payloads were fetched. See [remote-parquet-live.json](remote-parquet-live.json).

TweetEval has completed 200,785 rows across its native Parquet task configurations and splits. ClassLabel meanings are retained per shard, so an integer label is not assigned a universal meaning across tasks. MMStar completed its 1,500 records and COCO 2014 its 164,062 images with published annotations. Both 100-record previews passed actual image decoding.

## Further completed native preparations

Completed native indices cover the original LLaVA-Instruct-150K JSON (157,712 conversations), its separate FineVision representation, FGVC-Aircraft, COCO-QA, OK-VQA, HADES, VSR, Medical Multimodal Evaluation Data, and HallusionBench. These source populations completed and their preview images passed live checks; consult `reports/on-demand-preparation.json` and live preparation status for completed populations.

COCO-QA validates the alignment of its four native text files. OK-VQA joins questions and annotations by question ID and rejects missing, duplicate, orphan, or contradictory image joins. Original LLaVA conversations retain separate identities even when they share image IDs. VSR preserves random/zeroshot split memberships rather than claiming those overlapping configurations are unique examples.

HallusionBench's original Google Drive media link returned 404. The pinned LMMs-Lab-Encoder mirror reproduces all 1,129 original annotation rows field-for-field. Its image bytes are pinned by the mirror's shard SHA-256; equivalence to the unavailable original media archive is not established. See [hallusionbench-mirror-verification.json](hallusionbench-mirror-verification.json).

COCO 2014's recipe covers all 164,062 train/validation/test images and all published train/validation captions, instances and person keypoints. Test annotations remain absent, explicitly marked not released.

## Still incomplete

- Catalogue-wide coverage is unfinished. The exact current counts are generated in `reports/dataset_coverage.csv` and `reports/final-status.json`; many accessible native formats still need integration and verification.
- FineVision's approximately 4.65 TB of media and DataComp's approximately 340 GB of metadata are not copied wholesale. Remote Parquet support has real multi-shard evidence, but each source still needs its own layout, population, performance and media verification.
- Gated releases need authorized files or access. Never-published collections remain `not_applicable`; ambiguous variants retain their identity uncertainty. These are different from missing adapters.
- No new media publication approval is implied by local acquisition. Public packs remain restricted to the existing approved sources.

The three confirmed catalogue aliases from PR #3 remain `describable-textures-dataset` → `dtd`, `pets` → `oxfordpet`, and `okvqa` → `ok-vqa`. Family mentions are not automatically merged.

Additional native recipes with completed indices and live preview verification include all four MMBench v1
partitions (21,990 circular-evaluation rows), all author CausalGym splits (17,400
intervention pairs), RAVEL (6,828 entity inventories and 5,011 Wikipedia control prompts),
What's Up (all six native caption-comparison sets, 4,958 rows), Food-101, CIFAR-100-C,
and all EMNIST configurations plus its Letters subset. The two EMNIST plans reuse the
already cached original archive. MMBench's pinned mirror files match the authors'
evaluation-toolkit MD5s; the original HTTPS endpoint's certificate is expired.


PHANTOM is now locally authorized and indexed; it remains a gated source with explicitly
missing source-listed media. Caltech101, DreamBooth, GVIL, IllusoryVQA/IllusionMNIST,
Agent Security Bench, and HQH also have complete native annotation indices and live
preview receipts. Visual Genome completed its full eleven-table native index with
bounded disk-backed joins and 100 live preview images. T2I-CompBench also has all
17,861 native prompt-list memberships indexed. Its source QA/region join defects remain explicit.
