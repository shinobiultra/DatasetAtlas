# Analysis processors

Processors consume frozen selections and produce registered artifacts. The
coordinator owns snapshots, job status and registration; a processor never changes
source originals or registers an artifact independently. Read [contracts](contracts.md)
before changing shared shapes.

The trusted built-in allowlist lives in `processors/core.py`, with descriptors in
`registry/processors/builtins.yaml`. Dataset packs cannot supply executable code.
Keep heavy libraries behind optional imports. A new processor declares its input
unit, dependencies, device needs, deterministic configuration, output schema and
bounded resource estimate. Test missing inputs, partial failure, cancellation and
snapshot identity with meaningful fixtures.

## Inputs and outcomes

Every selected record is accounted for as completed, failed, skipped or not
applicable. A completed detector result with no boxes differs from an unavailable
asset or failed decode. Shared original assets can be processed once while each
example retains its own links. Source labels and predictions stay in separate
namespaces.

`quality.basic` reads rooted local image assets, verifies declared hashes and
reports dimensions, file/pixel hashes and basic image metrics. Detectors require
explicitly configured local weights and full hashes. Their boxes use EXIF-oriented
original image pixels, and extraction thresholds remain part of provenance.
Display thresholds cannot restore detections discarded during extraction.

MiniLM and SigLIP 2 use pinned local snapshots and local-only loaders. Representations
are explicit: text, question or image as supported by that processor. Labels,
filenames and captions are never silently mixed into an embedding. Space identity
includes the model recipe, weight digest, representation and normalization; equal
dimensions alone do not establish compatibility.

## Arrays and downstream analysis

Large runs use a `BulkResult`: ordered identities, checksummed arrays, optional text
columns and a coverage summary. The coordinator commits shards atomically and
registers one artifact. Small per-record outputs remain available through the same
result-item interface. See [analysis at scale](analysis-at-scale.md).

Projection, clustering and outlier processors read the selected embedding space by
reference. They record source run, input digest, fitted population, parameters and
backend. Refit creates a new fit identity; map filtering and recolouring do not fit
again. Missing vectors remain explicitly unprocessed.

Exact retrieval applies source eligibility before scoring and uses bounded chunks.
Query encoding must reproduce the compatible local model/representation recipe.
Imported vectors without an encoder can be searched by an example record.

`compare.fields` records denominators, missingness, unit and population scope.
`import.research` requires explicit stable IDs, source reference and rights; it
rejects duplicates, mixed units, malformed geometry and invalid numeric values.
Importing results does not confer independent scientific or human review.

`vlm.*`, `embed.api` and `score.vqa_accuracy` demonstrate columnar text/scalar output.
Their network client is separate from the processor; each requested record has an
outcome. See [model-server runs](model-server-runs.md). Current integration evidence
is linked from [release evidence](../reports/release_evidence.md); a stored model
artifact retains its exact historical input/snapshot provenance.
