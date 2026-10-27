# Shared v1 contracts

`src/dataset_atlas/models.py` is canonical. Use its Pydantic records verbatim; do not fork shapes. Frontend types are generated to `apps/web/src/generated.ts` by `scripts/generate_contracts.py` (lead owned).

Each dataset registry YAML validates as `Dataset`. Dataset `adapter_config` holds local preparation mapping; never publish this configuration. A local or public pack is `Pack`: dataset, fields, records, artifacts, population_scope, sampling, checksums. Preview paths: `work/packs/<dataset-id>/pack.json`; public packs `apps/web/public/data/<dataset-id>.json`, catalogue `data/catalogue.json` as array of Dataset. Empty metadata records have no pack. Static relative URLs must support Vite base paths. Asset.uri is a relative URL in public packs; backend translates configured-root local assets to opaque `/api/v1/media/...` URLs. Source fields use `source.<key>`; computed fields use `prediction.<key>`.

Provider API: `GET /api/v1/capabilities`, `/datasets`, `/datasets/{id}`, `/datasets/{id}/fields`, `/datasets/{id}/pack`, `/catalogue/thumbnails` (real preview tiles per prepared dataset, derived from packs and cached per pack revision; the static build publishes the same shape to `data/thumbnails.json` from approved records only); `POST /queries/{dataset_id}` Query -> QueryResult; `POST /aggregate/{dataset_id}` {query, field_ids, top} -> distributions over the population the filter matched, in both preview and complete scope. Aggregates never apply the browsing query's sample and say so in `warnings`; `aggregate_pack` (Python) and `aggregatePack` (TypeScript) are parity-tested against one generated fixture. `/selections` GET/POST Selection (accept blank id to assign); `/selections/{id}` GET; `/selections/{id}/export` GET portable JSON. `/processors` GET descriptors; `/runs` GET/POST {selection_id,processor_id,config}; `/runs/{id}` GET; `/runs/{id}/cancel` POST; `/artifacts` GET (optional `dataset_id` limits results to that dataset's prepared and complete snapshots; `view=browse` omits embedding `vector` values and lists them in `data.omitted_fields`, while `/artifacts/{id}` always returns the complete registered artifact); `/artifacts/{id}` GET. Providers `/providers` GET/POST configuration, `/providers/{id}/probe` POST; conversations `/conversations/context` POST and `/conversations` POST; analysis and provider agents supply routers or functions and communicate signatures.

Workbench is explicit `?mode=workbench`; same-origin API only. Static is default; never auto-probe localhost. State-changing API requests require `X-Atlas-Request: 1` and same-origin checks. Structured error detail from FastAPI; frontend displays actual error.

Filter AST: leaf {field_id,op,value} or {and:[...]}/{or:[...]}/{not:...}; bounded depth 8 and 64 leaves. eq/ne/in/contains/gt/gte/lt/lte/is_null; missing values match only is_null true (including ne must be false on missing). Literal contains case-insensitive. Sort null last both directions, id ascending tie-break. Search case-insensitive literal over text, question, source JSON. Sampling source/random/stratified with numeric seed and size, random uses FNV-1a hash of `seed:id` ascending so parity is portable. Cursor opaque bounded offset tied to query fingerprint. Selections save actual IDs, not only a query.

Do not edit shared models without coordinating with lead. Use optional imports for heavy dependencies and honest unavailable statuses. Synthetic data only in tests. Agents own their assigned files and must preserve others' changes.

On-demand preparation: `POST /datasets/{id}/preparation/plan` takes explicit `max_download_bytes` and `max_output_bytes`; `POST /preparation/{plan_id}/start` executes that saved plan. `GET /preparation?dataset_id=...`, `GET /preparation/{plan_id}`, and `POST /preparation/{plan_id}/cancel` expose durable status and cancellation. These workbench-only operations are not exposed as model tools. Prepared versions under `work/prepared` override active local registry coverage while preserving earlier snapshots. `GET /media/{token}?representation=safe-view` returns a deliberately blurred display derivative; `?representation=display` returns a faithful, bounded PNG rendering of an image a browser cannot decode (TIFF; header `X-Atlas-Media-Representation: display`; 16-bit samples scaled linearly to 8 bits, nothing blurred or cropped). Assets the adapter flags `browser_render_required` use it, and the original bytes stay the asset in records, selections and model inputs.

Selective Parquet preparation is additive: preparation plans accept optional `source_mode:
"selective"` (default `"download"`). The plan still covers every native Parquet shard in
its pinned source/configuration. `source_total_bytes` describes the remote source;
`expected_download_bytes` is an upper bound when `download_is_upper_bound` is true.
Only the bounded range cache and prepared output require local disk reservation. The
worker indexes all non-image columns and path leaves, retains image slot identities,
and fetches embedded image bytes on inspection. Strong ETags bind range consistency;
upstream full-file SHA-256 values are provenance, not falsely reported as locally checked.
Unsupported binary layouts, changed ETags, oversized row groups, exhausted budgets and
missing embedded bytes fail explicitly. Complete-index queries continue using the same
Parquet snapshot API. The CLI equivalent is `atlas datasets acquire --source-mode selective`.
For remote Parquet previews, preparation retains the 250 lowest hash-ranked
distinct-asset candidates, opens and decodes each selected original image,
then keeps the first 100 fully available records. Source slots containing only
an old filesystem path are skipped, counted in the receipt, and do not become
broken preview cards. The sampling manifest records this availability condition;
the full annotation index may still have partial media availability.
`atlas datasets preparation --id PLAN_ID --verify-remote-preview DATASET_ID`
re-derives that verified preview from an existing completed snapshot. It checks
the snapshot checksum and row count first, so path-only source defects can be
repaired without copying or re-indexing the whole remote population.

`structured_collection` combines pinned JSON/JSONL/CSV splits and optional remote ZIP
annotations with on-demand images. Every referenced filename is checked against a pinned
source inventory or archive directory before activation. Local media inventories are
copied into the immutable prepared version. Pruning preserves their transitive source
version dependencies and never removes a running preparation.

Selecting a whole population: `POST /selections/population` {dataset_id, query, name?, limit?} resolves every match on the
server (complete snapshots in one scan, in the snapshot's own order) and returns a `Selection` with `method: population`,
`ids: []` and `size`. Selections over 10,000 ids keep their ids in `work/selection-ids/<id>.json` (checksummed in
`atlas.sqlite`); listings and responses carry only the summary, `GET /selections/{id}/export` refuses them, and
`/runs` accepts them. Columnar runs freeze only what their processor reads (identity for projection, clustering and
neighbours; text and assets for embeddings), and their estimate digest binds the content-addressed selection rather than
re-hashing every record.

Large runs (`config.storage: "arrays"`, automatic above 5,000 records) are columnar. Their artifact has no `data.items` or
`data.points`; `data.bulk` is `{dir, count, ids: {file, sha256, bytes}, arrays: {name: {file, dtype, shape, sha256, bytes}},
extras?}` over a directory of `.npy` files beside `ids.json` (rows follow selection order; records that were skipped or
failed are in `skipped.json` and counted in `data.skipped`). `GET /artifacts/{id}/ids` returns the ids and
`GET /artifacts/{id}/arrays/{name}` the raw little-endian bytes with `X-Atlas-Dtype` and `X-Atlas-Shape` headers; both are
immutable. Projections store `coords` (n x 2 or n x 3, float32), clusterings `cluster` (int32, -1 is noise) plus
`probability` for HDBSCAN and `centroids` as a non-row array, with `data.summary` listing cluster sizes, exemplar ids
and a sampled silhouette; outlier runs store `outlier_score`. Analysis runs read upstream vectors by reference
(`vector_source`, set only by the server from a registered artifact, never by a client). Consumers that join results
onto records use `queries.result_items.result_items(artifact)`, which yields the same item dicts for both layouts.

Results that are text (model answers, tags, verdicts) add `data.bulk.texts`: `{name: {file, count, sha256, bytes}}`, one
JSON array of strings per column, aligned with `ids`; `GET /artifacts/{id}/texts/{name}` serves it (immutable). Text and
numeric columns join onto records alike as `prediction.<artifact>.<name>`. Model-server runs (`vlm.answer`, `vlm.tag`,
`vlm.judge`, `embed.api`) and `score.vqa_accuracy` are always columnar; their `data.summary` holds `completed`,
`not_completed`, `reasons`, token and latency totals (verdict or tag value spreads, and for scoring `mean_accuracy` with
breakdowns). `GET /processors` carries `preset: {template, use_images, max_tokens}` for the three `vlm.*` processors.
A batch run's `provider_id` must name a configured loopback provider; the run records the provider id, model and
address but never a credential.

`GET /datasets/{dataset_id}/column/{artifact_id}?field_id=&snapshot_id=&result=` returns one dataset field for every row of
an array result, in that result's row order, so a map can colour all of its points: the body is raw little-endian `int16`
category codes (`-1` none, `len(categories)` every other value) or `float32` values (NaN where missing), with
`X-Atlas-Dtype`, `X-Atlas-Shape` and `X-Atlas-Column` (URL-encoded JSON: `kind`, `categories`, `other`, `missing`,
`min`, `max`). It needs the complete index and refuses structured fields.

`POST /similarity/{dataset_id}` resolves a complete population as ids in one scan and accepts a `text` query for MiniLM,
SigLIP 2 and model-server (`embed.api`) spaces; the last embeds the text on the same loopback server with the space's
`query_prefix`. Cosine distances are never negative. Chat retrieval is this endpoint followed by the ordinary reviewed
context; the model gets no search tool of its own.

`atlas runs import <workspace|work dir> <run id>` copies one finished run, array bundle included, between workspaces after
re-deriving its selection, item keys, per-record outcomes and every file checksum; it is idempotent and leaves nothing on
refusal.

Browsing queries attach only explicitly selected analysis runs (maximum 32), rather
than all historical artifacts. The Results picker exposes every compatible run;
deselecting a run removes its dependent filters, sort and map colour. Inspector
run evidence and projection selection remain available independently. Frozen
selections retain the exact chosen result IDs in their saved query.

### Native source acquisition and missing media

Recipes may declare `credential_profile: huggingface`. This names locally available
`HF_TOKEN` or the Hugging Face token file; credentials are never embedded in a recipe,
plan, prepared dataset, or receipt. The bearer header is sent only to
`huggingface.co`, and is rebuilt without it on CDN redirects. Gated release access and
public redistribution rights remain separate.

`atlas datasets cache-source --path FILE --sha256 SHA256 --max-bytes N` verifies and
registers an already downloaded original in `work/source-objects/SHA256`. Workers can
reuse that retained source object independently of the evictable download cache. This
explicit source library consumes disk until removed by its owner; cache eviction does
not delete it or the caller's file. No input file is modified.

`repack_members` derives bounded member-addressable ZIPs from TAR members nested in a
source ZIP. Each derivative retains the source key, native member name, size and
checksum in the prepared receipt. `structured_collection` annotation `joins` preserve
native joined fields and reject duplicates, missing keys and undeclared unused rows.
`media_variants` names source conditions and their distinct target provenance; declared
absent conditions remain explicit fields rather than fabricated media.

An image listed by an upstream annotation but absent from the pinned source can be an
`Asset` with `uri: null`, `metadata.availability: absent_from_pinned_release`, and its
native `source_path`. It remains inspectable, is excluded from image transmission,
and is not a failed HTTP request or a placeholder image. Preparation reports these
missing references and marks the full annotation index as having partial media.
PHANTOM retains native grouped JSON, turn JSONL, and both behaviour annotation forms;
its conversation-bearing records remain example units, each with an ordered canonical
conversation. Source-listed absent images and the 12 JSONL-only conversations are
explicit. Local authorization does not make the release public.

Visual Genome streams its original ZIP/JSON tables with the optional `datasets`
extra (`ijson`) into a bounded disk-backed join index. All source rows survive,
including repeated paragraph rows and QA-region mappings without a released QA or
region. Unjoined mappings are separate annotation records with no invented image.
The derived join index is included in the preparation output budget and receipt.

The Visual Genome join writer requires an explicit `join_index_path`; preparation
workers place it inside their own version directory. Existing prepared derivatives
remain readable without creating files beside original archives. Streaming joins
check cancellation every 256 native rows, clean partial output after interruption,
and reject a QA-to-region mapping when both IDs exist but refer to different images.

Native image variants remain assets of their original example. BAPPS preserves
reference/p0/p1 roles, task, distortion group and scalar human judgements. MME
keeps both yes/no questions and a shared pair ID. MM-SafetyBench keeps all three
image conditions and their condition-specific question fields; image groups with
no released question remain explicitly unannotated examples. Browsing these
safety datasets does not execute their contents.

COVID-19 Radiography Kaggle v5 pairs each original radiograph with its released
mask as two image assets in one example. All four XLSX source tables join by
native filename. The tables' `256*256` value is kept as `source_table_size`;
all released radiographs decode at 299×299 and masks at 256×256, so this source
value must not be used as an asset width or height. The prepared release is
local-only pending medical-image rights review.

ObjectNet 1.0 is indexed from an ETag-bound remote ZIP directory and its
checksum-pinned folder-label mapping. The 197 GB archive stays remote; a
100-image original PNG preview is protected locally, with red borders intact.
Individual later originals are fetched by bounded ZIP ranges and checked by
the archive CRC and strong ETag. The complete archive SHA-256 and availability
of every later media member remain unverified. ObjectNet images are excluded
from public packs, and its [source licence](https://objectnet.dev/download.html)
forbids model-parameter tuning on the test set.

The Visual6502 revD `transdefs.js` adapter treats its 3,510 rows as structured
transistor examples and preserves every gate, channel, bounding box and geometry
value. It parses only a checksum-pinned literal table; no source JavaScript is
executed. The citing paper's exact 6507 input is not established by this public
6502 source file, so paper release identity remains a candidate. The records
stay local pending file-specific publication review.

`archive_variants` derives a complete native filename inventory from ETag-bound
ZIP directories and checks every expected per-split variant before activation.
DIV2K training's four wild realizations are distinct assets; validation has one.
`inventory_variants` joins pinned individual files by native image ID and scale,
retaining scale-specific HR crops. SUN397 separately exposes text evaluation
folds and the MATLAB non-training complements; those test populations differ.

Repeated local media reads reuse a bounded LRU of ZIP directories (four archives,
100 MB of encoded central-directory metadata) and six prepared adapter instances.
Those are cache limits, not a promise that decoded Python objects occupy 100 MB.
Local file identity changes invalidate cached checksum verification. Native image
condition/role labels appear in focused inspection; an image-specific question
is labelled separately from the record question.

Full preparations sample at most 100 representative examples while streaming the
complete index. SHA-256 priorities, seed 0, and primary-asset grouping make this
independent of source order. Every asset within a chosen example remains linked.
Preview media is original quality and resolution; existing source-order packs
retain their original sampling declarations until migrated.

When a released population has fewer than 100 distinct primary images, the
`primary_asset_then_example` sampler takes one SHA-256-ranked example per image
before filling the preview with SHA-256-ranked distinct examples. It preserves
the 100-example target without misrepresenting repeated media as new images.
`atlas datasets preparation --id ID --verify-full-media DATASET_ID` audits every
indexed image reference against a checksum-valid protected original before
marking the pinned population's media scope `full`. This says nothing about
other paper settings or publication rights.

`atlas storage status` measures unique allocated local file blocks, with hard-link,
external-symlink and shared-extent caveats. `atlas storage compact --dataset ID
--max-input-bytes N --max-output-bytes N` writes resumable full-dimension AVIF
browsing copies under `work/compact-media`, protecting all preview assets. It never
rewrites source archives, canonical records, or model inputs. `representation=compact`
serves a checksum-verified copy; `representation=original` retains the original
route. Browser assets explicitly label the copy and provide `metadata.original_uri`.
Unsupported pixel modes and animated images remain original. Compression is used
only when its measured output is smaller. Native EXIF orientation and ICC profiles
are retained without resizing. Original-source eviction is a separate operation
requiring verified retrieval and saved-selection dependency checks.

The optional remote-storage extra provides gzip TAR seek checkpoints. The original
archive is fully SHA-256 checked during indexing, each member has its own checksum,
and subsequent remote requests pin a strong ETag with an explicit transfer cap.
The retrieval receipt distinguishes transferred ranges from a full-file verification.

Native ZIP indices store original compressed offsets and per-member hashes without
keeping an uncompressed archive. `storage retire-original` checks retained snapshot
memberships, pins every preview original and installs routes before removing acquired
copies. Shared sources require all dependent datasets in the same checked operation.

`storage configure` enables `representation=optimized` for non-preview image browsing.
Its shared LRU cache is separate from bulk compaction, and model inputs remain original.
The browser's `optimized_on_demand` label allows an original-byte fallback when AVIF is
unsuitable or larger; response headers report the actual representation. Even an
explicit optimized request for a preview returns original bytes. Preparation planning
and dispatch account for configured external roots and running reservations against
the shared ceiling. Dataset coverage says "full population indexed", since complete
metadata does not imply that every original media file is resident on disk.

Remote shard fingerprinting and schema reads use at most eight concurrent readers,
preserve source order, and reserve shares of the same metadata transfer budget.
Native `conversation_pairs` mappings retain the original pair objects and expose
their ordered user/assistant text in canonical conversations. A configuration
directory is a filterable source field only when the recipe explicitly declares it.

The `text_pairs` adapter reads exact native text/label pairs without extraction,
using a declared reversible encoding and per-member checksums. `sad_structs`
preserves released sample templates and trial definitions without substituting
variables, executing benchmark code, or claiming procedural results. SAD's
anti-contamination terms prohibit committing or publishing plaintext questions;
its preview packs remain local and source receipts contain only aggregate counts,
paths and hashes.

Preparation admits at most two dataset writers, with an exclusive lease per dataset.
Each HTTP preparation uses its own admitted, bounded staging cache. Source
download/verification/linking is serialized within that cache so an object cannot
be evicted before retention; the two writers can transfer independently. A completed
worker removes its staging cache after source verification and immutable linking.
Remote indexing overlaps at most four
shards while preserving source order and global asset references. Each producer buffers
at most 32 batches and 32 MB of encoded records; these are not Python RSS limits.
ETag-bound readers reuse validated HTTPS connections and reconnect a stale socket once
before reading a response body. Saved shard fingerprints are reusable within the same
plan; every subsequent range still validates its pinned ETag.

A declared `record_filter: {asset_modality: image}` selects a native subpopulation.
The recipe must specify both `expected_source_count` and the selected `expected_count`.
Preparation checks both actual counts before activation and samples from selected
records only. This does not infer a paper-specific subset or invent native identifiers.

The Pathways adapter applies the pinned authors' caption parsing and VG two-object
exclusion rule, preserving native What's-Up annotations and original media bytes.
Its derived fields record the transformation revision; neither a historical paper
revision nor the authors' RGB image re-encoding is inferred.

TextVQA-X joins every native explanation and split ID to the original question and
image ID, rejecting missing/duplicate joins. Native boolean NumPy masks remain
available as array assets; separate, explicitly labelled PNG assets visualize their
exact values and dimensions. Pickles and object arrays are never deserialized.
Deflated TAR-to-ZIP repacking requires separate decoded-work and encoded-output
budgets, preserves native member bytes and enables random access without expanding
the entire sparse-mask collection on disk.

Snapshot writers default to a 2 MB encoded-record limit; a pinned source recipe may
opt in to at most 16 MB when a native record requires it. The snapshot manifest
records that bound. Complete-index queries cap the combined encoded record and
prediction payloads at 32 MB per page; a byte-shortened page retains an exact count
and a continuation cursor. This is a record-payload cap, not an HTTP-envelope or
process RSS claim. Native conversations are never truncated to meet the cap.
Recipe resource limits are validated and pinned in preparation plans, then applied
to both the worker cgroup command and its CPU/RSS/wall-time watchdog.

Keyed JSON annotations may declare `record_key_field`; collisions are rejected.
Explicit `many: true` joins retain every matching native row in source order and
still reject orphaned join keys. Nocaps uses image records with ten validation
captions, while its unpublished test captions remain absent. Public media manifests
may pin strong ETags plus exact lengths; every read validates both and records the
observed content hash. ETags are not presented as cryptographic content checksums.

Shapes datasets use bundled pure functions from the pinned MIT-licensed author
recipe. Generation is explicit preparation with bounds on pairs, image size,
decoded pixels and output bytes. Seeds, Python minor version, Pillow version and
source revision are pinned. Stored PNGs retain hashes and counterfactual pair
relations; existing prepared images can be read without rerunning the generator.
These populations are labelled author-recipe reconstructions, not archived
historical experiment images or Atlas test fixtures.

`storage retire-repacked` requires exact parity for every native archive member,
existing original access for every dependent snapshot, and pinned preview originals.
It does not delete snapshots, create replacement native routes, or remove external
source files. Index-writer failures close all owned iterators, including remote
prefetch producers.

Multipart ZIP sources pin the order, length and ETag of every byte chunk. Reads
cross chunk boundaries under one transfer cap without assembling a full archive.
This supports byte-split ZIPs, not ZIP multi-disk archives. Repeated media reads
reuse bounded parsed directories while retaining native header, name, overlap,
length and CRC checks. The cache bound measures encoded directory bytes, not
Python object RSS.

Multipart gzip TAR sources pin ordered part lengths and SHA-256 hashes before
bounded assembly. A complete combined archive SHA-256 is checked before native
indexing; the resulting member index preserves per-member hashes and gzip seek
checkpoints. Original reads may later use ETag-bound ranges over the individual
parts under one transfer limit after Atlas-owned archive copies are retired.
Preview image and audio originals are pinned before such retirement; full record
metadata and checksum-verified prompt tables remain local.

Native plain TAR sources use byte offsets and per-member SHA-256 hashes; compression
is detected from the bytes rather than a filename suffix. They need no gzip checkpoints.
Retiring a repack checks every native member, and retiring an original installs only
the corresponding source routes without replacing routes for other archives.

The Stanford SVHN exception accepts only the two official cropped train/test HTTP
URLs, exact file lengths and SHA-256 hashes. It rejects redirects and nonpublic IPs,
does not resume partial HTTP responses and permits no arbitrary HTTP recipes.

Structured native Parquet annotations preserve ordered list fields and frame identities.
Recipes can declare exact missing media references from a pinned source inventory;
every declared absence must be absent and every observed absence must be declared.
Missing records retain native paths with null media URIs rather than replacement images.

Storage cleanup defaults to a plan. Execution refuses active preparations in its
workspace, evicts only unpinned bounded-cache objects, and deduplicates immutable bytes
using full SHA-256 and stable file identity. Canonical JSON and SQLite remain mutable
and are excluded from derivative linking. Corpus inputs and model weights are retained.

`atlas storage pin-preview --dataset ID --max-input-bytes N --max-output-bytes N`
checks every preview image identity against the complete snapshot and retains
its exact original bytes in the protected compact-media store. This is useful
when a source's images are independently hosted and no single native archive
can be retired. A repeated run validates and reuses previously pinned bytes.

ROCO keeps the author's six split/domain annotation groups and their native
caption, image-link, keyword, CUI, semantic-type and per-image licence tables.
The archived FTP commands are never executed. An image request looks up its
filename in the current versioned PMC article metadata and checks the
downloaded image against that metadata's MD5. This verifies current PMC
access, not byte equivalence to the historical ROCO FTP image. All annotation
records are indexed, but media beyond the verified 100-image preview remain
on-demand and unverified until requested.

FIND preserves native function source, metadata and available model files as
passive text/array assets; importing never executes code or deserializes weights.
SEED question identities include native task IDs, retaining a repeated question
ID across two task types. All native choices and frame order survive; released
video frames are not described as full videos. FairFace retains both released
crop variants and labels them with their native padding conditions.

Selective workers honor the cache root and byte limit admitted by their plan.
Registered, checksum-verified originals on the destination filesystem can be
reserved for hard-link reuse. Such a plan fails if the original disappears or
linking fails; it cannot fall back to an unreserved download or copy.

Sampled previews retain original media in the immutable version's `pack/media`
directory. The API resolves this pack and verifies its recorded whole-file
checksum before considering a remote source reference. Default data roots include
`work/prepared`; explicit data-root settings remain authoritative. Extensionless
content-addressed image files use their decoded format for the HTTP media type.
A missing or changed retained file is an error, not an automatic remote download.

Model context requests may include `snapshot_ids`; the workbench resolves records and rights from those inspected versions and refuses unavailable bindings. Approved context policy records exact record versions, maximum completion tokens and optional `reasoning_effort`; configuration changes invalidate the approval digest.

### Release 1.0 query and preparation bindings

`POST /datasets/{dataset_id}/membership/{artifact_id}` accepts a `Query` and returns
one raw `uint8` byte per artifact subject, in registered artifact-ID order. Headers
`X-Atlas-Dtype: uint8` and `X-Atlas-Shape` describe the array. Values are exactly zero
or one. The server binds dataset, snapshot and unit, validates unique artifact IDs,
and applies filters, search and sampling before intersecting with artifact IDs;
browsing pagination does not limit membership. Pending, invalid or mismatched masks
render and select no points. A map point fetch passes its artifact snapshot explicitly.
The static provider computes the same membership over its complete preview pack.

Preparation plans accept optional `sample_seed`, an integer exactly representable
in JavaScript. Whole-source remote samplers freeze the resolved seed in the plan and
fingerprint. Changing a seed or a resource bound invalidates a prior browser plan.
`atlas datasets acquire --no-activate` builds a candidate without changing the active
pointer; durable `activate_on_success` survives retries and restarts. A candidate is
not runtime coverage until independently checked and activated.

Structured native collections may retain rows with unavailable media. Their source
path remains intact, `uri` is null, and availability is `not_acquired`; these rows
remain in the full index. Preview eligibility may require available originals without
changing that index population. Pinned exceptional file extensions require exact
size/hash/header checks and expose the detected MIME type; original bytes and source
names remain unchanged.

Current catalogue IDs and explicit friendly aliases resolve current cards only.
Frozen record/tool requests with an explicit snapshot may discover matching retained
prepared metadata even after a card is retired. Lookup is bounded to known local
metadata, literal historical IDs and the requested snapshot; it never rebinds a
retired ID to a different current dataset. Default catalogue listings exclude these
archives. Result browsing omits both vector and activation-value arrays; full artifact
retrieval preserves the exact original arrays.

Future whole-source sample snapshots use `snapshot_identity` provenance with a
versioned scheme, `source_population_sha256`, source population row/shard counts,
`cohort_sha256` and actual `record_count`. The source binding covers pinned native
files; the cohort binding covers ordered native envelopes, media hashes and
availability plus the effective schema. It excludes the top-level envelope
snapshot ID and generated cache paths, budgets and counters. Native source fields
(including a source field named `snapshot_id`) remain part of the content. Final
IDs are assigned to the dataset, records and receipt before persistence. Existing
active snapshots and native record IDs remain unchanged.
The source-population SHA is a fingerprint of pinned source descriptors and the
observed footer row count; it does not claim a local hash verification of every
byte in the remote source files.
