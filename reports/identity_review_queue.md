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

46 entries in 44 groups; 1 groups hold more than one entry.

Blocker types: `identity` 42, `access` 4, `unreleased` 0, `source_availability` 0, `adapter` 0.

Preview states of the entries: `none` 1, `complete_target` 45.

Retired ids (no group in the registry produces these keys any more, for example because a person resolved all its members or its group was merged or split; each id stays reserved and is never reused): IR-001 (`agent-security-bench`), IR-002 (`artbench-2`), IR-003 (`artchive`), IR-004 (`asteroids-rom`), IR-005 (`bam-fg`), IR-007 (`brca`), IR-009 (`cc3m`), IR-011 (`cifar-10`), IR-015 (`concept-editing-dataset`), IR-016 (`contrastive-prompts`), IR-019 (`cub-200-2011`), IR-020 (`custom-dataset`), IR-021 (`custom-image-editing-dataset`), IR-022 (`custom-neonatal-rat-ganglion-recordings`), IR-023 (`custom-speech-segment-collection`), IR-024 (`custom-ternus-psychophysics-responses`), IR-025 (`dall-e-generated-target-images`), IR-026 (`deepfashion`), IR-027 (`donkey-kong-rom`), IR-028 (`e-ic`), IR-029 (`e-vqa`), IR-036 (`first-person-social-interactions-dataset`), IR-039 (`gaussian-rubbish-examples`), IR-040 (`gda-adversarial-image-variants`), IR-041 (`gpt-4v-filtered-vl-gender-subset`), IR-042 (`group-labels`), IR-044 (`hc-bench`), IR-045 (`hellaswag-pro`), IR-046 (`ictcf`), IR-047 (`illusionbench-3c643c29`), IR-049 (`illusionvqa`), IR-050 (`imagenet|imagenet-1k|imagenet-ilsvrc-2012`), IR-051 (`itac`), IR-052 (`laion`), IR-053 (`laion-aesthetics`), IR-055 (`middlebury`), IR-059 (`mnist`), IR-061 (`ostris-dataset`), IR-062 (`paper-08e415961919a492-unnamed-11-image-inpainting-set`), IR-063 (`paper-08e415961919a492-unnamed-real-noise-benchmark-46`), IR-064 (`paper-12e8bd34b4a2f2a8-unnamed-harmful-instruction-evaluation-set`), IR-065 (`paper-12e8bd34b4a2f2a8-unnamed-harmful-sentence-corpus`), IR-066 (`paper-164d7c221452ffec-unnamed-cfd-morph-collection`), IR-067 (`paper-2aa40aa13ed2a25b-unnamed-objaverse-spatial-images`), IR-068 (`paper-2aa40aa13ed2a25b-unnamed-synthetic-spatial-training-set`), IR-069 (`paper-63c3bd849356e00f-unnamed-robust-nonrobust-feature-collections`), IR-070 (`paper-72040eccb96ead7a-unnamed-synthetic-spheres-dataset`), IR-071 (`paper-728d8c0964b540ad-unnamed-youtube-image-collection`), IR-072 (`paper-765a2362f8735bc4-unnamed-social-category-question-set`), IR-073 (`paper-9036b4eaa048dc21-unnamed-neuron-pair-judgment-collection`), IR-074 (`paper-944952997d24ce45-unnamed-van-gogh-painting-sample`), IR-075 (`paper-944952997d24ce45-unnamed-vma-candidate-pool`), IR-076 (`paper-959e8fc51787f7e4-unnamed-curated-internet-image-collection`), IR-077 (`paper-959e8fc51787f7e4-unnamed-internet-image-tracing-set`), IR-078 (`paper-959e8fc51787f7e4-unnamed-sea-otter-image-sample`), IR-079 (`paper-ab31cc6a994470fb-unnamed-human-adversarial-stimulus-collection`), IR-080 (`paper-c12960e5d652fb7f-unnamed-attack-generalization-collection`), IR-081 (`paper-f6dcb0e50d10ea38-unnamed-ai-generated-gender-image-attack-set`), IR-082 (`paper-f6dcb0e50d10ea38-unnamed-explicit-image-attack-set`), IR-083 (`paper-f6dcb0e50d10ea38-unnamed-historical-event-image-attack-set`), IR-084 (`paper-f6dcb0e50d10ea38-unnamed-product-screenshot-attack`), IR-085 (`paper-f6dcb0e50d10ea38-unnamed-public-figure-adversarial-image-set`), IR-088 (`perturbed-gender-benchmark-image-variants`), IR-089 (`pitfall-rom`), IR-091 (`raise1k`), IR-093 (`rosmap`), IR-096 (`sbbench|sbbench-syn|sbbench-syn-crop`), IR-103 (`simulated-transistor-traces`), IR-104 (`space-invaders-rom`), IR-110 (`via-bench`), IR-112 (`visual-counterfact-filtered-467`), IR-114 (`vl-gender`), IR-116 (`vqa-v2`), IR-118 (`vtab`), IR-119 (`wall-street-journal`), IR-120 (`wilds`).

Groups with more than one entry: IR-014 (3).

### Groups

| IR | Group | Entries | Preview states | Prepared target | Options |
| --- | --- | --- | --- | --- | --- |
| IR-006 | `bapps` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-008 | `causalgym` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-010 | `child-safety-intents` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-012 | `cifar-100-c` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-013 | `cinic-10` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-014 | linked to `coco` | 3 | complete_target 3 | `coco` (complete_target) | `alias_of:coco`, `distinct_release`, `keep_candidate` |
| IR-017 | `controlled-clevr` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-018 | `controlled-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-030 | `emoset` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-031 | `factoid` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-032 | `openimages` | 1 | complete_target 1 | `miap` (complete_target) | `alias_of:miap`, `distinct_release`, `keep_candidate` |
| IR-033 | `ffhq` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-034 | `fgvc-aircraft` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-035 | `finevision` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-037 | `flowers102` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-038 | `food101` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-043 | `gvil-paired-illusion-images` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-048 | `illusionmnist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-054 | `llava-instruct-150k-3a74a703` | 1 | complete_target 1 | `llava-instruct-150k` (complete_target) | `alias_of:llava-instruct-150k`, `distinct_release`, `keep_candidate` |
| IR-056 | `mit-states` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-057 | `mma-diffusion` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-058 | `mmstar` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-060 | `multitrust` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-086 | `pascal-voc` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-087 | `pata` | 1 | none 1 | no link | `distinct_release`, `keep_candidate` |
| IR-090 | `places` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-092 | `ring-a-bell` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-094 | `rs-vqa` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-095 | `saegis-clean-and-adversarial-splits` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-097 | `seedbench` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-098 | `set14` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-099 | `set5` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-100 | `shapes-localization` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-101 | `shapes-recognition` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-102 | `shapes-relations` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-105 | `tid2013` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-106 | `turing-eye-test` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-107 | `ucf101` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-108 | `vg-qa-one` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-109 | `vg-qa-two` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-111 | `visual-counterfact` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-113 | `visual6502-transistor-netlist` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-115 | `vqa-constraints` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |
| IR-117 | `vqa-v2-m-n-subsets` | 1 | complete_target 1 | no link | `distinct_release`, `keep_candidate` |

## Public sources whose adapter is not started

These entries have access `public` and adapter `not_started`. For each, what blocks it, read from the registry's own state:

No entry is in this state.

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

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `multitrust` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used. For `multitrust` (access `gated`) the blocker is access, a user action such as a request, terms or credentials, not identity; the identity decision can be taken independently.

**Options:** `distinct_release`, `keep_candidate`

### `multitrust` — MultiTrust

- State: access `gated`, adapter `tested`, preview `complete_target`, identity `candidate`.
- Blocker type: **access**. Access is `gated`: getting the data needs a request, terms or credentials, which is a user action. The identity decision is separate from it.
- Options: `distinct_release`, `keep_candidate`
- Registry identity audit: `author_benchmark_page_located` (2026-09-22).
- Registry blockers:
  > Hugging Face thu-ml/MultiTrust (CC BY-SA 4.0 per the card, auto-gated) requires each researcher to accept its terms on their own account; they allow non-commercial academic use only and forbid distributing any part of the dataset. Checked 2026-10-08 with the researcher's configured credential: auth_check and a HEAD of one data file answered HTTP 403 GatedRepo (the 10,549-file listing noted on 2026-10-06 does not show that access was ever granted). The researcher has since accepted the terms on their own account and on 2026-10-09 auth_check succeeded, so this workspace can read the release; a colleague must accept the terms themselves, and Atlas never accepts them for anyone.
  > A suite of heterogeneous tasks, not one homogeneous collection: 11,512 query rows of 50 member tasks in five aspects, read from 62 query files in six layouts. Each record is one query row; image-only tasks (450 images of the NSFW, risk-identification and stereo-generation tasks), shared image pools and pairings that the authors loaders make at run time (random pick, directory order, cross product) are counted in the task inventory and not joined to a row; the k-shot Enron table is not a query file and is not indexed.
  > Component source datasets (for example the VizWiz-Priv, VISPR, AdvGLUE, MM-SafetyBench, SafeBench and RealToxicityPrompts folders that the file names and the authors loaders name) keep their own licences and the authors state they do not own the image copyrights, so rights stay not_reviewed and the records and 100 preview originals are local only; the access terms forbid redistribution.
  > The citing papers use the MultiTrust framework for transfer attacks (ensemble SSA-CWA adversarial examples), so the examples a researcher would want are those they generated, which were not located; this entry is the authors current release at one pinned revision, not the corpus-used population, and identity stays candidate.
  > Images stay remote: all 12,566 image references of the rows were found in the pinned listing (none absent), but only the 100 preview originals were fetched and checked against their pinned hashes; the rest are fetched one at a time on request. 57 images exceed 10 MB (the largest is 51.9 MB); one of them was served whole by the media route in the live check, the others were not tried.
- Mentioned by 2 papers:
  - `paper-392b0c393c06b48e`, page 26, role: transfer-attack framework
    > Ensemble-based Transfer Attacks We further evaluate MLLM robustness using the MultiTrust benchmarking framework [68], which employs ensemble-based SSA-CWA attacks to generate highly transferable adve…
  - `paper-6dbb0d4a7b949143`, page 14, role: transfer-attack framework
    > g the attacks on the COCO image captioning task. These exam- MultiTrust benchmarking framework (Zhang et al., ples illustrate the varying degrees of model susceptibility

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

## IR-095 · SAEgis clean and adversarial splits

**Group key:** `saegis-clean-and-adversarial-splits` · **Entries:** 1 · **Blocker types:** `identity` 1

**Linked to:** nothing.

**Decision needed.** A person decides, for the entry below, which option applies; until then it stays a candidate. There is no registry link from this entry to another entry, so `alias_of` has no concrete target. The options are `distinct_release` (a release of its own) and `keep_candidate` (leave the identity open). `saegis-clean-and-adversarial-splits` already has a prepared preview of its own, yet the identity is still a candidate: the preview does not settle which release the paper used.

**Options:** `distinct_release`, `keep_candidate`

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
