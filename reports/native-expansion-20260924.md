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
| SafeBench | 2,300 native category/ordinal groups | Author release with exact text and image-prompt rows, one original PNG and two WAV assets per group. All 6,971 source members and 2,300 rows matched the index; 300 preview and three later original HTTP media reads passed. Structural grouping does not imply semantic equality. Local archive retired after original previews were pinned; later media use pinned multipart retrieval. [Verification](safebench-live-verification.json), [retirement](safebench-retirement-20260924.json). |
| ROCO | 87,927 original annotation records | All 36 author caption/link/keyword/CUI/semantic-type/licence tables are byte-identical to the prepared source, and every indexed row matches the native split, caption and image filename. All 100 sampled images decoded and matched the MD5 of their **current PMC article version**, then were pinned as exact local originals; a later image passed on-demand retrieval. Historical 2018 FTP-image byte identity and availability of the other images are not asserted. Seven preview licences say `NO-CC CODE`, so no ROCO media is approved for public packs. [Verification](roco-live-verification.json), [browser](roco-browser-20260924.json). |
| Cauldron | 1,880,992 native grouped examples | All 50 configurations across 938 pinned author Parquet shards are indexed; the 2.19 GB local snapshot passes SHA-256 and unique-ID checks. A deterministic 250-candidate pool yielded 100 records with 109 original images checked and pinned; five path-only source slots were excluded. Every preview image decoded through the live API, three later images from distinct shards passed original retrieval, and the focused browser view passed. Non-preview media remain on-demand and unverified; source-shard SHA-256s are author metadata, with fetched ranges bound by strong ETags. The citing paper's 72,000-pair selection and constituent media publication rights remain unresolved. [Verification](cauldron-live-verification-20260924.json). |
| QAVA VQA v2 m+n, released 32×50 setting | 1,600 native question/answer rows across 32 images | Every question, answer and image-group join matches the pinned author archive. The 100-record preview covers all 32 images, and every original image is locally pinned and checksum-verified across the complete indexed setting. One image was also byte-matched to the COCO 2014 source archive; the focused live browser view passed. Other m+n settings in the paper remain unidentified, and VQA/COCO publication rights are separate. [Verification](qava-live-verification-20260924.json). |
| eLife 55378 figure source data | 7 workbooks | Every native nonempty cell (1,229), sparse coordinate and all 135 shared formulas with cached values agree with an independent workbook reader. The seven original XLSX routes match pinned source checksums. Each workbook is an asset record; no artificial row-level observation table is inferred. [Receipt](elife-workbooks-live-verification.json). |

Large remote Parquet shards remain remote; source SHA-256 values are author
metadata and fetched ranges are bound by strong ETags, not misreported as
locally verified whole-shard hashes. Preview image requests use original
released bytes and pixel dimensions.

Six previously indexed datasets were migrated to prepared native versions with
hash-ranked 100-record previews. CIFAR-10 and CIFAR-100 passed 120,000
source-binary label checks and 200 pixel-exact preview PNG reads; PNG is a
lossless rendering of planar source pixels, not an original source file.
ImageNet-A, ImageNet-R and ImageNet-V2 MatchedFrequency passed complete
source-archive member/path parity and 300 byte-exact original preview reads.
IconQA passed 107,439 native question JSON and media-reference joins and 216
byte-exact preview PNG reads. These preparations do not add six to the full
index count because their prior local indices were already counted. See the
[CIFAR](cifar-native-live-verification-20260924.json),
[ImageNet-A](imagenet-a-live-verification-20260924.json),
[ImageNet-R](imagenet-r-live-verification-20260924.json),
[ImageNet-V2](imagenet-v2-live-verification-20260924.json), and
[IconQA](iconqa-live-verification-20260924.json) receipts.

The two native file collections also passed a [live browser inspection](browser-native-20260924.json):
seven loaded assets and an inspectable sample in each, with no page or HTTP errors.
