# Adding your own datasets

Add a dataset you care about and browse it exactly like a catalogue dataset: a grid and table of real examples, filters over your columns, a seeded 100-record preview, saved selections, and the optional analysis tools. Your files are read in place; Atlas never modifies, moves or uploads them. A registered dataset is private to your workspace and cannot enter the public site.

## What you can add

| Source | How it is read |
| --- | --- |
| A **folder** of images (`.jpg .jpeg .png .webp .gif .bmp`), or a `.zip`/`.tar`/`.tgz` of them | One example per image. If every image sits in a subfolder, the top-level folder name becomes a `label` field. |
| A **table**: `.csv`, `.tsv`, `.jsonl`/`.ndjson`, `.json` (a list of records) or `.parquet` | One example per row. Columns become fields. |
| A table **plus a folder of images** | Name the column holding image paths; paths are resolved against the folder you choose. |
| A **Parquet file with embedded images** (a struct with `bytes`) | Images are read from the file. |
| A **Hugging Face dataset** URL (`https://huggingface.co/datasets/owner/name`) | Pinned to the revision at the time you add it. Native Parquet repositories are sampled by range reads or downloaded within your budget. Gated repositories are reported, not bypassed. |

## From the interface

Catalogue → **Add dataset** → paste an absolute path or a Hugging Face URL → **Inspect**. You see what Atlas found before anything is registered: the kind, the exact count, labels, warnings, and for tables the detected columns. Change the image, text, question or ID column if the guess is wrong. **Add and build preview** registers the dataset and builds its index and preview; progress is shown, and the dataset opens when it finishes.

## From the command line

```bash
# Look first: nothing is registered or written.
atlas datasets inspect /data/my-images
atlas datasets inspect /data/annotations.csv

# Register and build the preview.
atlas datasets add /data/my-images --name "Field photos"
atlas datasets add /data/annotations.csv --name "Scored pictures" --media-column file --media-root /data/photos
atlas datasets add https://huggingface.co/datasets/owner/name

# Register only; build the preview later.
atlas datasets add /data/my-images --name "Field photos" --no-prepare

# The folder changed? Re-register it; earlier snapshots stay available to saved selections.
atlas datasets add /data/my-images --name "Field photos" --replace

# Unregister. Your files are never touched; --purge also deletes the prepared index and preview.
atlas datasets remove field-photos --purge
```

`--media-column`, `--text-column`, `--question-column`, `--id-column` and `--media-root` override what inspection guessed.

## How Atlas reads your table

Inspection makes one streaming pass, so the count is exact and column types come from every row, not a sample.

- **Numbers and booleans** are typed only if *every* non-blank cell parses. A column with one stray `n/a` stays text rather than being coerced.
- **Blank cells are missing, not zero.** A filter such as `score ≥ 0.7` never matches a blank.
- **Categories** (text columns with few repeated values) get a value list, so the interface offers them as filters.
- **Image columns** are columns whose values end in an image extension. Atlas checks that the first values exist under the media folder and warns if they do not; missing images show as placeholders, never as dropped records.
- **An ID column** must be unique; otherwise Atlas refuses it. With no ID column, records are identified by row position within the pinned file.
- **Source fields are preserved as written.** Atlas does not rename, merge or interpret your columns.

## Identity and changes

A dataset is pinned when you add it: tables by their SHA-256, folders by their file list and sizes. If the file changes later, indexing fails with a checksum error instead of silently mixing versions. To pick up changes, re-add with `--replace`; the new snapshot gets new IDs, and saved selections that reference the old snapshot keep working.

Folders are not content-hashed (that would read every image just to assign IDs); an image edited in place keeps its ID. Re-register if you replace files.

## Limits

- A single table or archive is limited to 2 GB. For larger data, use Parquet shards or a folder of files.
- Remote image URLs inside a table are not fetched: Atlas only reads media from folders you name. Download them first, or use a Hugging Face Parquet dataset with embedded images.
- Paths must be absolute and readable by the user running `atlas serve`. A dataset on a network mount works if the mount is available.
- Rights are recorded as *not reviewed*, so a dataset you add stays on your machine and is excluded from every publication build.

## Sharing with a colleague

Share the selection, not the data: export a saved selection (identities, annotations, run results) from the interface or with `atlas export selection`. A colleague can import it if they hold the same files and added them under the same dataset ID (`--id`): record IDs derive from the ID and the pinned fingerprint, so identical files give identical IDs and anything else is reported as a mismatch rather than silently misaligned. To give someone the dataset itself, give them the source files and the ID to use.
