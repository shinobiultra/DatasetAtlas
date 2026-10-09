# Storage reclaim plan, 2026-10-09 (dry run only)

Nothing was deleted. Sources: `atlas storage status`, `atlas storage clean` and `clean --idle-media-caches` dry runs, `atlas datasets prune` dry run, `retire-columnar` dry runs, inode-level hard-link accounting, `registry/recipes`, `work/original-access` routes and indices, the workbench selections table and `work/compact-media` preview stores. No candidate is reviewed by a human; statuses are mechanical.

Start: allocated 123,431,141,376 B (123.43 GB), target 100,000,000,000 B, above target by 23.43 GB; the 150 GB ceiling holds.

## Summary by status

| status | candidates | allocated GB (each inode counted once) | GB freed if only the listed path is unlinked |
|---|---|---|---|
| blocked | 73 | 47.70 | 27.36 |
| not_retrievable | 10 | 8.83 | 2.12 |
| verified_reclaimable | 2 | 2.17 | 0.00 |

verified_reclaimable totals 2.17 GB, which is 9.2% of the gap. Shared hard links are reported separately and are not freed by unlinking one path.

## Why nothing was executed

- The only verified_reclaimable candidates are evictable caches and byte-identical re-links, and both exist only inside atlas storage clean, which evicts every unpinned entry. That includes 384 MB of BBQ-V (sbbench) range cache and 1.8 MB of phantom cache, both coverage.access=gated, which the brief says never to delete. The command has no per-namespace option.
- A multitrust preparation (atlas previews fetch + worker) is running; atlas storage clean --execute refuses while a preparation is running, and the multitrust plan reads the gated thu-ml/MultiTrust source.
- Every work/sources and work/prepared body has an active reader and no retained native index, so retire-original/-repacked cannot be applied without first running atlas storage index-original, which is outside the commands this task allows. retire-columnar refuses (hallusionbench: a source shard has no dependent images; algopuzzlevqa: arrow not parquet; blink, realworldqa, sbbench-synthetic-*: adapter embedded_parquet).
- retire-cifar-c candidates (cifar-10-c, cifar-100-c) were already retired on 2026-10-07 (receipts reports/cifar-*-c-native-source-retirement-20261007.json); no local TAR remains.

## verified_reclaimable (dry run lists them; execution withheld)

| candidate | datasets | allocated GB | route | note |
|---|---|---|---|---|
| work/media-cache/remote-parquet | 14 datasets | 0.61 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/ranges | 17 datasets | 0.45 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/decoded | 0 datasets | 0.29 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/sbbench-syn-crop | 1 datasets | 0.27 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/sbbench-syn | 2 datasets | 0.25 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/originals | 3 datasets | 0.07 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/seed-bench-2 | 1 datasets | 0.04 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/div2k | 1 datasets | 0.02 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/seedbench | 1 datasets | 0.01 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/visualgenome | 2 datasets | 0.01 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/imagenet-sketch | 1 datasets | 0.01 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/selfexsr | 2 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/whatsup | 7 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/nocaps | 1 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/original-ranges | 0 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/illusoryvqa | 2 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| work/media-cache/optimized | 0 datasets | 0.00 | regenerable cache: ETag/fingerprint-bound remote range or decoded copy | dry run lists every entry; execution withheld only because the same command evicts the not |
| derivative-link dedup (clean dry run: derivative_links) | 2 datasets | 0.14 | none needed: identical bytes retained as hard links (SHA-256 checked b | bundled in atlas storage clean --execute with the cache eviction above; cannot run alone;  |

## not_retrievable caches (inseparable from the above)

- work/media-cache/sbbench: 0.38 GB, 55 entries. BBQ-V (sbbench), coverage.access=gated, researcher-token route; the command cannot exclude one namespace, so it is withheld as a whole
- work/media-cache/phantom: 0.00 GB, 3 entries. phantom/child-safety-intents, coverage.access=gated; the command cannot exclude one namespace, so it is withheld as a whole

## work/sources units over 100 MB

| candidate | datasets | alloc GB | freed by this path alone GB | route | status | blocking reference / reason |
|---|---|---|---|---|---|---|
| stl-10 | stl-10 | 3.12 | 3.12 | none | blocked | registry baseline adapter_config path points here for stl-10; no retained native retrieval index for this body |
| next-native/vqa-constraints-movies.archive | vqa-constraints | 2.43 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) vqa-constraints@7b84c703; no retained native retrieval index for this body |
| next-native/fairface-images125.zip | fairface | 2.09 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) fairface@ef260300; no retained native retrieval index for this body |
| gqa | gqa | 1.78 | 1.78 | recipe_pinned_url | blocked | read by active prepared version(s) gqa@9c85e41a; registry baseline adapter_config path points here for gqa |
| next-native/vqa-constraints-known.archive | vqa-constraints | 1.60 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) vqa-constraints@7b84c703; no retained native retrieval index for this body |
| blink | blink | 1.58 | 1.58 | none | blocked | registry baseline adapter_config path points here for blink; no retained native retrieval index for this body |
| whoops | whoops | 1.38 | 1.38 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for whoops; no retained native retrieval index for this body |
| vlmbias/sbbench-synthetic-age-crop-true | sbbench-synthetic-age-crop-true | 1.37 | 1.37 | none | blocked | registry baseline adapter_config path points here for sbbench-synthetic-age-crop-true; no retained native retrieval index for this body |
| realworldqa | realworldqa | 1.36 | 1.36 | none | blocked | registry baseline adapter_config path points here for realworldqa; no retained native retrieval index for this body |
| hod | hod | 1.22 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) hod@c683a46b; no retained native retrieval index for this body |
| coco | coco | 1.07 | 1.07 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for coco; frozen selections: cocox69; no retained native retrieval index for this body |
| visual-genome | high-quality-hallucination-benchmark,visual-genome | 0.86 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) high-quality-hallucination-benchmark@83c0f8cb, visual-genome@faffc9e1; no retained native retrieval index for this body |
| clevr | clevr,clevr-v1-full | 0.85 | 0.85 | none | blocked | registry baseline adapter_config path points here for clevr, clevr-v1-full; frozen selections: clevrx27 |
| acquisition-20260923/whatsup | controlled-clevr,controlled-images,vg-qa-one... | 0.84 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) controlled-clevr@43163236, controlled-images@e2956837, vg-qa-one@f5722075, vg-qa-two@b140c3bf, what-s-up@2a86da80; no retained native retrieval index for this body |
| covid-19-radiography | covid-19-radiography | 0.82 | 0.00 | recipe_pinned_url | not_retrievable | only recorded route is the Kaggle API (login required) with an unpinned dataset version; read by active prepared version(s) covid-19-radiography@d0955977; no retained native retrieval index for this body |
| cifar-10 | cifar-10,cifar-10-1,cifar-100 | 0.72 | 0.18 | recipe_pinned_url | blocked | read by active prepared version(s) cifar-10@8cc4c641, cifar-100@6a1e646c; registry baseline adapter_config path points here for cifar-10, cifar-10-1, cifar-100; no retained native retrieval index for this body |
| emnist | emnist,emnist-balanced,emnist-letters | 0.70 | 0.14 | recipe_pinned_url | blocked | read by active prepared version(s) emnist-letters@5f8fcf97, emnist@b4c5dbb6; registry baseline adapter_config path points here for emnist-balanced; no retained native retrieval index for this body |
| perceptual-cinic/CINIC-10.tar.gz | cinic-10 | 0.69 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) cinic-10@f7e34bd1; no retained native retrieval index for this body |
| next-native/fairface-images025.zip | fairface | 0.58 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) fairface@ef260300; no retained native retrieval index for this body |
| svhn | svhn | 0.55 | 0.55 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for svhn; no retained native retrieval index for this body |
| mm-safetybench | mm-safetybench | 0.50 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) mm-safetybench@ef9dc9d1; no retained native retrieval index for this body |
| vlmbias/sbbench-synthetic-gender-crop-true | sbbench-synthetic-gender-crop-true | 0.50 | 0.50 | none | blocked | registry baseline adapter_config path points here for sbbench-synthetic-gender-crop-true; no retained native retrieval index for this body |
| waterbirds | waterbirds | 0.49 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) waterbirds@1661bca0; no retained native retrieval index for this body |
| perceptual-cinic/cache |  | 0.46 | 0.46 | none | blocked | no retained native retrieval index for this body |
| vlmbias/sbbench-synthetic-age-crop-false | sbbench-synthetic-age-crop-false | 0.43 | 0.43 | none | blocked | registry baseline adapter_config path points here for sbbench-synthetic-age-crop-false; no retained native retrieval index for this body |
| vibeeval | vibeeval | 0.41 | 0.41 | none | blocked | registry baseline adapter_config path points here for vibeeval; no retained native retrieval index for this body |
| artbench | artbench | 0.38 | 0.38 | recipe_pinned_url | blocked | read by active prepared version(s) artbench@aac58a52; registry baseline adapter_config path points here for artbench; no retained native retrieval index for this body |
| factoid | factoid | 0.37 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) factoid@0fb4824a; no retained native retrieval index for this body |
| cifar-100 | cifar-100 | 0.35 | 0.18 | recipe_pinned_url | blocked | read by active prepared version(s) cifar-100@6a1e646c; registry baseline adapter_config path points here for cifar-100; no retained native retrieval index for this body |
| acquisition-20260923/flowers102 | flowers102 | 0.34 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) flowers102@bf66416e; no retained native retrieval index for this body |
| acquisition-20260923/caltech101 | caltech101 | 0.29 | 0.01 | recipe_pinned_url | blocked | read by active prepared version(s) caltech101@119fce6c; no retained native retrieval index for this body |
| visualpuzzle | visualpuzzle | 0.28 | 0.28 | none | blocked | registry baseline adapter_config path points here for visualpuzzle; no retained native retrieval index for this body |
| acquisition-20260923/coco2014 | coco-2014 | 0.25 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) coco-2014@887d3867; no retained native retrieval index for this body |
| pach | activations-csv,pairs-csv,top16-images-csv | 0.25 | 0.25 | none | blocked | registry baseline adapter_config path points here for activations-csv, pairs-csv, top16-images-csv; no retained native retrieval index for this body |
| vlmbias/sbbench-synthetic-gender-crop-false | sbbench-synthetic-gender-crop-false | 0.24 | 0.24 | none | blocked | registry baseline adapter_config path points here for sbbench-synthetic-gender-crop-false; no retained native retrieval index for this body |
| mme | mme,mme-perception | 0.20 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) mme-perception@5f39a6a7, mme@2bfda63c; no retained native retrieval index for this body |
| vqa-v2 | pope,vqa-v2 | 0.19 | 0.19 | none | blocked | registry baseline adapter_config path points here for pope, vqa-v2 |
| acquisition-20260923/mmbench | mmbench | 0.18 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) mmbench@f5c02c04; no retained native retrieval index for this body |
| halueval | halueval | 0.17 | 0.17 | none | blocked | registry baseline adapter_config path points here for halueval; no retained native retrieval index for this body |
| resume-corpus | jiechieu-tsopze-resume-corpus | 0.17 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) jiechieu-tsopze-resume-corpus@ecd34030; no retained native retrieval index for this body |
| audioset-native-20261005 |  | 0.16 | 0.16 | none | blocked | no retained native retrieval index for this body |
| phantom | child-safety-intents,phantom | 0.16 | 0.00 | recipe_pinned_url | not_retrievable | coverage.access is child-safety-intents=gated, phantom=gated; no anonymous pinned public route, so never deleted; read by active prepared version(s) child-safety-intents@364a5168, phantom@41623e4d; no retained native retrieval ind |
| coverage-next | dreambooth,gvil,gvil-paired-illusion-images | 0.16 | 0.02 | recipe_pinned_url | blocked | read by active prepared version(s) dreambooth@81737aa4, gvil-paired-illusion-images@a8eb8f89; registry baseline adapter_config path points here for gvil; no retained native retrieval index for this body |
| idenprof | idenprof | 0.15 | 0.15 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for idenprof; no retained native retrieval index for this body |
| vhd11k | vhd11k | 0.14 | 0.14 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for vhd11k |
| mm-vet | mm-vet | 0.13 | 0.13 | recipe_pinned_url | blocked | registry baseline adapter_config path points here for mm-vet; no retained native retrieval index for this body |
| foil-it | foil-it | 0.13 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) foil-it@1f1ff6c2; no retained native retrieval index for this body |
| bbq | bbq | 0.11 | 0.11 | none | blocked | registry baseline adapter_config path points here for bbq; no retained native retrieval index for this body |

## work/prepared version sources over 100 MB (not linked from work/sources)

| candidate | datasets | alloc GB | freed by this path alone GB | route | status | blocking reference / reason |
|---|---|---|---|---|---|---|
| the-pile/8226558da4db7905b521f887b269dd80fc71ba7 | the-pile | 3.81 | 1.03 | recipe_pinned_url | not_retrievable | coverage.access is the-pile=unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) the-pile@8226558d; no retained native retrieval index for this body |
| tid2013/804772e053e2949104e99466a26de0cb26c41d5c | tid2013 | 2.75 | 1.80 | recipe_pinned_url | blocked | read by active prepared version(s) tid2013@804772e0; no retained native retrieval index for this body |
| factoid/0fb4824a01fd1854109f5658181fe28730cb732d | factoid | 2.39 | 2.02 | recipe_pinned_url | blocked | read by active prepared version(s) factoid@0fb4824a; no retained native retrieval index for this body |
| laion-400m/a8906cc1719e2386f7fd159ad6ccf0499eb38 | laion-400m | 1.80 | 0.00 | recipe_pinned_url | blocked | read by active prepared version(s) laion-400m@a8906cc1; no retained native retrieval index for this body |
| celeba/4d935f2df56cb83d9be936065e0fbff6617aad61e | celeba | 1.51 | 0.01 | recipe_pinned_url | blocked | read by active prepared version(s) celeba@4d935f2d; no retained native retrieval index for this body |
| imagenet-segmentation/f95f2951813c3ce629b694fbe7 | imagenet-segmentation | 1.34 | 0.00 | recipe_pinned_url | not_retrievable | coverage.access is imagenet-segmentation=unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) imagenet-segmentation@f95f2951; no retained native retrieval index for this body |
| objaverse/c74b675ffb039e3edfe8356e647587158df55a | objaverse | 1.22 | 0.62 | none | not_retrievable | coverage.access is objaverse=unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) objaverse@c74b675f; no retained native retrieval index for this body |
| what-s-up/2a86da80652409309e2aa863dbd7564736f13d | what-s-up | 0.85 | 0.00 | none | blocked | read by active prepared version(s) what-s-up@2a86da80; no retained native retrieval index for this body |
| oxfordpet/c812b4c6a2a467571c2dc4eb5e41b56c12609d | oxfordpet | 0.81 | 0.81 | none | blocked | read by active prepared version(s) oxfordpet@c812b4c6; no retained native retrieval index for this body |
| cinic-10/f7e34bd1657f83c19d7563105cb0a10c0d7d6ac | cinic-10 | 0.79 | 0.79 | none | blocked | read by active prepared version(s) cinic-10@f7e34bd1; no retained native retrieval index for this body |
| vg-qa-one/f572207512f2f00015071b0b5e4d3156a9fde0 | vg-qa-one | 0.69 | 0.00 | none | blocked | read by active prepared version(s) vg-qa-one@f5722075; no retained native retrieval index for this body |
| vg-qa-two/b140c3bfe0075e77bed1b5db226c9b6ba3199b | vg-qa-two | 0.69 | 0.00 | none | blocked | read by active prepared version(s) vg-qa-two@b140c3bf; no retained native retrieval index for this body |
| snli-ve/38ebf70968e4b7932b920b141a678fdd909d168f | snli-ve | 0.64 | 0.00 | none | not_retrievable | coverage.access is snli-ve=unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) snli-ve@38ebf709; no retained native retrieval index for this body |
| dtd/86d68f5ee62fa4c586c07a12f5c2d1bf113e372cb805 | dtd | 0.63 | 0.63 | none | blocked | read by active prepared version(s) dtd@86d68f5e; no retained native retrieval index for this body |
| ffhq/489a42999f69dcbb3e44d04c3b9acb50f4f1ee8a1d7 | ffhq | 0.55 | 0.28 | recipe_pinned_url | blocked | read by active prepared version(s) ffhq@489a4299; no retained native retrieval index for this body |
| cocogender/f30e7701915f03c0b5190d5ad04e23ae4d933 | cocogender | 0.53 | 0.47 | none | blocked | read by active prepared version(s) cocogender@f30e7701; no retained native retrieval index for this body |
| cc3m/da9a8efd7b8a48b1447508a2f1f393167444d872001 | cc3m | 0.38 | 0.38 | none | blocked | read by active prepared version(s) cc3m@da9a8efd; no retained native retrieval index for this body |
| openimages/9c91d0b38f2c0b20d1314f01ae6bb97677054 | openimages | 0.36 | 0.29 | none | blocked | no retained native retrieval index for this body |
| flowers102/bf66416e2c87239627de1757b0cfca135f04e | flowers102 | 0.35 | 0.35 | none | blocked | read by active prepared version(s) flowers102@bf66416e; no retained native retrieval index for this body |
| rs-vqa/b00690ce1ca99b37e578c825ba9798a4e4936c057 | rs-vqa | 0.34 | 0.32 | recipe_pinned_url | blocked | no retained native retrieval index for this body |
| spoken-wikipedia/2d4444b129f6ae9e1702175637c22a5 | spoken-wikipedia | 0.33 | 0.18 | recipe_pinned_url | blocked | read by active prepared version(s) spoken-wikipedia@2d4444b1; no retained native retrieval index for this body |
| miap/2236d45f9cff14869f35fa852e7b0c4aadb4188cab9 | miap | 0.25 | 0.25 | none | not_retrievable | coverage.access is miap=unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) miap@2236d45f; no retained native retrieval index for this body |
| senator-tweets-2021/47e5564df91d1cbbb471a9eede20 | senator-tweets-2021 | 0.23 | 0.23 | none | blocked | read by active prepared version(s) senator-tweets-2021@47e5564d; no retained native retrieval index for this body |
| lingoqa/5fd702851af0eb6816d8b7bdd0636b97c5b1a4fc | lingoqa | 0.23 | 0.23 | recipe_pinned_url | blocked | read by active prepared version(s) lingoqa@5fd70285; no retained native retrieval index for this body |
| llava-instruct-150k/befd4bb56018b6d5b330b1b9a76a | llava-instruct-150k | 0.23 | 0.23 | recipe_pinned_url | blocked | read by active prepared version(s) llava-instruct-150k@befd4bb5; no retained native retrieval index for this body |
| algopuzzlevqa/d7290b7a41f1d5598624f81657149d6b13 | algopuzzlevqa | 0.23 | 0.23 | none | not_retrievable | coverage.access is algopuzzlevqa=source_page_public_data_unverified; no anonymous pinned public route, so never deleted; read by active prepared version(s) algopuzzlevqa@d7290b7a; no retained native retrieval index for this body |
| pascal-voc/cecb7ca799654e6e3714f178e1e76fc3c736b | pascal-voc | 0.18 | 0.18 | none | blocked | read by active prepared version(s) pascal-voc@cecb7ca7 |
| emoset/32ecd4a024d785b728a9997f89954b95b46c6bf98 | emoset | 0.17 | 0.13 | none | blocked | read by active prepared version(s) emoset@32ecd4a0 |
| audioset/d6b1feb521bd970f68496251923c094b73f0896 | audioset | 0.16 | 0.16 | recipe_pinned_url | blocked | read by active prepared version(s) audioset@d6b1feb5; no retained native retrieval index for this body |
| hallusionbench/4409608d811110c75d2a47ca743017e61 | hallusionbench | 0.15 | 0.15 | none | blocked | read by active prepared version(s) hallusionbench@4409608d; no retained native retrieval index for this body |
| datacomp-1b/ab636cb10a13e59e59bfe3ddaf0d8d81cfd6 | datacomp-1b | 0.13 | 0.13 | recipe_pinned_url | blocked | read by active prepared version(s) datacomp-1b@ab636cb1; no retained native retrieval index for this body |

## Other classes

- factoid native.gzip source link (clean dry run: source_links) (blocked): no net bytes
- atlas datasets prune (dry run) (blocked): no bytes to reclaim; sbbench is a gated dataset; skipped
- atlas storage compact (not run) (blocked): compact writes additional persistent copies and removes no source file (docs/storage.md); clean dry run lists compressed_copies=[] so there is nothing unprotected to evict; no demonstrated reduction of non-preview image bytes

## Kept, never candidates

- work/prepared active and frozen versions: 77.45 GB
- Qwen2.5-VL weights (external root): 7.52 GB
- .venv: 6.92 GB
- work/models (SigLIP2, MiniLM, detectors): 1.72 GB
- work/compact-media (protected preview originals): 2.00 GB
- work/snapshots (frozen canonical snapshots): 1.39 GB
- work/original-access (native indices, routes, receipts): 0.87 GB

## Next candidates and the cost in retrievability

Removing any of these needs a route made first: `atlas storage index-original` (reads the local body, writes a member index) then `retire-original` (fresh remote probes, installs preview routes). That step was not run because it is not among the commands this task allows. Where the recipe URL is a whole-file host without range support, the original would have to be re-downloaded in full to read any member.

| candidate | GB | recipe route | cost |
|---|---|---|---|
| tid2013/804772e053e2949104e99466a26de0cb26c41d | 2.75 | pinned in recipe | re-download of the covered archive(s), 0.96 GB; www.ponomarenko.info: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| next-native/vqa-constraints-movies.archive | 2.43 | pinned in recipe | re-download of the covered archive(s), 2.43 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| factoid/0fb4824a01fd1854109f5658181fe28730cb73 | 2.39 | pinned in recipe | re-download of the covered archive(s), 0.37 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| next-native/fairface-images125.zip | 2.09 | pinned in recipe | re-download of the covered archive(s), 2.09 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| laion-400m/a8906cc1719e2386f7fd159ad6ccf0499eb | 1.80 | pinned in recipe | re-download of the covered archive(s), 1.80 GB; deploy.laion.ai: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| gqa | 1.78 | pinned in recipe | re-download of the covered archive(s), 1.50 GB; downloads.cs.stanford.edu: whole-file HTTPS download, sha256 pinned in recipe, range support not probe |
| next-native/vqa-constraints-known.archive | 1.60 | pinned in recipe | re-download of the covered archive(s), 1.60 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| celeba/4d935f2df56cb83d9be936065e0fbff6617aad6 | 1.51 | pinned in recipe | re-download of the covered archive(s), 1.44 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| whoops | 1.38 | pinned in recipe | re-download of the covered archive(s), 0.69 GB; Hugging Face pinned revision (ETag range-capable); gated repos need the researcher token |
| hod | 1.22 | pinned in recipe | re-download of the covered archive(s), 1.22 GB; GitHub pinned ref: whole-file download, sha256 pinned, no ranges |
| coco | 1.07 | pinned in recipe | re-download of the covered archive(s), 1.07 GB; s3.amazonaws.com: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| visual-genome | 0.86 | pinned in recipe | re-download of the covered archive(s), 0.79 GB; homes.cs.washington.edu: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| acquisition-20260923/whatsup | 0.84 | pinned in recipe | re-download of the covered archive(s), 0.84 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| cifar-10 | 0.72 | pinned in recipe | re-download of the covered archive(s), 0.34 GB; www.cs.toronto.edu: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| emnist | 0.70 | pinned in recipe | re-download of the covered archive(s), 0.56 GB; biometrics.nist.gov: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| perceptual-cinic/CINIC-10.tar.gz | 0.69 | pinned in recipe | re-download of the covered archive(s), 0.69 GB; datashare.ed.ac.uk: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| next-native/fairface-images025.zip | 0.58 | pinned in recipe | re-download of the covered archive(s), 0.58 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| svhn | 0.55 | pinned in recipe | re-download of the covered archive(s), 0.25 GB; ufldl.stanford.edu: whole-file HTTPS download, sha256 pinned in recipe, range support not probed |
| ffhq/489a42999f69dcbb3e44d04c3b9acb50f4f1ee8a1 | 0.55 | pinned in recipe | re-download of the covered archive(s), 0.27 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |
| mm-safetybench | 0.50 | pinned in recipe | re-download of the covered archive(s), 0.50 GB; Google Drive share link: sha256 pinned in recipe, no ETag or range guarantee, availability not probed |

All 41 blocked candidates with a recipe route sum to 31.18 GB allocated, more than the 23.43 GB gap, but each one is read by an active prepared or registry version and would first need an index and a retire-original run that verifies its previews.

