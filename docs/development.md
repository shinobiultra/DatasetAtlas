# Development

The runtime models in `src/dataset_atlas/models.py` own the data contracts. Read
[contracts](contracts.md) before changing shared shapes, and follow [SPEC](../SPEC.md).
Catalogue originals remain read-only. Synthetic fixtures exercise software contracts;
published examples require real provenance and explicit rights.

## Run and test

```bash
uv sync --frozen --extra development
./start.sh
./start.sh --workbench
```

The sample browser needs uv and Node.js 26 (or 22.12+). Base browsing needs no GPU or models.
Install optional extras and pinned weights explicitly for analysis; see
[getting started](getting-started.md). Use `uv run --no-sync` with an intentionally
provisioned environment to preserve optional dependencies. Validate dependency or
CUDA upgrades in an isolated environment before adopting them.

The workbench supports Python 3.11–3.14; the latest supported patch tested here is
3.14.10. Python 3.15 is not yet admitted for the workbench: as of 2026-10-27,
Linux x86_64 binary-wheel resolution fails for the required PyYAML and DuckDB<2
dependencies and the optional h5py dataset reader. See the publishers' files for
[PyYAML](https://pypi.org/project/PyYAML/6.0.3/#files),
[DuckDB](https://pypi.org/project/duckdb/1.5.5/#files) and
[h5py](https://pypi.org/project/h5py/3.16.0/#files). The portable sample ZIP uses only
the standard library and has separately passed its launcher and HTTP checks on
Python 3.15.2. This does not establish scientific-package compatibility on 3.15.

```bash
uv run --no-sync pytest -q tests/unit/test_queries.py
uv run --no-sync pytest -q
prek run --all-files
npm --prefix apps/web test
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
uv run --no-sync atlas datasets validate --all
uv run --no-sync python scripts/generate_contracts.py
```

The pre-commit configuration runs pinned checks including `ty` over its declared
modules. That boundary does not imply repository-wide typing. Browser tests include
explicitly synthetic performance fixtures and approved real examples; optional live
journeys require the configured local services. See the [browser test guide](../apps/web/e2e/README.md).
Keep automated assertions, native source checks and human acceptance distinct.

Preparation plans state source pins, transfer/output budgets and scope before
execution. Complete indices retain native units and relationships. Full queries
operate on their declared source partitions; bounded samples never imply complete
local coverage. [Adding datasets](adding-datasets.md), [preparation](on-demand-preparation.md)
and [storage](storage.md) describe those contracts.

## Release reports

`scripts/report_release.py` reads the merged runtime registry, pack headers and
index manifests, and counts preview objects from JSON punctuation without decoding
their native values. It binds exact file hashes without inspecting record contents. It
writes the coverage matrix, source pins, release evidence, status and source
qualifications under `reports/`. Draft reports leave completion pending:

```bash
uv run --no-sync python scripts/report_release.py
uv run --no-sync python scripts/report_release.py --fingerprint
```

Finalize only after the current release checks are complete. A verification proof
uses `schema_version: "1.0"`, the package `release_version`, the two fingerprints
printed above, and `checks` keyed by `REQUIRED_CHECKS` in the generator. Every check
needs `status: "passed"`, `command`, timezone-aware `checked_at_utc` and a concise
aggregate `summary`. Keep machine paths and private source data out of that proof.
Pass it explicitly:

```bash
uv run --no-sync python scripts/report_release.py --verified work/release-verification.json
uv run --no-sync pytest -q tests/unit/test_status_consistency.py
```

A retained entry also needs its real preview target and either a matching complete
native index or a pinned whole-source sampler. A changed catalogue, active
pack/index or release source invalidates the proof.
The report test checks exact catalogue membership, scope/count consistency and the
current verification binding. Finalization does not assert human or scientific
acceptance, historical paper-use equivalence or broader redistribution rights.

## Distribute

Follow [publication](publication.md) for allowlist validation, archive inspection,
clean installation and the portable bundle. Use [GitHub Pages](github-pages.md) for
explicit deployment. [Release evidence](../reports/release_evidence.md) holds current
aggregate results; recovery and host-specific receipts stay in private workspace
storage. Do not copy a private maintainer directory into a release.
