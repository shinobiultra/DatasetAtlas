# Preview reproducibility from an empty workspace

Generated 2026-10-02 at commit `7ff682f`. A colleague's workspace holds only the shipped catalogue; this reports what `atlas previews fetch` can obtain from each dataset's own publisher. Planning reads source metadata only (per-dataset budget 10.0 GB); it downloads nothing.

**144 verified from scratch · 21 more fetchable (not yet tried) · 3 tried and failed · 1 need a larger budget · 26 gated · 121 with no acquisition path yet · 0 other** of 333 catalogue entries.

The maintainer's workspace holds 170 previews; 163 of them can be reproduced from the catalogue alone. The rest need a recipe (see below). A "verified" dataset was fetched in an empty workspace, produced a 100-record preview and complete index, and (where the catalogue pins one) carries the maintainer's snapshot ID.

## Verified from scratch (144)

Fetched from an empty workspace and checked.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `advbench` | yes | 0 B | 520 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `agent-security-bench` | yes | 441.3 KB | 843 records indexed, 441.3 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `algopuzzlevqa` | yes | 226.8 MB | 1,800 records indexed, 226.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `alpaca` | yes | 22.8 MB | 52,002 records indexed, 22.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `anthropic-red-teaming-prompts` | yes | 15.5 MB | 38,961 records indexed, 15.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `artbench` | yes | 183.9 MB | 60,000 records indexed, 183.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `bbq` | yes | 50.9 MB | 58,492 records indexed, 50.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `behonest` | yes | 5.3 MB | 19,059 records indexed, 5.3 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `bias-in-bios` | yes | 99.8 MB | 396,189 records indexed, 99.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `blink` | yes | 10.0 GB | index complete, 57.8 KB fetched, 2026-10-02 |
| `caltech101` | yes | 137.4 MB | 9,144 records indexed, 137.4 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `cauldron` | yes | 10.0 GB | index complete, 49.9 MB fetched, 2026-10-02 |
| `causalgym` | yes | 8.3 MB | 17,400 records indexed, 8.3 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `cebab` | yes | 2.2 MB | 18,600 records indexed, 2.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `chartqa` | yes | 4.6 MB | 32,719 records indexed, 4.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `child-safety-intents` | yes | 8.8 MB | 747 records indexed, 8.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `cifar-10` | yes | 170.1 MB | 60,000 records indexed, 170.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `cifar-100` | yes | 168.5 MB | 60,000 records indexed, 168.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `clevr` | yes | 0 B | 1,070 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `clevr-v1-full` | yes | 400.0 MB | 999,968 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `coco` | yes | 1.1 GB | 25,014 records indexed, 1.1 GB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `coco-2014` | yes | 293.6 MB | 164,062 records indexed, 253.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `coco-one` | yes | 20.2 MB | 2,247 records indexed, 182.8 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `coco-qa` | yes | 31.9 MB | 117,684 records indexed, 1.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `coco-two` | yes | 20.0 MB | 440 records indexed, 42.8 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `conceptarc` | yes | 147.4 KB | 176 records indexed, 147.4 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `controlled-clevr` | yes | 65.9 MB | 408 records indexed, 65.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `controlled-images` | yes | 95.2 MB | 412 records indexed, 95.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `counterfact` | yes | 45.1 MB | 21,919 records indexed, 45.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `covid-19-radiography` | yes | 816.0 MB | 21,165 records indexed, 816.0 MB fetched, 2026-10-02 |
| `cub-200-2011` | yes | 1.2 GB | 11,788 records indexed, 1.2 GB fetched, 2026-10-02 |
| `custom-propeller-and-rotating-snake-stimuli` | yes | 33.2 MB | 7 records indexed, 33.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `datacomp-1b` | no | 10.0 GB | index complete, 2.0 GB fetched, 2026-10-02 |
| `div2k` | yes | 5.0 MB | 900 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `dreambooth` | yes | 112.1 MB | 158 records indexed, 112.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `dtd` | yes | 625.2 MB | 5,640 records indexed, 625.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `emnist` | yes | 561.8 MB | 2,255,710 records indexed, 561.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `emnist-balanced` | yes | 561.8 MB | 131,600 records indexed, 561.8 MB fetched, 2026-10-02 |
| `emnist-letters` | yes | 561.8 MB | 145,600 records indexed, 561.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `eurosat` | yes | 94.7 MB | 27,000 records indexed, 94.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `fairface` | yes | 2.7 GB | 97,698 records indexed, 2.7 GB fetched, 2026-10-02 |
| `figure-linked-source-data-spreadsheets` | yes | 78.8 KB | 7 records indexed, 78.8 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `find` | yes | 2.7 MB | 2,275 records indexed, 2.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `finevision` | no | 10.0 GB | index complete, 1.5 GB fetched, 2026-10-02 |
| `flowers102` | yes | 344.9 MB | 8,189 records indexed, 344.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `foil-it` | yes | 171.6 MB | 594,536 records indexed, 131.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `glue-cola` | yes | 377.0 KB | 10,657 records indexed, 377.0 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `gqa` | yes | 300.0 MB | 132,062 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `gvil` | yes | 26.7 MB | 3,200 records indexed, 26.7 MB fetched, 2026-10-02 |
| `gvil-paired-illusion-images` | yes | 26.7 MB | 3,302 records indexed, 26.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `hades` | yes | 10.0 GB | index complete, 244.0 KB fetched, 2026-10-02 |
| `hallusionbench` | yes | 146.6 MB | 1,129 records indexed, 146.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `halueval` | yes | 63.4 MB | 34,507 records indexed, 63.4 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `harmbench` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `hatefulillusion` | yes | 530.7 KB | 2,160 records indexed, 530.7 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `high-quality-hallucination-benchmark` | yes | 38.4 MB | 4,000 records indexed, 8.4 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `hod` | yes | 1.2 GB | 10,631 records indexed, 1.2 GB fetched, 2026-10-02 |
| `iconqa` | yes | 1.9 GB | 107,439 records indexed, 1.9 GB fetched, 2026-10-02 |
| `idenprof` | yes | 154.7 MB | 11,000 records indexed, 154.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `illusionmnist` | yes | 433.0 KB | 5,069 records indexed, 433.0 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `illusoryvqa` | yes | 2.5 MB | 26,121 records indexed, 2.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `imagenet-a` | yes | 687.6 MB | 7,500 records indexed, 687.6 MB fetched, 2026-10-02 |
| `imagenet-r` | yes | 2.2 GB | 30,000 records indexed, 2.2 GB fetched, 2026-10-02 |
| `imagenet-sketch` | yes | 20.0 MB | 50,889 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `imagenet-v2` | yes | 1.3 GB | 10,000 records indexed, 1.3 GB fetched, 2026-10-02 |
| `imagenette` | yes | 99.0 MB | 13,394 records indexed, 99.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `jiechieu-tsopze-resume-corpus` | yes | 169.2 MB | 29,783 records indexed, 169.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `llava-instruct-150k` | yes | 248.9 MB | 157,712 records indexed, 228.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `llava-instruct-150k-3a74a703` | yes | 76.6 GB | index complete, 12.5 MB fetched, 2026-10-02 |
| `maliciousinstruct` | yes | 6.3 KB | 100 records indexed, 6.3 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mathvision` | yes | 63.9 MB | 3,344 records indexed, 63.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `medical-multimodal-evaluation-data` | yes | 26.0 MB | 17,303 records indexed, 6.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mllmu-bench` | yes | 10.0 GB | index complete, 1.1 MB fetched, 2026-10-02 |
| `mm-safetybench` | yes | 499.5 MB | 1,685 records indexed, 499.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mmbench` | yes | 180.9 MB | 21,990 records indexed, 180.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mme` | yes | 199.8 MB | 2,374 records indexed, 199.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mme-perception` | yes | 199.8 MB | 2,114 records indexed, 199.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mmmu-dev` | yes | 57.0 MB | 150 records indexed, 57.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mmstar` | yes | 41.8 MB | 1,500 records indexed, 41.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mnist` | yes | 11.6 MB | 70,000 records indexed, 11.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `mrpc` | yes | 1.5 MB | 5,801 records indexed, 1.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `naturalbench` | yes | 10.0 GB | index complete, 320.3 KB fetched, 2026-10-02 |
| `nocaps` | yes | 9.2 MB | 15,100 records indexed, 9.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `nrc-vad` | yes | 51.0 MB | 74,772 records indexed, 51.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `objectnet` | yes | 1.6 GB | 50,273 records indexed, 627.5 MB fetched, 2026-10-02 |
| `ok-vqa` | yes | 31.4 MB | 14,055 records indexed, 1.4 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `omnispatial` | yes | 30.0 MB | 8,431 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `oxfordpet` | yes | 811.1 MB | 7,349 records indexed, 811.1 MB fetched, 2026-10-02 |
| `pairs` | yes | 19.1 MB | 200 records indexed, 19.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `phantom` | yes | 145.0 MB | 55,350 records indexed, 145.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `phase` | yes | 2.6 GB | 18,889 records indexed, 2.6 GB fetched, 2026-10-02 |
| `pmc-vqa` | yes | 99.2 MB | 228,948 records indexed, 49.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `pope` | yes | 151.1 MB | 9,000 records indexed, 1.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `puzzlevqa` | yes | 61.7 MB | 2,000 records indexed, 61.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `qnli` | yes | 10.6 MB | 115,669 records indexed, 10.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `qqp` | yes | 41.7 MB | 795,241 records indexed, 41.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `ravel` | yes | 429.3 KB | 11,839 records indexed, 429.3 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `realtoxicityprompts` | yes | 0 B | 99,442 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `realworldqa` | yes | 10.0 GB | index complete, 169.6 KB fetched, 2026-10-02 |
| `recap-datacomp-1b` | no | 10.0 GB | index complete, 122.9 MB fetched, 2026-10-02 |
| `roco` | yes | 13.6 MB | 87,927 records indexed, 13.6 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `rsicd` | yes | 17.5 MB | 10,921 records indexed, 12.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `sad` | yes | 15.5 MB | 127,176 records indexed, 15.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `sbbench-syn` | yes | 10.0 GB | 539 records indexed, 137.7 KB fetched, 2026-10-02 |
| `sbbench-syn-crop` | yes | 10.0 GB | 917 records indexed, 207.7 KB fetched, 2026-10-02 |
| `sbbench-synthetic-age-crop-false` | yes | 10.0 GB | index complete, 69.6 KB fetched, 2026-10-02 |
| `sbbench-synthetic-age-crop-true` | yes | 10.0 GB | index complete, 136.1 KB fetched, 2026-10-02 |
| `sbbench-synthetic-gender-crop-false` | yes | 237.0 MB | 206 records indexed, 237.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `sbbench-synthetic-gender-crop-true` | yes | 10.0 GB | index complete, 70.5 KB fetched, 2026-10-02 |
| `scienceqa-img` | yes | 10.0 GB | index complete, 5.9 MB fetched, 2026-10-02 |
| `seed-bench-2` | yes | 68.1 MB | 24,371 records indexed, 18.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `seedbench` | yes | 57.2 MB | 17,990 records indexed, 7.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `senator-tweets-2021` | yes | 232.5 MB | 99,693 records indexed, 232.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `set14` | yes | 0 B | 14 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `set5` | yes | 0 B | 5 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `shapes-localization` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `shapes-recognition` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `shapes-relations` | yes | 0 B | 400 records indexed, 0 B fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `simplevqa` | yes | 10.0 GB | index complete, 415.7 MB fetched, 2026-10-02 |
| `smolim2-135m-10b` | yes | 10.0 GB | index complete, 295.9 MB fetched, 2026-10-02 |
| `socialcounterfactuals` | yes | 10.0 GB | index complete, 4.0 MB fetched, 2026-10-02 |
| `sst2` | yes | 7.4 MB | 70,042 records indexed, 7.4 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `stl-10` | yes | 2.6 GB | 113,000 records indexed, 2.6 GB fetched, 2026-10-02 |
| `t2i-compbench` | yes | 850.7 KB | 17,861 records indexed, 850.7 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `tdc2023` | yes | 7.8 KB | 100 records indexed, 7.8 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `textvqa` | yes | 47.5 MB | 45,336 records indexed, 27.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `textvqa-x` | yes | 80.5 MB | 18,096 records indexed, 60.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `turing-eye-test` | yes | 171.5 MB | 490 records indexed, 171.5 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `tweeteval` | yes | 14.2 MB | 200,785 records indexed, 14.2 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vg-qa-one` | yes | 679.8 MB | 1,160 records indexed, 679.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vg-qa-two` | yes | 679.8 MB | 288 records indexed, 679.8 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vibeeval` | yes | 205.3 MB | 269 records indexed, 205.3 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `visual-counterfact` | yes | 10.0 GB | index complete, 182.5 KB fetched, 2026-10-02 |
| `visual-genome` | yes | 889.8 MB | 116,367 records indexed, 859.8 MB fetched, 2026-10-02 |
| `visual6502-transistor-netlist` | yes | 265.3 KB | 3,510 records indexed, 265.3 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `visualpuzzle` | yes | 142.7 MB | 1,168 records indexed, 142.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vizwiz` | yes | 29.9 MB | 32,842 records indexed, 9.9 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vqa-v2` | yes | 164.0 MB | 214,354 records indexed, 14.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vqa-v2-m-n-subsets` | yes | 2.1 MB | 1,600 records indexed, 2.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `vsr` | yes | 35.0 MB | 16,023 records indexed, 5.0 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `waterbirds` | yes | 489.7 MB | 11,788 records indexed, 489.7 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `what-s-up` | yes | 861.2 MB | 4,958 records indexed, 841.2 MB fetched, 2026-10-02 |
| `wmdp` | yes | 1.1 MB | 3,668 records indexed, 1.1 MB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |
| `wnli` | yes | 29.0 KB | 852 records indexed, 29.0 KB fetched, 2026-10-01 (earlier run, first reported at 3b64daf) |

## Fetchable, not yet verified (21)

A source plan is ready within the budget; not yet fetched from an empty workspace.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `activations-csv` | yes | 22.0 MB | 22.0 MB · http_archive |
| `bapps` | yes | 7.7 GB | 7.7 GB · http_archive |
| `cifar-10-1` | yes | 6.2 MB | 6.2 MB · http_archive |
| `cifar-10-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cifar-100-c` | yes | 2.9 GB | 2.9 GB · http_archive |
| `cinic-10` | yes | 687.5 MB | 687.5 MB · http_archive |
| `fgvc-aircraft` | yes | 2.8 GB | 2.8 GB · http_archive |
| `food101` | yes | 5.0 GB | 5.0 GB · http_archive |
| `hc-bench` | yes | 11.7 MB | 11.7 MB · http_archive |
| `illusionvqa` | yes | 38.7 MB | 38.7 MB · http_archive |
| `jailbreakv-28k` | yes | 23.2 MB | 23.2 MB · http_archive |
| `llava-bench` | yes | 9.8 MB | 9.8 MB · http_archive |
| `mm-vet` | yes | 66.5 MB | 66.5 MB · http_archive |
| `mmbench-en-dev` | yes | 37.2 MB | 37.2 MB · http_archive |
| `omnisafebench-mm` | yes | 485.9 KB | 485.9 KB · http_archive |
| `pairs-csv` | yes | 22.0 MB | 22.0 MB · http_archive |
| `safebench` | yes | 4.7 GB | 4.7 GB · http_archive |
| `svo-probes` | yes | 14.2 MB | 14.2 MB · http_archive |
| `top16-images-csv` | yes | 22.0 MB | 22.0 MB · http_archive |
| `vqa-constraints` | yes | 4.1 GB | 4.1 GB · http_archive |
| `whoops` | yes | 689.3 MB | 689.3 MB · http_archive |

## Fetch attempted, failed (3)

A fetch from an empty workspace was attempted and failed; the stated reason is the last observed error, not a source restriction.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `exams-v` | yes | 10.0 GB | ValueError: Embedded image exceeds pixel budget |
| `illuchar` | yes | 10.0 GB | ValueError: Image row group exceeds decoded memory budget |
| `space-10` | yes | 10.0 GB | ValueError: Remote binary column image requires the full-download adapter; slot availability cannot be inferred |

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

## No acquisition path yet (121)

No pinned acquisition recipe or adapter yet. For a public source this is a gap in Atlas; where availability is unverified, source research comes first.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
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
| `hellaswag-pro` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ictcf` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionbench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionbench-3c643c29` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusory-vqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-1k` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-c` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `imagenet-sampled-1-000-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-segmentation` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `inaturalist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `interpbench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `itac` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `laion` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `laion-400m` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `laion-aesthetics` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `language-identification-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `lingoqa` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `miap` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `middlebury` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `mit-adobe-5k` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mit-states` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
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
| `openimages` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ostris-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
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
| `svhn` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `the-pile` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `tid2013` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
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

