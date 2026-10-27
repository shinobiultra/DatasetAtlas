# Preparing source data

Open a dataset in the local workbench and choose **Get preview** or **Prepare full
data**. Review the exact pinned population, transfer estimate, output reservation
and uncertainty. Set explicit budgets, then start the saved plan. Status, retry and
cancellation survive server restarts. No publisher agreement is accepted for you.

```bash
atlas datasets acquire --dataset illuchar --max-download-bytes 4000000000 --max-output-bytes 2000000000
# Add --execute to start the printed plan.
atlas datasets preparation --id PLAN_ID
atlas datasets preparation --id PLAN_ID --cancel
atlas datasets preparation --id PLAN_ID --retry
```

Plans use native Parquet/Arrow shards, checksum-pinned original archives or
configured local sources. No repository Python is executed. Different native
configurations, splits, annotations and linked media conditions retain their own
identities. A complete index covers the declared partition, not an unidentified
historical paper subset. An unavailable referenced image remains explicit rather
than removing its example.

## Large sources and another sample

Selective Parquet preparation indexes native non-image fields while retrieving
images through bounded, ETag-bound ranges. Choose **Keep Parquet images remote;
index annotations only**, or pass `--source-mode selective`. The transfer budget
covers actual range reads; output and cache reservations are separate. Oversized
row groups or changed source fingerprints fail explicitly.

FineVision and the SmolLM2 training mixture use a different declared representation:
a seeded sample over the pinned whole-source population, with all shard footers
included in the sampling frame. Their global source totals do not describe a local
query index. **Get another sample** reviews a new seed and fresh budgets before
preparing another bounded native sample. Existing versions and selections retain
their original snapshot.

```bash
atlas datasets acquire --dataset finevision --sample-seed 1 --max-download-bytes 4000000000 --max-output-bytes 1000000000
```

This command is a plan until `--execute` is added. A different seed can select new
records but does not promise disjoint samples. Sampling and media-availability
conditions remain in the manifest.

## Versions, resources and cleanup

`work/preparation/` holds plans, status and worker logs. Immutable versions under
`work/prepared/` hold source references, previews, receipts, and a complete index
when that representation is supported. Activation occurs only after validation.
Frozen selections and result/model context resolve their original snapshot, even
if a newer source version becomes active.

Download, source-read and output budgets are distinct. Workers recheck free space,
coordinate disk reservations, and expose their actual CPU, wall-time and memory
enforcement. A portable RSS watchdog can overshoot between samples; verified
cgroup delegation permits a kernel memory cap. Analysis uses its own resource queue.

Review `atlas datasets prune` before adding `--execute`. Retained dependencies,
active versions and frozen selections remain protected; failed resumable attempts
keep their provenance until an explicit cleanup. See [storage](storage.md).

Safe-view is a labelled display derivative. Original records, media and model inputs
remain unchanged. Exact similarity searches stay within the eligible filtered
population and use bounded working memory. See [analysis](analysis-at-scale.md).

For a metadata-only readiness audit without downloading data:

```bash
uv run --no-sync python scripts/audit_preparation.py --output work/preparation-readiness.json
```

An executable plan is distinct from a successful native preparation. Current
release counts and their verification are in [release evidence](../reports/release_evidence.md).
