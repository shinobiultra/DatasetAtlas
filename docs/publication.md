# Publication

Dataset Atlas separates code licensing, local source access and permission to
redistribute data. Only the exact approved CLEVR, EuroSAT and PAIRS previews enter
the public browser. Their notices travel with the static site and portable bundle.
A locally prepared dataset does not become public automatically.

## Exact approvals

The publication profile opts into records, annotations, derived artifacts and
individual media IDs. Each selected category must also have an approved registry
right. Media requires an explicit sensitive-media review. The builder copies only
existing relative approved files; it never fetches arbitrary remote media for
publication. Unknown rights retain metadata-only publication.

```bash
atlas publish validate --profile public
atlas publish build --profile public
```

Validation checks schemas, source URLs, local-path and credential markers, exact
media allowlists, artifact identity and the publication byte budget. Public records
omit private notes; adapter configuration and source evidence excerpts are excluded.
A successful build confirms those configured checks on those bytes. It does not
establish legal rights or exhaustive human review.

The CLEVR pack contains 100 question records and distinct rendered images from its
approved pinned validation subset. It remains separate from the workbench's full
canonical CLEVR index. Its approved records, original media and sampling provenance
are retained. Attribution: CLEVR (c) 2017 Facebook, Inc.; Johnson et al., CVPR 2017;
CC BY 4.0.

The PAIRS pack contains 100 author-generated images in 25 complete four-image
scenario groups. Generation prompt race and gender fields describe prompt words,
not inferred personal identities. Its author CC BY 4.0 notice and scope remain
attached; isolated images can reinforce stereotypes.

The EuroSAT pack contains 100 original RGB images, ten per land-cover class. It is
a balanced preview of the RGB release. The author's MIT notice and “Contains
modified Copernicus Sentinel data 2015–2018” attribution accompany the pack.

## Public metadata and exchange

`atlas publish schemas` refreshes `examples/public-schema/` from the current
workspace. It publishes field names, types, declared categories and source coverage,
without record values. The static guide adds how to obtain each source and the
corpus papers that mention it. Source-release identity does not establish the
exact population historically used by a paper.

Selection and pack exports use JSON plus checksum manifests. Imports reject
traversal, links, unexpected files, identity mismatches and size excess. Selection
exports omit local paths, private notes and media by default; media needs explicit
approval. An exchange checksum proves bytes and identities, not publication rights.

## Build and verify a release

```bash
uv run --no-sync python scripts/build_release.py
uv run --no-sync python scripts/verify_distribution.py
uv run --no-sync python scripts/verify_installation.py
uv run --no-sync python scripts/build_sample_bundle.py
```

The release builder embeds the root-base frontend and catalogue in the wheel and
creates an sdist. Distribution checks inspect actual archives for the approved
site, required assets, size limits and private-file markers. Clean-install checks
must run the bundled server from a fresh workspace and request its HTML, public
catalogue, approved JSON/media and capability API. The portable launcher verifies
its complete file manifest before serving on loopback.

[Release evidence](../reports/release_evidence.md) binds the current checks to the
source tree and active catalogue. [GitHub Pages](github-pages.md) describes the
separate manual deployment path. No build command grants publication permission.
