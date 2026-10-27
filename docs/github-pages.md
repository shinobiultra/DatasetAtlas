# GitHub Pages

The static site uses the same interface as the workbench. It runs without Python,
model services or a connection to a privileged localhost API. The repository's
workflow builds it with the repository base path and deploys only through an
explicit manual deployment action.

The site includes the current catalogue and acquisition guides, metadata-only field
schemas, and the exact approved previews from CLEVR, EuroSAT and PAIRS. A preview
is labelled with its population and sampling provenance. Local maintainer coverage
does not imply that a visitor has those data. Optional publisher-hosted previews
request data from that publisher and remain distinct from bundled approved packs.

## Build locally

```bash
uv sync --frozen --inexact
uv run --no-sync atlas publish validate --profile public
uv run --no-sync atlas publish build --profile public
npm --prefix apps/web ci
npm --prefix apps/web run build
```

The public builder validates the exact publication profile, rights categories and
media IDs before writing `apps/web/public/data/`. It excludes local paths, private
notes, adapter configuration, credentials and unapproved media. The built site must
fit the 200 MB publication budget. See [publication](publication.md).

`examples/approved-packs/` contains the approved previews.
`examples/public-schema/` contains field schemas and the current public coverage
snapshot. Regenerate the schema snapshot with `atlas publish schemas` after a
catalogue or preparation change. These inputs let CI build without the maintainer's
data directory. They do not publish record values from other datasets.

## Deploy

Open the repository's **Validate and publish Dataset Atlas** GitHub Actions workflow, run it
manually and select its deployment input. Repository Pages permissions and settings
must allow that action. Building a local site or portable ZIP does not deploy it.
Do not extend publication approvals merely to make a build pass: approve the exact
intended data and retain its rights evidence first.

For colleagues who do not need a hosted site, [the portable sample ZIP](sharing.md)
provides the approved browser using only Python's standard library. The
[current release evidence](../reports/release_evidence.md) records software checks;
[source qualifications](../reports/limitations.md) retain the limits of public scope.
