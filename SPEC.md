# Dataset Atlas 1.0 specification

## Release scope

Dataset Atlas is a local research dataset browser and an approved public sample
browser. Its core workflow is:

Find a dataset → inspect native examples and annotations → filter or sample → save
an immutable selection → compute or attach evidence → compare → export provenance.

The researcher's 2026-10-27 finalization decision defines the supported catalogue:
retain working native sources, remove inaccessible/unadapted entries and cards that
only duplicate, filter or concatenate retained populations. A published native
annotation release, modified stimulus population or author-generated reconstruction
is distinct from a mere view and must retain its precise source qualification.
Historical survey inventories and retirement ledgers are not part of the product.
They remain in local recovery storage alongside the read-only research originals.

One canonical card may provide several explicitly versioned releases or source
partitions. A local index of one publisher shard is never described as an index of
the publisher's entire corpus. Native mixed collections expose the unit kinds and
counts rather than labelling every source item an image or question. Missing media
and author-defined runtime pairings remain explicit; no pairing is invented.

Software completion means the retained catalogue and the functions in this contract
work and have current evidence. It does not confer scientific validity, human
review of a paper's historical subset, acceptance of publisher terms, or new data
redistribution rights. Declared source revisions must be resolved truthfully.
Historical paper use and mirror/reconstruction qualifications are descriptive
metadata, not unimplemented software hidden behind an external-blocker label.

## Data and identity

`docs/contracts.md` and `src/dataset_atlas/models.py` define the shared records.
Keep source fields, native order, IDs, precision, annotation semantics, grouping,
multiple references and assets. Do not substitute synthetic fixtures for real data.
Tests may use clearly synthetic records. Corpus originals are read-only.

Every retained card has a tested adapter, a pinned source or retained original,
a reproducible real preview of 100 records (or all if fewer), and a tested path
beyond that preview. Native structured rows are useful examples even when media
is unavailable. Very large native sources may use bounded, seeded source sampling
instead of a local global index; their preview and source counts remain distinct.

Keep dataset identity separate from byte deduplication. A snapshot binds its exact
population and schema. Selections save IDs, unit, snapshot and query/result bindings.
Never rebind a frozen record, result or model context to a newer active version.
Removed cards stay out of current catalogue routing; exact archived snapshot lookup
may recover retained records without resurrecting a card or guessing an alias.

## Storage and preparation

Separate originals, immutable prepared versions, frozen selections/results, and
reproducible caches. Preserve full-quality preview originals. Compression or display
representations must be labelled and cannot silently replace original model inputs.

Default workspace target: 100 GB; ceiling: 150 GB. Measure unique allocated blocks
and account for hard links separately from logical bytes. Dataset preparation shows
its source, population, download/output reservation and uncertainty before execution.
Unknown size never authorizes an unbounded transfer. No automatic model downloads,
term acceptance, paid execution or cluster jobs.

At most two preparation writers, one per dataset, hold normal writer/admission
leases. Cancellation and retries preserve verified reusable work and failure
receipts. A candidate may complete without activation; that intent survives retry
and restart. Activation is atomic after validation and retains earlier snapshots.

Native resampling freezes the explicit seed, pinned files, grouping and row policy.
The user reviews budgets before starting another sample. Native partial-media
collections preserve source paths with unavailable URIs, not fabricated assets.
Any pinned retained-media mapping checks exact source group/path, size and SHA-256.

Lossless deduplication verifies matching immutable bytes and ownership/permissions,
excludes active writers, uses anchored no-follow directories and retains rollback
through postchecks. Cleanup is manifest-bound and recovery-verified. Keep originals,
frozen dependencies, unique evidence, model weights and unrelated workloads.

## Browsing and evidence

Use the same React interface for static publication and the local workbench.
Static mode does not probe a local API. The workbench is explicit and loopback-only.
Source guides describe actual access and current runtime availability.

Provide catalogue search, typed Boolean filters, stable sorting, seeded sampling,
grid/table, source inspection, focused inspection, comparisons and saved selections.
Use OR within one facet's selected values and AND across fields; explicit advanced
constraints retain their own semantics. Debounce/cancel obsolete browser requests;
query changes invalidate every prior paging continuation and loading state.

Render visible records and limited prefetch only. Map membership follows the complete
current filter/sample over the projection's own IDs, rather than only loaded pages.
Use one mask for rendering, picking, lasso, legends and counts. Pending or invalid
membership selects nothing. Filtering never refits a projection. Inspecting a point
outside loaded pages retrieves its exact snapshot. A ceiling is explicit.

Counts state their unit, population, denominator and missingness. Aggregates concern
the filtered population and explicitly ignore a browsing sample. A preview never
becomes a population-prevalence estimate. Detector missing, failed, zero and partial
outcomes remain distinct. Coordinate transforms and extraction/display thresholds
remain inspectable; originals are available separately from display derivatives.

## Optional analysis and models

Support local detector runs, image/text embeddings, exact retrieval, PCA/UMAP,
clustering, outliers, scalar/text research imports and model-server tasks. Their
outputs join by immutable snapshot, unit and ID. Imported vectors are omitted from
ordinary browse payloads but remain intact at the full artifact endpoint.

Exact similarity is chunked and deterministic with bounded scratch/cache memory.
Analysis uses explicit budgets and durable per-item outcomes. Reuse verified
completed work; cancelled/failed items do not masquerade as successful computation.
GPU acceleration is optional. Respect other workloads and record measured scope.

Controls follow advertised capabilities. A base-only installation shows clear
setup guidance and the actual missing dependency/model reason; unavailable options
cannot start jobs. Browsing requires no GPU, model, account or heavy optional extras.

A configured model receives only explicitly selected, snapshot-bound context after
its exact approval. Record model, revision when known, settings, selected fields,
representation and context digest. Enforce local/external destination policy outside
the model. Bounded read-only tools cannot expand approved records, paths or budgets.
Treat dataset text as untrusted content. Never send native data to an external model
as part of agent development or verification. Generated benign provider probes and
synthetic tests remain distinct from real model demonstrations.

## Publication and distribution

Publication is an explicit allowlist of records, annotations, derived artifacts and
media, with source rights and sensitive-media review. Keep software and dataset
licences separate. Exclude credentials, local paths, original papers, private notes,
restricted data and unapproved media. Source facts do not self-approve rights.

Build approved public data from checked-in inputs before compiling the frontend.
Use relative asset paths and verify actual artifact size. Provide:

- GitHub source with one-command `./start.sh` sample startup;
- a compact checksummed sample ZIP with a standard-library Python launcher;
- an installable wheel with interface and supported catalogue;
- a source archive, contributor/setup/storage guides and current coverage evidence.

The sample launcher verifies every declared file, rejects unknown/link/escaping
paths and invalid Host headers, binds loopback and uses a stable default origin so
saved selections persist. An explicit temporary-port option is permitted.

No private machine audit is pushed to the public repository. Retired code, reports,
Git refs and unique failure evidence remain recoverable locally. Public Git history
is not rewritten to erase prior work.

## Acceptance and release evidence

Run meaningful synthetic regressions, frontend tests and browser checks. Run current
native preview/complete-index smoke checks for every retained prepared population.
Use fresh base-only installs of the final wheel and an extracted sample ZIP; the
source checkout test starts without ignored dependency or data directories.
Test supported current Python, and record exact package hashes and source parity.

The real demonstration includes a saved native selection, detector and embedding
runs, a linked projection, model-context provenance and an exported analysis pack.
Optional services/dependencies are reported accurately. Reuse historical model
outputs only with their exact input/snapshot provenance; never call an unavailable
server or unexecuted path freshly validated. Independent review is engineering
evidence and not human or scientific acceptance.

Performance evidence states hardware, shape, cold/warm conditions and what was
measured. Targets: responsive local catalogue search; under 200 ms filtering for a
10,000-record synthetic preview; virtualized grid/table; interactive 10,000-point
maps; bounded-memory complete queries, cancellation and original media on demand.
Wide scientific records or larger populations have explicit budgets/degradation.

Release 1.0 is complete when the retained inventory, coherent simple workflow,
optional capability/setup paths, publication/build/install artifacts, current
verification and recovery-safe cleanup satisfy this contract. Current data rights,
source availability and paper-use qualifications remain visible facts.

The acceptance matrix in `docs/acceptance-matrix.json` maps these sixteen areas to
current tests and release evidence: Corpus (supported-source provenance), Identity,
Repeated images, Overlays, Query parity, Scope, Sampling, Retrieval, Detector results,
Geometry, Projections, Model context, Tools, Jobs, Publication and Installation.
Synthetic regressions and native runtime receipts retain their distinct meanings.
