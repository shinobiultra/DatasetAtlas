# Resumed native population expansion, 2026-09-24

The user resumed the work after the 2026-09-23 stop. New prepared populations are
reported only after their complete native annotations and live original media pass
verification. Media rights and paper-specific selection identities remain separate.

| Dataset | Full native population | Verified scope |
|---|---:|---|
| MLLMU-Bench | 1,000 person/image records | Author Full_Set (500) and Test_Set (500), with all source fields and all image slots checked against three pinned Parquet shards; 191 original image reads across 100 preview plus three later records. Training/retain derivatives are not double counted. The citing paper's 438-item subset is unidentified. [Receipt](mllmu-bench-live-verification.json). |
| SBBench synthetic, noncrop | 539 images | Pinned author age (333) and gender (206) source releases. Complete native integer labels and image paths checked; all 103 original preview/later images decoded. No semantic label mapping or exact paper chart selection inferred. [Receipt](sbbench-syn-live-verification.json). |
| SBBench synthetic, crop | 917 images | Pinned author age (511) and gender (406) source releases. Complete native integer labels and image paths checked; all 103 original preview/later images decoded. No semantic label mapping or exact paper chart selection inferred. [Receipt](sbbench-syn-crop-live-verification.json). |

Cauldron is a separate running preparation and is excluded until full-index and
preview verification. Large remote Parquet shards remain remote; source SHA-256
values are author metadata and fetched ranges are bound by strong ETags, not
misreported as locally verified whole-shard hashes. Preview image requests use
original released bytes and pixel dimensions.
