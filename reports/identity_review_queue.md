# Identity review queue

These are decisions for a person. Nothing in this file changes any registry record: `coverage.identity`, `release`, `preview`, `adapter` and every other field stay exactly as they are until a person records a decision. Recommendations are not acceptance, and no option below is ranked or preferred.

## How to read this

- An entry is here because the registry records its `coverage.identity` as `candidate` or `family_or_variant_candidate`: a paper mentions the name, but the exact release, variant or subset the paper used is not human-verified. Every such entry appears exactly once.
- Entries the registry already links with `same_source_family_as`, `derived_from`, `annotation_overlay_of` or `source_subset_of` to the same target share a group. Nothing is grouped by name similarity. A group is a reading aid: each entry is decided on its own.
- Options. `alias_of:<id>`: the paper's name is another name for that registry entry. `distinct_release`: the paper's dataset is a release of its own. `accept_unreleased_custom_record`: a paper-private dataset with no public release, kept as an unreleased custom record. `keep_candidate`: leave the identity open.
- Preview and adapter states come from `reports/dataset_coverage.csv`, the merged catalogue view; identity, links, access and evidence come from `registry/datasets/*.yaml`. A link to a prepared family is a pointer, never coverage: an entry whose preview is `none` stays `none` until a person decides.
- Blocker types. `identity`: the exact release, variant or subset is not human-verified (a family alias or variant of another entry, or a name with no link). `access`: the data is gated or needs a request, which is a user action and not an identity question. `unreleased`: the registry records a paper-private dataset with no public release. `source_availability`: the registry's latest access audit records the source host as unresponsive or unresolvable. `adapter`: identity is settled and only an adapter is missing; such entries are outside this queue, so no entry below has this type.
- IDs. `IR-NNN` comes from `registry/identity-review-ids.json`. An assignment is never renumbered or reused; a group seen for the first time takes the next free number.
- Quoted lines (`>`) are text exactly as the registry stores it; paper excerpts are shortened to 200 characters.
- Each group is also appended once to `work/corpus/review_queue.jsonl` as a `kind: identity_decision` record with `status: open`.

## Summary

145 entries in 120 groups; 10 groups hold more than one entry.

Blocker types: `identity` 117, `access` 11, `unreleased` 16, `source_availability` 1, `adapter` 0.

Preview states of the entries: `none` 100, `complete_target` 45.

Groups with more than one entry: IR-014 (14), IR-019 (2), IR-032 (2), IR-034 (2), IR-037 (2), IR-044 (2), IR-050 (5), IR-059 (2), IR-095 (2), IR-096 (2).

### Groups

| IR | Group | Entries | Preview states | Prepared target | Options |
| --- | --- | --- | --- | --- | --- |
| IR-001 | `agent-security-bench` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-002 | `artbench-2` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-003 | `artchive` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-004 | `asteroids-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-005 | `bam-fg` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-006 | `bapps` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-007 | `brca` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-008 | `causalgym` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-009 | `conceptual-captions` | 1 | none 1 | `cc3m` (complete_target) | `alias_of:cc3m`, `distinct_release`, `keep_candidate` |
| IR-010 | `child-safety-intents` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-011 | `cifar-2` | 1 | none 1 | `cifar-10` (complete_target) | `alias_of:cifar-10`, `distinct_release`, `keep_candidate` |
| IR-012 | `cifar-100-c` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-013 | `cinic-10` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-014 | linked to `coco`, `coco-one`, `coco-two`, `cocogender` | 14 | none 11, complete_target 3 | `coco` (complete_target), `coco-one` (complete_target; also in this queue), `coco-two` (complete_target; also in this queue), `cocogender` (complete_target; also in this queue) | `alias_of:coco`, `alias_of:coco-one`, `alias_of:coco-two`, `alias_of:cocogender`, `distinct_release`, `keep_candidate` |
| IR-015 | `concept-editing-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-016 | `contrastive-prompts` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-017 | `controlled-clevr` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-018 | `controlled-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-019 | linked to `cub-200-2011` | 2 | none 2 | `cub-200-2011` (complete_target) | `alias_of:cub-200-2011`, `distinct_release`, `keep_candidate` |
| IR-020 | `custom-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-021 | `custom-image-editing-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-022 | `custom-neonatal-rat-ganglion-recordings` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-023 | `custom-speech-segment-collection` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-024 | `custom-ternus-psychophysics-responses` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-025 | `dall-e-generated-target-images` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-026 | `deepfashion` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-027 | `donkey-kong-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-028 | `e-ic` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-029 | `e-vqa` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-030 | `emoset` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-031 | `factoid` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-032 | linked to `fairface`, `miap`, `phase` | 2 | none 1, complete_target 1 | `fairface` (complete_target), `miap` (complete_target), `phase` (complete_target) | `alias_of:fairface`, `alias_of:miap`, `alias_of:phase`, `distinct_release`, `keep_candidate` |
| IR-033 | `ffhq` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-034 | linked to `fgvc-aircraft` | 2 | none 1, complete_target 1 | `fgvc-aircraft` (complete_target; also in this queue) | `alias_of:fgvc-aircraft`, `distinct_release`, `keep_candidate` |
| IR-035 | `finevision` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-036 | `first-person-social-interactions-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-037 | linked to `flowers102` | 2 | none 1, complete_target 1 | `flowers102` (complete_target; also in this queue) | `alias_of:flowers102`, `distinct_release`, `keep_candidate` |
| IR-038 | `food101` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-039 | `gaussian-rubbish-examples` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-040 | `gda-adversarial-image-variants` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-041 | `gpt-4v-filtered-vl-gender-subset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-042 | `group-labels` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-043 | `gvil-paired-illusion-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-044 | linked to `hc-bench` | 2 | none 2 | `hc-bench` (local_only) | `alias_of:hc-bench`, `distinct_release`, `keep_candidate` |
| IR-045 | `hellaswag-pro` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-046 | `ictcf` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-047 | `illusionbench` | 1 | none 1 | `illusionbench-3c643c29` (complete_target) | `alias_of:illusionbench-3c643c29`, `distinct_release`, `keep_candidate` |
| IR-048 | `illusionmnist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-049 | `illusory-vqa` | 1 | none 1 | `illusionvqa` (complete_target) | `alias_of:illusionvqa`, `distinct_release`, `keep_candidate` |
| IR-050 | linked to `imagenet`, `imagenet-1k`, `imagenet-ilsvrc-2012` | 5 | none 5 | `imagenet-1k` (complete_target), `imagenet-ilsvrc-2012` (complete_target) | `alias_of:imagenet`, `alias_of:imagenet-1k`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate` |
| IR-051 | `itac` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-052 | `laion` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-053 | `laion-aesthetics` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-054 | `llava-instruct-150k-3a74a703` | 1 | complete_target 1 | `llava-instruct-150k` (complete_target) | `alias_of:llava-instruct-150k`, `distinct_release`, `keep_candidate` |
| IR-055 | `middlebury` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-056 | `mit-states` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-057 | `mma-diffusion` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-058 | `mmstar` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-059 | linked to `mnist` | 2 | none 2 | `mnist` (complete_target) | `alias_of:mnist`, `distinct_release`, `keep_candidate` |
| IR-060 | `multitrust` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-061 | `ostris-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-062 | `paper-08e415961919a492-unnamed-11-image-inpainting-set` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-063 | `paper-08e415961919a492-unnamed-real-noise-benchmark-46` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-064 | `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-065 | `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-066 | `paper-164d7c221452ffec-unnamed-cfd-morph-collection` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-067 | `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-068 | `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-069 | `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-070 | `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-071 | `paper-728d8c0964b540ad-unnamed-youtube-image-collection` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-072 | `paper-765a2362f8735bc4-unnamed-social-category-question-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-073 | `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-074 | `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-075 | `paper-944952997d24ce45-unnamed-vma-candidate-pool` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-076 | `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-077 | `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-078 | `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-079 | `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-080 | `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-081 | `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-082 | `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-083 | `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-084 | `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-085 | `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` | 1 | none 1 | no link | `accept_unreleased_custom_record`, `keep_candidate` |
| IR-086 | `pascal-voc` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-087 | `pata` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-088 | `perturbed-gender-benchmark-image-variants` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-089 | `pitfall-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-090 | `places` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-091 | `raise1k` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-092 | `ring-a-bell` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-093 | `rosmap` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-094 | `rs-vqa` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-095 | linked to `saegis-clean-and-adversarial-splits` | 2 | none 1, complete_target 1 | `saegis-clean-and-adversarial-splits` (complete_target; also in this queue) | `alias_of:saegis-clean-and-adversarial-splits`, `distinct_release`, `keep_candidate` |
| IR-096 | linked to `sbbench`, `sbbench-syn`, `sbbench-syn-crop` | 2 | none 2 | `sbbench-syn` (complete_target), `sbbench-syn-crop` (complete_target) | `alias_of:sbbench`, `alias_of:sbbench-syn`, `alias_of:sbbench-syn-crop`, `distinct_release`, `keep_candidate` |
| IR-097 | `seedbench` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-098 | `set14` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-099 | `set5` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-100 | `shapes-localization` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-101 | `shapes-recognition` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-102 | `shapes-relations` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-103 | `simulated-transistor-traces` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-104 | `space-invaders-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-105 | `tid2013` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-106 | `turing-eye-test` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-107 | `ucf101` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-108 | `vg-qa-one` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-109 | `vg-qa-two` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-110 | `via-bench` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-111 | `visual-counterfact` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-112 | `visual-counterfact-filtered-467` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-113 | `visual6502-transistor-netlist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-114 | `vl-gender` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-115 | `vqa-constraints` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-116 | `visualqa` | 1 | none 1 | `vqa-v2` (complete_target) | `alias_of:vqa-v2`, `distinct_release`, `keep_candidate` |
| IR-117 | `vqa-v2-m-n-subsets` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-118 | `vtab` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-119 | `wall-street-journal` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-120 | `wilds` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |

## Public sources whose adapter is not started

These entries have access `public` and adapter `not_started`. For each, what blocks it, read from the registry's own state:

- `coco-caption` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_mentioned_split_unresolved` (2026-09-22).
  Registry blockers:
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- `coco-train` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `ms-coco` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `ms-coco-7f846b38` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `ms-coco-captions` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `mscoco` (group IR-014) — blocker type **identity**: a family alias or variant of `coco`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `cub200` (group IR-019) — blocker type **identity**: a family alias or variant of `cub-200-2011`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `first-person-social-interactions-dataset` (group IR-036) — blocker type **source_availability**. The registry's latest access audit (2026-10-08) records `author_page_identified_media_host_unresolvable`: the source host did not answer or did not resolve. This is source availability, not identity.
  Registry identity audit: `original_source_and_author_reformat_distinct` (2026-09-22).
  Registry description:
  > First-Person Social Interactions Dataset (FPSI) and Watanabe training selection.
  Registry blockers:
  > The author page (ai.stanford.edu/~alireza/Disney/) links 113 AVI videos and annotation ZIPs hosted on webshare.ipat.gatech.edu over plain HTTP; the host did not answer a HEAD request within 30 s over either http or https on 2026-10-06 (an upstream availability problem to retry).
  > The videos are AVI files, which browsers cannot play, and the host is HTTP-only, which Atlas's fetch layer does not use: even when the host returns, preparation needs a transcoding or an HTTPS mirror (an implementation gap beyond the outage).
  > The citing paper's training selection (the Watanabe selection) is not identified, and the page states no licence.
- `sb-syn` (group IR-096) — blocker type **identity**: a family alias or variant of `sbbench-syn`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `sb-syn-crop` (group IR-096) — blocker type **identity**: a family alias or variant of `sbbench-syn-crop`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_only` (2026-09-22).
  Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- `visualqa` (group IR-116) — blocker type **identity**: a family alias or variant of `vqa-v2`, whose release is already prepared (preview `complete_target`); the paper's exact release for this entry is unresolved. The adapter is not what blocks it.
  Registry identity audit: `family_mentioned_version_unresolved` (2026-09-22).
  Registry blockers:
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- `wilds` (group IR-120) — blocker type **identity**: no registry link to a prepared release; the paper's exact release, variant or component is unresolved.
  Registry identity audit: `family_only` (2026-09-22).
  Registry description:
  > WILDS is a collection of ten distribution-shift datasets across modalities; no single WILDS media release.
  Registry blockers:
  > Exact source variant or paper release is unresolved.
  > Adapter and preview are not implemented.

## IR-001 · Agent Security Bench

**Group key:** `agent-security-bench` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `agent-security-bench` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `agent-security-bench` — Agent Security Bench

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_protocol_located` (2026-09-22).
- Registry blockers:
  > Public source page located; exact paper-used data revision or archive is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-fdcf898e0b05daff`, page 33, role: bibliography-only reference
    > uang, Kai Mei, Yifei Yao, Zhenting Wang, Chenlu Zhan, Hongwei Wang, and Yongfeng Zhang. Agent security bench (asb): Formalizing and benchmarking attacks and defenses in llm-based agents, 2025b. URL h…

## IR-002 · Artbench-2

**Group key:** `artbench-2` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `artbench-2` — Artbench-2

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `derived_subset_identity_partly_resolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > Artbench-2 (Jha et al., 2024) CLIP —

## IR-003 · Artchive

**Group key:** `artchive` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `artchive` — Artchive

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_specific_image_manifest_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > , MoCov3, CLIP, ViT, — ImageNet-1K, BAM-FG, Artchive, ALADIN, SSCD

## IR-004 · Asteroids ROM

**Group key:** `asteroids-rom` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `asteroids-rom` — Asteroids ROM

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `source_binary_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 18, role: exclusion
    > OMs (Donkey Kong, Space Invaders, Pitfall, and Asteroids) ultimately choosing the first three as they reliably drove the TIA and subsequently p

## IR-005 · BAM-FG

**Group key:** `bam-fg` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `bam-fg` — BAM-FG

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `identity_resolved_release_access_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > DINO, MoCov3, CLIP, ViT, — ImageNet-1K, BAM-FG, Artchive, ALADIN, SSCD

## IR-006 · BAPPS

**Group key:** `bapps` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `bapps` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `bapps` — BAPPS

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-666de2b7486d80a3`, page 3, role: introduction
    > 1: Dataset comparison. A primary differentiator between our proposed Berkeley-Adobe Perceptual Patch Similarity (BAPPS) dataset and previous work is scale of distortion types. We provide human percep…

## IR-007 · BRCA

**Group key:** `brca` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `brca` — BRCA

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `project_resolved_paper_slice_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > DensetNet-121 — ITAC, iCTCF, BRCA, ROSMAP (Basu et al., 2024b) SD-1.5, SD-XL, DeepFloyd Model Editin

## IR-008 · CausalGym

**Group key:** `causalgym` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `causalgym` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `causalgym` — CausalGym

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_protocol_located` (2026-09-22).
- Registry blockers:
  > Public source page located; exact paper-used data revision or archive is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 2 papers:
  - `paper-8729802cb62942f0`, page 8, role: bibliography-only reference
    > topher Potts. der): Fazl Barez, Yonatan Belinkov, Yanai Elazar, 2024. CausalGym: Benchmarking causal inter- Thomas Fel, Neel Nanda, Chris Olah, Yuval Pin- pretability methods on linguistic
  - `paper-2ae8012d97e5e3da`, page 46, role: bibliography-only reference
    > n & review, 26(4): 1174–1194, 2019. Aryaman Arora, Dan Jurafsky, and Christopher Potts. CausalGym: Benchmarking causal interpretability methods on linguistic tasks. In Lun-Wei Ku, Andre Mar- tins, an…

## IR-009 · Conceptual Captions, linked to `cc3m`

**Group key:** `cc3m` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `cc3m` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `cc3m`. The options are `alias_of:cc3m` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `cc3m`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:cc3m`, `distinct_release`, `keep_candidate`

### `conceptual-captions` — Conceptual Captions

- State: access `base_source_public_variant_unverified`, adapter `not_started`, preview `none`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. The registry links this entry to `cc3m` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:cc3m`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `cc3m`
- Registry identity audit: `official_family_located_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > matzadeh, MMT, SMT Verb Understanding Conceptual Captions 2021) (Dahlgren Lindström et al., VSE++, VSE-C, H

## IR-010 · Child Safety intents

**Group key:** `child-safety-intents` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `child-safety-intents` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used. For `child-safety-intents` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `child-safety-intents` — Child Safety intents

- State: access `gated`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `derived_overlay_not_independent_release` (2026-09-22).
- Registry blockers:
  > Original-source registration, contact sharing, or licensed subscription is required.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2df1203e2d3767bb`, page 6, role: introduced intent overlay
    > ], MM- SafetyBench [2], OmniSafeBench-MM [4], and SafeBench [33]. Moreover, we added 747 intents related to the new Child Safety category, generated with the assistance of OpenAI GPT-5.4, accessed vi…

## IR-011 · CIFAR-2, linked to `cifar-10`

**Group key:** `cifar-10` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `cifar-10` (identity `resolved`, preview `complete_target`) via `derived_from` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `cifar-10`. The options are `alias_of:cifar-10` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `cifar-10`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:cifar-10`, `distinct_release`, `keep_candidate`

### `cifar-2` — CIFAR-2

- State: access `source_page_public_data_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `cifar-10` (identity `resolved`, preview `complete_target`) via `derived_from`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:cifar-10`, `distinct_release`, `keep_candidate`
- Registry links: `derived_from` → `cifar-10`
- Registry identity audit: `derived_protocol_located` (2026-09-22).
- Registry blockers:
  > Public source page located; exact paper-used data revision or archive is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > 024) DDPM — CIFAR-10, CIFAR-2, ArtBench (Park et al., 2023) ResNet-9; ResNet-18; BERT —

## IR-012 · CIFAR-100-C

**Group key:** `cifar-100-c` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `cifar-100-c` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `cifar-100-c` — CIFAR-100-C

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-a47845c66d4a3f48`, page 18, role: corruption evaluation
    > R-100 datasets [75] are obtained via the PyTorch loaders [105], while CIFAR-10-C and CIFAR-100-C [58], with the common corruptions, are downloaded from the official release (see https://zenodo.org/re…

## IR-013 · CINIC-10

**Group key:** `cinic-10` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `cinic-10` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `cinic-10` — CINIC-10

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
- Mentioned by 1 paper:
  - `paper-a47845c66d4a3f48`, page 7, role: evaluation
    > o dataset resampling bias (CIFAR-10.1, [112]) and image source shift (CINIC-10, [31]). For each of these datasets, we measure standard accuracy, and Fig. 3 shows that improvement in robust

## IR-014 · 14 entries linked to `coco`, `coco-one`, `coco-two`, `cocogender`

**Group key:** `coco|coco-one|coco-two|cocogender` · **Entries:** 14 · **Blocker types:** `identity` 14

**Linked to:**

- `coco` (identity `resolved`, preview `complete_target`) via `annotation_overlay_of` and `same_source_family_as` — prepared
- `coco-one` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue
- `coco-two` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue
- `cocogender` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue

**Decision needed.** A person decides, for each of the 14 entries below, which option applies; until then it stays a candidate. The registry links these entries to `coco`, `coco-one`, `coco-two` and `cocogender`. The options are `alias_of:coco`, `alias_of:coco-one`, `alias_of:coco-two` and `alias_of:cocogender` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `coco`, `coco-one`, `coco-two` and `cocogender`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `coco-one`, `coco-two` and `cocogender` already have a prepared preview of their own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:coco`, `alias_of:coco-one`, `alias_of:coco-two`, `alias_of:cocogender`, `distinct_release`, `keep_candidate`

### `coco-caption` — COCO Caption

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_mentioned_split_unresolved` (2026-09-22).
- Registry blockers:
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > 3) OSCAR, VinVL, BLIP, OFA Object Hallucination Detec- COCO Caption, NoCaps Linear Probing tio

### `coco-detection-dataset` — COCO Detection Dataset

- State: access `base_source_public_variant_unverified`, adapter `not_started`, preview `none`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `source_family_only` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > ., 2024) LLaVA, LLaVA-Phi Potential Application: COCO Detection Dataset Interpretability Coa

### `coco-gender` — COCO-gender

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `annotation_overlay_of` and `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `annotation_overlay_of` → `coco`; `same_source_family_as` → `coco`
- Registry identity audit: `derived_label_variant_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-c65ee35ca47313c9`, page 1, role: evaluation
    > rturb non-gender fea- such as LLaVA and InternVL [5] tend to assign positive tures across four widely used benchmarks (COCO-gender, traits like “friendly” to women while attributing negative FACET, M…

### `coco-one` — COCO_one

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 14, role: direct What’s Up split
    > the queries to our evaluation protocol (see §A.3). Localization. • COCO_one: Single-object localization queries on COCO images, from the COCO single- object split of What’s Up [Kamath et al.,

### `coco-spatial` — COCO-Spatial

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`; `coco-one` (identity `candidate`, preview `complete_target`) via `same_source_family_as`; `coco-two` (identity `candidate`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `alias_of:coco-one`, `alias_of:coco-two`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`; `same_source_family_as` → `coco-one`; `same_source_family_as` → `coco-two`
- Registry identity audit: `author_release_identified_subset_unpinned` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2aa40aa13ed2a25b`, page 3, role: evaluation
    > n the input sequence to swap, and Q̃ is all other indices. We use the COCO-S PATIAL benchmark (Kamath et al., 2023) for the mirrored images, which is a curated subset of COCO (Lin et al., 2014) annot…

### `coco-train` — COCO train

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2df1203e2d3767bb`, page 26, role: attack image source
    > ainst a batch of 8 affirmative target responses, starting from clean images from the COCO train dataset [54]. For the prompt engineering phase, we followed the standard iterative interaction flow. In…

### `coco-two` — COCO_two

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: direct What’s Up split
    > om the controlled images split of What’s Up [Kamath et al., 2023]. • COCO_two: Two-object spatial-relation queries based on COCO [Lin et al., 2014] images, from the natural COCO split of What’s

### `cocogender` — COCOgender

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `annotation_overlay_of` and `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `annotation_overlay_of` → `coco`; `same_source_family_as` → `coco`
- Registry identity audit: `candidate_mapping_unresolved` (2026-09-22).
- Registry blockers:
  > The DeBiasLens paper cites Tang et al. 2021 for 'Cocogender' without naming v1, v2 or the subset it trained on, so the exact paper population is unresolved.
  > The gender integer is the authors' native value, derived from caption words (not perceived or self-reported identity); the repository does not document the JSON field's own coding, so Atlas does not name its values.
  > COCO images keep their per-image Flickr licences and are read on request from COCO's official archives; no public redistribution review.
- Mentioned by 1 paper:
  - `paper-32cea5e43d940514`, page 4, role: training
    > ace, we train SAE using various data configura- [ tions: CelebA [52], Cocogender images [76], and Fair- Ng = Eg \  Eh  Face [41] for the image encoder and Cocogender cap- h∈G,h̸=g tions (Cocogend

### `cocogendertxt` — Cocogendertxt

- State: access `base_source_public_variant_unverified`, adapter `not_started`, preview `none`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`; `cocogender` (identity `candidate`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `alias_of:cocogender`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`; `same_source_family_as` → `cocogender`
- Registry identity audit: `derived_config_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-32cea5e43d940514`, page 4, role: SAE caption training
    > tions (Cocogendertxt) [76] and Bias in Bios [15] for the The set Ng thus comprises neurons that are activated

### `ms-coco` — MS-COCO

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 3 papers:
  - `paper-ebd63da316af82e5`, page 2, role: evaluation
    > sults on generic scenes prompts and longer, more complex prompts from MS-COCO [18]. In practice, we first retrieve a seed, low-frequency INR whose caption is most similar to the prompt. B
  - `paper-6d747c88d639c5aa`, page 5, role: source data
    > odels, we generated metamers of 36 randomly selected natural images across each of the 16 MS-COCO categories (see Supplement Table 4 for a summary of matching the visual model metamers, and Supplemen…
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > UNITER, LXMERT, ViLT POS Tagging, Object Count- Flickr30K, MS-COCO ing

### `ms-coco-7f846b38` — MS COCO

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-29349603429218b8`, page 8, role: source data
    > test” library,4 a pre-trained sentiment analysis Data. We randomly selected 10 images from MS COCO [12] model used in [9, 27] to capture sentiment-specific nuances and 5 images from ImageNet [35]. Fo…

### `ms-coco-captions` — MS-COCO captions

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-a291f2908480a2f8`, page 8, role: evaluation
    > es are crafted, to quantitatively evaluate the adversarial robustness of large VLMs. From MS-COCO captions [44], we randomly select a text description (usually a complete sentence, as shown in our Ap…

### `mscoco` — MSCOCO

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-7a1ff5996ce95273`, page 5, role: evaluation
    > MSCOCO Model Attack Method TR@1 TR@5 TR@10 IR@1 IR@5 IR@10 R@Mean AttackVLM-ii 0.4 1.0 1.4 0.24 1.08 2.16 1.05 Attac

### `mscoco-100-target-subset` — MSCOCO 100-target subset

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `coco` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:coco`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `coco`
- Registry identity audit: `paper_selection_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-7a1ff5996ce95273`, page 7, role: derived evaluation collection
    > ViT-L/14, respectively. All AnyAttack methods con- Quantitative Results. We selected 100 images from the sistently deliver competitive results, outperforming most MSCOCO dataset as target images and…

## IR-015 · Concept-Editing Dataset

**Group key:** `concept-editing-dataset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `concept-editing-dataset` — Concept-Editing Dataset

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `generic_descriptor_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > l., 2024b) SD-1.5, SD-XL, DeepFloyd Model Editing Concept-Editing Dataset Cross-attention (Neo et al., 2024) LLaVA, LLaVA-Phi Pote

## IR-016 · Contrastive Prompts

**Group key:** `contrastive-prompts` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `contrastive-prompts` — Contrastive Prompts

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `protocol_not_independent_release` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > 2024) CLIP, T2I Diffusion Image Editing Contrastive Prompts (Huang et al., 2024a) Qwen-VL, Idefics2-8B Many-shot L

## IR-017 · Controlled CLEVR

**Group key:** `controlled-clevr` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `controlled-clevr` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `controlled-clevr` — Controlled CLEVR

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: direct What’s Up split
    > red with the recognition queries by Neo et al. [2025]. Spatial relations. • Controlled CLEVR: Two-object spatial-relation scenes from the controlled CLEVR split of the What’s Up benchmark [Kamath et…

## IR-018 · Controlled Images

**Group key:** `controlled-images` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `controlled-images` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `controlled-images` — Controlled Images

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: direct What’s Up split
    > lled CLEVR split of the What’s Up benchmark [Kamath et al., 2023]. • Controlled Images: Two-object spatial-relation queries on natural photographs, from the controlled images split of What’s Up [Kama…

## IR-019 · 2 entries linked to `cub-200-2011`

**Group key:** `cub-200-2011` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `cub-200-2011` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `cub-200-2011`. The options are `alias_of:cub-200-2011` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `cub-200-2011`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:cub-200-2011`, `distinct_release`, `keep_candidate`

### `cub` — CUB

- State: access `base_source_public_variant_unverified`, adapter `not_started`, preview `none`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. The registry links this entry to `cub-200-2011` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:cub-200-2011`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `cub-200-2011`
- Registry identity audit: `official_family_located_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > a) CLIP Image Retrieval, Segmenta- Waterbirds, CUB, Places, ImageNet- Text-Explanations of t

### `cub200` — CUB200

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `cub-200-2011` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:cub-200-2011`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `cub-200-2011`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CUB200, VTAB (Pruthi et al., 2020) ResNet-56 —

## IR-020 · Custom Dataset

**Group key:** `custom-dataset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `custom-dataset` — Custom Dataset

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `generic_descriptor_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > l., 2022) Stable-Diffusion Visualization Custom Dataset Table 10: A comprehensive overview of interpretability methods for Section 5

## IR-021 · Custom Image Editing Dataset

**Group key:** `custom-image-editing-dataset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `custom-image-editing-dataset` — Custom Image Editing Dataset

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `generic_descriptor_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > al., 2022) Stable-Diffusion Image Editing Custom Image Editing Dataset (Tang et al., 2022) Stable-Diffusion Visualization

## IR-022 · custom neonatal rat ganglion recordings

**Group key:** `custom-neonatal-rat-ganglion-recordings` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `custom-neonatal-rat-ganglion-recordings` — custom neonatal rat ganglion recordings

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_primary_collection_raw_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-52015222b27e7099`, page 23, role: derived collection
    > Identifiers Additional information Strain, strain Long-Evans (rat) USC Vivarium RRID:RGD_2308852 Freshly isolated background (species)

## IR-023 · custom speech segment collection

**Group key:** `custom-speech-segment-collection` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `custom-speech-segment-collection` — custom speech segment collection

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_built_collection_not_released` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-6d747c88d639c5aa`, page 13, role: derived collection
    > in any word or speaker class was less than 2000. The resulting training dataset contained 230356 unique segments in 432 speaker classes and 793 word classes, with 40650 unique segments in the validat…

## IR-024 · custom Ternus psychophysics responses

**Group key:** `custom-ternus-psychophysics-responses` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `custom-ternus-psychophysics-responses` — custom Ternus psychophysics responses

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_primary_collection_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-347b77231e69b630`, page 4, role: derived collection
    > ected for each trial. The standard display size was ment lasted about 60 min and included three subtasks: Illusion identical to that used in the Illusion Ternus task. The small Ternus task, Illusion…

## IR-025 · DALL-E generated target images

**Group key:** `dall-e-generated-target-images` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `dall-e-generated-target-images` — DALL-E generated target images

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_generated_unreleased` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-a291f2908480a2f8`, page 8, role: derived collection
    > plified ×10 for visualization) and their corresponding captions are generated below. Here DALL-E acts as hξ to generate targeted images hξ (ctar ) for reference. We note that adversarial perturbation…

## IR-026 · DeepFashion

**Group key:** `deepfashion` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `deepfashion` — DeepFashion

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Source access has not been verified.
  > Exact source variant or paper release is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2038cb87115b4fb0`, page 9, role: future-work example
    > well as specialized datasets such as DeepFashion and distribute attention uniformly across remaining (Liu et a

## IR-027 · Donkey Kong ROM

**Group key:** `donkey-kong-rom` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `donkey-kong-rom` — Donkey Kong ROM

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `source_binary_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 3, role: experimental condition
    > Here we will examine three different “behaviors”, that is, three different games: Donkey Kong (1981), Space Invaders (1978), and Pitfall (1981). Obviously these “behaviors” are quali- tat

## IR-028 · E-IC

**Group key:** `e-ic` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `e-ic` — E-IC

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_source_resolved_file_version_unverified` (2026-09-22).
- Registry blockers:
  > The authors host the image captioning editing data on Google Drive and Baidu NetDisk (EasyEdit examples/MMEdit.md), not on a pinned, checksummable source. A 2026-10-06 request for the image archive through the Drive download endpoint returned an empty HTML body.
  > A Google Drive folder cannot be listed or pinned reproducibly here; mirrors on Hugging Face are third-party uploads and are not treated as the original release.
  > Adapter and preview are not implemented because no verifiable file could be fetched.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > ) BLIP2-OPT(2.7B), LLaVA- — E-VQA, E-IC V1.5(7B), MiniGPT-4(7B) (Mit

## IR-029 · E-VQA

**Group key:** `e-vqa` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `e-vqa` — E-VQA

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_source_resolved_file_version_unverified` (2026-09-22).
- Registry blockers:
  > The authors host the visual question answering editing data on Google Drive and Baidu NetDisk (EasyEdit examples/MMEdit.md), not on a pinned, checksummable source. A 2026-10-06 request for the image archive through the Drive download endpoint returned an empty HTML body.
  > A Google Drive folder cannot be listed or pinned reproducibly here; mirrors on Hugging Face are third-party uploads and are not treated as the original release.
  > Adapter and preview are not implemented because no verifiable file could be fetched.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > , 2024a) BLIP2-OPT(2.7B), LLaVA- — E-VQA, E-IC V1.5(7B), MiniGPT-4(7B)

## IR-030 · Emoset

**Group key:** `emoset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `emoset` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `emoset` — Emoset

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > The full author-linked 118K native population and verified original JPEG preview are prepared locally; unfetched media remains remote. No independent publisher archive checksum supplied.
  > Historical citing-paper release and subset identity remain unverified.
  > Native image redistribution and external-provider transmission are not approved.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > 4) LLaVA, MiniGPT, Qwen-VL Image-Content Reasoning Emoset, CIFAR10 (Qin et al., 2024) OpenFlamingo, GPT4V VQ

## IR-031 · FACTOID

**Group key:** `factoid` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `factoid` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `factoid` — FACTOID

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_source_resolved_file_version_unverified` (2026-09-22).
- Registry blockers:
  > The author-linked native release is prepared and independently reproduced locally as4150user rows; missing Reddit text remains missing. Exact historical paper membership is unverified.
  > One Atlas example is one native user row. Original post counts are not a claim of prepared post examples. Privacy and redistribution/external-provider rights remain unreviewed.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 22, role: bibliography-only reference
    > Flek. Navid Rajabi and Jana Kosecka. 2024. Q-groundcam: 2022. FACTOID: A new dataset for identifying Quantifying grounding in vision language models via misinf

## IR-032 · 2 entries linked to `fairface`, `miap`, `phase`

**Group key:** `fairface|miap|phase` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `fairface` (identity `resolved`, preview `complete_target`) via `derived_from` — prepared
- `miap` (identity `resolved`, preview `complete_target`) via `derived_from` and `same_source_family_as` — prepared
- `phase` (identity `resolved`, preview `complete_target`) via `derived_from` — prepared

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `fairface`, `miap` and `phase`. The options are `alias_of:fairface`, `alias_of:miap` and `alias_of:phase` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `fairface`, `miap` and `phase`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `openimages` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:fairface`, `alias_of:miap`, `alias_of:phase`, `distinct_release`, `keep_candidate`

### `openimages` — OpenImages

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `miap` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:miap`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `miap`
- Registry blockers:
  > The paper cites Open Images as the dataset MIAP annotates a subset of and as a dataset with gender-correlated features in prior studies; it names no release (V4 to V7) or split and does not use Open Images directly.
  > Native V7 validation metadata joins, 41,620-image index and 100 original previews are verified. Mask media, localized narratives, point labels and train/test remain outside this snapshot. Public redistribution rights are not approved.
- Mentioned by 1 paper:
  - `paper-c65ee35ca47313c9`, page 2, role: source lineage
    > te the influence of non-gender features ages. Meister et al. [34] showed that in COCO and Open- on measured bias and distinguish between unbiased mod- Images [26], non-gender features, such as color…

### `vlagenderbias` — VLAGenderBias

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `fairface` (identity `resolved`, preview `complete_target`) via `derived_from`; `miap` (identity `resolved`, preview `complete_target`) via `derived_from`; `phase` (identity `resolved`, preview `complete_target`) via `derived_from`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:fairface`, `alias_of:miap`, `alias_of:phase`, `distinct_release`, `keep_candidate`
- Registry links: `derived_from` → `fairface`; `derived_from` → `miap`; `derived_from` → `phase`
- Registry blockers:
  > Data-generation recipe, not a release: the author repository ships setup scripts (about 100 GB and ~24 hours of downloads per its README) and no images; the selected 5,000 images were not reproduced.
  > Member datasets: FairFace, MIAP and PHASE are browsable in this catalogue; PATA's images are third-party web files that are not archived (see entry pata).
  > Gender labels here are the member datasets' own annotations (perceived or annotated), and a model prediction is never one of them.
- Mentioned by 1 paper:
  - `paper-32cea5e43d940514`, page 5, role: evaluation
    > evaluating LVLMs, we use two recent bench- Adj Occup Act Ster marks: VLAGenderBias (VLA) [21] and SBBench [57]. CLIP (ViT-B/16) [67] − 22.9 33.7 19.5 33.8 CLIP (ViT-B/16)† − 21.9 33.5 19.8 32.

## IR-033 · FFHQ

**Group key:** `ffhq` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `ffhq` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `ffhq` — FFHQ

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > All 70,000 native metadata entries and verified original aligned PNG previews are prepared locally; the remaining full-resolution population remains remote.
  > The exact historical paper subset and preprocessing remain unidentified.
  > All 70,000 native metadata objects and 100 original aligned PNG previews are verified. Public redistribution and external providers are not approved.
- Mentioned by 2 papers:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > e Diffusion Image Editing Ostris Dataset, FFHQ (Baumann et al., 2024) CLIP, T2I Diffusion Image Editi
  - `paper-164d7c221452ffec`, page 14, role: model-training lineage
    > h image and text (Toney and that is pretrained on the high-quality FFHQ dataset. Caliskan, 2021; Wolfe and Caliskan, 2022b). Ad- To normalize images, we crop around the facial

## IR-034 · 2 entries linked to `fgvc-aircraft`

**Group key:** `fgvc-aircraft` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `fgvc-aircraft` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `fgvc-aircraft`. The options are `alias_of:fgvc-aircraft` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `fgvc-aircraft`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `fgvc-aircraft` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:fgvc-aircraft`, `distinct_release`, `keep_candidate`

### `fgvc` — FGVC

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `fgvc-aircraft` (identity `candidate`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:fgvc-aircraft`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `fgvc-aircraft`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original data download availability is unverified.
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-3e0db9c633ab204c`, page 7, role: evaluation
    > Cars Dtd Eurosat FGVC Flowers Pets Eval Model Training Data OpenAI-L/14

### `fgvc-aircraft` — FGVC-Aircraft

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > 2024) CLIP(ViT-B/16 + LoRA) — FGVC-Aircraft, Food101, Flowers102,

## IR-035 · FineVision

**Group key:** `finevision` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `finevision` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `finevision` — FineVision

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > The exact paper-used LLaVA subset and 500k training mixture remain unresolved; release identity stays candidate.
  > Only a bounded sampled preview is prepared; the approximately 4.65 TB release has no complete local annotation index.
  > Underlying source-specific annotation and image rights remain unreviewed; no public image pack is approved.
- Mentioned by 2 papers:
  - `paper-09b2d7393fc75cf7`, page 7, role: evaluation
    > crops. giving he (see multimodal steering in Appendix III-C). For evaluation, we use the FineVision dataset [50], selecting 10,000 images from the LLaVA_Instruct_150k subset, yielding 20,559 image–in…
  - `paper-d8a392188b9cf4d6`, page 5, role: training
    > the vision encoder, projection layer, and language model. We use the FineVision dataset (Wiedmann et al., 2025), training on 500k samples with a batch size of 16 and a learning rate of 5e-5. The SA

## IR-036 · First-Person Social Interactions Dataset

**Group key:** `first-person-social-interactions-dataset` · **Entries:** 1 · **Blocker types:** `source_availability` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). For `first-person-social-interactions-dataset` the source host did not answer or did not resolve at the registry's latest access audit; that is source availability, not an identity decision.

**Options:** `distinct_release`, `keep_candidate`

### `first-person-social-interactions-dataset` — First-Person Social Interactions Dataset

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **source_availability**. The registry's latest access audit (2026-10-08) records `author_page_identified_media_host_unresolvable`: the source host did not answer or did not resolve. This is source availability, not identity.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `original_source_and_author_reformat_distinct` (2026-09-22).
- Registry blockers:
  > The author page (ai.stanford.edu/~alireza/Disney/) links 113 AVI videos and annotation ZIPs hosted on webshare.ipat.gatech.edu over plain HTTP; the host did not answer a HEAD request within 30 s over either http or https on 2026-10-06 (an upstream availability problem to retry).
  > The videos are AVI files, which browsers cannot play, and the host is HTTP-only, which Atlas's fetch layer does not use: even when the host returns, preparation needs a transcoding or an HTTPS mirror (an implementation gap beyond the outage).
  > The citing paper's training selection (the Watanabe selection) is not identified, and the page states no licence.
- Mentioned by 1 paper:
  - `paper-4f53de240f8fc1af`, page 3, role: source data
    > redicted the 22nd image (P2) with reference with mean-squared error using videos from the First-Person to 21 consecutive images (T1 to T21) using P1 as the image Social Interactions Dataset (Fathi et…

## IR-037 · 2 entries linked to `flowers102`

**Group key:** `flowers102` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `flowers102` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `flowers102`. The options are `alias_of:flowers102` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `flowers102`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `flowers102` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:flowers102`, `distinct_release`, `keep_candidate`

### `flowers` — Flowers

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `flowers102` (identity `candidate`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:flowers102`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `flowers102`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original data download availability is unverified.
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-3e0db9c633ab204c`, page 7, role: evaluation
    > Cars Dtd Eurosat FGVC Flowers Pets Eval Model Training Data OpenAI-L/14

### `flowers102` — Flowers102

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > T-B/16 + LoRA) — FGVC-Aircraft, Food101, Flowers102,

## IR-038 · Food101

**Group key:** `food101` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `food101` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `food101` — Food101

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CLIP(ViT-B/16 + LoRA) — FGVC-Aircraft, Food101, Flowers102,

## IR-039 · Gaussian rubbish examples

**Group key:** `gaussian-rubbish-examples` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `gaussian-rubbish-examples` — Gaussian rubbish examples

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `generated_by_recipe_no_release` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-f7fa96d778a8d649`, page 10, role: derived collection
    > naively trained maxout network with a softmax layer on top had an error rate of 98.35% on Gaussian rubbish examples with an average confidence of 92.8% on mistakes. Changing the top layer to independ…

## IR-040 · GDA adversarial image variants

**Group key:** `gda-adversarial-image-variants` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `gda-adversarial-image-variants` — GDA adversarial image variants

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_derived_collection_no_release_located` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-f5da3ca03780a203`, page 8, role: derived collection
    > 4 0.4735 0.3072 0.3026 0.2574 0.3176 41.2 Datasets. We randomly sample 1,000 samples from each of three datasets for evaluation, correspond- ing to different multimodal tasks: image captioning on Fli…

## IR-041 · GPT-4V-filtered VL-Gender subset

**Group key:** `gpt-4v-filtered-vl-gender-subset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `gpt-4v-filtered-vl-gender-subset` — GPT-4V-filtered VL-Gender subset

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_subset_unpinned` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-f03c5ad315e6d835`, page 18, role: derived collection
    > ill yield better judgments regarding occupation- related content. Therefore, we provide a subset of 6000 images (1200 per dataset) to GPT-4V alongside the same prompt we used for InternVL2-40B. For 5…

## IR-042 · Group Labels

**Group key:** `group-labels` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `group-labels` — Group Labels

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_derived_lexicon_release_unresolved` (2026-09-22).
- Registry blockers:
  > The authors' repository (kshitishghate/bias_prop) releases only Data/template_and_group_words.json (3 templates, a 6-item prompt template list, 24 gender words, 36 race words and smaller subsets); the 864-phrase list itself and the code that builds it are not released ('will be added' per its README).
  > 24 gender words x 36 race words = 864 matches the paper's count, but the paper's exact phrase construction is not in the repository, so Atlas does not generate the list and present it as the released data.
  > The released word lists are a vocabulary resource, not a population of examples; no preview was prepared.
- Mentioned by 1 paper:
  - `paper-164d7c221452ffec`, page 4, role: direct lexical source
    > 000 words Valenced Text SC-EAT Valence ratings of retrieved text Group Labels 864 phrases Group-based text in SC-EAT Group representation in retrieved text Chicago Face Database (

## IR-043 · GVIL paired illusion images

**Group key:** `gvil-paired-illusion-images` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `gvil-paired-illusion-images` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `gvil-paired-illusion-images` — GVIL paired illusion images

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_release_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-b039401c04ff9b91`, page 4, role: derived collection
    > ure 3, each question The statistics of our dataset is shown in Table 2. concerns a pair of images (IMG1 and IMG2). One Note that since this dataset is only used for the eval- image (IMG1) is illusion…

## IR-044 · 2 entries linked to `hc-bench`

**Group key:** `hc-bench` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `hc-bench` (identity `resolved`, preview `local_only`) via `same_source_family_as` and `source_subset_of` — prepared

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `hc-bench`. The options are `alias_of:hc-bench` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `hc-bench`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:hc-bench`, `distinct_release`, `keep_candidate`

### `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-collection` — unnamed internet hidden-content collection

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `hc-bench` (identity `resolved`, preview `local_only`) via `same_source_family_as` and `source_subset_of`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:hc-bench`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `hc-bench`; `source_subset_of` → `hc-bench`
- Registry identity audit: `author_release_identified_version_drift` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2c07a8c6af8e33c2`, page 8, role: evaluation
    > 6.23+96.23 D EEP S EEK -VL2 0 0 0 0 84.90+84.90 Table 5: Validation of task difficulty on 53 internet-sourced hidden-content images, collected independently to reduce dataset-specific noise and biase…

### `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-set` — unnamed internet hidden-content set

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `hc-bench` (identity `resolved`, preview `local_only`) via `same_source_family_as` and `source_subset_of`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:hc-bench`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `hc-bench`; `source_subset_of` → `hc-bench`
- Registry identity audit: `author_release_identified_version_drift` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2c07a8c6af8e33c2`, page 8, role: independent validation collection
    > 0 84.90+84.90 Table 5: Validation of task difficulty on 53 internet-sourced hidden-content images, collected independently to reduce dataset-specific noise and biases. Failure case analysis. Rare err…

## IR-045 · HellaSwag-Pro

**Group key:** `hellaswag-pro` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `hellaswag-pro` — HellaSwag-Pro

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `unresolved` (2026-09-22).
- Registry blockers:
  > Source access has not been verified.
  > Exact source variant or paper release is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-20de77d4e60fd1bd`, page 8, role: related-work comparison
    > 25.27 15.06 31.74 21.00 lusionbench (Guan et al., 2024) and HellaSwag-Pro (Li et al., 2025a) probe hallucination and coun

## IR-046 · iCTCF

**Group key:** `ictcf` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `ictcf` — iCTCF

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `source_resolved_paper_slice_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > 24b) DensetNet-121 — ITAC, iCTCF, BRCA, ROSMAP (Basu et al., 2024b) SD-1.5, SD-XL, DeepFloyd Model

## IR-047 · IllusionBench+, linked to `illusionbench-3c643c29`

**Group key:** `illusionbench-3c643c29` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `illusionbench-3c643c29` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `illusionbench-3c643c29`. The options are `alias_of:illusionbench-3c643c29` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `illusionbench-3c643c29`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:illusionbench-3c643c29`, `distinct_release`, `keep_candidate`

### `illusionbench` — IllusionBench+

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `illusionbench-3c643c29` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:illusionbench-3c643c29`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `illusionbench-3c643c29`
- Registry identity audit: `original_citation_only` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-6a7364738bac9f07`, page 1, role: introduction
    > d in real-world scenarios, remain underexplored. To ad- D. we do not know dress this gap, we construct IllusionBench+, a large-scale visual GPT-4o: B. Standing on the table illusion dataset, encompas…

## IR-048 · IllusionMNIST

**Group key:** `illusionmnist` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `illusionmnist` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `illusionmnist` — IllusionMNIST

- State: access `public`, adapter `tested`, preview `complete_target`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_family_located_subset_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-20de77d4e60fd1bd`, page 8, role: related-work comparison
    > asets 5. Related Works (e.g., IllusionMNIST) for illusion recognition; The Art of 5.1. Multimodal Large Language Models Deception

## IR-049 · Illusory VQA, linked to `illusionvqa`

**Group key:** `illusionvqa` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `illusionvqa` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `illusionvqa`. The options are `alias_of:illusionvqa` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `illusionvqa`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:illusionvqa`, `distinct_release`, `keep_candidate`

### `illusory-vqa` — Illusory VQA

- State: access `base_source_public_variant_unverified`, adapter `not_started`, preview `none`, identity `family_or_variant_candidate`.
- Blocker type: **identity**. The registry links this entry to `illusionvqa` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:illusionvqa`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `illusionvqa`
- Registry identity audit: `author_family_located_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-used variant/configuration is not pinned to an exact source release.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-20de77d4e60fd1bd`, page 8, role: related-work comparison
    > gnificance. rent MLLMs. A line of related work includes Illusory VQA (Rostamkhani et al., 2025), which constructs ed

## IR-050 · 5 entries linked to `imagenet`, `imagenet-1k`, `imagenet-ilsvrc-2012`

**Group key:** `imagenet|imagenet-1k|imagenet-ilsvrc-2012` · **Entries:** 5 · **Blocker types:** `identity` 1, `access` 4

**Linked to:**

- `imagenet` (identity `candidate`, preview `none`) via `same_source_family_as` — no preview; also an entry in this queue
- `imagenet-1k` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared
- `imagenet-ilsvrc-2012` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for each of the 5 entries below, which option applies; until then it stays a candidate. The registry links these entries to `imagenet`, `imagenet-1k` and `imagenet-ilsvrc-2012`. The options are `alias_of:imagenet`, `alias_of:imagenet-1k` and `alias_of:imagenet-ilsvrc-2012` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `imagenet-1k` and `imagenet-ilsvrc-2012`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. For `imagenet` (access `gated`), `imagenet-ilsvrc` (access `gated`), `imagenet100` (access `gated`) and `imagenetval` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `alias_of:imagenet`, `alias_of:imagenet-1k`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`

### `imagenet` — ImageNet

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `alias_of:imagenet-1k`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `imagenet-1k`; `same_source_family_as` → `imagenet-ilsvrc-2012`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original source requires registration or licensed base images.
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 22 papers:
  - `paper-9036b4eaa048dc21`, page 5, role: training
    > ned on activation vectors pre-extracted from the model’s responses to ImageNet [13] images. For CLIP, activation vectors are extracted from the classification (CLS) tokens in the residual
  - `paper-a47845c66d4a3f48`, page 5, role: evaluation
    > and common corruption threat models on CIFAR-10, CIFAR-100 [75], and ImageNet [32] datasets (see Table 1 for details). We use the fixed budgets of ε∞ = 8/255 and ε2 = 0.5 for the `∞ and `2 leaderboar…
  - `paper-1e2474b15fec2d7d`, page 7, role: training
    > in Experiment 1: (1) Discriminative feedforward models: a VGG-16 [29] first trained on ImageNet and then retrained on upscaled CIFAR-10 (‘finetuned VGG-16’) and a Wide-Resnet trained exclusively on C…
  - `paper-c12960e5d652fb7f`, page 5, role: source data
    > eline accuracy without adversar- ial attacks, we used a subset of the ImageNet dataset [27], No Defense EigenShield randomly selecting a thousand images. To evaluate Eigen- Model RTP HarmBench RTP
  - `paper-959e8fc51787f7e4`, page 5, role: training
    > ces feature activations SmoLIM2-135M-10B [2] 2048 text tokens 144,000 ImageNet [31] 1 image; Caption 144,000 zℓ,t,i ∈ R, Cauldron [17] 1 image; QA Text 72,000 and each feature has an assoc
  - `paper-6dbb0d4a7b949143`, page 4, role: training
    > nt is leveraging CLIP, which has been widely MLLMs. Using a subset of ImageNet training data D, we adopted in MLLMs due to two crucial properties: (1) its optimize W by minimizing the alignment loss…
  - `paper-7ed1979562251931`, page 9, role: evaluation
    > Method VQA v2 scores experiments on several other datasets, including ImageNet (Deng et al., 2009), OKVQA (Marino LQAVA (RSQ25 ) 44.07 ± 0.83 et al., 2019), NoCaps (Agrawal et al., 2019),
  - `paper-208c53a35b62bc52`, page 6, role: evaluation
    > ng the worst case over all attacks, as MNIST, CIFAR-10, CIFAR-100 and ImageNet as datasets. we do for AutoAttack, improves the performance. We report first results for deterministic defens
  - `paper-78a318ad1ec346ef`, page 2, role: evaluation
    > tential application image recognition task, also with 10 classes; and ImageNet settings, but entirely defeats its purpose: an adversary who is [9], a large-image recognition task with 1000
  - `paper-728d8c0964b540ad`, page 2, role: evaluation
    > ned on top of an autoencoder. We refer to this network as “AE”. • The ImageNet dataset [3]. – Krizhevsky et. al architecture [9]. We refer to it as “AlexNet”. • ∼ 10M image samples from Yo
  - `paper-72040eccb96ead7a`, page 5, role: training
    > ifiers to capture all task-dependent variability. Attack on MNIST and ImageNet. After validating its potential to uncover adversarial subspaces, we apply metameric sampling to fully invert
  - `paper-d0229a9d15fd6b77`, page 2, role: evaluation
    > amples. be an incomplete defense to adversarial examples (Papernot On ImageNet, we evaluate over 1000 randomly selected et al., 2017; Tramèr et al., 2018). Despite this, we observe images
  - `paper-666de2b7486d80a3`, page 4, role: source data
    > Weighted Fourier Aggregation [11], and of these networks on the 1.3M ImageNet dataset [47] for 1 three variants of a deep video deblurring method [53]. epoch. The goal of each network is
  - `paper-ab31cc6a994470fb`, page 4, role: source data
    > Vision Pipeline 3.1.1 Dataset In our experiment, we used images from ImageNet [7]. ImageNet contains 1,000 highly specific classes that typical people may not be able to identify, such as
  - `paper-d098a79f00c8b2b5`, page 40, role: bibliography-only reference
    > ing CNNs with bag-of-local-features models works surprisingly well on imagenet. In International Conference on Learning Representations, 2019. URL https://openreview.net/forum?id=SkfMWhAqY
  - `paper-29349603429218b8`, page 8, role: source data
    > COCO [12] model used in [9, 27] to capture sentiment-specific nuances and 5 images from ImageNet [35]. For each image, we gener- in tweets. This model was trained on an extensive dataset of ated 100…
  - `paper-f7fa96d778a8d649`, page 3, role: evaluation
    > on of fast adversarial example generation applied to GoogLeNet (Szegedy et al., 2014a) on ImageNet. By adding an imperceptibly small vector whose elements are equal to the sign of the elements of the…
  - `paper-6d747c88d639c5aa`, page 13, role: model-training lineage
    > d across two NVIDIA GPUs each with 11GB memory. S1.2 Retrained ImageNet Description The ImageNet-trained architectures used to generate metamers for the behavioral and network- network experiments we…
  - `paper-3aa07dc1c7bc37d9`, page 23, role: bibliography-only reference
    > 6, 2023. R. Geirhos, P. Rubisch, C. Michaelis, M. Bethge, F. A. Wichmann, and W. Brendel. Imagenet-trained cnns are biased towards texture; increasing shape bias improves accuracy and robustness. arX…
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > ) CLIP Image Classification ImageNet Sparse AutoEncoder (Rao et al., 2024) CLIP, ResNet-50
  - `paper-b039401c04ff9b91`, page 2, role: related-work mention
    > at sual illusion. There are two main contributions of convolutional neural networks trained on ImageNet this work. First, this investigation provides an ini- or low-level vision tasks can be misled b…
  - `paper-392b0c393c06b48e`, page 8, role: baseline encoder retraining
    > CLIP-style adversarial pre- training on web-scale image–text data without subsequent ImageNet fine-tuning. All the adversarial trained models are publicly available. Baselines. We compare against the…

### `imagenet-ilsvrc` — ImageNet ILSVRC

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `alias_of:imagenet`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `imagenet`; `same_source_family_as` → `imagenet-ilsvrc-2012`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original source requires registration or licensed base images.
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-08e415961919a492`, page 14, role: training
    > inverting different layers of AlexNet (trained for classification on ImageNet ILSVRC) using three different regularizers: the deep image prior, the TV norm prior of [38], and the network trained

### `imagenet-sampled-1-000-images` — ImageNet sampled 1,000 images

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `imagenet` (identity `candidate`, preview `none`) via `same_source_family_as`; `imagenet-ilsvrc-2012` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:imagenet`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `imagenet`; `same_source_family_as` → `imagenet-ilsvrc-2012`
- Registry identity audit: `paper_subset_unpinned` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-c12960e5d652fb7f`, page 5, role: source data
    > No Defense EigenShield randomly selecting a thousand images. To evaluate Eigen- Model RTP HarmBench RTP HarmBench Shield’s robust

### `imagenet100` — ImageNet100

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `alias_of:imagenet`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `imagenet`; `same_source_family_as` → `imagenet-ilsvrc-2012`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original-source credentials or agreement are required.
  > Exact source variant or paper release is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CLIP — CIFAR100, ImageNet100, ImageNet-R,

### `imagenetval` — ImageNetVal

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `alias_of:imagenet`, `alias_of:imagenet-ilsvrc-2012`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `imagenet`; `same_source_family_as` → `imagenet-ilsvrc-2012`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Original source requires registration or licensed base images.
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > LAION, CelebA, ImageNetVal (Parekh et al., 2024) DePALM (CLIP+OPT) Image Classification

## IR-051 · ITAC

**Group key:** `itac` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `itac` — ITAC

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `in_house_no_release_verified` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > l., 2024b) DensetNet-121 — ITAC, iCTCF, BRCA, ROSMAP (Basu et al., 2024b) SD-1.5, SD-XL, DeepFloyd

## IR-052 · LAION

**Group key:** `laion` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `laion` — LAION

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_mentioned_variant_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 2 papers:
  - `paper-c941465e4095dbe8`, page 10, role: bibliography-only reference
    > ons. Birhane, A., Han, S., Boddeti, V., Luccioni, S., et al. Into the LAION’s den: Investigating hate in multimodal datasets. Overall, effective inner interpretability techniques should
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > LAION, CelebA, ImageNetVal (Parekh et al., 2024) DePALM (CLIP+OPT)

## IR-053 · LAION Aesthetics

**Group key:** `laion-aesthetics` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `laion-aesthetics` — LAION Aesthetics

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `derived_subset_family_identified_variant_unresolved` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
  > 2026-10-08 public-page reading: the Hugging Face laion/laion2B-en-aesthetic metadata is gated behind a contact-information agreement (not accepted by the agent), and which aesthetic subset the paper used is not stated.
- Mentioned by 1 paper:
  - `paper-ebd63da316af82e5`, page 3, role: source data
    > tion for inversion initial- ization. In practice, we used images from LAION Aesthetics (a subset of LAION-5B [32]). This data serves two purposes: (i) training INRs for initializing text-to-image

## IR-054 · LLaVA_Instruct_150k, linked to `llava-instruct-150k`

**Group key:** `llava-instruct-150k` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `llava-instruct-150k` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `llava-instruct-150k`. The options are `alias_of:llava-instruct-150k` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `llava-instruct-150k`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `llava-instruct-150k-3a74a703` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:llava-instruct-150k`, `distinct_release`, `keep_candidate`

### `llava-instruct-150k-3a74a703` — LLaVA_Instruct_150k

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `llava-instruct-150k` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:llava-instruct-150k`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `llava-instruct-150k`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-09b2d7393fc75cf7`, page 7, role: refusal evaluation subset
    > For evaluation, we use the FineVision dataset [50], selecting 10,000 images from the LLaVA_Instruct_150k subset, yielding 20,559 image–instruction pairs, and the test split of TextVQA [51], containin…

## IR-055 · Middlebury

**Group key:** `middlebury` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `middlebury` — Middlebury

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `benchmark_family_no_single_release` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-666de2b7486d80a3`, page 4, role: source data
    > Davis ing a variety of tasks, architectures, and losses, as shown in Middleburry dataset [50]. Because artifacts arising from Table 2 (right). Such tasks include autoencoding, denoising, fra

## IR-056 · MIT States

**Group key:** `mit-states` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `mit-states` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `mit-states` — MIT States

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Pinned public mirror population of 63,440 original JPEGs and 100 retained original previews is verified; publisher byte equivalence remains unverified.
  > Publisher archive byte/quality equality, exact paper subset and redistribution rights remain unverified.
- Mentioned by 2 papers:
  - `paper-2038cb87115b4fb0`, page 4, role: evaluation
    > adapt the image (see Figure 1). We implement SIP in three SVO-Probes, MIT States, and Facial Expressions diverse image-classification datasets: SVO-Probes image-classification datasets into
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CLIP Image Classification CIFAR100, MIT States, MSCOCO,

## IR-057 · MMA-Diffusion

**Group key:** `mma-diffusion` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `mma-diffusion` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used. For `mma-diffusion` (access `request_required`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `mma-diffusion` — MMA-Diffusion

- State: access `request_required`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **access**. Access is `request_required`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `official_source_resolved_not_human_reviewed` (2026-09-22).
- Registry blockers:
  > Original-source access requires an author or data-holder request.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-09b2d7393fc75cf7`, page 7, role: evaluation
    > vector-computation sets from the VHD11K [52] by sampling evaluate the purified version of MMA-Diffusion [62], released 250 harmful and 250 harmless images. We apply the same in [63], where we prepend…

## IR-058 · MMStar

**Group key:** `mmstar` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `mmstar` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `mmstar` — MMStar

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-80b7ba2e277a20c5`, page 7, role: out-of-domain evaluation
    > l variants enhance scale coverage. (VQA) tasks: SimpleVQA [8], MMStar [7], and RealWorldQA [30].

## IR-059 · 2 entries linked to `mnist`

**Group key:** `mnist` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `mnist` (identity `resolved`, preview `complete_target`) via `derived_from` — prepared

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `mnist`. The options are `alias_of:mnist` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `mnist`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:mnist`, `distinct_release`, `keep_candidate`

### `scrambled-mnist` — scrambled MNIST

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `mnist` (identity `resolved`, preview `complete_target`) via `derived_from`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:mnist`, `distinct_release`, `keep_candidate`
- Registry links: `derived_from` → `mnist`
- Registry identity audit: `derived_protocol_unpinned` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-1e2474b15fec2d7d`, page 17, role: OOD/background training
    > examples (non-digits) used as a background class for the small VGG− model. (A) pixel-scrambled MNIST images. (B) Fourier-phase scrambled MNIST-images. (C) EMNIST letters [61], excluding the letters o…

### `shiftmnist` — shiftMNIST

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `mnist` (identity `resolved`, preview `complete_target`) via `derived_from`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:mnist`, `distinct_release`, `keep_candidate`
- Registry links: `derived_from` → `mnist`
- Registry identity audit: `derived_protocol_unpinned` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-72040eccb96ead7a`, page 8, role: introduction
    > CE fi-RevNet 00.53 59.99 (b) Difference 00.53 27.84 (a) (b) Figure 8: shiftMNIST experiments. (a): Binary shiftMNIST, where the class is additionally encoded with a location-based binary cod

## IR-060 · MultiTrust

**Group key:** `multitrust` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). For `multitrust` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `multitrust` — MultiTrust

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_benchmark_page_located` (2026-09-22).
- Registry blockers:
  > Hugging Face thu-ml/MultiTrust (CC BY-SA 4.0, auto-gated: each researcher accepts the terms on their own account) holds 10,549 files across five trustworthiness aspects with task-specific formats.
  > A suite of heterogeneous tasks, not one homogeneous collection: it needs per-task adapters, an implementation gap rather than an access block.
  > The citing paper uses the MultiTrust framework for transfer attacks, so the examples a researcher would want are those it generated, which were not located.
  > Checked 2026-10-08 with the researcher's configured local Hugging Face credentials: a HEAD of one data file and auth_check both answered HTTP 403 GatedRepo, so the account has not been granted access, and the file listing noted on 2026-10-06 does not show otherwise. Access requires the researcher to accept the terms on their own account; until then no inventory, adapter or preview exists.
- Mentioned by 2 papers:
  - `paper-392b0c393c06b48e`, page 26, role: transfer-attack framework
    > Ensemble-based Transfer Attacks We further evaluate MLLM robustness using the MultiTrust benchmarking framework [68], which employs ensemble-based SSA-CWA attacks to generate highly transferable adve…
  - `paper-6dbb0d4a7b949143`, page 14, role: transfer-attack framework
    > g the attacks on the COCO image captioning task. These exam- MultiTrust benchmarking framework (Zhang et al., ples illustrate the varying degrees of model susceptibility

## IR-061 · Ostris Dataset

**Group key:** `ostris-dataset` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `ostris-dataset` — Ostris Dataset

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `survey_name_ambiguous` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > , 2025) Stable Diffusion Image Editing Ostris Dataset, FFHQ (Baumann et al., 2024) CLIP, T2I Diffusion Image

## IR-062 · unnamed 11-image inpainting set

**Group key:** `paper-08e415961919a492-unnamed-11-image-inpainting-set` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-08e415961919a492-unnamed-11-image-inpainting-set` — unnamed 11-image inpainting set

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_benchmark_identity_unpinned` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-08e415961919a492`, page 12, role: evaluation
    > Dmitry Ulyanov et al. Barbara Boat House Lena Peppers C.man Couple Finger Hill Man Montage Papyan et al. 28.14 31.44 34.58 35.04

## IR-063 · unnamed real-noise benchmark [46]

**Group key:** `paper-08e415961919a492-unnamed-real-noise-benchmark-46` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-08e415961919a492-unnamed-real-noise-benchmark-46` — unnamed real-noise benchmark [46]

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `original_source_identified_paper_snapshot_unpinned` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-08e415961919a492`, page 6, role: evaluation
    > on-Gaussian obtained in the last iterations (using exponential slid- noise we use the benchmark of [46]. Using the same ing window). If averaged over two optimization runs architecture and hyper-para…

## IR-064 · unnamed harmful-instruction evaluation set

**Group key:** `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set` — unnamed harmful-instruction evaluation set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry identity audit: `confirmed_duplicate_candidate` (2026-09-22).
- Registry blockers:
  > The paper describes 40 manually curated harmful instructions used for human evaluation; the audit found no public release.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-12e8bd34b4a2f2a8`, page 6, role: evaluation
    > f our visual adversarial examples, we pair them with a diverse set of 40 manually curated harmful textual instructions. These instructions explicitly ask for the generation of detrimental con

## IR-065 · unnamed harmful sentence corpus

**Group key:** `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus` — unnamed harmful sentence corpus

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry identity audit: `paper_custom_release_unverified` (2026-09-22).
- Registry blockers:
  > The paper describes a 66-sentence derogatory corpus used to optimize attacks; the audit found no public release.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-12e8bd34b4a2f2a8`, page 5, role: source data
    > ractice, we use a few-shot Do ********* corpus Y , consisting of only 66 derogatory sentences against (a bad thing) <gender-1>, <race-1>, and the human race, to bootstrap our attacks. We find that th…

## IR-066 · unnamed CFD morph collection

**Group key:** `paper-164d7c221452ffec-unnamed-cfd-morph-collection` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). For `paper-164d7c221452ffec-unnamed-cfd-morph-collection` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `paper-164d7c221452ffec-unnamed-cfd-morph-collection` — unnamed CFD morph collection

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `explicit_copyright_request_only_release_unverified` (2026-09-22).
- Registry blockers:
  > Author request or agreement is required for the described data; no public archive was verified.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-164d7c221452ffec`, page 14, role: derived collection
    > each morph. This produces to agreed upon terms. All personally identifiable a dataset of 30,000 morphed images with corre- information is anonymised (Ma et al., 2015) before sponding embeddings, each…

## IR-067 · unnamed Objaverse spatial images

**Group key:** `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images` — unnamed Objaverse spatial images

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_and_render_source_identified_outputs_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2aa40aa13ed2a25b`, page 18, role: derived collection
    > §D.1, we use 90 object pairs, and consider s = 4 from {224, 174, 124, 74}, yielding 86,400 images. Note that each image size is 224 × 4 = 896 in width and height. Synthetic Video generation for Tempo…

## IR-068 · unnamed synthetic spatial training set

**Group key:** `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). For `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set` — unnamed synthetic spatial training set

- State: access `gated`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `explicit_author_request_for_large_archive` (2026-09-22).
- Registry blockers:
  > Author request or agreement is required for the described data; no public archive was verified.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-2aa40aa13ed2a25b`, page 9, role: training
    > gher accuracy can be better this intuition, we finetune Qwen2-2B on a synthetic dataset simi- steered with spatial IDs. lar to the one used to extract spatial IDs, and evaluate on COCO- Spatial. We

## IR-069 · unnamed robust/nonrobust feature collections

**Group key:** `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections` — unnamed robust/nonrobust feature collections

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes robust/non-robust feature collections it constructed; no public release of them was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-63c3bd849356e00f`, page 5, role: derived collection
    > of the CIFAR-10 [Kri09] training set: the original training set; the robust training set Db R , restricted to features used by a robust model; and the non-robust training b set D NR , r

## IR-070 · unnamed synthetic spheres dataset

**Group key:** `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset` — unnamed synthetic spheres dataset

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes a synthetic spheres dataset it generated; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-72040eccb96ead7a`, page 5, role: evaluation
    > on adversarial spheres. First, we evaluate our analytic attack on the synthetic spheres dataset, where the task is to classify samples as belonging to one out of two spheres with differ- ent radii.

## IR-071 · unnamed YouTube image collection

**Group key:** `paper-728d8c0964b540ad-unnamed-youtube-image-collection` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-728d8c0964b540ad-unnamed-youtube-image-collection` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-728d8c0964b540ad-unnamed-youtube-image-collection` — unnamed YouTube image collection

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes a YouTube image collection it assembled; no public release was located and the frames carry third-party rights.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-728d8c0964b540ad`, page 2, role: source data
    > itecture [9]. We refer to it as “AlexNet”. • ∼ 10M image samples from Youtube (see [10]) – Unsupervised trained network with ∼ 1 billion learnable parameters. We refer to it as “QuocNet”.

## IR-072 · unnamed social-category question set

**Group key:** `paper-765a2362f8735bc4-unnamed-social-category-question-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-765a2362f8735bc4-unnamed-social-category-question-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-765a2362f8735bc4-unnamed-social-category-question-set` — unnamed social-category question set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry identity audit: `paper_custom_release_unverified` (2026-09-22).
- Registry blockers:
  > The paper describes 50 author-collected social-category questions; the audit found no public release.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-765a2362f8735bc4`, page 13, role: derived evaluation collection
    > 20 questions for gender and 30 questions for race (page 13; two-column extraction interleaves a results table)

## IR-073 · unnamed neuron-pair judgment collection

**Group key:** `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection` — unnamed neuron-pair judgment collection

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes human judgments it collected over neuron pairs; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-9036b4eaa048dc21`, page 6, role: introduction
    > rval. the Mechanical Turk platform. This study resulted in a total of 1000 questions across 71 unique users, with 3 answers per question aggregated through majority voting. Results of this study are…

## IR-074 · unnamed Van Gogh painting sample

**Group key:** `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-944952997d24ce45-unnamed-van-gogh-painting-sample` — unnamed Van Gogh painting sample

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_selection_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-944952997d24ce45`, page 9, role: source data
    > nonsensical outputs. To validate the effectiveness of VMA, we sample 874 publicly available Van Gogh paintings. We ask VLMs to describe these images and define random token sequences as targe

## IR-075 · unnamed VMA candidate pool

**Group key:** `paper-944952997d24ce45-unnamed-vma-candidate-pool` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-944952997d24ce45-unnamed-vma-candidate-pool` — unnamed VMA candidate pool

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_derived_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-944952997d24ce45`, page 6, role: derived collection
    > f VLMs, We construct an evaluation candidate pool by randomly pairing 1, 000 distinct prompts, images, and target outputs. Then, we randomly sample 1, 000 text-image input-output pairs for evaluation…

## IR-076 · unnamed curated internet image collection

**Group key:** `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection` — unnamed curated internet image collection

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes internet images it curated per experiment; no fixed public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-959e8fc51787f7e4`, page 6, role: circuit analysis collection
    > that make the underlying representations more explainable. sample of 20-100 internet images that are semantically re- The gap is largest in the middle layers (e.g. Layer 15), con- lated to the image…

## IR-077 · unnamed internet image tracing set

**Group key:** `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set` — unnamed internet image tracing set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry identity audit: `per_task_curated_samples_no_fixed_release_verified` (2026-09-22).
- Registry blockers:
  > The audit verified per-task curated internet image samples with no fixed release; the public repository holds code and models only.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-959e8fc51787f7e4`, page 6, role: evaluation
    > that make the underlying representations more explainable. sample of 20-100 internet images that are semantically re- The gap is largest in the middle layers (e.g. Layer 15), con- lated to the image…

## IR-078 · unnamed sea-otter image sample

**Group key:** `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample` — unnamed sea-otter image sample

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `specific_paper_sample_release_unverified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-959e8fc51787f7e4`, page 7, role: evaluation
    > offer a clearer picture of the compu- on a curated, small dataset of 30 sea otter images signifi- tational structure supporting vision-language reasoning. cantly increased the feature’s interpretabi

## IR-079 · unnamed human adversarial-stimulus collection

**Group key:** `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection` — unnamed human adversarial-stimulus collection

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes adversarial stimuli it produced for human trials; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-ab31cc6a994470fb`, page 6, role: derived collection
    > sented in one of four conditions as follows: • image: images from the ImageNet training set (rescaled to the [40, 255 − 40] range to avoid clipping when adversarial perturbations are added; see Figure

## IR-080 · unnamed attack-generalization collection

**Group key:** `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-c12960e5d652fb7f-unnamed-attack-generalization-collection` — unnamed attack-generalization collection

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes an attack-generalization image collection it assembled; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-c12960e5d652fb7f`, page 5, role: derived collection
    > th each text prompt to serve as VLM inputs. To evaluate EigenShield’s generalization under various real- world threat models, we generated adversarial examples using five distinct attack methods

## IR-081 · unnamed AI-generated gender-image attack set

**Group key:** `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set` — unnamed AI-generated gender-image attack set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes AI-generated attack images it produced; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-f6dcb0e50d10ea38`, page 10, role: derived collection
    > slightly perturbed version. We quantify this effect via a systematic evaluation with 20 AI- generated images of men and women, and all 10×10 = 100 adversar- ial images oof each woman as a source targ…

## IR-082 · unnamed explicit-image attack set

**Group key:** `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set` — unnamed explicit-image attack set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes an explicit-image attack set it assembled; no public release was located and none would be appropriate to mirror.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-f6dcb0e50d10ea38`, page 9, role: derived collection
    > tive imagery has been Case study 4: Evading NSFW detectors. We select 10 explicit censored to ensure appropriate academic presentation. images depicting nudity, each flagged as pornographic w

## IR-083 · unnamed historical-event image attack set

**Group key:** `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set` — unnamed historical-event image attack set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes a historical-event image attack set it assembled; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-f6dcb0e50d10ea38`, page 20, role: derived collection
    > (f) Surrender of Japan Figure 21: Adversarial versions of photographs of six well-documented historical events, each perturbed to match the text embedding of “fake news.” These images are used in the…

## IR-084 · unnamed product screenshot attack

**Group key:** `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack` — unnamed product screenshot attack

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes product-screenshot attack images it assembled; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-f6dcb0e50d10ea38`, page 11, role: derived collection
    > olving a browser agent, ChatGPT Atlas [40]. We present the VLM with a screenshot of top search results for the query “smart watch” on Amazon, and ask it to recommend one. To 5.4 Commercial Manipulati…

## IR-085 · unnamed public-figure adversarial image set

**Group key:** `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` · **Entries:** 1 · **Blocker types:** `unreleased` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `accept_unreleased_custom_record` (a paper-private dataset with no public release, kept as an unreleased custom record) and `keep_candidate` (leave the identity open). `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` is an unreleased paper-private record: accept as an unreleased custom record, or keep as candidate.

**Options:** `accept_unreleased_custom_record`, `keep_candidate`

### `paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set` — unnamed public-figure adversarial image set

- State: access `unreleased`, adapter `not_applicable`, preview `none`, identity `candidate`.
- Blocker type: **unreleased**. Access is `unreleased`: the registry records a paper-private dataset with no public release.
- Options: `accept_unreleased_custom_record`, `keep_candidate`
- Registry blockers:
  > The paper describes public-figure adversarial images it assembled; no public release was located.
  > No examples will be synthesized in its place; the record exists to carry the paper mention.
- Mentioned by 1 paper:
  - `paper-f6dcb0e50d10ea38`, page 8, role: derived collection
    > This yields a total of 10×9 = 90 adver-

## IR-086 · Pascal VOC

**Group key:** `pascal-voc` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `pascal-voc` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `pascal-voc` — Pascal VOC

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > The citing survey names Pascal VOC without year or split; this explicit VOC2011 archive does not resolve paper membership.
  > Native adapter and pinned recipe implemented; real preparation and independent limitations verification pending.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > ResNet50, VGG16 — ImageNet, Pascal VOC (Yang et al., 2024c) BLIP2(blip2-opt-2.7b), —

## IR-087 · PATA

**Group key:** `pata` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `pata` — PATA

- State: access `public`, adapter `implemented`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `identity_resolved_release_access_unresolved` (2026-09-22).
- Registry blockers:
  > All 4,934 native author label/URL rows and 24 caption groups have an exact metadata index. Reproduce with atlas datasets prepare-metadata --dataset pata --execute; no image preview is claimed.
  > Third-party images are not archived or fetched. URL availability and image rights remain unverified.
  > The demographic labels are author annotations, not self-reports. Historical paper membership and redistribution remain unreviewed.
- Mentioned by 2 papers:
  - `paper-f03c5ad315e6d835`, page 2, role: source data
    > 2021), MIAP (Schumann et al., 2021), Phase (Garcia et al., 2023), and PATA (Seth et al., 2023) datasets as they contain annotations for gender information, and all except MIAP also ann
  - `paper-32cea5e43d940514`, page 14, role: non-overlap evaluation
    > ns, we use a recent text-to-image editing Datasets PATA Pairs model Qwen-Image-Edit [83] to leave only one per- Prompts Adj

## IR-088 · perturbed gender-benchmark image variants

**Group key:** `perturbed-gender-benchmark-image-variants` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `perturbed-gender-benchmark-image-variants` — perturbed gender-benchmark image variants

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `derived_variants_unpinned` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-c65ee35ca47313c9`, page 3, role: derived collection
    > in Appendix C.1. We randomly sample images to balance 3. Preliminary: Detecting Spurious Features

## IR-089 · Pitfall ROM

**Group key:** `pitfall-rom` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `pitfall-rom` — Pitfall ROM

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `source_binary_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 3, role: experimental condition
    > Donkey Kong (1981), Space Invaders (1978), and Pitfall (1981). Obviously these “behaviors” are quali- tatively different from those of animals and m

## IR-090 · Places

**Group key:** `places` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `places` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `places` — Places

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > The citing survey names only Places; release and split remain unidentified. Native Places365 Standard256validation browsing does not resolve that paper membership.
  > Training, Challenge and other native image variants remain unprepared. Source-image publication rights remain unreviewed.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CLIP Image Retrieval, Segmenta- Waterbirds, CUB, Places, ImageNet- Text-Explanations of tion

## IR-091 · RAISE1k

**Group key:** `raise1k` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `raise1k` — RAISE1k

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Publisher RAISE-1K download requires name, affiliation, email and acceptance of research/education terms. No request was submitted on the user’s behalf.
  > Native NEF/TIFF/CSV acquisition and display adapter remain implementation work after authorized source access.
  > Exact citing-paper source release and selected membership remain unverified.
- Mentioned by 1 paper:
  - `paper-666de2b7486d80a3`, page 5, role: source data
    > ncompressed images) for Colorization [47] Val 4.7 5 training, and the RAISE1k dataset [10] for validation. 2AFC–Real Alg [Val] – Val 26.9k 5 To enable large-scale collection, our data is

## IR-092 · Ring-a-Bell

**Group key:** `ring-a-bell` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `ring-a-bell` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used. For `ring-a-bell` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `ring-a-bell` — Ring-a-Bell

- State: access `gated`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > The corpus paper does not state which concept or (K, eta) setting it evaluated; only nudity prompts are released.
  > Auto-gated on Hugging Face: each researcher must accept the dataset terms on their own account. Atlas never accepts terms on a researcher's behalf.
  > Prompts are adversarial text about explicit content: local browsing only; no public redistribution review.
- Mentioned by 1 paper:
  - `paper-09b2d7393fc75cf7`, page 7, role: evaluation
    > ce-of-means procedure described in Equation (4). We evaluate on COCO [59] annotations and Ring-a-Bell [60] Datasets. Under this setting, the attacker wishes the steering prompts, both containing only…

## IR-093 · ROSMAP

**Group key:** `rosmap` · **Entries:** 1 · **Blocker types:** `access` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). For `rosmap` (access `request_required`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `rosmap` — ROSMAP

- State: access `request_required`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **access**. Access is `request_required`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `cohort_resolved_paper_slice_unresolved` (2026-09-22).
- Registry blockers:
  > Original-source access requires an author or data-holder request.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > DensetNet-121 — ITAC, iCTCF, BRCA, ROSMAP (Basu et al., 2024b) SD-1.5, SD-XL, DeepFloyd Model Editing

## IR-094 · RS-VQA

**Group key:** `rs-vqa` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `rs-vqa` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `rs-vqa` — RS-VQA

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Survey table does not name an RSVQA variant; only the Low Resolution release is prepared.
  > Sentinel-2 imagery terms: no public redistribution review.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > LLaVa-next, InstructBLIP VQA LingoQA, RS-VQA, PMC-

## IR-095 · 2 entries linked to `saegis-clean-and-adversarial-splits`

**Group key:** `saegis-clean-and-adversarial-splits` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `saegis-clean-and-adversarial-splits` (identity `candidate`, preview `complete_target`) via `same_source_family_as` — prepared; also an entry in this queue

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `saegis-clean-and-adversarial-splits`. The options are `alias_of:saegis-clean-and-adversarial-splits` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `saegis-clean-and-adversarial-splits`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `saegis-clean-and-adversarial-splits` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:saegis-clean-and-adversarial-splits`, `distinct_release`, `keep_candidate`

### `nips17` — NIPS17

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `saegis-clean-and-adversarial-splits` (identity `candidate`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:saegis-clean-and-adversarial-splits`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `saegis-clean-and-adversarial-splits`
- Registry blockers:
  > The 1,000-image DEV set is described by dev_dataset.csv in the CleverHans repository, which lists image URLs; the repository does not host the images and its download_images.py links have been reported expired (cleverhans issue 1180).
  > The original Kaggle competition pages that host the images require a Kaggle login that Atlas will not use on a researcher's behalf.
  > The SAEgis paper's NIPS17 images are available separately as part of the SAEgis author release (entry saegis-clean-and-adversarial-splits); that does not establish this entry's identity.
- Mentioned by 3 papers:
  - `paper-d8a392188b9cf4d6`, page 5, role: evaluation
    > een attacks. 4.1.2 Datasets We conduct experiments on three datasets: NIPS17 (K et al., 2017), LLaVA-Instruct-150K (Liu et al., 2023) (LLaVA), and Medical Multimodal Evaluation Data (Che
  - `paper-6dbb0d4a7b949143`, page 14, role: evaluation
    > dataset For evaluation, we use 100 manually relabeled images from the NIPS17 dataset, focusing on commonly understood cat- These qualitative examples clearly demonstrate the strong egori
  - `paper-392b0c393c06b48e`, page 26, role: evaluation
    > image.” For evaluation, we use 100 manually relabeled images from the NIPS17 dataset, focusing on commonly recognizable object categories. Model predictions are assessed using GPT- 4, wh

### `saegis-clean-and-adversarial-splits` — SAEgis clean and adversarial splits

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_identified_paper_outputs_unpinned` (2026-09-22).
- Registry blockers:
  > Paper-to-release identity unverified: the paper names adversarial splits training and testing; the repository names them dev and test, and the paper version was not compared with this commit.
  > The repository has no licence file and every image derives from NIPS17, LLaVA-Instruct-150K (COCO) or Medical-Multimodal-Eval: local browsing only, no public redistribution review.
- Mentioned by 1 paper:
  - `paper-d8a392188b9cf4d6`, page 5, role: derived collection
    > hird contains medical images for out-of-domain evaluation. For each dataset, we construct clean splits of 800, 100, and 100 images for training (i.e., feature extraction), development (i.e., threshol…

## IR-096 · 2 entries linked to `sbbench`, `sbbench-syn`, `sbbench-syn-crop`

**Group key:** `sbbench|sbbench-syn|sbbench-syn-crop` · **Entries:** 2 · **Blocker types:** `identity` 2

**Linked to:**

- `sbbench` (identity `resolved`, preview `none`) via `same_source_family_as` — no preview
- `sbbench-syn` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared
- `sbbench-syn-crop` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for each of the 2 entries below, which option applies; until then it stays a candidate. The registry links these entries to `sbbench`, `sbbench-syn` and `sbbench-syn-crop`. The options are `alias_of:sbbench`, `alias_of:sbbench-syn` and `alias_of:sbbench-syn-crop` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `sbbench-syn` and `sbbench-syn-crop`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:sbbench`, `alias_of:sbbench-syn`, `alias_of:sbbench-syn-crop`, `distinct_release`, `keep_candidate`

### `sb-syn` — SB-Syn

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `sbbench` (identity `resolved`, preview `none`) via `same_source_family_as`; `sbbench-syn` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:sbbench`, `alias_of:sbbench-syn`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `sbbench`; `same_source_family_as` → `sbbench-syn`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-32cea5e43d940514`, page 7, role: introduction
    > ed on the motivation that our main image dataset D E B IAS L ENS Rule SB-Syn SB-Syn 84.32 44.59 D E B IAS L ENS Rule SB-Syn-Crop SB-Syn-Crop 84.71 45.55 FairFace [41] seems to better yie

### `sb-syn-crop` — SB-Syn-Crop

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `sbbench` (identity `resolved`, preview `none`) via `same_source_family_as`; `sbbench-syn-crop` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:sbbench`, `alias_of:sbbench-syn-crop`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `sbbench`; `same_source_family_as` → `sbbench-syn-crop`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper selection is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-32cea5e43d940514`, page 7, role: introduction
    > t D E B IAS L ENS Rule SB-Syn SB-Syn 84.32 44.59 D E B IAS L ENS Rule SB-Syn-Crop SB-Syn-Crop 84.71 45.55 FairFace [41] seems to better yield effective social D E B IAS L ENS Rule FairFace SB

## IR-097 · SEEDBench

**Group key:** `seedbench` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `seedbench` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `seedbench` — SEEDBench

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > ructBLIP-13B, LLaVA-1.5- — Winoground, WHOOPS!, SEEDBench, 13, Sphinx, GPT-4V

## IR-098 · Set14

**Group key:** `set14` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `set14` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `set14` — Set14

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `original_citation_only` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-08e415961919a492`, page 9, role: evaluation
    > 20.28 24.35 Table 1: Detailed super-resolution PSNR comparison on the Set14 dataset with different scaling factors. 4× super-resolution where d(·) : R3×tH×tW → R3×H×W is a downsampling

## IR-099 · Set5

**Group key:** `set5` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `set5` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `set5` — Set5

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `original_citation_only` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-08e415961919a492`, page 9, role: evaluation
    > our approach Table 2: Detailed super-resolution PSNR comparison using Set5 [4] and Set14 [62] datasets. We use a scaling on the Set5 dataset with different scaling factors. factor of 4

## IR-100 · Shapes Localization

**Group key:** `shapes-localization` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `shapes-localization` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `shapes-localization` — Shapes Localization

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_generation_recipe_identified` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Author-recipe reconstruction; historical experiment pixels are not available.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: introduction
    > es Datasets We generate three synthetic datasets: Shapes Recognition, Shapes Localization, and Shapes Relations, using a single pipeline. The shared generation ensures all three datasets are construc

## IR-101 · Shapes Recognition

**Group key:** `shapes-recognition` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `shapes-recognition` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `shapes-recognition` — Shapes Recognition

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_generation_recipe_identified` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Author-recipe reconstruction; historical experiment pixels are not available.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: introduction
    > p A.1 Synthetic Shapes Datasets We generate three synthetic datasets: Shapes Recognition, Shapes Localization, and Shapes Relations, using a single pipeline. The shared generation ensures all three

## IR-102 · Shapes Relations

**Group key:** `shapes-relations` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `shapes-relations` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `shapes-relations` — Shapes Relations

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_generation_recipe_identified` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Author-recipe reconstruction; historical experiment pixels are not available.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 13, role: introduction
    > hree synthetic datasets: Shapes Recognition, Shapes Localization, and Shapes Relations, using a single pipeline. The shared generation ensures all three datasets are constructed from the same prim

## IR-103 · simulated transistor traces

**Group key:** `simulated-transistor-traces` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `simulated-transistor-traces` — simulated transistor traces

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_release_claim_conflicts_with_repo_readme` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 18, role: derived collection
    > ior were simulated for each game, resulting in over 250 frames per game. Lesion studies Whole-circuit simulation

## IR-104 · Space Invaders ROM

**Group key:** `space-invaders-rom` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `space-invaders-rom` — Space Invaders ROM

- State: access `source_release_unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `source_binary_unresolved` (2026-09-22).
- Registry blockers:
  > Exact source data release or paper-used subset is unverified.
  > Public data/media reuse rights require separate review.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 3, role: experimental condition
    > is, three different games: Donkey Kong (1981), Space Invaders (1978), and Pitfall (1981). Obviously these “behaviors” are quali- tatively different from th

## IR-105 · TID2013

**Group key:** `tid2013` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `tid2013` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `tid2013` — TID2013

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > The authors native release is verified; the citing paper exact selected evaluation membership/protocol has not been independently reconciled.
  > Image and annotation redistribution rights remain unreviewed.
- Mentioned by 1 paper:
  - `paper-666de2b7486d80a3`, page 14, role: evaluation
    > e show the Spearman correlation coefficient of various methods on the TID2013 Dataset [45]. Note that deep networks trained for classification perform well out of the box (blue). C. TID2013 Datas

## IR-106 · Turing Eye Test

**Group key:** `turing-eye-test` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `turing-eye-test` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `turing-eye-test` — Turing Eye Test

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Public preview redistribution is not approved.
- Mentioned by 1 paper:
  - `paper-20de77d4e60fd1bd`, page 3, role: source data
    > f the textual priors in q. Specifically, the ground resolution perceptual datasets (e.g., Turing Eye Test (TET) truth is established based on the intrinsic properties of x. (Gao et al., 2025)). Each…

## IR-107 · UCF101

**Group key:** `ucf101` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `ucf101` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `ucf101` — UCF101

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Pinned public mirror population of 13,320 native AVI files, three recognition folds and 100 retained original previews is verified. Bounded browser displays retain decoded-frame parity; publisher byte equivalence remains unverified.
  > Publisher byte equivalence, exact paper splits/subsets and redistribution rights remain unverified.
- Mentioned by 2 papers:
  - `paper-6dbb0d4a7b949143`, page 5, role: evaluation
    > . We focus on robust vision en- CIFAR100, Pets (Parkhi et al., 2012), UCF101 (Soomro, coders, specifically large-scale adversarially trained Ima- 2012), and Caltech101 (Li et al., 2022).
  - `paper-392b0c393c06b48e`, page 6, role: zero-shot adversarial diagnostic evaluation
    > Figure 2 x-axis label: UCF101

## IR-108 · VG_QA_one

**Group key:** `vg-qa-one` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `vg-qa-one` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `vg-qa-one` — VG_QA_one

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 14, role: direct What’s Up split
    > object split of What’s Up [Kamath et al., 2023, Lin et al., 2014]. • VG_QA_one: Single-object localization queries on Visual Genome images, from the VG single-object split of What’s Up [Kamath e

## IR-109 · VG_QA_two

**Group key:** `vg-qa-two` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `vg-qa-two` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `vg-qa-two` — VG_QA_two

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_identified_variant_unpinned` (2026-09-22).
- Registry blockers:
  > Public preview redistribution is not approved.
  > Available author-defined reconstruction; historical paper-used revision is not established.
- Mentioned by 1 paper:
  - `paper-6c99cf73401b37d4`, page 14, role: direct What’s Up split
    > • VG_QA_two: Two-object spatial-relation queries based on Visual Genome [Krishna et al., 2017] images, from the natural VG spli

## IR-110 · VIA-Bench

**Group key:** `via-bench` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `via-bench` — VIA-Bench

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `no_release_found_name_collision_recorded` (2026-10-06).
- Registry blockers:
  > No release located: the paper (arXiv 2602.01816) says its data and code 'will be released'; no repository or dataset link was found on 2026-10-06.
  > Hugging Face MCG-NJU/VIABench and Riverlu/VIABench are a DIFFERENT benchmark (VIABench, arXiv 2607.14660: videos from blind individuals). They share a name only and must not be attached to this entry.
  > Adapter and preview are not implemented because there is no data to adapt.
- Mentioned by 1 paper:
  - `paper-20de77d4e60fd1bd`, page 1, role: introduction
    > mmon-sense priors. To stimuli. Our findings reveal a fundamental diver- address this gap, we introduce VIA-Bench, a gence between machine and human perception, challenging benchmark designed to probe…

## IR-111 · Visual-Counterfact

**Group key:** `visual-counterfact` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `visual-counterfact` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `visual-counterfact` — Visual-Counterfact

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Public preview redistribution is not approved.
- Mentioned by 1 paper:
  - `paper-24b951c4e4ec2d31`, page 3, role: evaluation
    > Setting defined below), to identify which components carry We use the Visual-Counterfact dataset (Golo- information that causally determines how the con- vanevsky et al., 2025a), which contains 469 c…

## IR-112 · Visual-Counterfact filtered 467

**Group key:** `visual-counterfact-filtered-467` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `visual-counterfact-filtered-467` — Visual-Counterfact filtered 467

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `paper_selection_release_unverified` (2026-09-22).
- Registry blockers:
  > The current author filter reconstructed over the pinned 493-row color release selects 469 rows, not the paper-reported 467. Exact historical source revision or additional selection remains unresolved.
  > A supported author-source filtering adapter remains implementation work; this audit is not preview coverage.
- Mentioned by 1 paper:
  - `paper-24b951c4e4ec2d31`, page 10, role: derived analysis subset
    > lysis for interpreting neural nlp: ping original and counterfactual colors, leaving 467 The case of gender bias. Preprint, arXiv:2004.12265. examples for analysis.

## IR-113 · Visual6502 transistor netlist

**Group key:** `visual6502-transistor-netlist` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `visual6502-transistor-netlist` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `visual6502-transistor-netlist` — Visual6502 transistor netlist

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `original_project_identified_exact_netlist_unresolved` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 2, role: source data
    > [10] for a comprehensive review). The Visual6502 team reverse-engineered the 6507 from physical integrated circuits [11] by ch

## IR-114 · VL-Gender

**Group key:** `vl-gender` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `vl-gender` — VL-Gender

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_recipe_located_no_hosted_data` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-f03c5ad315e6d835`, page 2, role: introduction
    > s including occupation-related information, we drop those images. Our VL-Gender evaluation contains 5,000 images, i.e. 1,000 images from each dataset, balanced for the gender and ethnicity attributes

## IR-115 · VQA-Constraints

**Group key:** `vqa-constraints` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `vqa-constraints` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `vqa-constraints` — VQA-Constraints

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Public media redistribution is not approved.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 29, role: cited-study dataset in survey table
    > 4a) LLaVa VQA, Model Editing VQA-Constraints Causal Tracing (Basu et al., 2024b) SD-XL, DeepFloyd Knowledge L

## IR-116 · visualQA, linked to `vqa-v2`

**Group key:** `vqa-v2` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `vqa-v2` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `vqa-v2`. The options are `alias_of:vqa-v2` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `vqa-v2`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`.

**Options:** `alias_of:vqa-v2`, `distinct_release`, `keep_candidate`

### `visualqa` — visualQA

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. The registry links this entry to `vqa-v2` (identity `resolved`, preview `complete_target`) via `same_source_family_as`. The exact release, variant or subset the paper used is not human-verified.
- Options: `alias_of:vqa-v2`, `distinct_release`, `keep_candidate`
- Registry links: `same_source_family_as` → `vqa-v2`
- Registry identity audit: `family_mentioned_version_unresolved` (2026-09-22).
- Registry blockers:
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > , 2024c) BLIP2(blip2-opt-2.7b), — visualQA, CroPA instructBLIP(instructblip-

## IR-117 · VQA v2 m+n subsets

**Group key:** `vqa-v2-m-n-subsets` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `vqa-v2-m-n-subsets` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `vqa-v2-m-n-subsets` — VQA v2 m+n subsets

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_subset_file_identified` (2026-09-22).
- Registry blockers:
  > Exact paper-specific source release or selected subset remains unverified; source research alone does not resolve this candidate.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-7ed1979562251931`, page 4, role: derived evaluation collection
    > ons. We define the dataset “What color is”, among others. VQA v2 m+n as a subset of VQA v2, including m images, each associated with n questions, result

## IR-118 · VTAB

**Group key:** `vtab` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `vtab` — VTAB

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `benchmark_suite_no_single_release` (2026-10-08).
- Registry blockers:
  > Original release identity and rights need verification.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CUB200, VTAB (Pruthi et al., 2020) ResNet-56 —

## IR-119 · Wall Street Journal

**Group key:** `wall-street-journal` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `wall-street-journal` — Wall Street Journal

- State: access `unverified`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_mentioned_version_unresolved` (2026-09-22).
- Registry blockers:
  > Access to the exact data files has not been verified.
  > The exact paper release, source variant, or derived collection remains unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-6d747c88d639c5aa`, page 13, role: source data
    > cognition task described in [8], but with an updated training set using segments from the Wall Street Journal [40] and Spoken Wikipedia Corpora [41]. We screened the Wall Street Journal (WSJ) [40], T…

## IR-120 · WILDS

**Group key:** `wilds` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open).

**Options:** `distinct_release`, `keep_candidate`

### `wilds` — WILDS

- State: access `public`, adapter `not_started`, preview `none`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `family_only` (2026-09-22).
- Registry blockers:
  > Exact source variant or paper release is unresolved.
  > Adapter and preview are not implemented.
- Mentioned by 1 paper:
  - `paper-a47845c66d4a3f48`, page 13, role: bibliography-only reference
    > , M. Zhang, A. Balsubramani, W. Hu, M. Yasunaga, R. L. Phillips, I. Gao, et al. Wilds: A benchmark of in-the-wild distribution shifts. arXiv preprint arXiv:2012.07421, 2020. [75] A. Krizhevsky and G.…
