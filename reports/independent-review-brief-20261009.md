# Review of the 2026-10-09 changes

Scope: the commits after `0497363` on branch `coverage-next`. **A same-model-family review is not human acceptance**, and no human has reviewed these changes.

## What changed

| Area | Files |
| --- | --- |
| Shared remote-Parquet code | `src/dataset_atlas/storage/ranges.py` (timeout retry, gate message), `preparation/remote_sample.py` (recipe-fixed row-group sample), `preparation/worker.py`, `adapters/remote_columnar.py` (configuration pattern) |
| New datasets | BBQ-V (`registry/recipes/sbbench.yaml`), MultiTrust (`adapters/multitrust.py`, `registry/recipes/multitrust.yaml`, `registry/media/multitrust.json`) |
| Catalogue | 49 alias, view, platform and no-dataset entries moved to `registry/excluded/` with records in `registry/candidate_dispositions.yaml` (3 restored after review); `scripts/exclude_catalogue_entries.py` |
| Public site | `exports/guide.py`, `exports/publication.py`, `cli` (`publish schemas`), `apps/web/src/dataset/GuideCards.tsx`, `provider.ts`, `examples/public-schema/` |
| Verification | `docs/acceptance-matrix.json`, `scripts/verify_acceptance_matrix.py`, `queries/results.py` (unjoined overlay items counted) |

## Review performed

A separate Sonnet 5.5 reviewer, given the code but not the author's conclusions, read the shared-code and public-site changes and the registry exclusions. Findings, all fixed in `503c658` with regression tests unless noted:

- Three entries were excluded although their own records describe separately released data (`laion-aesthetics`, two hidden-content sets): restored.
- `illusory-vqa` pointed at IllusionVQA instead of IllusoryVQA; four live entries still linked to moved IDs: corrected.
- `FixedRowGroupSampler` lacked `.total`, which a native record filter reads: added.
- The guide called credentialed public mirrors gated: fixed.
- `atlas publish schemas` could delete unrelated JSON files or all committed schemas: now deletes only schemas it wrote and refuses when nothing could be written.
- A failed guide fetch was cached for the page's lifetime; the guide card could show the previous dataset for one render: fixed.
- Stale 333 counts (README, getting started, a browser test): fixed; a test now ties the headline numbers together.

Accepted, not changed: bytes of a timed-out range attempt are discarded and not counted against the budget (documented in the code); `items_unjoined` is relative to the pack an artifact is attached to, so subset packs report more; schemas publish field names and recipe-declared categories whatever the annotations right says.

## Not reviewed

MultiTrust's adapter and tests were written by a delegate and checked by its own tests and live verification only. The seven GitHub-hosted entries and the storage plan are evidence records. No change was reviewed by the person who owns the data decisions.
