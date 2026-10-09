# Dataset Atlas — specification and implementation plan

**Build a useful dataset browser first, with optional analysis attached to the same samples.** The public version should work without installation or model computation. The local/server workbench should add complete-data access, detectors, embeddings, projections, and model-assisted exploration.

The paper directory below is the agents’ authoritative starting point. **Scraping it and establishing dataset coverage are implementation deliverables—not work you need to perform manually.**

Save this specification as `SPEC.md`. Give the opening brief to the lead implementation agent.

---

# 0. Lead-agent handoff

```text
Implement Dataset Atlas according to SPEC.md.

Authoritative local paper directory:
"/home/bitwise/Documents/Media_Bias_Group/MechinterpAdversarialAttacks/Flight Package"

Recursively inspect this directory, including PDFs, bibliography exports,
supplementary files, and relevant subdirectories. Treat it as read-only.

Extract every dataset and benchmark used or mentioned in the papers.
Do not limit extraction to abstracts, datasets sections, or a preselected list.
Do not assume there are approximately 50 datasets.
The actual inventory must come from the complete corpus.

Distinguish:
- datasets from models, methods, metrics, and benchmark suites;
- base datasets from annotation overlays and derived releases;
- datasets actually used from related-work and bibliography-only mentions;
- original dataset properties from paper-specific subsets.

For each dataset:
- identify its original source and release;
- record evidence linking it to the papers;
- implement browsing through reusable adapters where access permits;
- provide 100 inspectable examples, or all examples if fewer exist;
- support extending beyond the preview without changing frontend code;
- explicitly record access, licensing, availability, and implementation blockers.

Do not mark metadata-only records as fully browsable.
Do not disguise unfinished adapters as externally blocked datasets.
Do not substitute synthetic samples for real dataset coverage.

Architecture:
- React + TypeScript + Vite frontend.
- Static GitHub Pages build for catalogue, previews, and published artifacts.
- Optional Python workbench serving the same frontend and a local API.
- Read-only original data, immutable derived artifacts, resumable jobs.
- Local paths, mounted network storage, and remote-source adapters.
- LanceDB for optional local vector retrieval; exact search first.
- No mandatory FAISS, external database service, custom Rust, or account system.

Required analysis:
- NudeNet.
- A person/object detector.
- Image/text embeddings and filtered similarity search.
- PCA/UMAP with linked sample inspection.
- Basic clustering, outlier, and two-variable comparison tools.
- LM Studio/vLLM/OpenAI-compatible provider connections.
- Selected-sample conversations and bounded, read-only tool-assisted exploration.
- Import of externally computed classifier and mechanistic-interpretability outputs.

Keep the frontend minimal:
a searchable catalogue, one browsing workspace, and optional drawers.

Work in milestones. Establish the shared contracts before parallelizing.
Demonstrate real end-to-end dataset browsing early.
Every claimed capability must have tests and recorded evidence.

Do not modify the paper directory, overwrite unrelated repository work,
download entire large datasets without an explicit budget, publish private
material, or send dataset contents to external model providers without approval.

If the corpus directory is inaccessible, report the exact failure.
Continue independent infrastructure work, but do not fabricate corpus results
or replace the local corpus with an arbitrary online reading list.
```

---

# 1. Product definition

## 1.1 Purpose

Dataset Atlas lets a researcher move through this workflow:

> Find a dataset → inspect real examples and annotations → select an interesting population → compute or load additional evidence → compare examples and representations → export a reproducible selection.

The application is **not primarily a paper-management system**, a training platform, or a chatbot. Papers establish the initial catalogue and provenance. The central objects are datasets, their examples, and optional computed results.

## 1.2 Primary user journeys

| Journey                                                    | Expected outcome                                                                                            |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| “This paper mentions a dataset. Show me what it contains.” | Find the dataset by name, alias, description, or paper; inspect examples immediately.                       |
| “Show me 100 examples with these labels.”                  | Apply explicit filters, choose the sampling unit and method, and browse a reproducible selection.           |
| “Where do detectors disagree?”                             | Filter or colour samples using results from named detector runs; inspect underlying images and predictions. |
| “What is this embedding space organizing?”                 | Open a projection, overlay annotations, inspect neighbours, and compare representations.                    |
| “Ask my local VLM about these examples.”                   | Preview exactly what will be sent, run the request, and save responses with provenance.                     |
| “The dataset is on another machine.”                       | Browse through a mount or run the workbench near the data and connect through an SSH tunnel.                |
| “Share this discovery with a colleague.”                   | Export sample identities, results, configuration, and approved media without copying the entire dataset.    |

## 1.3 Product principles

**Useful without models.** Browsing, metadata inspection, filtering, and saved selections must not require a GPU or an LLM.

**One representation of the data.** Grid, table, map, statistics, and model tools operate on the same identities and selections.

**No silent scope changes.** A preview is not the full dataset. An approximate search is not exact search. A failed computation is not a negative prediction.

**Preserve original meaning.** Retain source fields, annotation definitions, task structure, and uncertainty.

**Add datasets without editing the frontend.** Ordinary integrations should consist of a manifest, mappings, and tests.

**Simple operations; extensible internals.** Avoid exposing a workflow graph, database administration interface, or model-serving console to ordinary users.

---

# 2. Scope and release boundaries

## 2.1 Required for v1.0

V1.0 includes the complete corpus inventory, working dataset browsing, optional local analysis, and controlled model integration.

| Area             | Required scope                                                                                                        |
| ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| Corpus           | Account for every relevant local paper and extract all dataset/benchmark mentions.                                    |
| Catalogue        | Search names, aliases, descriptions, tasks, labels, access status, and paper references.                              |
| Browsing         | Image, text, multi-image, question–answer, paired-example, and conversation records.                                  |
| Other modalities | Preserve all records; use native audio/video playback where supported and structured/raw-record inspection otherwise. |
| Data access      | Local paths, existing filesystem mounts, HTTPS sources, and tested source adapters.                                   |
| Previews         | Target 100 real examples per accessible dataset, or all if smaller.                                                   |
| Complete data    | Adapter-based access beyond previews, with explicit download/indexing requirements.                                   |
| Analysis         | Detector runs, embeddings, exact similarity search, PCA/UMAP, basic clustering/outlier analysis.                      |
| Models           | Configurable compatible endpoints, capability checks, selected-sample questions, bounded read-only tools.             |
| Reproducibility  | Versioned runs, immutable selections, input provenance, export/import.                                                |
| Publication      | Static build, sanitized publication manifest, deployment instructions, and coverage report.                           |

**Initial inventory coverage is mandatory. Initial computation over every complete dataset is not.** V1 should support running analyses on selected populations, rather than automatically embedding every dataset mentioned anywhere in the corpus.

## 2.2 Experimental or later

Custom FAISS acceleration, distributed workers, native desktop packaging, browser-only model inference, advanced annotation editing, and comprehensive model training remain extensions.

Direct browser access to user-selected local folders may be added as a convenience. It must not replace the reliable local-workbench workflow.

Do not introduce accounts, billing, multi-tenant permissions, Kubernetes, Redis/Celery, or a mandatory vector-database server.

---

# 3. Architecture

## 3.1 Two deployment modes, one frontend

### Public static mode

Publish the application shell, catalogue, approved preview packs, and optional precomputed results.

There is no application backend to operate. Users can search catalogue metadata, browse published examples, filter within the published population, and inspect published projections.

A public build must remain useful when upstream services are unavailable.

GitHub Pages is a static hosting service. Its published-site limit is currently 1 GB, with a 100 GB/month soft bandwidth limit; the build should therefore be a browser and curated preview distribution, not a full dataset mirror. ([GitHub Docs][1])

### Workbench mode

A Python service provides data access, queries, jobs, and model connections. It serves the **same built frontend**.

The workbench can run on the researcher’s laptop or on a machine with datasets and GPUs. Bind to loopback by default; document access through an SSH tunnel.

Do not make the public website connect to a privileged localhost service by default.

## 3.2 Implementation stack

| Component                | Decision                                                                                           |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| Frontend                 | React, TypeScript, Vite                                                                            |
| Styling                  | Small set of reusable components; ordinary CSS or the repository’s existing styling convention     |
| Backend                  | Python, FastAPI, Pydantic                                                                          |
| HTTP clients             | A maintained Python HTTP client with timeout, cancellation, and retry support                      |
| Registry                 | Human-reviewable YAML/JSON                                                                         |
| Dataset/result artifacts | JSON for small manifests; Parquet for tabular records; appropriate binary formats for arrays/media |
| Operational state        | SQLite for jobs, local settings, notes, and artifact registrations                                 |
| Analytical queries       | DuckDB over immutable data/result snapshots                                                        |
| Vector retrieval         | Optional LanceDB, initially without approximate indexes                                            |
| Storage interface        | Local filesystem plus `fsspec`-based remote access                                                 |
| Testing                  | Python tests, frontend component tests, browser end-to-end tests, contract fixtures                |
| Packaging                | Python package containing the built frontend; separate frontend development workspace              |

These are libraries within one application, not separate deployed services.

**Storage ownership must be clear:** SQLite holds mutable operational state; Parquet/manifests hold durable dataset and analysis artifacts; LanceDB holds rebuildable search structures. Do not maintain competing authoritative copies of source annotations.

Use a single coordinator for state changes. Workers write staged results; the coordinator validates and registers them. Do not let arbitrary worker processes concurrently mutate a shared database file over network storage. DuckDB’s documentation specifically calls for caution with database files on shared directories and network-attached storage. ([DuckDB][2])

## 3.3 Shared frontend contract

Implement two providers behind one interface:

```text
StaticDataProvider
WorkbenchDataProvider
```

Both expose catalogue discovery, record retrieval, field descriptions, supported queries, selections, and artifact discovery.

The workbench additionally exposes computation and provider connections.

A capability response determines which actions are enabled. Do not scatter environment-specific conditionals throughout UI components.

## 3.4 Versioning

Version schemas, APIs, dataset snapshots, and analysis artifacts independently.

Use one canonical schema definition with generated or mechanically validated TypeScript representations. Do not manually maintain divergent Python and TypeScript data models.

Readers must reject incompatible major versions with an actionable message. Migrations must not overwrite the only copy of an older artifact.

---

# 4. Initial corpus extraction

## 4.1 Authoritative input

```text
/home/bitwise/Documents/Media_Bias_Group/MechinterpAdversarialAttacks/Flight Package
```

Treat this path as read-only. Keep generated text, downloaded source pages, extraction results, and caches in the application workspace—not beside the papers.

The previously supplied RIS contains 64 bibliographic records, but the directory inventory is authoritative and may differ. The RIS is a cross-check, not a fixed expected paper count. 

## 4.2 Inventory every source

For each file, record its relative location, type, checksum, processing status, and its relationship to a paper where identifiable.

For PDFs, also record page count and extraction quality. Deduplicate byte-identical copies while retaining their original locations. Preserve different versions of the same paper.

Do not follow symlinks outside the approved corpus root without explicit configuration.

Every paper must finish with one of these outcomes:

```text
processed
processed_with_review_items
no_dataset_mentions_found_after_review
extraction_failed
unavailable
```

An extraction failure is not evidence that the paper mentions no datasets.

## 4.3 Extract from the complete paper

Inspect the body, appendices, tables, captions, footnotes, supplementary material, and bibliography.

Extract candidate mentions of named datasets, benchmark suites, annotation releases, custom evaluation collections, and data-generation recipes.

For every mention, preserve:

```text
paper_id and paper_version
source_file_hash
page and section/table location
name_as_written
short supporting excerpt
mention_role
reported properties
candidate canonical identity
review status
```

Classify the role as introduction, training, evaluation, source data, derived collection, related-work mention, or bibliography-only reference.

Do not interpret “a model was pretrained on X” as “this paper evaluates on X.”

## 4.4 Resolve identities without erasing distinctions

Resolve candidates through the local citation and original author/project sources.

Distinguish datasets from methods, model names, metrics, and suites. A suite can have a catalogue record linking to member datasets without pretending that the suite is itself one homogeneous image collection.

Retain base-dataset relationships and annotation dependencies. Do not merge two releases merely because names look similar.

For unnamed custom data, create a clearly labelled paper-associated record. Mark unreleased material as unreleased; do not synthesize replacements and present them as original samples.

Paper-specific filtering belongs in the mention evidence.

## 4.5 Evidence and review rules

Use extraction plus a separate reconciliation pass. Review suspected aliases, conflicting sizes, ambiguous references, and low-quality PDF extraction.

Prefer extracted text and page inspection. Use OCR selectively only when needed.

An LLM may propose candidates, but accepted records require identifiable source evidence. Model confidence is not a substitute for evidence.

When online material differs from a local paper version, retain both versions and their claims separately. Do not silently replace the local evidence with a newer paper.

Do not recursively ingest the reading lists of every cited paper. Follow references far enough to resolve the dataset actually mentioned.

## 4.6 Required outputs

```text
work/corpus/corpus_manifest.json
work/corpus/papers.jsonl
work/corpus/dataset_mentions.jsonl
work/corpus/review_queue.jsonl

registry/datasets/*.yaml
registry/papers/*.yaml

reports/corpus_coverage.md
reports/dataset_coverage.csv
reports/source_access_report.md
```

Full extracted paper text stays outside public exports and version control by default.

---

# 5. Dataset coverage and acceptance

A single “supported” boolean is insufficient.

Track these dimensions independently:

| Dimension            | Example states                                                        |
| -------------------- | --------------------------------------------------------------------- |
| Identity             | Candidate / resolved / ambiguous                                      |
| Source               | Verified / missing / changed                                          |
| Access               | Public / gated / locally supplied / unavailable                       |
| Adapter              | Not started / implemented / tested / failing                          |
| Preview              | None / partial / complete target                                      |
| Complete-data access | Supported / requires preparation / externally blocked / unimplemented |
| Publication          | Approved / metadata-only / prohibited / not reviewed                  |
| Analysis             | Available runs and their actual coverage                              |

For accessible datasets, the preview target is **100 inspectable examples or the entire dataset if smaller**. Prefer that many distinct assets when the task repeats images, while retaining their linked examples.

Every preview must include its sampling method and population.

Large datasets keep approximately 100 reproducibly sampled examples as their local
preview. Preview media retains the original resolution and quality; thumbnail,
blurred safe-view, and browsing derivatives are separate representations. Prefer
deterministic random selection across the pinned population and distinct primary
assets when many examples reuse an image. Record the seed, grouping rule, and
population; grouped sampling is not an example-prevalence estimate.

Full-data support means the adapter can operate beyond a hard-coded preview. Test that path on additional records or a bounded integration run; do not require downloading an enormous dataset merely to test the abstraction.

Acceptable external blockers include unavailable releases, access approval, unavailable underlying media, and restrictions on obtaining or publishing data.

“Complicated format,” “not on Hugging Face,” or “agent ran out of scope” are **implementation gaps**, not external blockers.

Publication restrictions do not automatically prevent local browsing.

---

# 6. Data model

## 6.1 Core records

| Record     | Meaning                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------- |
| Dataset    | Stable catalogue identity, aliases, description, tasks, modalities                          |
| Release    | A particular source version or captured snapshot                                            |
| Asset      | An image, text document, video, audio file, or other source object                          |
| Example    | A task record referencing one or more assets: question, choices, answer, conversation, etc. |
| Entity     | A region/person/object within an asset where annotations require it                         |
| Annotation | A source label, human review, or computed observation attached to an explicit subject       |
| Relation   | A typed link between records, such as paired examples or shared source assets               |
| Selection  | A frozen set of typed record identities with provenance                                     |
| Run        | A computation request, configuration, status, and outputs                                   |
| Artifact   | A versioned result: vectors, coordinates, predictions, statistics, or exported pack         |

These can be implemented as ordinary tables and files. No graph database is required.

## 6.2 Identity

Identifiers must remain stable across pagination, sorting, caching, and mounting the same data at another path.

Prefer upstream identifiers scoped to a release. When they do not exist, create a deterministic mapping for the pinned source snapshot.

Do not use a mutable dataframe row offset as the only identity.

Do not require downloading every image just to assign IDs. Compute content hashes lazily when bytes are available.

Keep source identity separate from content deduplication: two records can reference identical bytes while retaining different provenance.

## 6.3 Asset versus example

Image-only detectors operate on assets. Question answering operates on examples. Region classifiers operate on entities.

An image reused by twenty questions should not be decoded and passed through the same image-only detector twenty times.

The UI may use “sample” as a friendly term, but must expose whether the current unit is an asset, example, entity, or conversation.

## 6.4 Original and normalized fields

Retain original source fields and a source-schema description.

Normalized fields are an interoperability layer, not a replacement for original data. Preserve multi-image order, conversation roles, multiple references, annotation disagreements, and label definitions.

Keep separate logical namespaces:

```text
source       Original dataset annotations
prediction   Results from a specified run
human        User reviews and corrections
```

Use field descriptors with stable IDs, types, units, subject scope, and provenance. Display names such as `prediction.person_count` need not be literal database column names.

## 6.5 Annotation semantics

Every annotation identifies its subject, attribute, value, provenance, and—where supplied—annotator or aggregation method.

Preserve “unknown,” “not applicable,” and disagreement categories. Do not silently coerce them into binary labels.

Demographic analysis should preserve the source’s exact construct. Self-reported identity, annotator-perceived presentation, and a model prediction are not interchangeable.

Source-provided demographic annotations and existing research classifier outputs may be inspected separately. V1 must not automatically manufacture sensitive identity labels from faces or reinterpret detector class names as demographic ground truth.

## 6.6 Relations

Support at least:

```text
same_asset
paired_with
counterfactual_of
edited_from
adversarial_variant_of
duplicate_candidate_of
```

Each relation records who supplied or computed it. Embedding similarity is not evidence that two examples are valid counterfactuals.

## 6.7 Measurements

Never store only an ambiguous `dataset_size`.

A measurement records value, unit, release/split/selection, source, method, and whether it is reported or computed.

Keep these distinguishable:

```text
Reported upstream
Reported in paper
Computed on complete available release
Computed on preview
Computed on filtered selection
```

---

# 7. Dataset adapters and packs

## 7.1 Adapter interface

The following is an interface contract, not a required exact class implementation:

```python
class DatasetAdapter:
    def probe(self, config) -> SourceDescription: ...
    def plan(self, request) -> PreparationPlan: ...
    def prepare(self, approved_plan) -> PreparedSource: ...
    def iter_records(self, source, cursor=None) -> RecordBatch: ...
    def resolve_asset(self, asset_ref) -> MediaHandle: ...
    def validate(self, source) -> ValidationReport: ...
```

`probe` identifies source capabilities without bulk acquisition.

`plan` explains required downloads, indexing, dependencies, and estimated storage.

`prepare` executes an approved bounded plan.

`iter_records` emits records incrementally.

`resolve_asset` retrieves approved media without exposing arbitrary filesystem access.

## 7.2 Initial adapter families

Implement reusable support for structured JSON/JSONL/CSV/Parquet sources, Hugging Face releases, directory/archive-backed media, and annotation overlays joined to base datasets.

Custom adapters are allowed where genuinely necessary. Dataset-specific frontend components are not the default solution.

Each adapter declares whether it supports streaming, random access, resumable preparation, local-copy requirements, and selective media retrieval.

Do not promise zero-extraction arbitrary browsing for every archive format. Record and expose preparation requirements.

## 7.3 Portable packs

```text
pack/
  manifest.json
  fields.json
  browse-index.json
  records/
    part-*.parquet
  preview/
    samples-*.json
    media/
  relations/
  statistics/
  artifacts/
```

The manifest records schema version, dataset/release identities, record units, file checksums, provenance, rights decisions, and coverage.

A public preview pack may omit complete records and original media. A local pack may reference authorized external storage.

No pack should contain machine-specific absolute paths or credentials.

Every published artifact must have sufficient identifiers to align it with the correct records.

## 7.4 Adapter tests

Every integration needs a small safe fixture, identity tests, schema checks, media-resolution tests, and validation of relevant joins.

For overlays, report unmatched and multiply matched source IDs. Do not silently drop them.

For live sources, retain the checked revision and date. Network integration tests must be separately runnable so an upstream outage does not make all unit tests unusable.

---

# 8. Storage, caching, and large datasets

## 8.1 Storage locations

Separate the paper corpus, original datasets, derived artifacts, and disposable cache.

Support local paths and existing SSHFS/NFS/SMB-style mounts as filesystem roots. Add HTTPS and object-storage access through the storage interface where required by the inventory.

`fsspec` provides common filesystem abstractions and caching facilities; adapters must still account for differences between individual storage backends. ([fsspec][3])

## 8.2 Operating modes

**Laptop mode:** fetch selected records/media and cache them locally.

**Near-data mode:** run the workbench beside the dataset and compute resources; stream browser-visible metadata and media to the user.

The application must not require copying an entire remote collection to the laptop.

## 8.3 Cache policy

Implement bounded caches, pinning, explicit eviction, resumable transfers, and limited prefetch.

Cache identity includes the source revision, asset identity, and transformation. A changed source or preprocessing recipe must not reuse a stale result.

Do not assume an upstream ETag is a cryptographic content hash. Record the type of fingerprint actually available.

Active indexes and operational databases should live on storage controlled by the workbench, not an uncoordinated shared writable mount.

## 8.4 Budgets

Any bulk preparation or analysis action must show its selected population, expected downloads, output footprint, and uncertainty.

Users approve the budget before execution. Unknown size is not permission for an unbounded download.

Cancellation must preserve reusable completed work.

The local Atlas storage target is **100 GB**, within the requested **50–150 GB**
range. Measure actual unique local storage, including retained sources, indices,
preview media, caches, models, and temporary preparation output. Report shared
hard links separately from logical file sizes. A per-dataset cache limit does not
replace a workspace-wide budget.

Keep full-resolution original-quality preview samples. Apply modern compression
to other retained dataset content, with codec/settings, original provenance,
measured size savings, and verified decoding recorded. Lossless JPEG recompression
must reconstruct the original bytes; lossy representations must be explicitly
labelled and must not silently become evaluation inputs. An original remains
retrievable on demand. Compression ratios must be measured rather than assumed.
For collections that still exceed the budget, retain source manifests and bounded
caches and retrieve selected data on demand rather than mirror the entire release.

Lossy compression of non-preview images is authorized. Retain original pixel
dimensions, use a modern codec such as AVIF, and protect every asset of a preview
example (including its image variants) at original quality. The browser identifies
compressed copies and offers the original. Canonical model inputs remain original
unless a run explicitly requests and records a compressed representation.

## 8.5 Input integrity

Keep original bytes, display previews, crops, safe-view derivatives, and model inputs distinct.

Every model run identifies the representation it consumed. UI thumbnails must never become evaluation inputs merely because they are cached.

Record orientation handling, resizing/cropping, colour conversion, and other transformations. Map detector boxes back to a documented coordinate system and retain original detector coordinates where needed.

---

# 9. Queries, filtering, and selections

## 9.1 Three explicit search modes

| Mode              | Scope                                                                    |
| ----------------- | ------------------------------------------------------------------------ |
| Catalogue search  | Dataset names, aliases, descriptions, paper references, available labels |
| Record search     | Text and structured fields within a selected population                  |
| Similarity search | A named embedding space and compatible query representation              |

A chat box must not replace ordinary search and filtering.

A new semantic text query requires a compatible query encoder. Precomputed dataset vectors alone do not make arbitrary new queries computation-free.

## 9.2 Typed query language

Define a bounded filter structure supporting comparisons, membership, literal text matching, null checks, and boolean composition.

Compile field IDs through a registered schema. Never concatenate arbitrary user/model strings into SQL.

Example:

```json
{
  "snapshot_id": "snapshot-id",
  "unit": "asset",
  "filter": {
    "and": [
      {
        "field_id": "field-id-for-person-count",
        "op": "eq",
        "value": 1
      },
      {
        "field_id": "field-id-for-selected-score",
        "op": "gte",
        "value": 0.7
      }
    ]
  },
  "sort": [
    {
      "field_id": "field-id-for-selected-score",
      "direction": "desc"
    }
  ],
  "limit": 100
}
```

Use explicit null semantics consistently across static and workbench providers. Unknown or unavailable fields must not silently become zero.

Unsupported operations return an actionable error; they must not fall back to filtering only the currently loaded page.

## 9.3 Query response scope

Every response carries:

```text
snapshot_id
unit
population_scope
returned_count
matched_count, when known
count_status: exact / estimated / unknown
coverage
ordering
continuation cursor
warnings
```

A similarity top-20 result is not evidence that exactly twenty matching records exist.

Pin queries to dataset and result snapshots so a job completing mid-query does not change the population underneath the user.

## 9.4 Sampling

Provide source order, seeded random sampling, and stratified sampling where supported.

Save actual selected IDs as well as the method and seed.

Sampling operates over an explicitly identified available population. Missing media and excluded records must be reported.

Distinguish “sample 100 assets” from “sample 100 examples.” Stratified previews must not be presented as population-prevalence estimates.

## 9.5 Cross-dataset use

Allow selections spanning datasets through common normalized fields and explicit mapping definitions.

Do not silently harmonize labels with superficially similar names. Incompatible fields remain distinct.

Exports must preserve each record’s dataset and release identity.

---

# 10. Enrichment and analysis processors

## 10.1 One processor system

Detectors, embeddings, captions, quality checks, imported predictions, and mechanistic signals use the same run/artifact infrastructure.

```python
class Processor:
    def describe(self) -> ProcessorDescription: ...
    def validate_inputs(self, selection, config) -> ValidationReport: ...
    def estimate(self, selection, config) -> ResourceEstimate: ...
    def run_batch(self, inputs, config) -> ResultBatch: ...
```

The description includes supported input units, output schema, dependencies, batching, device requirements, and configuration.

Use installed, trusted plugins. Do not execute arbitrary code shipped inside dataset packs.

## 10.2 Required initial processors

| Processor              | Initial behaviour                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------- |
| NudeNet                | Preserve classes, scores, boxes, and run configuration                                        |
| Person/object detector | Boxes, class predictions, scores, derived person counts                                       |
| Basic quality          | Dimensions, aspect ratio, decode failures, duplicate-related fingerprints                     |
| Embeddings             | Image/text and text-only recipes                                                              |
| Projection             | PCA and UMAP                                                                                  |
| Cluster/outlier        | One basic clustering method and a documented embedding-space outlier score                    |
| Import                 | Attach external scalar, categorical, vector, region, and model-response outputs by stable IDs |

NudeNet exposes batch detection and returns class, score, and bounding-box results. Preserve that structure rather than storing only a binary nudity flag. 

A concrete initial person/object baseline is Torchvision’s `fasterrcnn_mobilenet_v3_large_320_fpn` with explicitly pinned `COCO_V1` weights. Its documented categories include people. Treat it as an integration baseline, not a claim of state-of-the-art detection. ([PyTorch Docs][4])

OCR, segmentation, pose, additional content detectors, and captioning recipes should fit this interface. They need not all be bundled into the default installation.

## 10.3 Run metadata

Each run records:

```text
run_id and processor_id
processor/package version
model identifier and exact revision or weight checksum
configuration and preprocessing
input unit and frozen selection
dataset snapshots
input representation
seed and reproducibility settings
start/end timestamps
per-item status and errors
output schemas and artifact locations
```

Do not use a mutable “latest model” alias as the only provenance.

## 10.4 Per-item states

Keep these distinct:

```text
not_scheduled
queued
running
completed
failed
skipped
not_applicable
```

A completed detector result may contain zero detections. Missing computation is not zero detections.

## 10.5 Derived columns

Raw outputs remain available. Aggregations such as maximum score, detection count, or detected area fraction are named, versioned transformations.

Threshold changes should normally update a derived view without rerunning the detector.

Store the extraction threshold too: the interface must not imply that lowering a display threshold reveals detections the original run never retained.

All computed fields become available to filtering, tables, map overlays, statistics, exports, and approved model context.

## 10.6 Imported research outputs

Support importing predictions, probe scores, SAE feature activations, layer summaries, intervention effects, and other externally computed results.

Validate IDs, units, dimensionality, duplicate rows, and coverage before registration.

Importing a result must not require integrating the training or mechanistic-intervention code into Atlas.

---

# 11. Embeddings and retrieval

## 11.1 Initial recipes

Use explicit, replaceable baseline recipes:

| Recipe                  | Initial implementation                                                  |
| ----------------------- | ----------------------------------------------------------------------- |
| Image/text shared space | `google/siglip2-base-patch16-224`                                       |
| Text-only space         | `sentence-transformers/all-MiniLM-L6-v2`                                |
| External provider       | Compatible embedding endpoint, only for capabilities actually supported |

SigLIP 2’s model card documents image–text retrieval and image feature extraction; the MiniLM model card documents sentence/paragraph embeddings. These are starting integrations, not permanent “best model” selections. Pin tested revisions during implementation. ([Hugging Face][5])

Model recipes must declare pooling, normalization, text instructions, truncation, preprocessing, dimensionality, and distance metric.

Do not silently embed labels, filenames, captions, and raw images together. Each input recipe defines exactly what contributes.

## 11.2 Embedding-space identity

An embedding-space identity includes the model revision and the complete representation recipe.

Equal dimensionality does not establish compatibility.

Keep image-only, text-only, image–question, crop, and imported hidden-state embeddings distinguishable.

Support cross-modal querying only for a compatible encoder/recipe pairing.

## 11.3 Retrieval implementation

Use LanceDB as the initial optional local implementation. Start with exact search and retain an exact validation path after approximate indexes are introduced.

LanceDB supports metadata pre-filtering and an index-bypass path for exhaustive vector search. Its documentation distinguishes approximate neighbours from exact distances on reranked candidates; the UI should preserve that distinction. ([LanceDB][6])

For a query restricted to a subgroup, search **within that subgroup**. Do not retrieve globally and silently post-filter.

For filters on external result tables, resolve the eligible identities first or construct a validated search snapshot. If the backend cannot express the predicate correctly, use an exact fallback or reject the operation.

Do not implement multiple vector backends before the first one works.

## 11.4 Approximate search

Add approximate indexes only after measuring actual workload requirements.

Record index type, parameters, snapshot, and retrieval mode. Evaluate recall against exact search globally and within representative filters.

Portable embedding artifacts remain authoritative; indexes must be rebuildable.

FAISS is a later optional accelerator, not a required dependency.

---

# 12. Maps, clusters, outliers, and comparisons

## 12.1 Map behaviour

A map references one projection artifact, which references one embedding run and a frozen population.

Keep these operations separate:

```text
Change colour
Filter visible records
Select records
Refit projection
```

Changing colour or filtering must not silently refit the map.

Refitting creates a new artifact. Independently fitted maps must not be overlaid as though they share coordinates.

UMAP configuration must retain its seed, implementation version, and relevant execution settings. Its documentation notes reproducibility differences associated with stochastic and multithreaded execution. ([UMAP Documentation][7])

## 12.2 Linked inspection

Clicking a point opens the ordinary sample inspector.

A lasso selection becomes an ordinary selection usable in the grid, table, analyses, and model context.

Display missing annotation values distinctly. Show detector/result coverage separately from the projected population.

## 12.3 Clustering and outliers

Provide a basic clustering recipe and a nearest-neighbour-distance outlier recipe in the original embedding space.

Record their metrics, parameters, and population. “Outlier” always means relative to a named representation and reference set.

Clustering in projection coordinates may be an explicitly labelled experimental option, never the hidden default.

## 12.4 Comparisons

V1 should provide numeric correlations, categorical cross-tabs, and grouped numeric summaries, all linked to selections.

Show sample unit, denominators, missingness, and whether results concern a preview or complete selected population.

Repeated images across multiple questions must not silently be treated as independent image observations.

Do not automatically turn an exploratory association into a causal claim or a fairness score.

---

# 13. Model connections and conversations

## 13.1 Provider abstraction

Implement an initial OpenAI-compatible HTTP provider with configurable endpoint, model, authentication reference, and limits.

Support LM Studio and vLLM through tested configurations rather than application-specific UI branches.

LM Studio documents compatible tool-use endpoints; vLLM documents multimodal input and model-specific tool-calling support. Compatibility must be tested for the actual model–server combination. ([LM Studio][8])

## 13.2 Capability checks

Track text generation, single-image input, multiple-image input, structured output, tool calls, text embeddings, and image embeddings independently.

Use benign capability probes after the user connects a provider. Store the test outcome and configuration.

An untested capability is unknown, not supported.

Do not assume that a VLM can return retrieval embeddings or that an embedding endpoint accepts images.

## 13.3 Selected-sample conversation

The flow is:

> Select records → choose provider → choose context → inspect the outgoing context → ask → save the result.

The context builder can include original questions, selected image representations, source annotations, computed results, OCR, captions, and prior outputs.

Keep filenames and gold labels off by default.

For text-only models, include an explicit image-unavailable notice and only the permitted textual evidence. Do not claim the model saw an image.

For vision models, send actual supported image content—not an inaccessible local path.

## 13.4 Exploration versus evaluation

Provide two visible modes.

**Exploration:** users can include annotations and other model outputs to help interpret examples.

**Evaluation:** only task-approved inputs are sent. Gold labels, answer-bearing filenames, and auxiliary predictions remain excluded unless explicitly part of the saved protocol.

Context permissions are enforced in code. They must not depend on remembering to phrase the prompt correctly.

## 13.5 Request provenance

Store provider/model identifiers, input IDs, actual outgoing context policy, prompts, generation settings, image representation, response, errors, and usage data where available.

Expose an “Input sent” inspector. Distinguish known client preprocessing from unknown provider-side processing.

Do not promise bitwise reproducibility for remote model outputs.

Batch mode must specify whether records are evaluated independently or jointly. A conversation about eight images is not eight independent evaluations.

---

# 14. Bounded tool-assisted exploration and RAG

## 14.1 Initial tools

```text
describe_dataset(...)
describe_fields(...)
search_records(...)
get_records(...)
aggregate(...)
inspect_images(...)
get_run_results(...)
```

These tools call the same query and media services as the frontend.

Tool results include IDs, source/run references, scope, coverage, and truncation information.

## 14.2 Execution limits

Use configurable defaults, initially:

```text
Maximum model iterations: 8
Maximum tool calls: 16
Maximum total returned rows: 1,000
Maximum transmitted images: 8, or the provider's lower supported limit
```

These are application defaults, not claims about model limits.

Display and enforce token, time, and external-spending limits where applicable. Do not automatically raise limits in response to a model’s request.

Tools are read-only. The model may propose a saved selection or computation, but starting a new job, downloading data, or exporting information requires user action.

## 14.3 RAG behaviour

Retrieve actual records or catalogue evidence and return stable references.

Counts and summaries over populations must come from deterministic query tools. The model must not estimate dataset prevalence from a retrieved handful of examples.

Validate that cited sample IDs exist and were available in the interaction.

Keep “observed in these retrieved examples” separate from “computed across this population.”

## 14.4 Untrusted content

Images, captions, annotations, papers, and model responses are untrusted content.

Do not provide arbitrary shell, Python execution, filesystem reads, unrestricted SQL, or arbitrary URL-fetch tools.

Enforce scope, fields, source roots, approved network destinations, and budgets outside the model.

The corpus itself includes work on image-borne instructions, so adversarial content is an expected input condition rather than an exceptional one. 

---

# 15. Frontend specification: keep it small

## 15.1 Information architecture

Use **two primary screens**:

1. Catalogue.
2. Reusable dataset/selection browser.

Settings, jobs, analysis configuration, and model conversations are drawers or dialogs.

Use a hash-based routing scheme for the initial static deployment, avoiding server-side route-rewrite requirements.

Do not add a separate dashboard, paper graph, chatbot landing page, or processor-specific application.

## 15.2 Catalogue

The catalogue opens immediately. No oversized hero section.

Show one search field and a compact list/table containing:

```text
Dataset name
One-line description
Modalities / task
Available labels
Access / preview state
```

Counts must identify their unit and source.

A small filter control exposes modality, task, annotations, accessibility, and mentioned-by-paper.

Clicking a dataset opens examples directly. Its longer description, provenance, and source links belong in an “About” section.

## 15.3 Browsing workspace

```text
┌─────────────────────────────────────────────────────────────────┐
│ Atlas   Dataset / saved selection       Public/Workbench   ⚙ Jobs│
├─────────────────────────────────────────────────────────────────┤
│ Search records…  [Filters]  [Sample 100]     Grid | Table | Map    │
│ Scope: preview · 100 assets · release … · 37 match filters        │
├───────────────────────────────────────────┬─────────────────────┤
│                                           │ Sample inspector    │
│                                           │                     │
│       Grid, table, or embedding map        │ Original / preview  │
│                                           │ Text / question      │
│                                           │ Source annotations  │
│                                           │ Computed results    │
│                                           │ Related examples    │
│                                           │ Notes / provenance  │
├───────────────────────────────────────────┴─────────────────────┤
│ 12 selected     [Save] [Analyze] [Ask model] [Compare] [Export]    │
└─────────────────────────────────────────────────────────────────┘
```

The inspector is closed until needed. The selection toolbar appears only when something is selected.

On smaller screens, the inspector becomes a drawer.

## 15.4 Grid

Use uncluttered cards with an image or text preview and a few user-selected labels.

Show multi-image and conversation indicators. Avoid printing every metadata field on every card.

Provide size adjustment and keyboard navigation. Load visible media lazily and virtualize large collections.

A broken image shows a useful placeholder and reason, not a disappearing record.

## 15.5 Table

Use the same population and selection as the grid.

Allow column selection, typed sorting, and inspection of original versus computed fields.

Do not force users to learn raw field identifiers. Technical names remain available in field details.

## 15.6 Map

Keep the controls to:

```text
Projection
Colour by
Filter
Selection
```

Advanced projection settings belong in the analysis drawer.

When coordinates are unavailable, explain whether the user can load a published artifact or compute one in workbench mode. Do not show an empty decorative chart.

## 15.7 Inspector

The inspector displays media/text first, then expandable sections for source annotations, computed results, relations, notes, and raw data.

Box overlays must identify their run and threshold.

Original/preview/model-input labels must be obvious.

Include “Copy ID” and “Show input sent” where relevant.

## 15.8 Analysis drawer

Use one consistent form:

```text
Analysis type
Input selection and unit
Model/recipe
Important parameters
Output coverage and resource estimate
Run
```

Hide advanced configuration initially.

After a run completes, offer its outputs through the existing field and projection selectors. Do not create a new bespoke page.

## 15.9 Model drawer

Show provider, exploration/evaluation mode, context choices, the message box, and responses.

An expandable panel shows transmitted records and fields.

Tool activity is inspectable but collapsed by default. Returned sample references open the normal inspector.

## 15.10 Visual and accessibility rules

Use a neutral visual style, one restrained accent, readable typography, and clear spacing. Prefer familiar controls to novel interactions.

Support keyboard operation, visible focus, semantic labels, text alternatives, and reduced-motion preferences. Do not encode important states only by colour.

Persist ordinary view preferences locally. Never place credentials in URLs or browser-persisted public configuration.

**Frontend success criterion:** a new user can open a dataset, inspect examples, filter them, and save a selection without reading documentation.

---

# 16. Jobs and resource management

Use a coordinator with durable job records and subprocess workers for expensive work.

Jobs reference frozen selections and immutable configurations. The coordinator commits completed output shards and registers them only after validation.

Support progress, cancellation, retries, per-item failure reporting, and restart recovery.

Idempotency keys should include processor, model revision, configuration, input representation, and input identity. Do not recompute successful items unnecessarily.

Use resource classes such as CPU, GPU, network, and external API. Start with one GPU-heavy job at a time by default.

Atlas should connect to existing model servers rather than becoming a general-purpose model-serving manager.

Partial results may be browsed only with explicit coverage and status. They must not be published as completed runs.

---

# 17. Security, privacy, and publication

## 17.1 Local security

Bind to loopback by default. Validate origin/host information and protect state-changing requests.

Filesystem access is restricted to configured roots. Resolve paths safely and reject traversal or symlink escapes.

Allow only configured provider endpoints and approved source locations. Do not allow dataset text or model tool calls to choose arbitrary network destinations.

For remote media, validate redirects and destination policies. vLLM’s multimodal documentation explicitly discusses domain restrictions and redirect-related SSRF risks; the Atlas fetch layer needs equivalent care. ([vLLM][9])

Render dataset text as untrusted content. Sanitize HTML and avoid executing scripts embedded in imported files.

## 17.2 Publication allowlist

Public export is an explicit operation over an allowlist.

Exclude credentials, local paths, original PDFs, private notes, unapproved images, unreviewed annotation exports, and externally restricted results.

Track rights separately for code, annotations, images, and derived artifacts. Unknown publication status defaults to metadata-only.

Do not assume a code repository’s licence grants permission to redistribute its underlying images.

## 17.3 Sensitive media

Local users can choose a safe-view display mode. It creates display derivatives and does not alter originals or analysis inputs.

Public builds should exclude explicit sensitive imagery by default. A detector is not the sole publication gate.

GitHub Pages also has content restrictions, independently of its storage limits; deployment approval must consider the hosting service’s terms as well as dataset permissions. ([GitHub Docs][10])

## 17.4 External providers

Require an explicit choice of provider and approved data scope before transmission.

Show what will leave the machine. Restricted datasets should be local-only unless an appropriate explicit policy permits otherwise.

Redact secrets from logs and exports.

## 17.5 Imported artifacts

Use non-executable exchange formats. Do not deserialize untrusted pickle/joblib objects or run arbitrary dataset loaders automatically.

Imports must validate schemas, checksums, identities, and size limits before registration.

---

# 18. API and command-line contracts

## 18.1 API surface

Implement a versioned API around a small number of resources:

| Resource          | Operations                                    |
| ----------------- | --------------------------------------------- |
| Capabilities      | Describe deployment and available operations  |
| Datasets/releases | List, search, describe                        |
| Fields            | Describe types, provenance, and query support |
| Queries           | Search, filter, sort, aggregate, paginate     |
| Records/media     | Retrieve approved records and representations |
| Selections        | Create, read, export, import                  |
| Processors/runs   | Describe, estimate, start, inspect, cancel    |
| Artifacts         | Discover, validate, load, export              |
| Providers         | Configure locally, probe, list capabilities   |
| Conversations     | Submit, stream, save, inspect context         |
| Publication       | Validate and build approved static packs      |

Use bounded requests, structured errors, and cancellation. SSE or polling is sufficient for job progress and streamed responses; do not introduce unnecessary transport complexity.

## 18.2 Desired CLI

These are commands the agents should implement, not an assertion that a package already exists.

```bash
PAPERS="/home/bitwise/Documents/Media_Bias_Group/MechinterpAdversarialAttacks/Flight Package"

atlas corpus scan \
  --papers-dir "$PAPERS" \
  --output work/corpus

atlas corpus extract \
  --manifest work/corpus/corpus_manifest.json

atlas corpus resolve \
  --mentions work/corpus/dataset_mentions.jsonl \
  --registry registry

atlas datasets validate --all

atlas datasets prepare \
  --dataset DATASET_ID \
  --preview-size 100 \
  --dry-run

atlas serve

atlas analyze \
  --selection SELECTION_ID \
  --processor PROCESSOR_ID \
  --config CONFIG_FILE

atlas export selection SELECTION_ID --output OUTPUT_DIRECTORY

atlas publish validate --profile public
atlas publish build --profile public

atlas doctor
```

`atlas doctor` checks installation, storage permissions, configured roots, optional dependencies, and selected provider connections without triggering bulk downloads.

## 18.3 Installation

Keep optional extras separate:

```text
base
vision
embeddings
projection
remote-storage
development
```

Basic browsing must install without CUDA or model-serving frameworks.

Ship the built frontend in the Python distribution so ordinary workbench users do not need Node.js. Developers can run the frontend separately.

Pin tested dependency versions and model revisions. Do not specify guessed “latest” versions in the specification.

---

# 19. Repository layout

```text
dataset-atlas/
  SPEC.md
  AGENTS.md
  README.md

  apps/
    web/

  src/
    dataset_atlas/
      api/
      corpus/
      registry/
      adapters/
      storage/
      queries/
      processors/
      providers/
      jobs/
      exports/
      cli/

  schemas/
  registry/
    datasets/
    papers/
    models/
    processors/

  tests/
    fixtures/
    unit/
    contracts/
    integration/
    e2e/

  docs/
    adding-datasets.md
    adding-processors.md
    model-connections.md
    remote-workbench.md
    publication.md

  reports/
  examples/
  .github/workflows/

  work/                  # ignored
  local-config/          # ignored
```

Do not commit source datasets, model weights, downloaded papers, caches, secrets, or generated full-text extraction.

Keep the exact user-specific corpus path in local configuration and this handoff. Generic contributor documentation should use a configurable placeholder.

---

# 20. Implementation plan and agent ownership

## Milestone 0 — Repository and corpus audit

**Owner:** lead agent plus corpus agent.

Inspect the existing repository before scaffolding. Preserve unrelated work. Establish development commands, dependency policy, and workspace locations.

Inventory the complete paper directory and produce the first extraction-quality report.

**Gate:** every input file is accounted for; failures and duplicates are visible. No invented dataset total.

---

## Milestone 1 — Shared contracts and representative fixtures

**Owner:** lead/backend agent.

Implement schemas for releases, assets, examples, annotations, relations, selections, runs, and artifacts. Establish query semantics and static/workbench provider interfaces.

Build safe fixtures covering an annotation overlay, repeated images with multiple questions, multi-image/conversation examples, pairs, and text-only data. Use actual inventory examples where possible; synthetic fixtures are for tests only.

**Gate:** identity, unit, annotation, and query contracts pass tests. A fixture survives export/import without losing structure.

---

## Milestone 2 — First real end-to-end browser

**Owners:** adapter agent and frontend agent.

Implement catalogue and browsing screens, pack reading, a minimal local service, and a few structurally different real datasets.

The first demonstration must show actual media/text, annotations, filtering, sampling, and a saved selection.

**Gate:** one static build and one workbench build browse the same pinned preview correctly.

Do not postpone this milestone until every dataset adapter is finished.

---

## Milestone 3 — Complete corpus extraction and coverage expansion

**Owners:** corpus agent and parallel adapter agents.

Finish full-paper extraction, candidate reconciliation, source resolution, and the registry.

Assign adapters by source family or dataset, with one owner for each integration. Continue until every resolved dataset has real browsing support or a documented external blocker.

**Gate:** the coverage report accounts for every paper, mention, resolved dataset, preview, and remaining limitation. Implementation gaps remain explicitly incomplete.

---

## Milestone 4 — Storage and resumable jobs

**Owner:** backend/storage agent.

Implement approved source roots, mounted-path workflows, remote fetching, cache budgets, preparation plans, and resumable processing.

Test interrupted transfers, changed sources, inaccessible mounts, cancelled jobs, and recovery.

**Gate:** a selected population can be prepared from remote storage without an implicit full-dataset download; interrupted work resumes correctly.

---

## Milestone 5 — Detectors, embeddings, and maps

**Owner:** analysis agent, with frontend integration.

Implement NudeNet, the initial person/object detector, embedding recipes, exact filtered retrieval, PCA/UMAP, basic clustering/outliers, and imported result columns.

Connect all results to the existing table, filters, inspector, and map.

**Gate:** run a real selection through detection and embeddings, colour its projection by a detector output, inspect outliers, and export/reload the results.

---

## Milestone 6 — Model-assisted inspection

**Owner:** provider/tool agent.

Implement endpoint configuration, capability probes, selected-sample questions, exploration/evaluation context policies, and saved responses.

Then add bounded read-only tools and grounded summaries.

**Gate:** demonstrate both image-capable and text-only behaviour, enforce hidden-label exclusion in evaluation mode, and reject unsafe tool requests.

Test LM Studio and vLLM independently where available. Missing access to a server is a reported integration-test limitation, not a passed test.

---

## Milestone 7 — Publication, packaging, and release

**Owner:** integration/release agent, reviewed independently.

Package the Python workbench, build the static site, implement publication checks, complete documentation, and exercise the full application.

Vite documents a GitHub Pages deployment path; use a tested Actions workflow and validate repository-base-path behaviour. ([vitejs][11])

**Gate:** installation from a clean environment works, the public site contains only approved artifacts, and the full acceptance matrix has evidence.

---

# 21. Parallel-agent coordination

The lead agent owns schemas, shared API contracts, and architectural decisions.

Adapter agents may add manifests, mappings, fixtures, and source-specific implementation. They must not independently redesign record identities or annotation semantics.

The frontend agent consumes shared contracts and realistic fixtures. It must not invent simplified backend data shapes.

The analysis agent owns processor outputs, run provenance, and embedding-space definitions. The provider agent owns model contexts and bounded tools.

Each agent’s handoff should contain changed files, tests run, real datasets exercised, known limitations, and remaining work.

Use small vertical changes rather than long-lived branches rewriting the whole application.

Any change to a shared contract requires an accompanying fixture update and compatibility decision.

---

# 22. Acceptance tests

## 22.1 Required test matrix

| Area             | Acceptance condition                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| Corpus           | Every paper has a processing outcome; accepted mentions have evidence.                           |
| Identity         | IDs survive sorting, pagination, remounting, and export/import.                                  |
| Repeated images  | Multiple questions reference one asset without duplicating image-only computation.               |
| Overlays         | Join failures are counted and visible; no silent record loss.                                    |
| Query parity     | Static and workbench providers return the same IDs for supported queries over the same snapshot. |
| Scope            | Preview-only results never appear as complete-release statistics.                                |
| Sampling         | Saved IDs reproduce the selection; unit and method remain visible.                               |
| Retrieval        | Filtered search respects its population; exact results validate approximate indexes.             |
| Detector results | Missing, failed, and zero-detection cases remain distinct.                                       |
| Geometry         | Overlays align after orientation, resizing, and letterboxing transformations.                    |
| Projections      | Recolouring/filtering does not refit; artifact provenance survives export.                       |
| Model context    | Text-only models receive no false image-access claim; evaluation excludes disallowed fields.     |
| Tools            | Bounds, schemas, roots, and network restrictions are enforced outside the model.                 |
| Jobs             | Cancellation and restart do not duplicate successful work or register corrupt artifacts.         |
| Publication      | Secrets, absolute paths, PDFs, and unapproved media are rejected.                                |
| Installation     | Browser-only use does not require GPU/model dependencies.                                        |

## 22.2 Adversarial and failure fixtures

Include examples with broken URLs, expired media access, missing labels, contradictory annotations, malformed records, duplicate source IDs, unsafe paths, hostile embedded text, unsupported provider capabilities, and partial processor outputs.

The test suite must verify honest failure behaviour, not only successful demos.

## 22.3 Performance targets

Treat these as proposed acceptance targets, not existing measurements:

| Workload              | Initial target                                                                       |
| --------------------- | ------------------------------------------------------------------------------------ |
| Catalogue search      | Responsive without network requests after its index loads                            |
| Preview filtering     | Under 200 ms for a 10,000-record test index on the documented reference machine      |
| Grid/table            | Virtualized; no rendering the complete collection into the DOM                       |
| Map                   | Interactive selection/pan on 10,000 plotted points on the reference browser          |
| Complete-data queries | Bounded memory, cancellation, and measured timings on a larger fixture               |
| Media browsing        | Fetch visible media and limited prefetch only                                        |
| Static publication    | Stay below a conservative internal size budget, with CI checking the actual artifact |

Record hardware, dataset shape, cold/warm cache conditions, and browser versions. Larger workloads should degrade through explicit sampling or background work, not frozen interfaces or silently incomplete results.

---

# 23. Required release deliverables

The implementation is not finished with a polished homepage.

The release must include the working static browser, installable workbench, corpus and dataset coverage reports, tested adapters, analysis plugins, provider integration, publication tooling, and contributor documentation.

Also include:

```text
A real demonstration selection
Its detector and embedding runs
A projection with linked inspection
A saved model interaction with context provenance
An exported analysis pack
An independently reviewed limitations report
```

The public demo may use a smaller approved subset. The complete local catalogue must still expose the entire resolved inventory and its coverage states.

Do not mark unavailable model servers, inaccessible datasets, or unexecuted tests as validated.

---

# 24. Definition of done

**Dataset Atlas v1 is done when the researcher can choose any dataset in the resolved paper-derived inventory, understand its access and coverage state, inspect real examples wherever access permits, apply reliable filters, save a reproducible selection, attach computed evidence, and inspect that evidence through the same simple interface.**

For an accessible image dataset, the demonstration should be:

> Open it → inspect 100 examples → filter on source labels → run a person detector and NudeNet → compute embeddings → colour a UMAP by detector results → inspect an unusual selection → ask a connected model about it → export the selection and provenance.

For restricted or unavailable data, the application must explain the precise limitation and authorized path forward rather than displaying fabricated samples or a misleading “supported” badge.

**The two priorities that should govern implementation are real dataset coverage and correct sample-level evidence. Everything else—including additional vector backends, custom Rust, and elaborate dashboards—comes after those foundations.**

[1]: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages?utm_source=chatgpt.com "What is GitHub Pages? - GitHub Docs"
[2]: https://duckdb.org/docs/current/connect/concurrency?utm_source=chatgpt.com "Concurrency – DuckDB"
[3]: https://filesystem-spec.readthedocs.io/en/latest/features.html "Features of fsspec — fsspec 2026.9.0.post2+gd20ad256b.d20260921 documentation"
[4]: https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.fasterrcnn_mobilenet_v3_large_320_fpn.html "fasterrcnn_mobilenet_v3_large_320_fpn — Torchvision 0.29 documentation"
[5]: https://huggingface.co/google/siglip2-base-patch16-224 "google/siglip2-base-patch16-224 · Hugging Face"
[6]: https://docs.lancedb.com/search/filtering "Metadata Filtering in LanceDB - LanceDB"
[7]: https://umap-learn.readthedocs.io/en/latest/reproducibility.html "UMAP Reproducibility — umap 0.5.8 documentation"
[8]: https://lmstudio.ai/docs/developer/openai-compat/tools?utm_source=chatgpt.com "Tool Use | LM Studio"
[9]: https://docs.vllm.ai/en/latest/features/multimodal_inputs/?utm_source=chatgpt.com "Multimodal Inputs - vLLM"
[10]: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits?utm_source=chatgpt.com "GitHub Pages limits - GitHub Docs"
[11]: https://vite.dev/guide/static-deploy.html "Deploying a Static Site | Vite"
