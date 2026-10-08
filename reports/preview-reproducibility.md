# Preview reproducibility from an empty workspace

Generated 2026-10-07 from the modified working tree based on `ea5052e` (source/registry/schema SHA-256 `1f66d46f3f8a65ab4e5920a8e45545c36227da19f13506237c8afd9466a27477`). A colleague's workspace holds only the shipped catalogue; this reports what `atlas previews fetch` can obtain from each dataset's own publisher. Planning reads source metadata only (per-dataset source budget 10.0 GB, output budget 1.0 GB); it downloads nothing.

**79 verified from scratch · 87 more fetchable (not yet tried) · 0 tried and failed · 4 need a larger budget · 18 gated · 80 with no acquisition path yet · 17 unreleased · 48 other** of 333 catalogue entries.

The maintainer's workspace holds 218 previews; 170 of them can be reproduced from the catalogue alone, subject to the individual source budgets and access conditions below. A "verified" dataset was fetched in an empty workspace, produced a preview of 100 records (or all if smaller). Complete indices and sampled previews are distinguished below; a sampled preview does not prove full-population indexing. Earlier evidence retains its original date and commit, but certifies the current recipe only when its recipe checksum matches; other historical successes remain explicitly historical. The snapshot ID refers to the acquired release, whose scope can differ from the paper-used subset.

## Verified from scratch (79)

Fetched from an empty workspace and checked.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `activations-csv` | yes | 22.0 MB | 930 records indexed, 22.0 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `agent-security-bench` | yes | 441.3 KB | 843 records indexed, 441.3 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `audioset` | yes | 103.8 MB | 2,084,320 records indexed, 103.8 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `bapps` | yes | 7.7 GB | 197,344 records indexed, 7.7 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `behonest` | yes | 5.3 MB | 19,059 records indexed, 5.3 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `causalgym` | yes | 8.3 MB | 17,400 records indexed, 8.3 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `cebab` | yes | 2.2 MB | 18,600 records indexed, 2.2 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `celeba` | yes | 1.5 GB | 202,599 records indexed, 1.5 GB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `chartqa` | yes | 4.6 MB | 32,719 records indexed, 4.6 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `cifar-10-1` | yes | 6.2 MB | 2,000 records indexed, 6.2 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `cifar-10-c` | yes | 2.9 GB | 950,000 records indexed, 2.9 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `cifar-100-c` | yes | 2.9 GB | 950,000 records indexed, 2.9 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `cinic-10` | yes | 687.5 MB | 270,000 records indexed, 687.5 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `cocogender` | yes | 100.5 MB | 244,242 records indexed, 97.6 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `conceptarc` | yes | 147.4 KB | 176 records indexed, 147.4 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `datacomp-1b` | yes | 130.5 MB | 532,229 records indexed, 130.5 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `div2k` | yes | 5.0 MB | 900 records indexed, 1.3 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `docci` | yes | 7.6 GB | 14,847 records indexed, 7.6 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `factoid` | yes | 369.3 MB | 4,150 records indexed, 369.3 MB fetched, 2026-10-07 |
| `fgvc-aircraft` | yes | 2.8 GB | 10,000 records indexed, 2.8 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `figure-linked-source-data-spreadsheets` | yes | 78.8 KB | 7 records indexed, 78.8 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `find` | yes | 2.7 MB | 2,275 records indexed, 2.7 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `flickr30k` | yes | 22.9 MB | 31,014 records indexed, 40.4 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `food101` | yes | 5.0 GB | 101,000 records indexed, 5.0 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `glue-cola` | yes | 377.0 KB | 10,657 records indexed, 377.0 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `hatefulillusion` | yes | 530.7 KB | 2,160 records indexed, 530.7 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `hc-bench` | yes | 11.7 MB | 53 records indexed, 11.7 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `illusionbench-3c643c29` | yes | 21.9 MB | 1,041 records indexed, 2.3 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `illusionmnist` | yes | 433.0 KB | 5,069 records indexed, 433.0 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `illusionvqa` | yes | 38.7 MB | 1,435 records indexed, 38.7 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `illusoryvqa` | yes | 2.5 MB | 26,121 records indexed, 2.5 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `imagenet-segmentation` | yes | 1.3 GB | 4,276 records indexed, 1.3 GB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `interpbench` | yes | 76.4 KB | 86 records indexed, 76.4 KB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `jailbreakv-28k` | yes | 23.2 MB | 28,000 records indexed, 23.2 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `language-identification-dataset` | yes | 15.3 MB | 90,000 records indexed, 15.3 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `lingoqa` | yes | 232.2 MB | 1,000 records indexed, 232.2 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `llava-bench` | yes | 9.8 MB | 60 records indexed, 9.8 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `maliciousinstruct` | yes | 6.3 KB | 100 records indexed, 6.3 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `miap` | yes | 49.1 MB | 100,000 records indexed, 84.0 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `mit-adobe-5k` | yes | 5.3 GB | 25,000 records indexed, 5.2 GB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `mit-states` | yes | 170.0 MB | 63,440 records indexed, 28.0 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `mm-vet` | yes | 66.5 MB | 218 records indexed, 66.5 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `mma-diffusion` | yes | 301.0 KB | 1,000 records indexed, 301.0 KB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `mmbench-en-dev` | yes | 37.2 MB | 4,329 records indexed, 37.2 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `mrpc` | yes | 1.5 MB | 5,801 records indexed, 1.5 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `mvbench-scene-qa` | yes | 301.1 MB | 200 records indexed, 270.3 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `oasis` | yes | 92.1 MB | 900 records indexed, 92.1 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `objaverse` | yes | 598.0 MB | 798,759 records indexed, 1.0 GB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `omnisafebench-mm` | yes | 485.9 KB | 1,500 records indexed, 485.9 KB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `openimages` | yes | 171.7 MB | 41,620 records indexed, 103.2 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `pairs-csv` | yes | 22.0 MB | 1,000 records indexed, 22.0 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `paper-1e2474b15fec2d7d-unnamed-controversial-stimuli-collection` | yes | 19.5 MB | 1,863 records indexed, 19.5 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `places` | yes | 592.7 MB | 36,500 records indexed, 592.7 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `ravel` | yes | 429.3 KB | 11,839 records indexed, 429.3 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `recap-datacomp-1b` | yes | 572.4 KB | 1,000 records indexed, 572.4 KB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `ring-a-bell` | yes | 77.5 KB | 285 records indexed, 77.5 KB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `rs-vqa` | yes | 126.0 MB | 77,232 records indexed, 126.0 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `saegis-clean-and-adversarial-splits` | yes | 6.7 KB | 4,800 records indexed, 6.7 KB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `safebench` | yes | 4.7 GB | 2,300 records indexed, 4.7 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `shapeworld` | yes | 84.2 MB | 2,100 records indexed, 84.2 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `snli-ve` | yes | 57.7 MB | 565,286 records indexed, 68.5 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `sorrybench` | yes | 8.3 MB | 9,240 records indexed, 8.3 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `sst2` | yes | 7.4 MB | 70,042 records indexed, 7.4 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `svhn` | yes | 246.3 MB | 99,289 records indexed, 246.3 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `svo-probes` | yes | 14.2 MB | 36,841 records indexed, 14.2 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `t2i-compbench` | yes | 850.7 KB | 17,861 records indexed, 850.7 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `tdc2023` | yes | 7.8 KB | 100 records indexed, 7.8 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `tid2013` | yes | 957.7 MB | 3,000 records indexed, 957.7 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `top16-images-csv` | yes | 22.0 MB | 930 records indexed, 22.0 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `ucf101` | yes | 155.1 MB | 13,320 records indexed, 54.0 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `vhd11k` | yes | 78.4 MB | 11,000 records indexed, 68.4 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `visu-text` | yes | 50.8 MB | 168,700 records indexed, 50.8 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `visual6502-transistor-netlist` | yes | 265.3 KB | 3,510 records indexed, 265.3 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `vizwiz-priv` | yes | 11.0 MB | 13,571 records indexed, 1.0 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `vqa-constraints` | yes | 4.1 GB | 9,463 records indexed, 4.0 GB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `vqa-v2-m-n-subsets` | yes | 2.1 MB | 1,600 records indexed, 2.1 MB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |
| `whoops` | yes | 689.3 MB | 500 records indexed, 689.3 MB fetched, 2026-10-05 (earlier run, first reported at ea5052e) |
| `winoground` | yes | 1.1 MB | 400 records indexed, 108.5 MB fetched, 2026-10-06 (earlier run, first reported at ea5052e) |
| `wnli` | yes | 29.0 KB | 852 records indexed, 29.0 KB fetched, 2026-10-07 (earlier run, first reported at ea5052e) |

## Fetchable, not yet verified (87)

A source plan is ready within the budget; not yet fetched from an empty workspace.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `alpaca` | yes | 22.8 MB | 22.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `anthropic-red-teaming-prompts` | yes | 15.5 MB | 15.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `artbench` | yes | 183.9 MB | 183.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `bbq` | yes | 50.9 MB | 50.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `caltech101` | yes | 137.4 MB | 137.4 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `child-safety-intents` | yes | 8.8 MB | 8.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `cifar-10` | yes | 170.1 MB | 170.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `cifar-100` | yes | 168.5 MB | 168.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `clevr-v1-full` | yes | 400.0 MB | up to 400.0 MB · local; earlier success 2026-10-01, current recipe unverified |
| `coco` | yes | 1.1 GB | 1.1 GB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `coco-2014` | yes | 293.6 MB | 293.6 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `coco-one` | yes | 20.2 MB | 20.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `coco-qa` | yes | 31.9 MB | 31.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `coco-two` | yes | 20.0 MB | 20.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `controlled-clevr` | yes | 65.9 MB | 65.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `controlled-images` | yes | 95.2 MB | 95.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `counterfact` | yes | 45.1 MB | 45.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `covid-19-radiography` | yes | 816.0 MB | 816.0 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `cub-200-2011` | yes | 1.2 GB | 1.2 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `custom-propeller-and-rotating-snake-stimuli` | yes | 33.2 MB | 33.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `dreambooth` | yes | 112.1 MB | 112.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `dtd` | yes | 625.2 MB | 625.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `emnist` | yes | 561.8 MB | 561.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `emnist-balanced` | yes | 561.8 MB | 561.8 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `emnist-letters` | yes | 561.8 MB | 561.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `eurosat` | yes | 94.7 MB | 94.7 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `fairface` | yes | 2.7 GB | 2.7 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `flowers102` | yes | 344.9 MB | 344.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `foil-it` | yes | 171.6 MB | 171.6 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `gqa` | yes | 300.0 MB | up to 300.0 MB · local; earlier success 2026-10-01, current recipe unverified |
| `gvil` | yes | 26.7 MB | 26.7 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `gvil-paired-illusion-images` | yes | 26.7 MB | 26.7 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `halueval` | yes | 63.4 MB | 63.4 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `high-quality-hallucination-benchmark` | yes | 38.4 MB | 38.4 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `hod` | yes | 1.2 GB | 1.2 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `iconqa` | yes | 1.9 GB | 1.9 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `idenprof` | yes | 154.7 MB | 154.7 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `imagenet-a` | yes | 687.6 MB | 687.6 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `imagenet-r` | yes | 2.2 GB | 2.2 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `imagenet-sketch` | yes | 20.0 MB | 20.0 MB · local; earlier success 2026-10-01, current recipe unverified |
| `imagenet-v2` | yes | 1.3 GB | 1.3 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `imagenette` | yes | 99.0 MB | 99.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `inaturalist` | yes | 8.9 GB | 8.9 GB · http_sequential_tar |
| `jiechieu-tsopze-resume-corpus` | yes | 169.2 MB | 169.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `laion-400m` | yes | 1.8 GB | 1.8 GB · http_archive |
| `llava-instruct-150k` | yes | 248.9 MB | 248.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `medical-multimodal-evaluation-data` | yes | 26.0 MB | 26.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `mm-safetybench` | yes | 499.5 MB | 499.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `mmbench` | yes | 180.9 MB | 180.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `mme` | yes | 199.8 MB | 199.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `mme-perception` | yes | 199.8 MB | 199.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `mnist` | yes | 11.6 MB | 11.6 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `nocaps` | yes | 9.2 MB | 9.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `nrc-vad` | yes | 51.0 MB | 51.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `objectnet` | yes | 1.6 GB | up to 1.6 GB · local; earlier success 2026-10-02, current recipe unverified |
| `ok-vqa` | yes | 31.4 MB | 31.4 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `omnispatial` | yes | 30.0 MB | 30.0 MB · local; earlier success 2026-10-01, current recipe unverified |
| `oxfordpet` | yes | 811.1 MB | 811.1 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `pairs` | yes | 19.1 MB | 19.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `pascal-voc` | yes | 1.8 GB | 1.8 GB · http_archive |
| `phantom` | yes | 145.0 MB | 145.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `phase` | yes | 2.6 GB | 2.6 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `pmc-vqa` | yes | 99.2 MB | 99.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `pope` | yes | 151.1 MB | up to 151.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `qnli` | yes | 10.6 MB | 10.6 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `qqp` | yes | 41.7 MB | 41.7 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `roco` | yes | 13.6 MB | 13.6 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `rsicd` | yes | 17.5 MB | 17.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `sad` | yes | 15.5 MB | 15.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `sbbench-syn` | yes | 10.0 GB | up to 10.0 GB · local; earlier success 2026-10-02, current recipe unverified |
| `sbbench-syn-crop` | yes | 10.0 GB | up to 10.0 GB · local; earlier success 2026-10-02, current recipe unverified |
| `seed-bench-2` | yes | 68.1 MB | 68.1 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `seedbench` | yes | 57.2 MB | 57.2 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `set14` | yes | 0 B | 0 B · local; earlier success 2026-10-01, current recipe unverified |
| `set5` | yes | 0 B | 0 B · local; earlier success 2026-10-01, current recipe unverified |
| `stl-10` | yes | 2.6 GB | 2.6 GB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `textvqa` | yes | 47.5 MB | 47.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `textvqa-x` | yes | 80.5 MB | 80.5 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `the-pile` | yes | 2.8 GB | 2.8 GB · http_archive |
| `vg-qa-one` | yes | 679.8 MB | 679.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `vg-qa-two` | yes | 679.8 MB | 679.8 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `visual-genome` | yes | 889.8 MB | 889.8 MB · http_archive; earlier success 2026-10-02, current recipe unverified |
| `vizwiz` | yes | 29.9 MB | 29.9 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `vqa-v2` | yes | 164.0 MB | up to 164.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `vsr` | yes | 35.0 MB | 35.0 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `waterbirds` | yes | 489.7 MB | 489.7 MB · http_archive; earlier success 2026-10-01, current recipe unverified |
| `what-s-up` | yes | 861.2 MB | 861.2 MB · http_archive; earlier success 2026-10-02, current recipe unverified |

## Needs a larger preparation budget (4)

Fetchable, but the source or output exceeds the per-dataset budgets used here.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `emoset` | yes | 11.5 GB | Source download exceeds the selected download budget. |
| `imagenet-c` | yes | 66.0 GB | Source download exceeds the selected download budget. |
| `spoken-wikipedia` | yes | 39.1 GB | Native ZIP/TAR seek indices require dataset-atlas[remote-storage] (indexed-gzip). |
| `sun397` | yes | 39.1 GB | Indexed gzip access requires the remote-storage extra (indexed-gzip). |

## Gated at the source (18)

Source requires an account, agreement or approval; Atlas does not bypass it.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `chicago-face-database` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `coco-demographic-annotations` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `facet` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `facial-expression-recognition-2013` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `fer-2013` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `google-web-1t-corpus` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `gyafc` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet-ilsvrc` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenet100` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `imagenetval` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `ms-cxr` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `multitrust` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `paper-164d7c221452ffec-unnamed-cfd-morph-collection` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `rosmap` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `sbbench` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |
| `timit` | no | 0 B | This release needs approval or an agreement from its source, which Atlas does not bypass; add authorized local files to use it. |

## No acquisition path yet (80)

No pinned acquisition recipe or adapter yet. For a public source this is a gap in Atlas; where availability is unverified, source research comes first.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `advbench` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc; earlier success 2026-10-01, current recipe unverified |
| `artbench-2` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `artchive` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `asteroids-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `bam-fg` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `brain-score` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `brca` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `broden` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `cifar-2` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `clevr` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc; earlier success 2026-10-01, current recipe unverified |
| `coco-caption` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `coco-detection-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-gender` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-spatial` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `coco-train` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
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
| `donkey-kong-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `e-ic` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `e-vqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `fgvc` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `first-person-social-interactions-dataset` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `flowers` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gaussian-rubbish-examples` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gda-adversarial-image-variants` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `gpt-4v-filtered-vl-gender-subset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `group-labels` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `harmbench` | yes | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc; earlier success 2026-10-01, current recipe unverified |
| `hellaswag-pro` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ictcf` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusionbench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `illusory-vqa` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `imagenet-sampled-1-000-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `itac` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `laion` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `laion-aesthetics` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `middlebury` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ms-coco` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ms-coco-7f846b38` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `ms-coco-captions` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mscoco` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `mscoco-100-target-subset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `nips17` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `ostris-dataset` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-08e415961919a492-unnamed-11-image-inpainting-set` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-08e415961919a492-unnamed-real-noise-benchmark-46` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-944952997d24ce45-unnamed-vma-candidate-pool` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pata` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `perturbed-gender-benchmark-image-variants` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `pitfall-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `raise1k` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `robustbench` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `sb-syn` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `sb-syn-crop` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
| `scrambled-mnist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `shiftmnist` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `simulated-transistor-traces` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `space-invaders-rom` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `via-bench` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `visual-counterfact-filtered-467` | no | 0 B | Atlas has no acquisition path for this release, and its public availability has not been verified. Identity or source research is needed bef |
| `visualqa` | no | 0 B | Atlas has no pinned acquisition recipe for this release yet. The source is public, so this is a gap in Atlas, not a restriction by the sourc |
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

## Other (48)

Another stated requirement.

| Dataset | Maintainer preview | Source size | Detail |
| --- | --- | --- | --- |
| `algopuzzlevqa` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `bias-in-bios` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `blink` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `cauldron` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `cc3m` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `docvqa` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `exams-v` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-05, current recipe unverified |
| `ffhq` | yes | 517.8 MB | FFHQ metadata conversion requires ijson; install dataset-atlas[datasets] before acquisition. |
| `finevision` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-05, current recipe unverified |
| `hades` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `hallusionbench` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `illuchar` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-05, current recipe unverified |
| `imagenet-1k` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `imagenet-ilsvrc-2012` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `llava-instruct-150k-3a74a703` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `mathvision` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `mllmu-bench` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `mmmu-dev` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `mmstar` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `naturalbench` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection` | no | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set` | no | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `puzzlevqa` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `realtoxicityprompts` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `realworldqa` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `restricted-imagenet` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `sbbench-synthetic-age-crop-false` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `sbbench-synthetic-age-crop-true` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `sbbench-synthetic-gender-crop-false` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `sbbench-synthetic-gender-crop-true` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `scienceqa-img` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `senator-tweets-2021` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `shapes-localization` | yes | 0 B | ImportError: cannot import name 'ImageDraw' from 'PIL' (/home/bitwise/Documents/vibe/DatasetAtlas/.venv/lib/python3.12/site-packages/PIL/__i; earlier success 2026-10-01, current recipe unverified |
| `shapes-recognition` | yes | 0 B | ImportError: cannot import name 'ImageDraw' from 'PIL' (/home/bitwise/Documents/vibe/DatasetAtlas/.venv/lib/python3.12/site-packages/PIL/__i; earlier success 2026-10-01, current recipe unverified |
| `shapes-relations` | yes | 0 B | ImportError: cannot import name 'ImageDraw' from 'PIL' (/home/bitwise/Documents/vibe/DatasetAtlas/.venv/lib/python3.12/site-packages/PIL/__i; earlier success 2026-10-01, current recipe unverified |
| `simplevqa` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `smolim2-135m-10b` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `socialcounterfactuals` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `space-10` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-05, current recipe unverified |
| `stanford-cars` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `turing-eye-test` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `tweeteval` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `vibeeval` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `visu` | no | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution) |
| `visual-counterfact` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-02, current recipe unverified |
| `visualpuzzle` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-01, current recipe unverified |
| `wmdp` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-07, current recipe unverified |
| `zerobench` | yes | 0 B | ValueError: Host did not resolve after 4 retries: huggingface.co (Temporary failure in name resolution); earlier success 2026-10-07, current recipe unverified |

