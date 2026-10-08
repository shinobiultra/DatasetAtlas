# Adding a dataset

1. Confirm the paper mention in `work/corpus/curated_dataset_evidence.jsonl` or `work/corpus/dataset_mentions.jsonl`. Keep the paper ID, source hash, page, excerpt, and role. A related-work mention does not become a direct-use claim.
2. Verify the original dataset identity, release, source access, and rights from an author or project source. Pin an immutable revision and retain the source URL and checksum. Keep a base dataset distinct from overlays, paper subsets, and derived releases.
3. Add `registry/datasets/<id>.yaml` validating against `dataset_atlas.models.Dataset`. State all coverage dimensions separately. `adapter_config` is local-only; it is stripped from preview packs. Unknown publication rights mean metadata-only. Unfinished format support is an implementation gap, not an external access block.
4. Configure a reusable adapter. `structured` handles JSON, JSONL, CSV, and Parquet; Parquet cursor reads skip earlier row groups using metadata counts. `https` downloads a pinned structured file with a strict byte cap and SHA-256 verification; `directory` and `archive` handle media; `overlay` joins local base/annotation tables. Archive `path_regex` named groups become source fields. `order: round_robin_label` balances a class preview, while `order: section_priority` with an explicit section list preserves complete scenario groups for a purposeful preview. `field_types` casts numeric folder IDs, `label_index_maps` preserves multiple source class-index conventions, and `constant_fields` records an exact source variant. `idx` reads original MNIST-style image and label gzip files; `cifar_binary`, `cifar100_binary`, and `artbench_binary` read documented binary archives without unpickling data; `stl10`, `svhn_cropped_mat`, `coco`, `vqa_v2`, `gqa_balanced`, `docci`, and `clevr_full` read their pinned native release structures and resolve media selectively. The `huggingface` rows API adapter pages without cloning, but its live endpoint does **not** honor a revision parameter; it requires `allow_live_rows` and is unsuitable for release-grade pinned packs. For those, use a pinned repository file through a structured adapter. Map upstream IDs and original fields. Use a pinned `snapshot_id` if row positions are the only available source identity.
5. Probe and approve a bounded plan before preparation: `adapter = get_adapter(dataset); plan = adapter.plan(limit=100, max_bytes=20_000_000); source = adapter.prepare(plan)`. Then call `adapter.iter_records(source, cursor, limit)` until the requested population is reached. Check `RecordBatch.next_cursor` and warnings. `resolve_asset` uses rooted no-follow local reads or pinned HTTPS with exact source/CDN host allowlists, public-DNS checks, a bounded revision cache, and atomic rooted writes. For large releases, set a source-specific cap covering both download and preparation; explicit plans permit up to 100 GB, while `fetch_bounded` resumes partial HTTPS transfers and verifies the expected checksum. Local-source plans report zero expected download bytes. Only report complete-data support after an actual final-record read.
6. Validate duplicate IDs and overlay joins with `adapter.validate(source)`. Unmatched and multiply matched overlay IDs must be reported. Test 100 real inspectable examples, then read beyond row 100 or perform another bounded integration read. Avoid a full large-source download merely to exercise pagination.
7. Write a local canonical pack with `build_preview(dataset, Path("work/packs/<id>"), limit=100, max_bytes=...)`. If repeated questions share assets, use `distinct_assets=True`; `include_media=True` copies original bytes or lossless renderings and checksums into the **local** pack. This does not approve public redistribution. The pack states its actual population and sampling method. Synthetic records belong only in tests. For on-demand browsing, `resolve_dataset_asset(dataset, asset_ref, max_bytes=10_000_000)` returns a bounded `MediaHandle` for an asset reference obtained from a source record; the caller should authorize the record ID first.
8. Build the complete Parquet index with `atlas datasets index --dataset <id> --expected-count <verified-count> --max-bytes <budget>` once the last record and source count are checked. The immutable index enables complete-scope filtering and exact counts. Media may still be partial: SVO-Probes, for example, has a complete original CSV but only 119 of 196 selected photo links fetched and verified locally. Record text, referenced URL reachability, locally available media, and public redistribution rights separately.
9. Update `reports/dataset_coverage.csv` and `reports/source_access_report.md` with measured counts, byte budgets, hashes, rights decisions, and unresolved limits. Declare source field types and known categorical `values` in `adapter_config.fields`; numeric labels need numeric values for correct query controls. Public packs require a separate publication review; a local pack alone does not authorize redistribution.

Use `PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_adapters.py tests/unit/test_adapters_gqa.py tests/unit/test_adapters_coverage.py tests/unit/test_remote_zip.py tests/unit/test_storage.py` for adapter and source-access tests. Network integration reads should be separately runnable and pinned to a checked source revision. CLEVR and VQA v2 demonstrate image/question mappings; HarmBench and AdvBench demonstrate text/CSV mappings; Alpaca demonstrates JSON-to-JSONL streaming; MNIST, CIFAR, STL-10, and EuroSAT demonstrate complete image releases with on-demand media. PAIRS demonstrates a rights-reviewed four-image scenario preview; its generated demographic words are prompt specifications, not inferred identities.

GQA demonstrates a measured distinction between complete annotation rows and partial local media. Its official 21.8 GB image ZIP supports checked HTTP byte ranges, so `PinnedHTTPRangeReader` can copy a selected 100-image set while the bounded full-archive download continues. The reader enforces exact host, public DNS, strong ETag, content length/range, per-member size, total transfer, request count, ZIP CRC, and JPEG decode checks. Its `selected_preview` media scope keeps all 132,062 original validation-balanced question rows browseable but marks every image absent from the selected local archive as unavailable; only `full` media scope may claim all images joined. The local preview is not a public rights decision.

EMNIST Balanced demonstrates optional IDX `mapping_file`/`mapping_sha256`/`class_count` for an original character mapping and `pixel_transform: transpose` for an upright display PNG. Preserve the raw IDX gzip files and record this display transform; the numeric source labels remain unchanged. Keep this named NIST split distinct from EMNIST Letters and the other four release splits.

### Images embedded in Parquet

`embedded_parquet` reads pinned local Parquet files with image `bytes/path` structs, including lists and multiple top-level image columns. Configure `path`, required `sha256`, `media_columns: [image]`, and ordinary `mapping`/`fields`. It preserves original image bytes; source JSON contains path/hash/size metadata instead of binary data. Missing bytes remain visible as missing assets, and repeated image bytes share an asset ID. Row-group access resolves one original image without extracting the whole population. Limits are 10 MB per image, 20 MB of image bytes per record, and 32 images per record. RealWorldQA demonstrates the complete 765-row source and a 100-original-image preview; its two source shards are consolidated with explicit shard/row provenance by `scripts/prepare_visual_sources.py`.

The workbench media endpoint supports HEAD and single HTTP byte ranges. It bounds each original read at 10 MB for images, 100 MB for audio, and 250 MB for video. ZIP-backed videos are currently decompressed as bounded complete members before serving a range, so range support does not imply streaming ZIP decompression. Browsing retains at most 10,000 media-handle metadata entries; requery an old complete-data page after eviction to obtain live handles.

### Full annotations with images on request

Use `structured_collection` for releases with separate split annotations. A recipe can
map JSON arrays, JSONL records, CSV rows, or a checksummed JSON member in an ETag-pinned
remote ZIP. Original fields stay in `source`; `_atlas_origin` records split, annotation
file and identity. Use `identity_fields` for IDs scoped to a category, and
`identity_prefix` when multiple annotation groups share a split. Never silently discard
duplicate IDs. Media templates may name multiple images per record. HTTPS ZIP references
are checked against the complete directory; individual images are checked against a
SHA-256 or Git blob inventory. ChartQA, TextVQA, VizWiz, HatefulIllusion, OmniSpatial and
PMC-VQA provide tested recipes. Their exact populations and rights remain distinct.

For native Parquet repositories, choose **Keep Parquet images remote; index annotations
only** in the preparation dialog, or pass `--source-mode selective` to `atlas datasets
acquire`. The download limit caps actual range transfers. The prepared-data limit caps
persisted output; the source remains remote behind a bounded cache. Reading an image may
require its Parquet row group. Oversized groups require a local shard or a separately
configured larger media budget; they are never silently truncated.

`classic_vision` supports native CUB-200-2011, Flowers-102 and FGVC-Aircraft annotations;
Flowers requires the `datasets` extra for MATLAB label files. `cifar_c_npy` addresses
CIFAR-C arrays directly inside the original uncompressed TAR without executing pickle.
The optional `archive_preparation: zip-store` copies regular TAR member bytes into a
random-access derived ZIP, within the approved prepared-data budget. Originals remain
read-only, and the transformation checksum is recorded separately.

`embedded_tsv` reads native image-bearing benchmark TSVs. Each `tables` entry names
its `path_key`, split and optional language; source files have pinned checksums.
The default `index` identifies a row within its table. Numeric `image` values are
references to another row in that same table, including forward references; missing
or cyclic references fail before indexing. Base64 payloads stay in the original TSV,
with byte offsets used for bounded decoding on inspection. Circular permutations
remain separate examples and share image assets. MMBench's recipe records both the
mirror SHA-256 and the evaluation toolkit's checksum.

`structured_collection` also supports local ZIP archives via `local_archives` entries
with a `path_key`. Set `repack_paths` to the configuration keys holding native TARs
to copy their members into derived stored ZIPs during preparation. All repacked
archives share the same prepared-data budget, and every checksum is retained in the
receipt. `array_columns` names fixed-width JSON-array columns; `choices_columns`
selects their ordered options. `text_parts_field` joins original text segments without
altering the original arrays. These transformations describe source data; they never
create replacement examples.

The native `ravel` adapter retains all five author-released domain inventories,
attribute templates and independent Wikipedia control prompts. Entity splits and
prompt splits remain separate; absent attribute values remain absent. These source
inventories are not a model-specific evaluation subset. `classic_vision` additionally
supports Food-101's native class names and train/test manifests, retaining the
intentionally noisy training labels.

`emnist_archive` reads NIST's original `gzip.zip`, with explicit configurations and
train/test counts. Its metadata pass reads only IDX headers and labels. Image access
lazily decodes one gzip partition under a separate 600 MB default decoded-byte limit;
only one partition is retained in memory. Native Letters labels start at 1 and its
mapping retains both character codes. All-six-configuration counts describe overlapping
configuration memberships. Display PNGs record their transpose; stored pixels are
unchanged.

For large gzip TAR sources, `archive_preparation: indexed-gzip` builds a native
member inventory and gzip seek checkpoints instead of another full-sized archive.
The optional `remote-storage` extra supplies `indexed-gzip`. `archive`,
`classic_vision`, and `sun397` can read these inventories and retrieve verified
original members locally or through ETag-bound HTTPS ranges. The checkpoint
library lives under `work/original-access/<source SHA-256>`; it is retained storage,
not an evictable cache. Both member SHA-256 values and the derivative checksums
are recorded. `max_uncompressed_bytes` bounds the indexing pass.

To prepare space-efficient browsing media while keeping full-quality previews:

```sh
atlas storage status
atlas storage compact --dataset DATASET_ID --max-input-bytes 4000000000 --max-output-bytes 3000000000
```

Compaction is resumable and defaults to full-dimension AVIF quality 60, speed 6,
4:4:4 chroma. It preserves every preview asset byte-for-byte. Compressed copies
remain separate from canonical model inputs; unsupported image modes stay original.
It does not itself delete source archives: original eviction requires a complete
compaction receipt, a verified retrieval route, and preserved snapshot dependencies.

## Making a dataset reproducible for colleagues

A catalogue dataset that only works because its files are already in `work/sources/` cannot be fetched by a colleague. `reports/preview-reproducibility.md` (generated by `scripts/report_reproducibility.py`) lists every dataset that lacks an acquisition path. A recipe in `registry/recipes/<dataset-id>.yaml` closes that gap, using one of four patterns. Always carry over the catalogue entry's `release` and `snapshot_id`: a colleague's preview then has the maintainer's identity and saved selections are interchangeable. Without a declared `snapshot_id`, the ID is derived from the acquired checksums, revision, recipe and scope (never from the workspace path or budgets).

**1. Pinned files.** List each original with its URL, byte length and SHA-256, and the adapter configuration key it satisfies:

```yaml
files:
- {source_name: val2017.zip, url: https://…/val2017.zip, bytes: 815585330, sha256: 4f7e2ccb…, format: zip, config_key: images_archive}
allowed_hosts: [s3.amazonaws.com]
```

Check that the URL serves exactly that length, and (for the first fetch) that the SHA-256 matches the file the entry already pins. `config_dir` (and optionally `dest_name`) places files by name in a directory the adapter reads. For a publisher that ships one large zip of many files, a `format: zip` entry with `config_dir` and `extract: [{member, sha256}]` verifies the zip as a whole and places only those members, each checked against its own SHA-256 (see `registry/recipes/emnist-balanced.yaml`). Redirects must stay on `allowed_hosts`; `*.example.com` admits subdomains of a CDN that issues a random host per download.

**2. Ranged reads of a huge archive.** When the source is a multi-gigabyte ZIP (VQA v2's images, GQA, CLEVR), declare it instead of downloading it:

```yaml
adapter_config:
  remote_images: {url: https://…/val2014.zip, bytes: 6645013297, etag: '"3925cc4d…-793"', allowed_hosts: [s3.amazonaws.com]}
  remote_cache_root: work/media-cache/vqa-v2-remote
  media_scope: on_demand_unverified
```

The adapter reads the ZIP's directory and only the members a user inspects, through HTTPS ranges bound to the strong ETag (`adapters/remote_media.py`). A strong ETag is a consistency fingerprint, not a content hash, so coverage reports the media as unverified and every record says so. Plans report the bounded directory reads instead of zero bytes.

`atlas previews fetch` plans in `auto` mode, which downloads a source completely while it is small (under 250 MB) because that also yields a complete index. Some small shards cannot be read that way: ZeroBench's 95 MB Parquet holds embedded images above the full-download limit of 10 MB each, so a complete download fails at the preview step even though selective range reads succeed. A recipe can say so with `auto_source_mode: selective`, and `auto` then takes the selective route (which needs a native Parquet source) whenever its plan is ready. Only `selective` is accepted; any other value is refused.

**3. Conversions.** If the catalogue's records are a deterministic conversion of originals, write the rule as a converter (`dataset_atlas/converters/`) and pin the originals plus the converted rows' digest:

```yaml
convert: {name: bbq, params: {categories: [Age, …]}, count: 58492, rows_sha256: 8e201cc5…}
```

`digest_existing(path, fmt)` gives the digest of the maintainer's table. The fetch fails unless the converted rows match it exactly, so a colleague's table cannot silently differ. The digest is over row content, not file bytes, because Parquet encoding varies between library versions. Where the original already equals the maintained table (Alpaca's JSON array), no converter is needed; point the structured adapter at the original with `format: json`.

**4. Verify from an empty workspace.** `atlas init` a scratch directory (or copy `registry/` and `schemas/`) and run `atlas previews fetch --execute --dataset <id>`. Compare `snapshot_id` with the maintained entry, resolve a few media, then regenerate the report with `--verified-from <that workspace>`.

## Images a browser cannot decode (TIFF)

Keep the original bytes as the asset. The structured adapter flags any image asset whose file name ends in `.tif`/`.tiff` with `browser_render_required` and `source_format: TIFF`; the grid and inspector then request `?representation=display`, a faithful, bounded PNG rendering (16-bit and floating-point samples are scaled linearly to 8 bits, alpha is kept, nothing is blurred or cropped, the longer edge is capped at 4096 px). `?representation=safe-view` remains a different, deliberately blurred derivative that the researcher opts into. Records, selections and model inputs always carry the original asset. RSVQA-LR (`registry/recipes/rs-vqa.yaml`, `converters/remote_sensing.py`) is the worked example.

## Images that a source repository commits without a table

When an author repository commits media but no annotation file, state the structure its paths carry as a converter over a **pinned inventory**. Write `registry/media/<id>.json` once from the repository tree at the pinned commit (`{"files": {path: {"bytes": n, "git_blob_sha1": sha}}}`), pin its SHA-256 in the recipe, and let the converter (`converters/adversarial_images.py` for SAEgis) emit one row per file without opening any image. Images are fetched on demand from `raw.githubusercontent.com/<owner>/<repo>/<commit>/<path>` and each read is checked against its Git blob SHA-1; `atlas storage pin-preview --dataset <id>` then retains the 100 preview originals locally so the preview survives an upstream outage. Verify any relationship the paths imply (a clean image and its attacked variant sharing a file name) on the real files and keep the receipt (`scripts/verify_saegis_pairing.py` checks all 1,800 SAEgis pairs by pixel similarity and every fetched file's blob hash).

## Source research that does not end in a preview

Record what was checked on the entry: the URL and revision, what the source actually holds (files, counts, licence), and why nothing was prepared. A name shared with an unrelated release (VIA-Bench versus the video benchmark VIABench) is evidence to keep, so nobody attaches the wrong data later. A source that is only a recipe over other datasets (VLAGenderBias) links to its members with `derived_from`. Say whether the blocker is external (unreachable host, gate, unreleased) or an implementation gap; the two are never interchangeable.
