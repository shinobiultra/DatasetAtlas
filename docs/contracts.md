# Shared v1 contracts

`src/dataset_atlas/models.py` is canonical. Use its Pydantic records verbatim; do not fork shapes. Frontend types are generated to `apps/web/src/generated.ts` by `scripts/generate_contracts.py` (lead owned).

Each dataset registry YAML validates as `Dataset`. Dataset `adapter_config` holds local preparation mapping; never publish this configuration. A local or public pack is `Pack`: dataset, fields, records, artifacts, population_scope, sampling, checksums. Preview paths: `work/packs/<dataset-id>/pack.json`; public packs `apps/web/public/data/<dataset-id>.json`, catalogue `data/catalogue.json` as array of Dataset. Empty metadata records have no pack. Static relative URLs must support Vite base paths. Asset.uri is a relative URL in public packs; backend translates configured-root local assets to opaque `/api/v1/media/...` URLs. Source fields use `source.<key>`; computed fields use `prediction.<key>`.

Provider API: `GET /api/v1/capabilities`, `/datasets`, `/datasets/{id}`, `/datasets/{id}/fields`, `/datasets/{id}/pack`, `/catalogue/thumbnails` (real preview tiles per prepared dataset, derived from packs and cached per pack revision; the static build publishes the same shape to `data/thumbnails.json` from approved records only); `POST /queries/{dataset_id}` Query -> QueryResult; `POST /aggregate/{dataset_id}` {query, field_ids, top} -> distributions over the population the filter matched, in both preview and complete scope. Aggregates never apply the browsing query's sample and say so in `warnings`; `aggregate_pack` (Python) and `aggregatePack` (TypeScript) are parity-tested against one generated fixture. `/selections` GET/POST Selection (accept blank id to assign); `/selections/{id}` GET; `/selections/{id}/export` GET portable JSON. `/processors` GET descriptors; `/runs` GET/POST {selection_id,processor_id,config}; `/runs/{id}` GET; `/runs/{id}/cancel` POST; `/artifacts` GET; `/artifacts/{id}` GET. Providers `/providers` GET/POST configuration, `/providers/{id}/probe` POST; conversations `/conversations/context` POST and `/conversations` POST; analysis and provider agents supply routers or functions and communicate signatures.

Workbench is explicit `?mode=workbench`; same-origin API only. Static is default; never auto-probe localhost. State-changing API requests require `X-Atlas-Request: 1` and same-origin checks. Structured error detail from FastAPI; frontend displays actual error.

Filter AST: leaf {field_id,op,value} or {and:[...]}/{or:[...]}/{not:...}; bounded depth 8 and 64 leaves. eq/ne/in/contains/gt/gte/lt/lte/is_null; missing values match only is_null true (including ne must be false on missing). Literal contains case-insensitive. Sort null last both directions, id ascending tie-break. Search case-insensitive literal over text, question, source JSON. Sampling source/random/stratified with numeric seed and size, random uses FNV-1a hash of `seed:id` ascending so parity is portable. Cursor opaque bounded offset tied to query fingerprint. Selections save actual IDs, not only a query.

Do not edit shared models without coordinating with lead. Use optional imports for heavy dependencies and honest unavailable statuses. Synthetic data only in tests. Agents own their assigned files and must preserve others' changes.

On-demand preparation: `POST /datasets/{id}/preparation/plan` takes explicit `max_download_bytes` and `max_output_bytes`; `POST /preparation/{plan_id}/start` executes that saved plan. `GET /preparation?dataset_id=...`, `GET /preparation/{plan_id}`, and `POST /preparation/{plan_id}/cancel` expose durable status and cancellation. These workbench-only operations are not exposed as model tools. Prepared versions under `work/prepared` override active local registry coverage while preserving earlier snapshots. `GET /media/{token}?representation=safe-view` returns a display derivative; original record references are unchanged.

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

`structured_collection` combines pinned JSON/JSONL/CSV splits and optional remote ZIP
annotations with on-demand images. Every referenced filename is checked against a pinned
source inventory or archive directory before activation. Local media inventories are
copied into the immutable prepared version. Pruning preserves their transitive source
version dependencies and never removes a running preparation.

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
