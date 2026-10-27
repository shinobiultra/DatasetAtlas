# Dataset Atlas 1.0 release scope

Dataset Atlas provides a source-backed catalogue, a portable approved sample browser
and an optional local research workbench. The release supports the native source
populations declared in the registry, including linked examples, annotations and
media variants. It preserves original source material and frozen snapshot identity.

The current implementation and verification state is recorded in
[final-status.json](reports/final-status.json). The [coverage matrix](reports/dataset_coverage.csv)
lists every current catalogue entry exactly once, with its active snapshot, bounded
preview, declared source total and actual local index scope. [Pinned sources](reports/catalogue-sources.json)
record release identities and recipe checksums. These generated files own the counts.

Release verification covers Python and frontend behavior, browser journeys, native
indices and preview media, catalogue and publication validation, analysis, the
portable bundle, distribution archives and clean installation. [Release evidence](reports/release_evidence.md)
binds the completed checks to both the current source tree and active catalogue.
`scripts/report_release.py` emits a draft until supplied with a matching completed
verification proof; a stale or partial proof cannot mark `full_v1_complete` true.

The [SPEC](SPEC.md) and [acceptance matrix](docs/acceptance-matrix.json) define the
software acceptance contract. The [source and rights qualifications](reports/limitations.md)
describe historical paper-use uncertainty, large-source sampling and media rights.
They remain visible even when the software release checks pass. Automated checks
and a working adapter do not amount to human or scientific acceptance.

Future catalogue additions must preserve native units and relationships, specify
bounded preparation and source pins, and have a working adapter. New public media
requires an explicit publication decision for the exact intended files. See
[adding datasets](docs/adding-datasets.md) and [publication](docs/publication.md).
