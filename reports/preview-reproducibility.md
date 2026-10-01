# Preview reproducibility from an empty workspace

Generated 2026-10-01 at commit `76b9d3c`. A colleague's workspace holds only the shipped catalogue; this reports what `atlas previews fetch` can obtain from each dataset's own publisher. Planning reads source metadata only (per-dataset budget 10.0 GB); it downloads nothing.

**42 verified from scratch · 92 more fetchable · 1 need a larger budget · 3 gated · 195 with no acquisition path yet · 0 other** of 333 catalogue entries.

The maintainer's workspace holds 169 previews; 131 of them can be reproduced from the catalogue alone. The rest need a recipe (see below). A "verified" dataset was fetched in an empty workspace, produced a 100-record preview and complete index, and (where the catalogue pins one) carries the maintainer's snapshot ID.

## Verified from scratch (42)

Fetched from an empty workspace and checked.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `advbench` | yes | 0 B | 520 records indexed, 0 B fetched, 2026-10-01 |
| `artbench` | yes | 183.9 MB | 60,000 records indexed, 183.9 MB fetched, 2026-10-01 |
| `bias-in-bios` | yes | 99.8 MB | 396,189 records indexed, 99.8 MB fetched, 2026-10-01 |
| `cifar-10` | yes | 170.1 MB | 60,000 records indexed, 170.1 MB fetched, 2026-10-01 |
| `cifar-100` | yes | 168.5 MB | 60,000 records indexed, 168.5 MB fetched, 2026-10-01 |
| `clevr` | yes | 0 B | 1,070 records indexed, 0 B fetched, 2026-10-01 |
| `coco` | yes | 1.1 GB | 25,014 records indexed, 1.1 GB fetched, 2026-10-01 |
| `coco-one` | yes | 20.2 MB | 2,247 records indexed, 182.8 KB fetched, 2026-10-01 |
| `coco-two` | yes | 20.0 MB | 440 records indexed, 42.8 KB fetched, 2026-10-01 |
| `conceptarc` | yes | 147.4 KB | 176 records indexed, 147.4 KB fetched, 2026-10-01 |
| `controlled-clevr` | yes | 65.9 MB | 408 records indexed, 65.9 MB fetched, 2026-10-01 |
| `controlled-images` | yes | 95.2 MB | 412 records indexed, 95.2 MB fetched, 2026-10-01 |
| `custom-propeller-and-rotating-snake-stimuli` | yes | 33.2 MB | 7 records indexed, 33.2 MB fetched, 2026-10-01 |
| `eurosat` | yes | 94.7 MB | 27,000 records indexed, 94.7 MB fetched, 2026-10-01 |
| `figure-linked-source-data-spreadsheets` | yes | 78.8 KB | 7 records indexed, 78.8 KB fetched, 2026-10-01 |
| `find` | yes | 2.7 MB | 2,275 records indexed, 2.7 MB fetched, 2026-10-01 |
| `harmbench` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `idenprof` | yes | 154.7 MB | 11,000 records indexed, 154.7 MB fetched, 2026-10-01 |
| `imagenet-sketch` | yes | 20.0 MB | 50,889 records indexed, 0 B fetched, 2026-10-01 |
| `imagenette` | yes | 99.0 MB | 13,394 records indexed, 99.0 MB fetched, 2026-10-01 |
| `jiechieu-tsopze-resume-corpus` | yes | 169.2 MB | 29,783 records indexed, 169.2 MB fetched, 2026-10-01 |
| `mathvision` | yes | 63.9 MB | 3,344 records indexed, 63.9 MB fetched, 2026-10-01 |
| `mnist` | yes | 11.6 MB | 70,000 records indexed, 11.6 MB fetched, 2026-10-01 |
| `nocaps` | yes | 9.2 MB | 15,100 records indexed, 9.2 MB fetched, 2026-10-01 |
| `nrc-vad` | yes | 51.0 MB | 74,772 records indexed, 51.0 MB fetched, 2026-10-01 |
| `pairs` | yes | 19.1 MB | 200 records indexed, 19.1 MB fetched, 2026-10-01 |
| `realtoxicityprompts` | yes | 0 B | 99,442 records indexed, 0 B fetched, 2026-10-01 |
| `rsicd` | yes | 17.5 MB | 10,921 records indexed, 12.5 MB fetched, 2026-10-01 |
| `sad` | yes | 15.5 MB | 127,176 records indexed, 15.5 MB fetched, 2026-10-01 |
| `sbbench-synthetic-gender-crop-false` | yes | 237.0 MB | 206 records indexed, 237.0 MB fetched, 2026-10-01 |
| `seed-bench-2` | yes | 68.1 MB | 24,371 records indexed, 18.1 MB fetched, 2026-10-01 |
| `seedbench` | yes | 57.2 MB | 17,990 records indexed, 7.2 MB fetched, 2026-10-01 |
| `shapes-localization` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `shapes-recognition` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `shapes-relations` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `textvqa-x` | yes | 80.5 MB | 18,096 records indexed, 60.5 MB fetched, 2026-10-01 |
| `turing-eye-test` | yes | 171.5 MB | 490 records indexed, 171.5 MB fetched, 2026-10-01 |
| `vg-qa-one` | yes | 679.8 MB | 1,160 records indexed, 679.8 MB fetched, 2026-10-01 |
| `vg-qa-two` | yes | 679.8 MB | 288 records indexed, 679.8 MB fetched, 2026-10-01 |
| `vibeeval` | yes | 205.3 MB | 269 records indexed, 205.3 MB fetched, 2026-10-01 |
| `visualpuzzle` | yes | 142.7 MB | 1,168 records indexed, 142.7 MB fetched, 2026-10-01 |
| `wmdp` | yes | 1.1 MB | 3,668 records indexed, 1.1 MB fetched, 2026-10-01 |

## Fetchable, not yet verified (92)

A source plan is ready within the budget; not yet fetched from an empty workspace.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `agent-security-bench` | yes | 441.3 KB | 441.3 KB · http_archive |
| `algopuzzlevqa` | yes | 226.8 MB | 226.8 MB · huggingface_columnar |
| `bapps` | yes | 7.7 GB | 7.7 GB · http_archive |
| `blink` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `caltech101` | yes | 137.4 MB | 137.4 MB · http_archive |
| `cauldron` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `causalgym` | yes | 8.3 MB | 8.3 MB · http_archive |
| `chartqa` | yes | 4.6 MB | 4.6 MB · http_archive |
| `child-safety-intents` | yes | 8.8 MB | 8.8 MB · http_archive |
| `cifar-10-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cifar-100-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cinic-10` | yes | 687.5 MB | 687.5 MB · http_archive |
| `coco-2014` | yes | 293.6 MB | 293.6 MB · http_archive |
| `coco-qa` | yes | 31.9 MB | 31.9 MB · http_archive |
| `counterfact` | yes | 45.1 MB | 45.1 MB · http_archive |
| `covid-19-radiography` | yes | 816.0 MB | 816.0 MB · http_archive |
| `cub-200-2011` | yes | 1.2 GB | 1.2 GB · http_archive |
| `datacomp-1b` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `div2k` | yes | 5.0 MB | 5.0 MB · local |
| `dreambooth` | yes | 112.1 MB | 112.1 MB · http_archive |
| `dtd` | yes | 625.2 MB | 625.2 MB · http_archive |
| `emnist` | yes | 561.8 MB | 561.8 MB · http_archive |
| `emnist-letters` | yes | 561.8 MB | 561.8 MB · http_archive |
| `exams-v` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `fairface` | yes | 2.7 GB | 2.7 GB · http_archive |
| `fgvc-aircraft` | yes | 2.8 GB | 2.8 GB · http_archive |
| `finevision` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `flowers102` | yes | 344.9 MB | 344.9 MB · http_archive |
| `foil-it` | yes | 171.6 MB | 171.6 MB · http_archive |
| `food101` | yes | 5.0 GB | 5.0 GB · http_archive |
| `gvil-paired-illusion-images` | yes | 26.7 MB | 26.7 MB · http_archive |
| `hades` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `hallusionbench` | yes | 146.6 MB | 146.6 MB · huggingface_columnar |
| `hatefulillusion` | yes | 530.7 KB | 530.7 KB · http_archive |
| `high-quality-hallucination-benchmark` | yes | 38.4 MB | 38.4 MB · http_archive |
| `hod` | yes | 1.2 GB | 1.2 GB · http_archive |
| `iconqa` | yes | 1.9 GB | 1.9 GB · http_archive |
| `illuchar` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `illusionmnist` | yes | 433.0 KB | 433.0 KB · http_archive |
| `illusoryvqa` | yes | 2.5 MB | 2.5 MB · http_archive |
| `imagenet-a` | yes | 687.6 MB | 687.6 MB · http_archive |
| `imagenet-r` | yes | 2.2 GB | 2.2 GB · http_archive |
| `imagenet-v2` | yes | 1.3 GB | 1.3 GB · http_archive |
| `llava-instruct-150k` | yes | 248.9 MB | 248.9 MB · http_archive |
| `llava-instruct-150k-3a74a703` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `medical-multimodal-evaluation-data` | yes | 26.0 MB | 26.0 MB · http_archive |
| `mllmu-bench` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `mm-safetybench` | yes | 499.5 MB | 499.5 MB · http_archive |
| `mmbench` | yes | 180.9 MB | 180.9 MB · http_archive |
| `mme` | yes | 199.8 MB | 199.8 MB · http_archive |
| `mme-perception` | yes | 199.8 MB | 199.8 MB · http_archive |
| `mmmu-dev` | yes | 57.0 MB | 57.0 MB · huggingface_columnar |
| `mmstar` | yes | 41.8 MB | 41.8 MB · huggingface_columnar |
| `naturalbench` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `objectnet` | yes | 1.6 GB | up to 1.6 GB · local |
| `ok-vqa` | yes | 31.4 MB | 31.4 MB · http_archive |
| `omnispatial` | yes | 30.0 MB | 30.0 MB · local |
| `oxfordpet` | yes | 811.1 MB | 811.1 MB · http_archive |
| `phantom` | yes | 145.0 MB | 145.0 MB · http_archive |
| `phase` | yes | 2.6 GB | 2.6 GB · http_archive |
| `pmc-vqa` | yes | 99.2 MB | 99.2 MB · http_archive |
| `puzzlevqa` | yes | 61.7 MB | 61.7 MB · huggingface_columnar |
| `ravel` | yes | 429.3 KB | 429.3 KB · http_archive |
| `realworldqa` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `recap-datacomp-1b` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `roco` | yes | 13.6 MB | 13.6 MB · http_archive |
| `safebench` | yes | 4.7 GB | 4.7 GB · http_archive |
| `sbbench-syn` | yes | 10.0 GB | up to 10.0 GB · local |
| `sbbench-syn-crop` | yes | 10.0 GB | up to 10.0 GB · local |
| `sbbench-synthetic-age-crop-false` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `sbbench-synthetic-age-crop-true` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `sbbench-synthetic-gender-crop-true` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `scienceqa-img` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `senator-tweets-2021` | yes | 232.5 MB | 232.5 MB · huggingface_columnar |
| `set14` | yes | 0 B | 0 B · local |
| `set5` | yes | 0 B | 0 B · local |
| `simplevqa` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `smolim2-135m-10b` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `socialcounterfactuals` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `space-10` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `t2i-compbench` | yes | 850.7 KB | 850.7 KB · http_archive |
| `textvqa` | yes | 47.5 MB | 47.5 MB · http_archive |
| `tweeteval` | yes | 14.2 MB | 14.2 MB · huggingface_columnar |
| `visual-counterfact` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `visual-genome` | yes | 889.8 MB | 889.8 MB · http_archive |
| `visual6502-transistor-netlist` | yes | 265.3 KB | 265.3 KB · http_archive |
| `vizwiz` | yes | 29.9 MB | 29.9 MB · http_archive |
| `vqa-constraints` | yes | 4.1 GB | 4.1 GB · http_archive |
| `vqa-v2-m-n-subsets` | yes | 2.1 MB | 2.1 MB · http_archive |
| `vsr` | yes | 35.0 MB | 35.0 MB · http_archive |
| `waterbirds` | yes | 489.7 MB | 489.7 MB · http_archive |
| `what-s-up` | yes | 861.2 MB | 861.2 MB · http_archive |

## Needs a larger download budget (1)

Fetchable, but the source is larger than the per-dataset budget used here.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `sun397` | yes | 39.1 GB | Source download exceeds the selected download budget. |

## Gated at the source (3)

Source requires an account, agreement or approval; Atlas does not bypass it.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `visu` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |
| `visu-text` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |
| `winoground` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |

## No acquisition path yet (195)

No pinned acquisition recipe or adapter yet: an implementation gap, not a source restriction.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `activations-csv` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `alpaca` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `anthropic-red-teaming-prompts` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `artbench-2` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `artchive` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `asteroids-rom` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `audioset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `bam-fg` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `bbq` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `behonest` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `brain-score` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `brca` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `broden` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cc3m` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cebab` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `celeba` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `chicago-face-database` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cifar-10-1` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cifar-2` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `clevr-v1-full` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-caption` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-demographic-annotations` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-detection-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-gender` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-spatial` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `coco-train` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cocogender` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cocogendertxt` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `concept-editing-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `conceptual-captions` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `contrastive-prompts` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cub` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `cub200` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `custom-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `custom-image-editing-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `custom-neonatal-rat-ganglion-recordings` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `custom-speech-segment-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `custom-ternus-psychophysics-responses` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `dall-e-generated-target-images` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `deepfashion` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `docci` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `docvqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `donkey-kong-rom` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `e-ic` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `e-vqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `emnist-balanced` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `emoset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `facet` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `facial-expression-recognition-2013` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `factoid` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `fer-2013` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ffhq` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `fgvc` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `first-person-social-interactions-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `flickr30k` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `flowers` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gaussian-rubbish-examples` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gda-adversarial-image-variants` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `glue-cola` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `google-web-1t-corpus` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gpt-4v-filtered-vl-gender-subset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gqa` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `group-labels` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gvil` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `gyafc` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `halueval` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `hc-bench` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `hellaswag-pro` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ictcf` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `illusionbench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `illusionbench-3c643c29` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `illusionvqa` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `illusory-vqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-1k` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-c` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-ilsvrc` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-ilsvrc-2012` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-sampled-1-000-images` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet-segmentation` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenet100` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `imagenetval` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `inaturalist` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `interpbench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `itac` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `jailbreakv-28k` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `laion` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `laion-400m` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `laion-aesthetics` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `language-identification-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `lingoqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `llava-bench` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `maliciousinstruct` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `miap` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `middlebury` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mit-adobe-5k` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mit-states` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mm-vet` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mma-diffusion` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mmbench-en-dev` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mrpc` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ms-coco` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ms-coco-7f846b38` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ms-coco-captions` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ms-cxr` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mscoco` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mscoco-100-target-subset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `multitrust` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `mvbench-scene-qa` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `nips17` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `oasis` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `objaverse` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `omnisafebench-mm` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `openimages` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ostris-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `pairs-csv` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-08e415961919a492-unnamed-11-image-inpainting-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-08e415961919a492-unnamed-real-noise-benchmark-46` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-164d7c221452ffec-unnamed-cfd-morph-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-1e2474b15fec2d7d-unnamed-controversial-stimuli-collection` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-6a7364738bac9f07-unnamed-online-illusion-repositories` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-728d8c0964b540ad-unnamed-youtube-image-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-765a2362f8735bc4-unnamed-social-category-question-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-944952997d24ce45-unnamed-vma-candidate-pool` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `pascal-voc` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `pata` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `perturbed-gender-benchmark-image-variants` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `pitfall-rom` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `places` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `pope` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `qnli` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `qqp` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `raise1k` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `restricted-imagenet` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ring-a-bell` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `robustbench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `rosmap` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `rs-vqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `saegis-clean-and-adversarial-splits` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `sb-syn` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `sb-syn-crop` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `sbbench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `scrambled-mnist` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `shapeworld` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `shiftmnist` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `simulated-transistor-traces` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `snli-ve` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `sorrybench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `space-invaders-rom` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `spoken-wikipedia` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `sst2` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `stanford-cars` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `stl-10` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `svhn` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `svo-probes` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `tdc2023` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `the-pile` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `tid2013` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `timit` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `top16-images-csv` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `ucf101` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vhd11k` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `via-bench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `visual-counterfact-filtered-467` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `visualqa` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vizwiz-priv` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vl-gender` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vlagenderbias` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vqa-v2` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `vtab` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `wall-street-journal` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `whoops` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `wilds` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `wnli` | yes | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |
| `zerobench` | no | 0 B | A pinned acquisition recipe or authorized local source is required for this release. |

