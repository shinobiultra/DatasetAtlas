# Identity review queue

These are decisions for a person. Nothing in this file changes any registry record: `coverage.identity`, `release`, `preview`, `adapter` and every other field stay exactly as they are until a person records a decision. Recommendations are not acceptance, and no option below is ranked or preferred.

## How to read this

- An entry is here because the registry records its `coverage.identity` as `candidate` or `family_or_variant_candidate`: a paper mentions the name, but the exact release, variant or subset the paper used is not human-verified. Every such entry appears exactly once.
- Entries the registry already links with `same_source_family_as`, `derived_from`, `annotation_overlay_of` or `source_subset_of` to the same target share a group. Nothing is grouped by name similarity. A group is a reading aid: each entry is decided on its own.
- Options. `alias_of:<id>`: the paper's name is another name for that registry entry. `distinct_release`: the paper's dataset is a release of its own. `accept_unreleased_custom_record`: a paper-private dataset with no public release, kept as an unreleased custom record. `keep_candidate`: leave the identity open.
- Preview and adapter states come from `reports/dataset_coverage.csv`, the merged catalogue view; identity, links, access and evidence come from `registry/datasets/*.yaml`. A link to a prepared family is a pointer, never coverage: an entry whose preview is `none` stays `none` until a person decides.
- Blocker types. `identity`: the exact release, variant or subset is not human-verified (a family alias or variant of another entry, or a name with no link). `access`: the data is gated or needs a request, which is a user action and not an identity question. `unreleased`: the registry records a paper-private dataset with no public release. `source_availability`: the registry's latest access audit records the source host as unresponsive or unresolvable. `adapter`: identity is settled and only an adapter is missing; such entries are outside this queue, so no entry below has this type.
- IDs. `IR-NNN` comes from `registry/identity-review-ids.json`. An id is never renumbered or reused. When a person resolves one member of a group, the group keeps its id even though its set of link targets changed. A group formed by merging or splitting other groups takes a new id, and the ids it replaced are listed as retired in the summary.
- Quoted lines (`>`) are text exactly as the registry stores it (the line the merged catalogue view has already dropped as disproved, such as `Adapter and preview are not implemented.` on a prepared entry, is not quoted); paper excerpts are shortened to 200 characters.
- This markdown is the current source of truth. Each group is also kept as a `kind: identity_decision` record in `work/corpus/identity_review_queue.jsonl`, a file this builder owns (the corpus pipeline's own review queue is never touched). While a record has status `open`, its `group_key`, `members` and `options` are a snapshot refreshed on every run; a record with any other status is never changed; a record whose group no longer exists is flagged `retired: true`.

## Summary

99 entries in 96 groups; 2 groups hold more than one entry.

Blocker types: `identity` 75, `access` 7, `unreleased` 16, `source_availability` 1, `adapter` 0.

Preview states of the entries: `none` 54, `complete_target` 45.

Retired ids (no group in the registry produces these keys any more, for example because a person resolved all its members or its group was merged or split; each id stays reserved and is never reused): IR-002 (`artbench-2`), IR-009 (`cc3m`), IR-011 (`cifar-10`), IR-015 (`concept-editing-dataset`), IR-016 (`contrastive-prompts`), IR-019 (`cub-200-2011`), IR-020 (`custom-dataset`), IR-021 (`custom-image-editing-dataset`), IR-023 (`custom-speech-segment-collection`), IR-025 (`dall-e-generated-target-images`), IR-039 (`gaussian-rubbish-examples`), IR-040 (`gda-adversarial-image-variants`), IR-041 (`gpt-4v-filtered-vl-gender-subset`), IR-044 (`hc-bench`), IR-049 (`illusionvqa`), IR-050 (`imagenet|imagenet-1k|imagenet-ilsvrc-2012`), IR-053 (`laion-aesthetics`), IR-059 (`mnist`), IR-061 (`ostris-dataset`), IR-088 (`perturbed-gender-benchmark-image-variants`), IR-096 (`sbbench|sbbench-syn|sbbench-syn-crop`), IR-112 (`visual-counterfact-filtered-467`), IR-114 (`vl-gender`), IR-116 (`vqa-v2`).

Groups with more than one entry: IR-014 (3), IR-095 (2).

### Groups

| IR | Group | Entries | Preview states | Prepared target | Options |
| --- | --- | --- | --- | --- | --- |
| IR-001 | `agent-security-bench` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-003 | `artchive` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-004 | `asteroids-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-005 | `bam-fg` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-006 | `bapps` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-007 | `brca` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-008 | `causalgym` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-010 | `child-safety-intents` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-012 | `cifar-100-c` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-013 | `cinic-10` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-014 | linked to `coco` | 3 | complete_target 3 | `coco` (complete_target) | `alias_of:coco`, `distinct_release`, `keep_candidate` |
| IR-017 | `controlled-clevr` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-018 | `controlled-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-022 | `custom-neonatal-rat-ganglion-recordings` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-024 | `custom-ternus-psychophysics-responses` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-026 | `deepfashion` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-027 | `donkey-kong-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-028 | `e-ic` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-029 | `e-vqa` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-030 | `emoset` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-031 | `factoid` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-032 | `openimages` | 1 | complete_target 1 | `miap` (complete_target) | `alias_of:miap`, `distinct_release`, `keep_candidate` |
| IR-033 | `ffhq` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-034 | `fgvc-aircraft` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-035 | `finevision` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-036 | `first-person-social-interactions-dataset` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-037 | `flowers102` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-038 | `food101` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-042 | `group-labels` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-043 | `gvil-paired-illusion-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-045 | `hellaswag-pro` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-046 | `ictcf` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-047 | `illusionbench` | 1 | none 1 | `illusionbench-3c643c29` (complete_target) | `alias_of:illusionbench-3c643c29`, `distinct_release`, `keep_candidate` |
| IR-048 | `illusionmnist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-051 | `itac` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-052 | `laion` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-054 | `llava-instruct-150k-3a74a703` | 1 | complete_target 1 | `llava-instruct-150k` (complete_target) | `alias_of:llava-instruct-150k`, `distinct_release`, `keep_candidate` |
| IR-055 | `middlebury` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-056 | `mit-states` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-057 | `mma-diffusion` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-058 | `mmstar` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-060 | `multitrust` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
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
| IR-089 | `pitfall-rom` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-090 | `places` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-091 | `raise1k` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-092 | `ring-a-bell` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-093 | `rosmap` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-094 | `rs-vqa` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-095 | linked to `saegis-clean-and-adversarial-splits` | 2 | none 1, complete_target 1 | `saegis-clean-and-adversarial-splits` (complete_target; also in this queue) | `alias_of:saegis-clean-and-adversarial-splits`, `distinct_release`, `keep_candidate` |
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
| IR-113 | `visual6502-transistor-netlist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-115 | `vqa-constraints` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-117 | `vqa-v2-m-n-subsets` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-118 | `vtab` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-119 | `wall-street-journal` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-120 | `wilds` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |

## Public sources whose adapter is not started

These entries have access `public` and adapter `not_started`. For each, what blocks it, read from the registry's own state:

- `first-person-social-interactions-dataset` (group IR-036) — blocker type **source_availability**. The registry's latest access audit (2026-10-08) records `author_page_identified_media_host_unresolvable`: the source host did not answer or did not resolve. This is source availability, not identity.
  Registry identity audit: `original_source_and_author_reformat_distinct` (2026-09-22).
  Registry description:
  > First-Person Social Interactions Dataset (FPSI) and Watanabe training selection.
  Registry blockers:
  > The author page (ai.stanford.edu/~alireza/Disney/) links 113 AVI videos and annotation ZIPs hosted on webshare.ipat.gatech.edu over plain HTTP; the host did not answer a HEAD request within 30 s over either http or https on 2026-10-06 (an upstream availability problem to retry).
  > The videos are AVI files, which browsers cannot play, and the host is HTTP-only, which Atlas's fetch layer does not use: even when the host returns, preparation needs a transcoding or an HTTPS mirror (an implementation gap beyond the outage).
  > The citing paper's training selection (the Watanabe selection) is not identified, and the page states no licence.
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
- Mentioned by 1 paper:
  - `paper-2df1203e2d3767bb`, page 6, role: introduced intent overlay
    > ], MM- SafetyBench [2], OmniSafeBench-MM [4], and SafeBench [33]. Moreover, we added 747 intents related to the new Child Safety category, generated with the assistance of OpenAI GPT-5.4, accessed vi…

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

## IR-014 · 3 entries linked to `coco`

**Group key:** `coco` · **Entries:** 3 · **Blocker types:** `identity` 3

**Linked to:**

- `coco` (identity `resolved`, preview `complete_target`) via `annotation_overlay_of` and `same_source_family_as` — prepared

**Decision needed.** A person decides, for each of the 3 entries below, which option applies; until then it stays a candidate. The registry links these entries to `coco`. The options are `alias_of:coco` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open); each entry offers only the alias options for the targets it links to. A prepared preview exists for `coco`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `coco-one`, `coco-two` and `cocogender` already have a prepared preview of their own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:coco`, `distinct_release`, `keep_candidate`

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

## IR-032 · OpenImages, linked to `miap`

**Group key:** `miap` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:**

- `miap` (identity `resolved`, preview `complete_target`) via `same_source_family_as` — prepared

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. The registry links this entry to `miap`. The options are `alias_of:miap` (the paper's name is another name for that entry), `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). A prepared preview exists for `miap`; the paper's exact release is unresolved, so no entry here inherits it, and an entry whose preview is `none` stays `none`. `openimages` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `alias_of:miap`, `distinct_release`, `keep_candidate`

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

## IR-034 · FGVC-Aircraft

**Group key:** `fgvc-aircraft` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `fgvc-aircraft` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `fgvc-aircraft` — FGVC-Aircraft

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
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

## IR-037 · Flowers102

**Group key:** `flowers102` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `flowers102` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

### `flowers102` — Flowers102

- State: access `public`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **identity**. No registry link to another entry; the exact release, variant or subset the paper used is not human-verified.
- Options: `distinct_release`, `keep_candidate`
- Registry blockers:
  > Original release identity and rights need verification.
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
- Mentioned by 1 paper:
  - `paper-25eaa8c74ce76800`, page 30, role: cited-study dataset in survey table
    > CLIP(ViT-B/16 + LoRA) — FGVC-Aircraft, Food101, Flowers102,

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
- Mentioned by 1 paper:
  - `paper-b039401c04ff9b91`, page 4, role: derived collection
    > ure 3, each question The statistics of our dataset is shown in Table 2. concerns a pair of images (IMG1 and IMG2). One Note that since this dataset is only used for the eval- image (IMG1) is illusion…

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
- Mentioned by 1 paper:
  - `paper-80b7ba2e277a20c5`, page 7, role: out-of-domain evaluation
    > l variants enhance scale coverage. (VQA) tasks: SimpleVQA [8], MMStar [7], and RealWorldQA [30].

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
- Mentioned by 1 paper:
  - `paper-ad50206beabc5a94`, page 2, role: source data
    > [10] for a comprehensive review). The Visual6502 team reverse-engineered the 6507 from physical integrated circuits [11] by ch

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
