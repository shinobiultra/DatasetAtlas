# Preparing a dataset on request

In the local workbench, open a dataset and choose **Prepare full data**. Set download and index budgets, review the source population and pinned files, then choose **Download and prepare**. Planning reads source metadata but does not download the dataset. Preparation runs in a separate process; its status survives a server restart. The same panel exposes cancellation, retry and opening the prepared result.

The command-line equivalent is:

```sh
atlas datasets acquire --dataset illuchar --max-download-bytes 4000000000 --max-output-bytes 2000000000
# Add --execute to approve and start the printed plan.
atlas datasets preparation --id PLAN_ID
atlas datasets preparation --id PLAN_ID --cancel
atlas datasets preparation --id PLAN_ID --retry
# Re-derive a completed version's coverage/evidence from its own receipt (idempotent),
# and optionally make it the active version. This is the only sanctioned way to change
# a prepared version's catalogue metadata.
atlas datasets preparation --id VERSION_ID --refresh-metadata DATASET_ID --activate
# Explicit eviction: list, then remove, versions nothing can reach any more.
atlas datasets prune
atlas datasets prune --execute
```

Supported acquisition paths are pinned native Hugging Face Arrow/Parquet shards, explicit original-archive recipes in `registry/recipes`, and already configured local adapters. A repository revision and optional subdirectory in a Hugging Face source URL are respected. No repository Python code is executed. All selected source shards are retained separately, with source filename, row and checksum provenance. Different configurations or overlapping splits are not deduplicated or asserted to be independent examples.

Recipes name an adapter, exact expected population count, original source URLs, byte lengths and checksums. SHA-256 is verified for pinned files; older official MD5 recipes are additionally hashed with SHA-256 after acquisition. HTTPS redirects are individually allowlisted and DNS/IP checked. Successful partial transfers can resume when their strong ETag agrees. Gated releases are not bypassed. Missing recipes remain implementation gaps.

`atlas datasets prune` removes failed, cancelled and interrupted runs, non-active versions whose snapshot the active version already serves, and superseded versions no saved selection references. Versions a selection references are pinned and reported as such. Freed-byte figures ignore inodes shared with a retained version, so they are what deletion actually reclaims. Nothing is removed without `--execute`.

`work/preparation/<plan-id>` contains the approved plan, status, cancellation marker and worker log. `work/prepared/<dataset-id>/<version>` contains retained source references, a 100-record preview (or all smaller populations), an immutable full-population Parquet index, and a receipt. Only after exact count and output validation succeeds is `active.json` atomically switched. Earlier versions and the original tracked registry remain available; frozen selections resolve their original snapshot.

Download, source-read and output budgets are separate. Plans reserve source/cache space plus the output budget and recheck free space before execution. Acquisition workers serialize their disk-intensive preparation stage. Analysis workers retain their existing resource queues and GPU lock. Workers use kernel CPU limits, a wall-time/RSS watchdog, and—when verified user cgroup delegation is available—a kernel memory cap with swap disabled. The plan/estimate identifies the actual memory enforcement; the portable watchdog can overshoot between its 100 ms samples.

Completed downloads do not grant publication rights. A complete index means **the population named in the plan**, not every historical release or an unidentified paper subset. Large repositories that exceed the configured storage budget are rejected; selective remote Parquet acquisition for multi-terabyte releases is not implemented by this workflow.

Safe-view is available under **Settings → Appearance**. It requests pixelated image derivatives from the local media endpoint and hides unsupported/external image URLs. Saved records, originals, analysis inputs and model contexts retain their original representation. It is a display option, not a content classifier.

Complete-data similarity resolves the complete query's eligible IDs and performs exact, prefiltered LanceDB searches in bounded ID partitions. It merges their top-k results; it never retrieves globally and then drops ineligible neighbors. Population resolution retains a 30-second interactive budget.

Recipes may restrict Hugging Face files with `source_patterns` and a named scope. For example, MMMU-dev selects `*/dev-*.parquet` rather than silently including test and validation. An optional declared count must match the acquired shards. Columnar field discovery unions every shard's schema, including fields missing from the first 100 records. Large integer fields use exact JSON storage rather than a lossy floating-point query column.

The `annotated_archive` adapter reads bounded JSON, JSONL or CSV annotations inside ZIP/TAR files without extracting or executing repository code. Task documents can retain complete nested train/test examples. Every referenced image must exist in the original archive. The `media_encoding: base64` mapping supports explicitly identified encoded image columns, with decoding limits and original-byte checksums.

Run `python scripts/audit_preparation.py` to check preparation readiness for the entire catalogue without starting downloads. `reports/preparation-readiness.json` distinguishes an executable plan from tested local coverage. Run `python scripts/report_prepared_workspace.py` to refresh local coverage and immutable preparation receipts.
