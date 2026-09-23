# Native population expansion, 2026-09-23

Nine additional populations have complete indices and 100 randomly sampled,
original-quality previews. All retain their released pixel dimensions. Access
and local preparation do not approve redistribution.

| Dataset | Native population indexed | Preserved scope and verification |
|---|---:|---|
| FIND | 2,275 functions | All source definitions, auxiliary tables and code match the author ZIP. All 150 available weight files remain passive bytes. No benchmark execution or deserialization. [Receipt](find-live-verification.json). |
| FairFace | 97,698 examples | 86,744 train and 10,954 validation rows, both original padding=0.25 and padding=1.25 crops. 206 live image reads match native ZIP bytes. Human-provided demographic labels remain annotations. [Receipt](fairface-live-verification.json). |
| ImageNet-Sketch | 50,889 images | All 1,000 native synset folders in the author-linked HF ZIP; 103 original images decoded and checked against native member length/CRC. [Receipt](imagenet-sketch-live-verification.json). |
| SEED-Bench | 17,990 questions | Native choices and answers, 12 task dimensions, images and ordered eight-frame video representations. Both instances of the repeated question ID survive as separate task records. [Receipt](seedbench-live-verification.json). |
| SEED-Bench 2 | 24,371 questions | All 27 native task dimensions, image groups and ordered author video frames. Native images fetched from the 72-part archive without downloading the whole 52 GB source. [Receipt](seed-bench-2-live-verification.json). |
| Visual CounterFact | 1,220 pairs | Both author color (493) and size (727) splits, original/counterfactual pairs and native labels. This does not identify the separate paper-specific 469/467-example subsets. [Receipt](visual-counterfact-live-verification.json). |
| Turing Eye Test | 490 examples | Full author split: HiddenText 150, 3DCaptcha 150, Colorblind 150, ChineseLigature 40. Duplicate task splits/older copies excluded. [Receipt](turing-eye-test-live-verification.json). |
| VQA-Constraints | 9,463 questions | All three author CSVs, all native candidate images, exact Unicode directory joins and original COCO images. 195 live image reads verified; seven unannotated image directories remain explicitly uncounted. [Receipt](vqa-constraints-live-verification.json). |
| RSICD | 10,921 images | All 54,605 native caption entries, their tokens/IDs and split labels. Repeated caption strings retained. All 103 live images retain the native 224×224 dimensions. [Receipt](rsicd-live-verification.json). |

Native annotation parity is checked over each complete index. Live checks cover
all 100 preview examples and three further complete-index examples per dataset,
including every image in those examples. CRC/ETag checks are described as such;
selectively read archives do not acquire a false full-file SHA-256 verification.

[Browser checks](browser-seed-bench-2.json) verify frame ordering and labels;
[FairFace browser checks](browser-fairface.json) verify both labelled crop variants.
The remote ZIP directory cache reduced four warm-range-cache frame reads from
0.427 seconds for the initial parse to 0.020–0.027 seconds for subsequent frames
in that archive. This is a local measurement with warm disk ranges, not a
cold-network claim. [Timing receipt](remote-zip-performance.json).
