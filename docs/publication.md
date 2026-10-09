# Static publication and portable exports

The static site contains the browser, a sanitized catalogue, and only preview packs explicitly approved in `registry/publication.json`. The public profile currently approves pinned CLEVR, EuroSAT RGB, and PAIRS previews; every other registry entry appears as metadata only unless separately allowlisted. A local preview pack is **not** publication approval. Validation reads local files and does not upload or deploy anything.

## Approval profile

Each registry dataset has separate `rights` decisions for `records`, `annotations`, `images`, and `derived_artifacts`. To publish a preview, the registry right for that category must be `approved`, `public`, or `redistributable` **and** the profile must opt in. Record text needs `records`; source labels need `annotations`; computed results need `derived_artifacts`. Unknown rights remain metadata only.

```json
{
  "schema_version": "1.0",
  "datasets": {
    "reviewed-dataset-id": {
      "records": true,
      "annotations": true,
      "derived_artifacts": false,
      "media_asset_ids": [],
      "sensitive_media_reviewed": false
    }
  }
}
```

Media needs the `images` registry right, each asset ID in `media_asset_ids`, and an explicit sensitive-media review recorded by `sensitive_media_reviewed: true`. Approved media must be an existing relative file inside the pack directory; the publisher does not fetch remote URLs. Images default to excluded, even when records are approved. Do not approve media solely from a detector output. The profile records a publication decision, not its evidence; keep that evidence in a review record before changing the profile.

The builder reads `registry/datasets/*.{yaml,yml,json}` and a supplied pack root. Local preparation uses `work/packs/<id>/pack.json`; reproducible CI uses the reviewed preview copied to `examples/approved-packs/<id>/pack.json`. It writes `apps/web/public/data/catalogue.json`, one `data/<id>.json` per approved preview, and any individually approved media. Catalogue entries retain coverage and rights but omit adapter configuration, evidence excerpts, and relationships. Public records omit private human notes; annotations, predictions, artifacts, and media each require their matching approval. Any selected payload containing a local path, PDF reference, or recognizable credential fails validation. Source URLs must be plain HTTP(S) URLs without credentials or query strings.

The approved CLEVR preview retains its attribution in the public catalogue and pack: “CLEVR (c) 2017 Facebook, Inc.; Johnson et al., CVPR 2017. CC BY 4.0.” Its source and licence are linked from the [official CLEVR page](https://cs.stanford.edu/people/jcjohns/clevr/). The pinned replica and exact source checksum remain in the local registry; the published pack contains 100 question records with 100 distinct rendered images from the pinned 1,070-question validation subset. This is a preview, not a complete-release mirror or a random sample of the official release.
The media review used the official dataset description of computer-rendered geometric scenes, checked every copied file's checksum and image format, and visually spot-checked images at the beginning, middle, and end of the selected preview. It was not an exhaustive per-image visual review.

Derived results live in the separate `examples/approved-packs/clevr/analysis-artifacts.json` overlay, leaving the source `pack.json` unchanged. The profile pins both the exact artifact IDs and the overlay SHA-256, and the publisher rejects incomplete coverage, mismatched IDs, local file references, and unapproved fields. Six 100/100 completed artifacts are approved for the static view: UMAP, PCA, COCO detection, KMeans clusters, KNN outliers, and basic image quality. The projection uses question embeddings from the pinned [Apache-2.0 MiniLM model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41). Model weights and full embeddings are not in the public pack; these remain local. Computed values describe this 100-record preview only and do not estimate the full CLEVR release.

The approved PAIRS preview contains 100 author-generated 256×256 PNGs in 25 complete four-image scenario groups: 20 occupation groups and five status groups. Potential-crime scenes are excluded from this public candidate. The [author datasheet](https://github.com/katiefraser/PAIRS/blob/507075ac84d244c4f98b965ba257b197d4944b04/Data%20Sheet.md) states CC BY 4.0 and author ownership of the generated images, and warns that isolated images can reinforce stereotypes. The published `prompt_race` and `prompt_gender` values are **generation prompt words**, not inferred personal identities. The [scoped publication review](../reports/pairs-publication-review.md) records the exact source checksum, 100-file validation, scenario selection, and 16-image visual spot check; it does not claim exhaustive visual inspection. Only those 100 asset IDs are allowlisted locally. No remote site deployment has occurred.

The approved EuroSAT preview contains 100 original 64×64 RGB JPEGs, ten per land-cover class, from the [author's v2 Zenodo release](https://zenodo.org/records/7711810). The [author README](https://github.com/phelber/EuroSAT/blob/353fc2ff01447cbcf84c4496dd98e82f197515bd/README.md) licenses the dataset under MIT. The [Copernicus Sentinel legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice) permits modified-data redistribution with a source notice; the public catalogue says “Contains modified Copernicus Sentinel data 2015–2018.” That inclusive year range is inferred from the Sentinel-2A launch and v2 release because individual capture dates are not provided. The full [author MIT notice](../apps/web/public/licenses/eurosat-MIT.txt) is bundled with the static site. The [scoped review](../reports/eurosat-publication-review.md) records checksum validation for every selected JPEG, a ten-class visual spot check, and the attribution basis. This is a balanced preview, not a complete or random sample of 27,000 RGB images, and it does not cover the multispectral variant.

```bash
atlas publish validate --profile public
atlas publish build --profile public
```

The Python callable interface is `validate_publication(registry_dir, packs_dir, output_dir, profile_path)` and `build_publication(...)` from `dataset_atlas.exports`. Build writes the `data/` subtree only after complete validation. The internal data budget is 200,000,000 bytes; CI also measures the entire built site against that limit. `atlas publish build` is a local operation. The GitHub Pages workflow deploys only when manually dispatched with its `deploy` input set to true. This repository has no standing approval to publish a dataset or site.

## Public guide and committed state

Besides the approved previews, the build writes `data/guide.json`: for every catalogue dataset, a computed how-to-get state, the corpus papers that name it (title, year, DOI or URL only) and, for datasets the maintainers prepared, the field schema of the preview. A schema lists field names, types, descriptions and categories declared in the recipe; it never holds record values, and it is documentation of structure rather than content. Two committed inputs keep CI independent of the workspace: `examples/public-schema/<id>.json` (schemas) and `examples/public-schema/coverage.json` (each dataset's coverage as a workspace merges it with its prepared version; the tracked YAML predates preparation). Regenerate both with `atlas publish schemas` after preparing or changing datasets and commit them; a test fails if the snapshot disagrees with `reports/dataset_coverage.csv`. Without `examples/public-schema` next to the packs directory the build still succeeds but publishes no schemas and the unmerged coverage. See [GitHub Pages edition](github-pages.md).

## Portable selection and pack exchange

`export_selection(selection, records, output_dir)` writes `selection.json`, `records.json`, and a checksum manifest to a new directory. The record IDs must exactly match the saved selection, including unit, dataset, and snapshot. Local paths, private notes, and media URIs are removed by default. To include specific approved local images, pass `media_root` and `approved_media_ids`; the export copies only those relative files and records their checksums. `import_selection(path)` checks size, file list, checksums, schema, and IDs before returning data. The JSON API form is `selection_export_payload(selection, records)` and contains no media files.

`export_pack(pack, output_dir)` and `import_pack(path)` use non-executable JSON files with a checksum manifest. They reject path traversal, links, unknown files, size excess, invalid schema, and mismatched identities. They never load pickle or run code from a pack. Exporters require the caller to supply authorized, path-free content; these APIs do not make a private dataset public. For large tabular releases, Parquet is the intended follow-on representation. Current portable exchange emits JSON preview records, while the local canonical `Pack` remains `work/packs/<id>/pack.json`.

The current checks are deliberately conservative and cannot establish legal rights or detect every sensitive image or secret. Reviewers must inspect the exact intended preview and rights evidence before adding it to the profile. A successful build confirms only that the configured checks passed on the current files.

## Installable release check

`python scripts/build_release.py` installs the locked frontend dependencies, builds the root-base frontend, copies it into `src/dataset_atlas/web`, and builds a wheel and source archive under `dist/`. `python scripts/verify_distribution.py` checks both archives for the bundled public site, the approved CLEVR, EuroSAT, and PAIRS media, size limits, and private-file markers. The GitHub Pages build is separate: CI tests the frontend and generated Python-to-TypeScript contracts, builds the site with its repository base path, checks the entire site against the 200 MB budget, and only deploys after an explicit `workflow_dispatch` with `deploy: true`.

Before sharing a Python release, inspect both archives for private source files, weights, local paths, credentials, and other non-public artifacts. Install the wheel into a fresh virtual environment with only the declared base dependencies, start `atlas serve` from a clean workspace that has no source checkout or local registry, and request the actual root page, static catalogue, approved preview JSON/media, and `/api/v1/capabilities`. A successful `atlas --help` alone does not establish that the bundled frontend or HTTP server works. The installation receipt for the current build is in [`reports/installation-verification.json`](../reports/installation-verification.json); it names the exact archive and requests tested. Rebuild that receipt whenever the registry, approved pack, or frontend changes.
