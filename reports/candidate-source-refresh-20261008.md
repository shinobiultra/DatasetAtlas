# Candidate-source refresh, 2026-10-08

98 catalogue entries with no preview and a release that is not paper-private. Each URL was probed by HEAD (or a 1-byte ranged GET); no payload was downloaded and no credentials were sent. `unreachable`, a WAF challenge and a Google Drive page are no information and keep the prior state. A reachable landing page is not evidence that the data is public. `released_after_audit` and `still_unreleased` come only from a dated reading of public pages by the implementing agent (not human-reviewed, not a probe); the latest such reading stands unless a pinned data file appears.

Provenance: Observations were made live on 2026-10-08: 114 URLs probed between 2026-10-08T04:58:00Z and 2026-10-08T04:59:07Z (workers 4, 1.0 s between requests to a host, timeout 15.0 s, 2 attempts). The classification, the registry notes and these receipts were replayed from those recorded observations at 2026-10-08T05:08:44Z after a code change, with no network access; the replay did no probing. 10 further URLs carry the latest observation recorded by probe_sources --extra in reports/source-reprobe-20261008.json (2026-10-08T03:40:40Z to 2026-10-08T04:03:58Z).

Dispositions: `unchanged` 22; `now_public_pinnable` 0; `public_unpinned` 72; `now_gated` 1; `released_after_audit` 0; `still_unreleased` 3.

Legend: `unchanged` the recorded state stands: no new information, or the answer says nothing about the files; `now_public_pinnable` a data file answers without credentials and carries a pin; a candidate for integration only; `public_unpinned` a recorded page answers without credentials and nothing on a data file is pinned; this does not establish that the data itself is public; `now_gated` a source answered 401/403 (or an agent reading found a gate) on an entry not recorded as gated; unconfirmed; `released_after_audit` an agent reading of public pages found a release; not human-reviewed, identity not verified; `still_unreleased` an agent reading of public pages located no public release; not human-reviewed.

`Record also says` lists what the entry's own blockers, rights note and earlier audit notes already record (a login, a request or terms form, a licence agreement, a gate, a recipe, an in-house cohort, an outage), found by a keyword rule; it never changes a disposition.

| Entry | Recorded access | Disposition | Latest probe | Record also says | Note |
| --- | --- | --- | --- | --- | --- |
| `artbench-2` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `artchive` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `asteroids-rom` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `bam-fg` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `brain-score` | platform_public_dataset_varies | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `brca` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `broden` | public | unchanged | unreachable - (+5 URLs) | host outage | data-file URL unreachable; the reachable page says nothing about the files. |
| `chicago-face-database` | gated | unchanged | reachable 200 | access request or terms; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `cifar-2` | source_page_public_data_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `coco-caption` | public | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `coco-demographic-annotations` | author_request_required | unchanged | reachable 200 | access request or terms | recorded gate unchanged; a reachable page says nothing about the files. |
| `coco-detection-dataset` | base_source_public_variant_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `coco-gender` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `coco-spatial` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `coco-train` | public | public_unpinned | reachable 200 (+2 URLs) | - | landing page reachable; no data file, no pin. |
| `cocogendertxt` | base_source_public_variant_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `concept-editing-dataset` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `conceptual-captions` | base_source_public_variant_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `contrastive-prompts` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `cub` | base_source_public_variant_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `cub200` | public | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `custom-dataset` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `custom-image-editing-dataset` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `custom-neonatal-rat-ganglion-recordings` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `custom-speech-segment-collection` | unverified | still_unreleased | reachable 200 | licence agreement; in-house or no public release | Agent reading, not human-reviewed: No public release of the segment collection was located on the paper's NeurIPS page. The component corpora have their own access routes (WSJ: LDC licence; Spoken Wikipedia: public project), tracked under their own catalogue entries. |
| `custom-ternus-psychophysics-responses` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `dall-e-generated-target-images` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `deepfashion` | unverified | public_unpinned | reachable 200 | access request or terms; licence agreement | landing page reachable; no data file, no pin. |
| `donkey-kong-rom` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `e-ic` | unverified | public_unpinned | reachable 200 (+5 URLs) | - | landing page reachable; no data file, no pin. |
| `e-vqa` | unverified | public_unpinned | reachable 200 (+3 URLs) | - | landing page reachable; no data file, no pin. |
| `facet` | gated | unchanged | reachable 200 (+1 URL) | access request or terms; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `facial-expression-recognition-2013` | gated | unchanged | reachable 200 (+1 URL) | login or registration | recorded gate unchanged; a reachable page says nothing about the files. |
| `fer-2013` | gated | unchanged | gone 404 | login or registration; licence agreement; in-house or no public release | gone (HTTP 404), a single observation; prior state kept. |
| `fgvc` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `first-person-social-interactions-dataset` | public | public_unpinned | reachable 200 (+1 URL) | host outage | landing page reachable; no data file, no pin. |
| `flowers` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `gaussian-rubbish-examples` | unverified | still_unreleased | reachable 200 | recipe, not a release | Agent reading, not human-reviewed: The arXiv page and the paper text name no released examples or code for this experiment; the abstract page lists no code or data link. Regenerating the set needs only the stated distribution. |
| `gda-adversarial-image-variants` | unverified | still_unreleased | reachable 200 | - | Agent reading, not human-reviewed: The arXiv page (v2, marked under review) and the HTML text state no code, adversarial images or other release. None was located. |
| `google-web-1t-corpus` | gated | unchanged | reachable 200 | login or registration; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `gpt-4v-filtered-vl-gender-subset` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `group-labels` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `gyafc` | request_required | unchanged | reachable 200 (+1 URL) | access request or terms | recorded gate unchanged; a reachable page says nothing about the files. |
| `hellaswag-pro` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `ictcf` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `illusionbench` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `illusory-vqa` | base_source_public_variant_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `imagenet` | gated | unchanged | reachable 200 (+1 URL) | login or registration | recorded gate unchanged; a reachable page says nothing about the files. |
| `imagenet-ilsvrc` | gated | unchanged | reachable 200 (+1 URL) | login or registration | recorded gate unchanged; a reachable page says nothing about the files. |
| `imagenet-sampled-1-000-images` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `imagenet100` | gated | unchanged | reachable 200 | login or registration; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `imagenetval` | gated | unchanged | reachable 200 (+1 URL) | login or registration | recorded gate unchanged; a reachable page says nothing about the files. |
| `itac` | unverified | public_unpinned | reachable 200 | in-house or no public release | landing page reachable; no data file, no pin. |
| `laion` | unverified | public_unpinned | reachable 200 (+1 URL) | gated | landing page reachable; no data file, no pin. |
| `laion-aesthetics` | unverified | now_gated | reachable 200 (+2 URLs) | access request or terms; licence agreement; gated | Agent reading, not human-reviewed: The LAION Hugging Face dataset page for laion2B-en-aesthetic (parquet, about 8.35 GB) is gated behind an agreement to share contact information. The page was read without signing in and the terms were not accepted. LAION's Re-LAION-5B release is likewise gated (laion.ai/blog/r... |
| `middlebury` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. An agent reading of public pages is recorded on the entry (not human-reviewed). |
| `ms-coco` | public | public_unpinned | reachable 200 (+2 URLs) | - | landing page reachable; no data file, no pin. |
| `ms-coco-7f846b38` | public | public_unpinned | reachable 200 (+2 URLs) | - | landing page reachable; no data file, no pin. |
| `ms-coco-captions` | public | public_unpinned | reachable 200 (+2 URLs) | - | landing page reachable; no data file, no pin. |
| `ms-cxr` | gated | unchanged | reachable 200 (+1 URL) | login or registration; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `mscoco` | public | public_unpinned | reachable 200 (+2 URLs) | - | landing page reachable; no data file, no pin. |
| `mscoco-100-target-subset` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `multitrust` | gated | unchanged | reachable 200 (+1 URL) | gated | recorded gate unchanged; a reachable page says nothing about the files. |
| `nips17` | unverified | public_unpinned | reachable 200 | login or registration | landing page reachable; no data file, no pin. |
| `ostris-dataset` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `paper-08e415961919a492-unnamed-11-image-inpainting-set` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `paper-08e415961919a492-unnamed-real-noise-benchmark-46` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `paper-164d7c221452ffec-unnamed-cfd-morph-collection` | gated | unchanged | reachable 200 (+2 URLs) | access request or terms; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` | gated | unchanged | reachable 200 | access request or terms; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. An agent reading of public pages is recorded on the entry (not human-reviewed). |
| `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. An agent reading of public pages is recorded on the entry (not human-reviewed). |
| `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `paper-944952997d24ce45-unnamed-vma-candidate-pool` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `pata` | public | public_unpinned | reachable 200 (+3 URLs) | - | landing page reachable; no data file, no pin. |
| `perturbed-gender-benchmark-image-variants` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `pitfall-rom` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `raise1k` | unverified | public_unpinned | reachable 200 | access request or terms | landing page reachable; no data file, no pin. |
| `robustbench` | public | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `rosmap` | request_required | unchanged | reachable 200 (+1 URL) | - | recorded gate unchanged; a reachable page says nothing about the files. |
| `sb-syn` | public | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `sb-syn-crop` | public | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `sbbench` | gated | unchanged | gated_or_forbidden 401 (+2 URLs) | access request or terms; gated | HTTP 401 re-observed; the recorded gate stands. |
| `scrambled-mnist` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `shiftmnist` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `simulated-transistor-traces` | unverified | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `space-invaders-rom` | source_release_unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `timit` | gated | unchanged | reachable 200 | login or registration; licence agreement | recorded gate unchanged; a reachable page says nothing about the files. |
| `via-bench` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `visu` | gated | unchanged | reachable 200 (+1 URL) | - | recorded gate unchanged; a reachable page says nothing about the files. |
| `visual-counterfact-filtered-467` | unverified | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
| `visualqa` | public | public_unpinned | reachable 200 (+1 URL) | - | landing page reachable; no data file, no pin. |
| `vl-gender` | unverified | unchanged | reachable 200 | recipe, not a release | Agent reading, not human-reviewed: The README directs users to run setup_data.sh, which downloads and processes the source datasets (about 100 GB of disk and about 24 hours per the README). It offers no hosted copy of the 5,000 selected images; the recipe is public, but each source dataset keeps its own access ... |
| `vlagenderbias` | unverified | public_unpinned | reachable 200 | recipe, not a release | landing page reachable; no data file, no pin. |
| `vtab` | unverified | unchanged | reachable 200 (+1 URL) | - | Agent reading, not human-reviewed: The code repository loads the member datasets through TensorFlow Datasets; its README says Diabetic Retinopathy and Resisc45 cannot be downloaded automatically. There is no single VTAB archive to pin; each member dataset has its own source. |
| `wall-street-journal` | unverified | public_unpinned | reachable 200 (+1 URL) | licence agreement | landing page reachable; no data file, no pin. |
| `wilds` | public | public_unpinned | reachable 200 | - | landing page reachable; no data file, no pin. |
