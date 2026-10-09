# Review brief for the 2026-10-06 Claude pass

This brief was written before any independent review of this pass existed. The Codex pass's reviewer then read it and, at 17:41 JST, extended [its code-only review](independent-limitations-review-20261006.md) to the files below (synthetic checks and aggregate receipts only). It reproduced one integrity defect and sent four more concrete findings for repair: a stale content-addressed processor-input cache was trusted by name, COCO-GB stripped caption whitespace while calling the values raw, a non-finite floating TIFF erased finite contrast, RSVQA and COCO-GB read ZIP members before checking a size bound, and the weak native-ZIP verification path did not compare the retained payload with the recorded CRC and length. Each now has a regression test in the modules listed below. The brief's own note on the delegation model is historical: this pass did not delegate, because the Claude tooling that did the work cannot select the model AGENTS.md names, and the only review of it was the Codex reviewer's. The reviewer inspected no real native record, image or caption, so it does not replace a read of the converters against the real releases. Everything is uncommitted and shares a working tree with the Codex pass, so `git diff` mixes both; the file list below is the Claude pass's own.

## Shared surfaces changed (review these first; each has a regression test)

| File | Change | Test |
| --- | --- | --- |
| `src/dataset_atlas/storage/display.py` | `browser_render()`: faithful, bounded PNG rendering of TIFF (16-bit and float scaled linearly, alpha kept, longer edge capped at 4096) | `tests/unit/test_display_rendering.py` |
| `src/dataset_atlas/api/app.py` | `?representation=display` (+ `cached_display`, header `X-Atlas-Media-Representation: display`); `.tif/.tiff` allowed for pack-local media; TIFF flagged `browser_render_required` at exposure; `pinned_preview_original()` hands processors a content-addressed file for a protected pinned original; extensionless retained videos typed by container signature | `test_display_rendering.py`, `test_pinned_preview_inputs.py`, `test_retained_video_type.py` |
| `src/dataset_atlas/adapters/core.py` | `.tif/.tiff` media type; structured adapter flags TIFF assets | `test_display_rendering.py` |
| `src/dataset_atlas/adapters/archive_variants.py` | `prepare_media()` so a media read does not re-open every remote archive directory | `test_archive_variants.py` |
| `src/dataset_atlas/jobs/coordinator_lock.py`, `src/dataset_atlas/cli/__init__.py` | workspace flock held by `atlas serve` and `atlas analyze` (SPEC 3.2) | `test_coordinator_lock.py` |
| `src/dataset_atlas/catalogue.py` | catalogue tiles skip records flagged `_atlas_source_status` | `test_catalogue_and_aggregate.py` |
| `apps/web/src/lib/display.ts` (+ test) | non-browser images use `display`; safe view still wins when the researcher turns it on | `display.test.ts` |
| `src/dataset_atlas/converters/{remote_sensing,adversarial_images,captioning_bias,visual_illusions}.py`, `text.py` (`ring_a_bell_nudity`), `__init__.py` | new deterministic converters, each pinned by row digest in its recipe | `tests/unit/test_converters_*.py` |
| `scripts/verify_native_previews.py` | reports which native check each asset got; remote-ZIP members are accepted only with a receipt saying there is no independent content hash | `test_verify_native_identity.py` |

## Questions worth asking

1. `pinned_preview_original()` writes into `work/media-cache`. Is a content-addressed name safe against a corrupted pin (the bytes are read from the compact store, which verifies its own checksum)?
2. The `display` route accepts `application/octet-stream`. Is Pillow decoding of attacker-supplied bytes bounded enough (50 M pixel check after `Image.open`, then thumbnail)?
3. The coordinator lock protects the entry points, not `create_app()`: a script that builds an app directly can still run a second coordinator. Is that acceptable, or should `JobManager` own the lock?
4. `scripts/derive_catalogue_modalities.py` reports a modality only if a preview record maps the field; sources whose question text is unmapped (for example NaturalBench) read as image-only. Is under-reporting acceptable?
5. Identity states: IllusionBench is marked `resolved` to the authors' Hugging Face release although the release disagrees with the paper's counts; COCO-GB, SAEgis, RS-VQA and Ring-A-Bell stay `candidate`. Do the stated reasons hold?

## Reproduce the receipts

```bash
.venv/bin/python -m pytest -q                                    # Python suite
npm test --prefix apps/web && npx tsc -b --noEmit -p apps/web    # frontend
.venv/bin/atlas datasets validate --all                          # 333 entries, 0 errors
.venv/bin/atlas serve --port 8767 &                              # one coordinator per workspace
ATLAS_LIVE_API=http://127.0.0.1:8767 npx --prefix apps/web playwright test   # live specs
.venv/bin/python scripts/verify_preview_media_smoke.py --api http://127.0.0.1:8767 --output /tmp/media.json
.venv/bin/python scripts/verify_complete_index_smoke.py --api http://127.0.0.1:8767 --output /tmp/index.json
.venv/bin/python scripts/verify_native_previews.py --dataset rs-vqa --dataset saegis-clean-and-adversarial-splits --api http://127.0.0.1:8767 --output /tmp/native.json
.venv/bin/python scripts/verify_saegis_pairing.py --output /tmp/pairing.json   # network: fetches 2,400 pinned files
```

Empty-workspace reproduction of any new dataset: copy `registry/` and `schemas/` into a scratch directory, then `atlas --root DIR previews fetch --execute --dataset ID --per-dataset-download-bytes N --per-dataset-output-bytes N --total-download-bytes N` and compare `snapshot_id` with this workspace (the six new datasets matched exactly).

## Known limits a reviewer should confirm are stated honestly

- Four live browser specs (model-send opt-ins) were skipped, not run: no local VLM was serving.
- iNaturalist (8.9 GB) was not re-fetched from an empty workspace.
- Storage is above the 100 GB target (ceiling 150 GB holds): see `reports/final-status.json`.
- The SAEgis embedding observation is exploratory on a 100-image preview and is not an attack-detection result.
- Ring-A-Bell is auto-gated: reproducing it needs the reviewer's own Hugging Face account to have accepted the dataset terms.
