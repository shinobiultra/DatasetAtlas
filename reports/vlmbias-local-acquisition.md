# VLMBias local source acquisition — 2026-09-22

Four distinct synthetic image configurations were acquired from author Hugging Face repositories at exact pinned revisions. All source files matched the repository SHA-256 and declared byte size. Full local Parquet indices and 100-record local preview packs were built. The images and binary labels remain local; dataset cards are empty, so media publication and numeric label meanings are not approved or inferred.

| Source | Complete records | Local preview | Original source |
|---|---:|---:|---|
| `sbbench-synthetic-gender-crop-false` | 206 | 100 | [revision](https://huggingface.co/datasets/vlmbias/sbbench_synthetic_gender_crop_False/tree/b3f53090f541bfcdb491217dfec7aa639289ad8a) |
| `sbbench-synthetic-age-crop-false` | 333 | 100 | [revision](https://huggingface.co/datasets/vlmbias/sbbench_synthetic_age_crop_False/tree/95ac0c3020ff710295a6ed5c0216718f03383151) |
| `sbbench-synthetic-gender-crop-true` | 406 | 100 | [revision](https://huggingface.co/datasets/vlmbias/sbbench_synthetic_gender_crop_True/tree/a7679386395cf29e9640757f16923f823d6251ef) |
| `sbbench-synthetic-age-crop-true` | 511 | 100 | [revision](https://huggingface.co/datasets/vlmbias/sbbench_synthetic_age_crop_True/tree/43769ef07d9388ebb4c3dc74b548eea615d0c93b) |

Total: **1,456** real author records and **400** local preview records across four source-specific IDs. Source transfer: **1,850,267,056 bytes** across five pinned Parquet shards.

`tests/integration/test_vlmbias_local.py` passed 5/5 real local checks for source hashes, preview and index counts, complete-result label filters, and on-demand image-byte resolution. Details and every shard digest are in `reports/vlmbias-local-acquisition.json`.

ViSU-Text is a separate metadata-only child. Its author repository at [revision 9afabb85](https://huggingface.co/datasets/aimagelab/ViSU-Text/tree/9afabb85b5570fa883b7caa0561d8c8d71d84dcd) requires a manual institutional application and contact sharing; no files were acquired. Its unsafe vision images are deliberately unreleased. This is an actual access gate for text and an unavailable vision component, distinct from an adapter gap.

A workbench API smoke query over the 206-record complete snapshot returned one record and exact count 206; fetching that record's tokenized media returned HTTP 200, `image/png`, 1,688,110 bytes. The source assets remain local and are not in the public static bundle.
