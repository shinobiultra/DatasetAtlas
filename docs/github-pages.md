# GitHub Pages edition

The Pages site is the same interface as the local workbench, built in static mode from the repository alone. It holds none of the roughly 100 GB the maintainers' workspace needs. This page says what the site is for, what it contains, how it stays true, and how to deploy it. **Nothing has been deployed**: publishing is a manual step that needs your decision (see [Deploy](#deploy)).

## What a visitor gets

| Tier | Content | Who sees it | Source |
| --- | --- | --- | --- |
| 1. Catalogue | Every real dataset (284 on 2026-10-09): description, modalities, tasks, access and coverage state, rights, relationships, source link, filters and search | everyone | `registry/datasets/*.yaml` plus the merged coverage snapshot |
| 2. Guide | For each dataset: how to obtain it (computed, see below), the corpus papers that name it, and the field schema of the maintainers' preview (names, types, declared categories; **no record values**) | everyone | `guide.json` |
| 3. Approved examples | Real, browsable previews with media, filters, selections, maps and results | only datasets whose publication was reviewed: CLEVR, EuroSAT, PAIRS | `registry/publication.json`, `examples/approved-packs/` |

Everything else is deliberately absent: record text and media of datasets whose rights are unreviewed, adapter configuration, evidence excerpts, review notes, local paths, source PDFs, model weights, embeddings and every prepared version in `work/`.

The guide answers the question a visitor actually has about a dataset they cannot browse here. The state is computed from the registry and recipes, never typed by hand:

| State | Computed from | What the page says |
| --- | --- | --- |
| Examples on this site | publication approved | open the Samples tab |
| Fetch with Dataset Atlas | a recipe exists | the two commands: plan (`atlas previews fetch --dataset ID`) then fetch (`... --execute`) |
| Accept terms, then fetch | a recipe exists and the source is gated or the recipe needs a local credential | same commands, plus the link to the [authorization guide](dataset-authorization.md); Atlas never accepts terms for anyone |
| Maintainer preview, no public recipe | a preview exists but no recipe is tracked | a colleague cannot rebuild it from the source yet |
| Gated at the source / Request from the authors | gated or request-required, no recipe | where to ask |
| Public source, no Atlas recipe yet | public, no recipe | stated as a gap in Dataset Atlas, not a restriction |
| Not released / No verified public source | unreleased or unverified | nothing can be fetched |

## Why it is small, and how big

Measured 2026-10-09 on the built site: **31.7 MB** in total (`catalogue.json` 0.37 MB, `guide.json` 0.53 MB, the three approved packs 1.1 MB, approved media 28.5 MB, the interface about 1.1 MB). GitHub Pages allows published sites up to 1 GB and about 100 GB of bandwidth a month; CI fails the build above 200 MB. Growth is bounded by the approval list: a text-only approved preview costs a few hundred kB, an image preview a few MB per 100 records.

## How it stays true without the workspace

The build runs in CI from the repository alone, so the facts that only exist in a workspace are committed as small, reviewed files under `examples/public-schema/`:

- `<id>.json`: the field schema of each prepared preview (one per dataset, about 0.9 MB in total).
- `coverage.json`: the coverage of every dataset as a workspace merges it with its prepared version. The tracked YAML predates preparation, so without this file a prepared dataset would read "no preview, adapter not started".

Regenerate both after preparing or changing datasets, then commit:

```bash
atlas publish schemas          # needs the workspace; writes examples/public-schema/
atlas publish validate --profile public
```

`tests/unit/test_publication_guide.py` fails if `coverage.json` disagrees with `reports/dataset_coverage.csv`, if a schema names another dataset, or if any file holds a path, secret or PDF reference. The same scanner that protects approved packs scans the guide.

## Adding a dataset's examples to the site

1. Review the rights and the exact files; keep the evidence in `reports/`.
2. Set the registry `rights` to approved for the categories to publish.
3. Copy the reviewed pack to `examples/approved-packs/<id>/` and list it in `registry/publication.json` (records, annotations, each media asset ID, sensitive-media review).
4. `atlas publish validate --profile public`, then the browser suite. See [publication](publication.md).

## Deploy

Prerequisites: the repository is `github.com/shinobiultra/DatasetAtlas`; the workflow `.github/workflows/validate-and-publish.yml` already builds, tests and size-checks the site with the repository base path.

1. Repository **Settings → Pages → Build and deployment → Source: GitHub Actions**.
2. Check the data you are about to make public: `atlas publish validate --profile public`; confirm `registry/publication.json` lists only what you reviewed; read `apps/web/public/data/guide.json` once.
3. **Actions → Validate and publish Dataset Atlas → Run workflow**, set `deploy` to true. Pushes and pull requests build and test but never deploy.
4. The site appears at `https://shinobiultra.github.io/DatasetAtlas/`. Open a gated dataset page and one with approved examples.

### Status on 2026-10-09

The repository is public and `main` holds the finished site, but nothing is deployed: the owner chose to hold the site back for now. The history was scanned for tokens and secrets and none were found; it does expose the maintainer's workspace paths in about 60 reports, the corpus folder name and the author e-mail on 90 commits. To go live later:

```bash
gh api -X POST repos/shinobiultra/DatasetAtlas/pages -f build_type=workflow
gh workflow run validate-and-publish.yml --ref main -f deploy=true
```

Then open `https://shinobiultra.github.io/DatasetAtlas/`. Also restrict the `github-pages` environment to `main` in the repository settings. A prebuilt copy of the exact site for `/DatasetAtlas/` is in `dist/dataset-atlas-site-*.zip` (gitignored) for any static host.

Rollback: re-run the workflow from the previous good commit, or disable Pages in settings. Cached copies and search-engine indexes can outlive a deletion, so publish only what you would accept being copied.

## Not built, and why

- **A static page that drives your local workbench.** The browser could talk to `atlas serve` on loopback, but the server refuses cross-origin requests on purpose. Allowing one origin needs an explicit opt-in flag and a CSRF design review first.
- **Larger approved previews outside Pages.** Packs could be hosted as a Hugging Face dataset and loaded lazily by the site, keeping Pages small. It needs the same rights approval per dataset, so it only matters once more than a few datasets are approved.
- **Live status.** Coverage on the site is a committed snapshot, not a service.

## Limits

The site shows what the maintainers prepared and reviewed, not the datasets. A field schema describes the maintainers' preview and says nothing about the full release. A catalogue entry's identity is still a candidate until a person reviews it; the site does not say otherwise. `full_v1_complete` is false.
