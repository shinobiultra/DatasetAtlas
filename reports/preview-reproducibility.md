# Preview reproducibility from an empty workspace

Generated 2026-10-01 at commit `3b64daf`. A colleague's workspace holds only the shipped catalogue; this reports what `atlas previews fetch` can obtain from each dataset's own publisher. Planning reads source metadata only (per-dataset budget 10.0 GB); it downloads nothing.

**108 verified from scratch · 44 more fetchable · 1 need a larger budget · 26 gated · 137 with no acquisition path yet · 0 other** of 333 catalogue entries.

The maintainer's workspace holds 170 previews; 150 of them can be reproduced from the catalogue alone. The rest need a recipe (see below). A "verified" dataset was fetched in an empty workspace, produced a 100-record preview and complete index, and (where the catalogue pins one) carries the maintainer's snapshot ID.

## Verified from scratch (108)

Fetched from an empty workspace and checked.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `advbench` | yes | 0 B | 520 records indexed, 0 B fetched, 2026-10-01 |
| `agent-security-bench` | yes | 441.3 KB | 843 records indexed, 441.3 KB fetched, 2026-10-01 |
| `algopuzzlevqa` | yes | 226.8 MB | 1,800 records indexed, 226.8 MB fetched, 2026-10-01 |
| `alpaca` | yes | 22.8 MB | 52,002 records indexed, 22.8 MB fetched, 2026-10-01 |
| `anthropic-red-teaming-prompts` | yes | 15.5 MB | 38,961 records indexed, 15.5 MB fetched, 2026-10-01 |
| `artbench` | yes | 183.9 MB | 60,000 records indexed, 183.9 MB fetched, 2026-10-01 |
| `bbq` | yes | 50.9 MB | 58,492 records indexed, 50.9 MB fetched, 2026-10-01 |
| `behonest` | yes | 5.3 MB | 19,059 records indexed, 5.3 MB fetched, 2026-10-01 |
| `bias-in-bios` | yes | 99.8 MB | 396,189 records indexed, 99.8 MB fetched, 2026-10-01 |
| `caltech101` | yes | 137.4 MB | 9,144 records indexed, 137.4 MB fetched, 2026-10-01 |
| `causalgym` | yes | 8.3 MB | 17,400 records indexed, 8.3 MB fetched, 2026-10-01 |
| `cebab` | yes | 2.2 MB | 18,600 records indexed, 2.2 MB fetched, 2026-10-01 |
| `chartqa` | yes | 4.6 MB | 32,719 records indexed, 4.6 MB fetched, 2026-10-01 |
| `child-safety-intents` | yes | 8.8 MB | 747 records indexed, 8.8 MB fetched, 2026-10-01 |
| `cifar-10` | yes | 170.1 MB | 60,000 records indexed, 170.1 MB fetched, 2026-10-01 |
| `cifar-100` | yes | 168.5 MB | 60,000 records indexed, 168.5 MB fetched, 2026-10-01 |
| `clevr` | yes | 0 B | 1,070 records indexed, 0 B fetched, 2026-10-01 |
| `clevr-v1-full` | yes | 400.0 MB | 999,968 records indexed, 0 B fetched, 2026-10-01 |
| `coco` | yes | 1.1 GB | 25,014 records indexed, 1.1 GB fetched, 2026-10-01 |
| `coco-2014` | yes | 293.6 MB | 164,062 records indexed, 253.6 MB fetched, 2026-10-01 |
| `coco-one` | yes | 20.2 MB | 2,247 records indexed, 182.8 KB fetched, 2026-10-01 |
| `coco-qa` | yes | 31.9 MB | 117,684 records indexed, 1.9 MB fetched, 2026-10-01 |
| `coco-two` | yes | 20.0 MB | 440 records indexed, 42.8 KB fetched, 2026-10-01 |
| `conceptarc` | yes | 147.4 KB | 176 records indexed, 147.4 KB fetched, 2026-10-01 |
| `controlled-clevr` | yes | 65.9 MB | 408 records indexed, 65.9 MB fetched, 2026-10-01 |
| `controlled-images` | yes | 95.2 MB | 412 records indexed, 95.2 MB fetched, 2026-10-01 |
| `counterfact` | yes | 45.1 MB | 21,919 records indexed, 45.1 MB fetched, 2026-10-01 |
| `custom-propeller-and-rotating-snake-stimuli` | yes | 33.2 MB | 7 records indexed, 33.2 MB fetched, 2026-10-01 |
| `div2k` | yes | 5.0 MB | 900 records indexed, 0 B fetched, 2026-10-01 |
| `dreambooth` | yes | 112.1 MB | 158 records indexed, 112.1 MB fetched, 2026-10-01 |
| `dtd` | yes | 625.2 MB | 5,640 records indexed, 625.2 MB fetched, 2026-10-01 |
| `emnist` | yes | 561.8 MB | 2,255,710 records indexed, 561.8 MB fetched, 2026-10-01 |
| `emnist-letters` | yes | 561.8 MB | 145,600 records indexed, 561.8 MB fetched, 2026-10-01 |
| `eurosat` | yes | 94.7 MB | 27,000 records indexed, 94.7 MB fetched, 2026-10-01 |
| `figure-linked-source-data-spreadsheets` | yes | 78.8 KB | 7 records indexed, 78.8 KB fetched, 2026-10-01 |
| `find` | yes | 2.7 MB | 2,275 records indexed, 2.7 MB fetched, 2026-10-01 |
| `flowers102` | yes | 344.9 MB | 8,189 records indexed, 344.9 MB fetched, 2026-10-01 |
| `foil-it` | yes | 171.6 MB | 594,536 records indexed, 131.6 MB fetched, 2026-10-01 |
| `glue-cola` | yes | 377.0 KB | 10,657 records indexed, 377.0 KB fetched, 2026-10-01 |
| `gqa` | yes | 300.0 MB | 132,062 records indexed, 0 B fetched, 2026-10-01 |
| `gvil-paired-illusion-images` | yes | 26.7 MB | 3,302 records indexed, 26.7 MB fetched, 2026-10-01 |
| `hallusionbench` | yes | 146.6 MB | 1,129 records indexed, 146.6 MB fetched, 2026-10-01 |
| `halueval` | yes | 63.4 MB | 34,507 records indexed, 63.4 MB fetched, 2026-10-01 |
| `harmbench` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `hatefulillusion` | yes | 530.7 KB | 2,160 records indexed, 530.7 KB fetched, 2026-10-01 |
| `high-quality-hallucination-benchmark` | yes | 38.4 MB | 4,000 records indexed, 8.4 MB fetched, 2026-10-01 |
| `idenprof` | yes | 154.7 MB | 11,000 records indexed, 154.7 MB fetched, 2026-10-01 |
| `illusionmnist` | yes | 433.0 KB | 5,069 records indexed, 433.0 KB fetched, 2026-10-01 |
| `illusoryvqa` | yes | 2.5 MB | 26,121 records indexed, 2.5 MB fetched, 2026-10-01 |
| `imagenet-sketch` | yes | 20.0 MB | 50,889 records indexed, 0 B fetched, 2026-10-01 |
| `imagenette` | yes | 99.0 MB | 13,394 records indexed, 99.0 MB fetched, 2026-10-01 |
| `jiechieu-tsopze-resume-corpus` | yes | 169.2 MB | 29,783 records indexed, 169.2 MB fetched, 2026-10-01 |
| `llava-instruct-150k` | yes | 248.9 MB | 157,712 records indexed, 228.9 MB fetched, 2026-10-01 |
| `maliciousinstruct` | yes | 6.3 KB | 100 records indexed, 6.3 KB fetched, 2026-10-01 |
| `mathvision` | yes | 63.9 MB | 3,344 records indexed, 63.9 MB fetched, 2026-10-01 |
| `medical-multimodal-evaluation-data` | yes | 26.0 MB | 17,303 records indexed, 6.0 MB fetched, 2026-10-01 |
| `mm-safetybench` | yes | 499.5 MB | 1,685 records indexed, 499.5 MB fetched, 2026-10-01 |
| `mmbench` | yes | 180.9 MB | 21,990 records indexed, 180.9 MB fetched, 2026-10-01 |
| `mme` | yes | 199.8 MB | 2,374 records indexed, 199.8 MB fetched, 2026-10-01 |
| `mme-perception` | yes | 199.8 MB | 2,114 records indexed, 199.8 MB fetched, 2026-10-01 |
| `mmmu-dev` | yes | 57.0 MB | 150 records indexed, 57.0 MB fetched, 2026-10-01 |
| `mmstar` | yes | 41.8 MB | 1,500 records indexed, 41.8 MB fetched, 2026-10-01 |
| `mnist` | yes | 11.6 MB | 70,000 records indexed, 11.6 MB fetched, 2026-10-01 |
| `mrpc` | yes | 1.5 MB | 5,801 records indexed, 1.5 MB fetched, 2026-10-01 |
| `nocaps` | yes | 9.2 MB | 15,100 records indexed, 9.2 MB fetched, 2026-10-01 |
| `nrc-vad` | yes | 51.0 MB | 74,772 records indexed, 51.0 MB fetched, 2026-10-01 |
| `ok-vqa` | yes | 31.4 MB | 14,055 records indexed, 1.4 MB fetched, 2026-10-01 |
| `omnispatial` | yes | 30.0 MB | 8,431 records indexed, 0 B fetched, 2026-10-01 |
| `pairs` | yes | 19.1 MB | 200 records indexed, 19.1 MB fetched, 2026-10-01 |
| `phantom` | yes | 145.0 MB | 55,350 records indexed, 145.0 MB fetched, 2026-10-01 |
| `pmc-vqa` | yes | 99.2 MB | 228,948 records indexed, 49.2 MB fetched, 2026-10-01 |
| `pope` | yes | 151.1 MB | 9,000 records indexed, 1.1 MB fetched, 2026-10-01 |
| `puzzlevqa` | yes | 61.7 MB | 2,000 records indexed, 61.7 MB fetched, 2026-10-01 |
| `qnli` | yes | 10.6 MB | 115,669 records indexed, 10.6 MB fetched, 2026-10-01 |
| `qqp` | yes | 41.7 MB | 795,241 records indexed, 41.7 MB fetched, 2026-10-01 |
| `ravel` | yes | 429.3 KB | 11,839 records indexed, 429.3 KB fetched, 2026-10-01 |
| `realtoxicityprompts` | yes | 0 B | 99,442 records indexed, 0 B fetched, 2026-10-01 |
| `roco` | yes | 13.6 MB | 87,927 records indexed, 13.6 MB fetched, 2026-10-01 |
| `rsicd` | yes | 17.5 MB | 10,921 records indexed, 12.5 MB fetched, 2026-10-01 |
| `sad` | yes | 15.5 MB | 127,176 records indexed, 15.5 MB fetched, 2026-10-01 |
| `sbbench-synthetic-gender-crop-false` | yes | 237.0 MB | 206 records indexed, 237.0 MB fetched, 2026-10-01 |
| `seed-bench-2` | yes | 68.1 MB | 24,371 records indexed, 18.1 MB fetched, 2026-10-01 |
| `seedbench` | yes | 57.2 MB | 17,990 records indexed, 7.2 MB fetched, 2026-10-01 |
| `senator-tweets-2021` | yes | 232.5 MB | 99,693 records indexed, 232.5 MB fetched, 2026-10-01 |
| `set14` | yes | 0 B | 14 records indexed, 0 B fetched, 2026-10-01 |
| `set5` | yes | 0 B | 5 records indexed, 0 B fetched, 2026-10-01 |
| `shapes-localization` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `shapes-recognition` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `shapes-relations` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 |
| `sst2` | yes | 7.4 MB | 70,042 records indexed, 7.4 MB fetched, 2026-10-01 |
| `t2i-compbench` | yes | 850.7 KB | 17,861 records indexed, 850.7 KB fetched, 2026-10-01 |
| `tdc2023` | yes | 7.8 KB | 100 records indexed, 7.8 KB fetched, 2026-10-01 |
| `textvqa` | yes | 47.5 MB | 45,336 records indexed, 27.5 MB fetched, 2026-10-01 |
| `textvqa-x` | yes | 80.5 MB | 18,096 records indexed, 60.5 MB fetched, 2026-10-01 |
| `turing-eye-test` | yes | 171.5 MB | 490 records indexed, 171.5 MB fetched, 2026-10-01 |
| `tweeteval` | yes | 14.2 MB | 200,785 records indexed, 14.2 MB fetched, 2026-10-01 |
| `vg-qa-one` | yes | 679.8 MB | 1,160 records indexed, 679.8 MB fetched, 2026-10-01 |
| `vg-qa-two` | yes | 679.8 MB | 288 records indexed, 679.8 MB fetched, 2026-10-01 |
| `vibeeval` | yes | 205.3 MB | 269 records indexed, 205.3 MB fetched, 2026-10-01 |
| `visual6502-transistor-netlist` | yes | 265.3 KB | 3,510 records indexed, 265.3 KB fetched, 2026-10-01 |
| `visualpuzzle` | yes | 142.7 MB | 1,168 records indexed, 142.7 MB fetched, 2026-10-01 |
| `vizwiz` | yes | 29.9 MB | 32,842 records indexed, 9.9 MB fetched, 2026-10-01 |
| `vqa-v2` | yes | 164.0 MB | 214,354 records indexed, 14.0 MB fetched, 2026-10-01 |
| `vqa-v2-m-n-subsets` | yes | 2.1 MB | 1,600 records indexed, 2.1 MB fetched, 2026-10-01 |
| `vsr` | yes | 35.0 MB | 16,023 records indexed, 5.0 MB fetched, 2026-10-01 |
| `waterbirds` | yes | 489.7 MB | 11,788 records indexed, 489.7 MB fetched, 2026-10-01 |
| `wmdp` | yes | 1.1 MB | 3,668 records indexed, 1.1 MB fetched, 2026-10-01 |
| `wnli` | yes | 29.0 KB | 852 records indexed, 29.0 KB fetched, 2026-10-01 |

## Fetchable, not yet verified (44)

A source plan is ready within the budget; not yet fetched from an empty workspace.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `bapps` | yes | 7.7 GB | 7.7 GB · http_archive |
| `blink` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `cauldron` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `cifar-10-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cifar-100-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cinic-10` | yes | 687.5 MB | 687.5 MB · http_archive |
| `covid-19-radiography` | yes | 816.0 MB | 816.0 MB · http_archive |
| `cub-200-2011` | yes | 1.2 GB | 1.2 GB · http_archive |
| `datacomp-1b` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `exams-v` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `fairface` | yes | 2.7 GB | 2.7 GB · http_archive |
| `fgvc-aircraft` | yes | 2.8 GB | 2.8 GB · http_archive |
| `finevision` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `food101` | yes | 5.0 GB | 5.0 GB · http_archive |
| `hades` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `hod` | yes | 1.2 GB | 1.2 GB · http_archive |
| `iconqa` | yes | 1.9 GB | 1.9 GB · http_archive |
| `illuchar` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `imagenet-a` | yes | 687.6 MB | 687.6 MB · http_archive |
| `imagenet-r` | yes | 2.2 GB | 2.2 GB · http_archive |
| `imagenet-v2` | yes | 1.3 GB | 1.3 GB · http_archive |
| `llava-instruct-150k-3a74a703` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `mllmu-bench` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `naturalbench` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `objectnet` | yes | 1.6 GB | up to 1.6 GB · local |
| `oxfordpet` | yes | 811.1 MB | 811.1 MB · http_archive |
| `phase` | yes | 2.6 GB | 2.6 GB · http_archive |
| `realworldqa` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `recap-datacomp-1b` | no | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `safebench` | yes | 4.7 GB | 4.7 GB · http_archive |
| `sbbench-syn` | yes | 10.0 GB | up to 10.0 GB · local |
| `sbbench-syn-crop` | yes | 10.0 GB | up to 10.0 GB · local |
| `sbbench-synthetic-age-crop-false` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `sbbench-synthetic-age-crop-true` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `sbbench-synthetic-gender-crop-true` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `scienceqa-img` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `simplevqa` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `smolim2-135m-10b` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `socialcounterfactuals` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `space-10` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `visual-counterfact` | yes | 10.0 GB | up to 10.0 GB · huggingface_remote_sample |
| `visual-genome` | yes | 889.8 MB | 889.8 MB · http_archive |
| `vqa-constraints` | yes | 4.1 GB | 4.1 GB · http_archive |
| `what-s-up` | yes | 861.2 MB | 861.2 MB · http_archive |

## Needs a larger download budget (1)

Fetchable, but the source is larger than the per-dataset budget used here.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `sun397` | yes | 39.1 GB | Source download exceeds the selected download budget. |

## Gated at the source (26)

Source requires an account, agreement or approval; Atlas does not bypass it.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `chicago-face-database` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `coco-demographic-annotations` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `facet` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `facial-expression-recognition-2013` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `fer-2013` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `flickr30k` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `google-web-1t-corpus` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `gyafc` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet-ilsvrc` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet-ilsvrc-2012` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet100` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenetval` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `mma-diffusion` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `ms-cxr` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `paper-164d7c221452ffec-unnamed-cfd-morph-collection` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `restricted-imagenet` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `rosmap` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `sbbench` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `sorrybench` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `timit` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `visu` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |
| `visu-text` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |
| `winoground` | no | 0 B | This release is gated. Obtain authorized local files and configure its adapter. |
| `zerobench` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |

## No acquisition path yet (137)

No pinned acquisition recipe or adapter yet. For a public source this is a gap in Atlas; where availability is unverified, source research comes first.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `activations-csv` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `artbench-2` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `artchive` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `asteroids-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `audioset` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `bam-fg` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `brain-score` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `brca` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `broden` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `cc3m` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `celeba` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `cifar-10-1` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `cifar-2` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-caption` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `coco-detection-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-gender` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-spatial` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-train` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `cocogender` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `cocogendertxt` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `concept-editing-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `conceptual-captions` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `contrastive-prompts` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `cub` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `cub200` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `custom-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `custom-image-editing-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `custom-neonatal-rat-ganglion-recordings` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `custom-speech-segment-collection` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `custom-ternus-psychophysics-responses` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `dall-e-generated-target-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `deepfashion` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `docci` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `docvqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `donkey-kong-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `e-ic` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `e-vqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `emnist-balanced` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `emoset` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `factoid` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ffhq` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `fgvc` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `first-person-social-interactions-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `flowers` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gaussian-rubbish-examples` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gda-adversarial-image-variants` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gpt-4v-filtered-vl-gender-subset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `group-labels` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gvil` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `hc-bench` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `hellaswag-pro` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ictcf` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionbench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionbench-3c643c29` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionvqa` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `illusory-vqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-1k` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-c` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `imagenet-sampled-1-000-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-segmentation` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `inaturalist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `interpbench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `itac` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `jailbreakv-28k` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `laion` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `laion-400m` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `laion-aesthetics` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `language-identification-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `lingoqa` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `llava-bench` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `miap` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `middlebury` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `mit-adobe-5k` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mit-states` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `mm-vet` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mmbench-en-dev` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ms-coco` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ms-coco-7f846b38` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ms-coco-captions` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mscoco` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mscoco-100-target-subset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `multitrust` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `mvbench-scene-qa` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `nips17` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `oasis` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `objaverse` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `omnisafebench-mm` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `openimages` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ostris-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pairs-csv` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `paper-08e415961919a492-unnamed-11-image-inpainting-set` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-08e415961919a492-unnamed-real-noise-benchmark-46` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-1e2474b15fec2d7d-unnamed-controversial-stimuli-collection` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set` | no | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-944952997d24ce45-unnamed-vma-candidate-pool` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pascal-voc` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pata` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `perturbed-gender-benchmark-image-variants` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pitfall-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `places` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `raise1k` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ring-a-bell` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `robustbench` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `rs-vqa` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `saegis-clean-and-adversarial-splits` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `sb-syn` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `sb-syn-crop` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `scrambled-mnist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `shapeworld` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `shiftmnist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `simulated-transistor-traces` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `snli-ve` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `space-invaders-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `spoken-wikipedia` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `stanford-cars` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `stl-10` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `svhn` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `svo-probes` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `the-pile` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `tid2013` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `top16-images-csv` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ucf101` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `vhd11k` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `via-bench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `visual-counterfact-filtered-467` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `visualqa` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `vizwiz-priv` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `vl-gender` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `vlagenderbias` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `vtab` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `wall-street-journal` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `whoops` | yes | 0 B | No native Arrow/Parquet shards in this release; a format-specific acquisition recipe is required. |
| `wilds` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |

## Unreleased (17)

The authors have not released this data; nothing can be fetched.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-6a7364738bac9f07-unnamed-online-illusion-repositories` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-728d8c0964b540ad-unnamed-youtube-image-collection` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-765a2362f8735bc4-unnamed-social-category-question-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |
| `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` | no | 0 B | The authors have not released this data, so there is nothing to fetch; the entry records where it is described. |

