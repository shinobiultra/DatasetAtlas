# Acquisition plan — what is prepared, what is next, what is blocked

Generated 2026-09-22 against the 333-entry catalogue. This is a plan, not coverage: an entry
is only "browsable" once a preparation run has downloaded, verified and indexed its declared
population. Nothing in this file was downloaded to produce it beyond HTTP `HEAD` size probes.

## Prepared this session

| Dataset | Release | Records | Downloaded | Notes |
| --- | --- | --- | --- | --- |
| `space-10` | `efd7316e…` (HF revision pin) | 4,132 / 4,132 | 872 MB | Eight embedded images per record; complete-population index and media serve live. Only the 2D QA release is public — the 3D media release is not out, so `access` stays `partial_public_2d_only`. |

The approved budget for this session was ≈1 GB and `space-10` consumed 872 MB of it. No other
download was started.

## Ready to run — needs a budget approval only

| Dataset | Kind | Download | Blocker |
| --- | --- | --- | --- |
| `cifar-10-c` | `http_archive` (Zenodo) | 2.92 GB (md5 pinned) | Over the session budget, **and** needs a `cifar_c_npy` adapter (stacked `.npy` per corruption); the recipe is committed but not runnable. |

## Recipes written, deliberately not ready

The planner refuses an `http_archive` plan without a per-file checksum and a declared
`expected_count`, so these fail closed rather than downloading something unverified:

| Dataset | Download | What it needs |
| --- | --- | --- |
| `textvqa` | 24.8 MB (two annotation JSONs) | SHA-256 for `TextVQA_0.5.1_{train,val}.json`. Images come from Open Images and are a separate, larger fetch. |
| `vizwiz` | 1.7 MB (`Annotations.zip`) | SHA-256 for `Annotations.zip`. Images are a separate ~9 GB fetch. |

Recording those two checksums is a one-off ~27 MB fetch; that is the smallest next budget ask
and would add two annotation-only datasets (media referenced, not embedded).

## Hugging Face releases that need a format-specific recipe

`hatefulillusion`, `omnispatial`, `pmc-vqa` — the planner reports "no native Arrow/Parquet
shards in this release". The columnar path cannot be pointed at them; each needs its own
acquisition recipe. Not attempted.

## Catalogue-wide state (333 entries)

| State | Count | Meaning |
| --- | --- | --- |
| Previews prepared | 79 | Preview pack built from verified source. |
| Complete-population indices | 74 | Whole declared population indexed and queryable. |
| `access: public` | 141 | Public source located; not the same as prepared. |
| `access: unverified` | 118 | Source page not yet verified against the paper's claim. |
| `access: gated` | 22 | Registration, licence click-through or request form. |
| `access: unreleased` | 17 | Paper describes a collection that was never published; `adapter: not_applicable`. |
| `access: request_required` | 4 | Author contact required. |
| Other verification states | 28 | Source page public but data link unverified, variant of a base source, etc. |

`scripts/audit_preparation.py` reports 80 entries as plannable and 253 as requiring
`work/access` material (credentials, manual downloads or a licence acceptance that this tool
does not click through).

## Duplicate catalogue pairs resolved

Three pairs described the same release under two IDs. Each retired ID is now an alias of the
canonical entry, recorded as an `alias_resolved_from` relationship plus an
`alias_redirects` disposition, and old deep links still resolve through the API:

- `describable-textures-dataset` → `dtd`
- `pets` → `oxfordpet`
- `okvqa` → `ok-vqa`

## Not done

- No adapter exists for `cifar_c_npy`, COCO-QA (line-aligned files) or OK-VQA (two-file join).
  Those three datasets cannot be prepared regardless of budget.
- The 235 entries with no recipe are unchanged apart from the relationship and access-state
  corrections above; most sit behind gated or unverified sources.
