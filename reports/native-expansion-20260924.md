# Resumed native population expansion, 2026-09-24

The user resumed the work after the 2026-09-23 stop. New prepared populations are
reported only after their complete native annotations and live original media pass
verification. Media rights and paper-specific selection identities remain separate.

| Dataset | Full native population | Verified scope |
|---|---:|---|
| MLLMU-Bench | 1,000 person/image records | Author Full_Set (500) and Test_Set (500), with all source fields and all image slots checked against three pinned Parquet shards; 191 original image reads across 100 preview plus three later records. Training/retain derivatives are not double counted. The citing paper's 438-item subset is unidentified. [Receipt](mllmu-bench-live-verification.json). |
| SBBench synthetic, noncrop | 539 images | Pinned author age (333) and gender (206) source releases. Complete native integer labels and image paths checked; all 103 original preview/later images decoded. No semantic label mapping or exact paper chart selection inferred. [Receipt](sbbench-syn-live-verification.json). |
| SBBench synthetic, crop | 917 images | Pinned author age (511) and gender (406) source releases. Complete native integer labels and image paths checked; all 103 original preview/later images decoded. No semantic label mapping or exact paper chart selection inferred. [Receipt](sbbench-syn-crop-live-verification.json). |
| Watanabe Test_data stimuli | 7 assets | Exact Figshare 5483680 v1: five still images and two propeller MP4 files. All seven native file IDs, checksums, index rows and workbench original-media routes passed; images decoded and videos probed. The paper describes six test conditions, but a condition-to-file mapping is not inferred. The v2-only InkBlots ZIP is excluded. [Receipt](figshare-stimuli-live-verification.json). |
| eLife 55378 figure source data | 7 workbooks | Every native nonempty cell (1,229), sparse coordinate and all 135 shared formulas with cached values agree with an independent workbook reader. The seven original XLSX routes match pinned source checksums. Each workbook is an asset record; no artificial row-level observation table is inferred. [Receipt](elife-workbooks-live-verification.json). |

Cauldron is a separate running preparation and is excluded until full-index and
preview verification. Large remote Parquet shards remain remote; source SHA-256
values are author metadata and fetched ranges are bound by strong ETags, not
misreported as locally verified whole-shard hashes. Preview image requests use
original released bytes and pixel dimensions.

The two native file collections also passed a [live browser inspection](browser-native-20260924.json):
seven loaded assets and an inspectable sample in each, with no page or HTTP errors.
