# Storage and original-quality previews

Atlas can keep complete metadata indices while retaining only preview originals
and a bounded cache of other media. This is the default strategy for large
collections; an entire remote release need not fit on disk.

```bash
atlas storage configure --target-bytes 100000000000 --ceiling-bytes 150000000000 \
  --optimized-cache-bytes 5000000000
atlas storage status
```

The configuration is local to this workspace. Add `--external-root /path/to/model`
for each external model/source directory that should count toward its budget.
Accounting counts hard links once and reports allocated regular-file blocks.
Unconfigured external directories and directory metadata are excluded; shared
reflink extents may be counted twice. A changing file can make a live scan
incomplete, which blocks preparation admission until a complete scan succeeds.

New preparations reserve their conservative source/cache/output upper bounds
against the shared ceiling. Dispatch rechecks the footprint under a common lock
and includes all running preparation reservations. This is application admission
control, not a filesystem quota: unrelated processes and explicitly invoked
maintenance commands can still write files. `status` reports the actual footprint.

## Browsing representations

New full preparations select up to 100 examples by reproducible SHA-256 priorities
over primary-asset groups. They retain every image variant in a selected example.
Existing source-order previews keep their declared sampling methods until migrated.

Preview images remain byte-for-byte original, including when a caller requests
the optimized route explicitly. Other images can be encoded on inspection as
full-dimension AVIF, quality 60, speed 6, 4:4:4 chroma. A shared 5 GB LRU cache
prevents growth proportional to the source dataset's size. Two encoders may run
at once. Cache identities include the immutable snapshot and encoding version.

The browser labels the representation and links to **Open original**. It does not
predict that every file will shrink. Animated/scientific modes, unsupported native
metadata, orientation changes and larger AVIF outputs retain the original bytes.
The response records the actual representation and original SHA-256. Source
records, saved selections, detector inputs and model inputs remain original.
AVIF requires a compatible Pillow build; without the codec the browser continues
to use originals. The static public site is unaffected by this local policy.

Optional bounded bulk conversion is resumable:

```bash
atlas storage compact --dataset DATASET_ID \
  --max-input-bytes 8000000000 --max-output-bytes 3000000000
```

This command retains its verified outputs on interruption. It does not remove
source files. Its persistent copies are counted separately from the on-demand
cache. Preview protection matches stable asset IDs as well as native filenames,
including older packs that materialized files below `media/`.

## Native CIFAR-C array retirement

`atlas storage retire-cifar-c --dataset cifar-10-c` (or `cifar-100-c`) verifies a
retirement plan before `--execute` removes acquired TAR copies. The plan may
create retrieval indices and protect original previews. Every retained canonical
row must match native corruption, integer severity, original test index, label
and RGB array membership. All retained preview pixels must remain protected;
unverified older dependencies, missing snapshots, foreign hard links and unsafe
indices refuse removal.

Original access reads exact 3,072-byte C-order RGB rows using whole-source
SHA-256 block pins and a hash-pinned receipt, then renders the same lossless
32×32 PNG. It performs no resizing, normalization or pixel conversion. The
original TAR stays remote after retirement; its availability remains an upstream
dependency. Corpus originals, canonical records, frozen selections and required
model weights are preserved.

## Original archive access and retirement

For already acquired native ZIP, plain TAR or gzip TAR archives, `index-original` verifies
the entire source SHA-256 and records every member's SHA-256, size and position.
Gzip TAR uses seek checkpoints through the optional `remote-storage` extra;
Plain TAR uses native member offsets; ZIP uses native compressed-member offsets. A filename ending in `.tar.gz` is not accepted as proof of gzip encoding; Atlas checks the actual format. Remote retrieval uses pinned strong
ETags, strict HTTPS byte ranges, bounded decompression and member hash checks.
An ETag alone is not treated as a full-file cryptographic hash.

```bash
atlas storage index-original --source work/sources/DATASET/native.zip \
  --sha256 SOURCE_SHA256 --url https://SOURCE_HOST/native.zip \
  --allow-host SOURCE_HOST --format zip --name DATASET-native \
  --max-input-bytes 30000000000 --max-index-bytes 500000000
atlas storage retire-original --dataset DATASET_ID \
  --source work/sources/DATASET/native.zip --index DATASET-native
```

The second command is a read-only retirement plan. `--execute` installs verified
preview originals and routes for every retained snapshot before unlinking any
acquired copy. It performs fresh remote original probes, checks source/index
integrity and refuses unaccounted hard links or another dataset's dependency.
Use `--also-dataset ID` to include a shared source's other datasets in the same
verified operation. For example, VQA v2 and POPE share COCO val2014 images.

`--asset-prefix` and `--member-prefix` express native archive naming differences.
`--extracted-root` can retire extracted image copies only after checking every
file against the native member hashes. Corpus originals and arbitrary external
files cannot be retired. Receipts stay under `work/original-access/retirements`.
No snapshot or frozen selection is deleted, and absent upstream media remains
explicitly absent. A remote source that disappears later produces an availability
error; neither an AVIF copy nor a successful earlier probe fabricates an original.

A redundant stored ZIP produced during earlier preparation can also be retired:

```bash
atlas storage retire-repacked --source work/prepared/DATASET/VERSION/sources/original-members.zip \
  --sha256 REPACKED_ZIP_SHA256 --index DATASET-native --max-decoded-bytes 6000000000
```

This verifies every repacked member against the native archive's member hashes,
requires existing original routes and pinned previews for every dependent snapshot,
and performs fresh native retrieval probes. `--execute` removes only the checked
Atlas-owned redundant archive. It cannot establish routes by itself; first complete
native indexing and preview retention. Food101's additional 5.14 GB retirement is
recorded in `reports/food101-repacked-retention.json`.

## Cleanup

```bash
atlas storage clean                             # inspect the proposed cleanup
atlas storage clean --execute                  # evict unpinned caches and share duplicate immutable files
atlas storage clean --execute --include-model-test-env
```

Cleanup preserves prepared versions, original previews, saved selections, model
weights and native source paths. It evicts unpinned download/range entries and
unprotected AVIF copies, removes disposable installation-test environments, and
replaces byte-identical native source, preview and canonical index copies with
hard links after complete SHA-256 checks. Mutable JSON and SQLite files are never
shared this way. A pinned cache object, shared protected original, active
preparation or held storage lock prevents unsafe removal.

The last option also removes the regeneratable isolated vLLM test environment;
it preserves its model weights and receipts. Recreate that environment with
`scripts/setup-local-vlm.sh` before using `scripts/start-local-vlm.sh`. Atlas's
main development environment is retained.

HTTP preparations use separate bounded staging caches in each version, allowing
the two admitted writers to transfer concurrently without evicting each other's
source files. Failed/cancelled preparations retain resumable partials and their
attempt history. Completion removes staging-cache links after native source
links exist. Remote Parquet preview caches follow the same staged lifecycle.

The 2026-10-05 cleanup additionally retired BAPPS's native plain TAR and redundant
ZIP copies after full member-hash parity, protected previews and fresh original
retrieval probes. STL-10 retains every native pixel/label/metadata member and its
pinned receipt after removal of the duplicate compressed archive. Fresh-download
verification copies are disposable only after their counts, hashes, plans,
status, preview media checks and logs have been retained. See the latest
`reports/storage-footprint-20261005.json` and release evidence for measured bytes;
logical file sizes alone overstate savings when hard links are present.
