# Finish Dataset Atlas — Remaining-Gap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every SPEC.md gap that engineering can close, convert every other gap into an evidence-dated external or human-review blocker, and ship a rebuilt, re-verified release whose numbers agree everywhere.

**Architecture:** The product is built (workbench, static mode, adapters, processors, providers, publication). This plan adds no subsystem. It adds one reusable source-probe module, a refresh of stale source evidence, per-dataset integrations that the refresh unlocks, a human identity-review queue, an acceptance-traceability matrix, a storage reduction toward the 100 GB target, and a synchronized release closeout.

**Tech Stack:** Python 3.12 (`.venv`, never `uv sync` it — it holds the verified model stack), `pytest`, `httpx`, `uvx ty==0.0.83`, `prek`, React/TS/Vite, Playwright, Python 3.14 env at `work/verify-install/python314-env`.

**Spec:** `SPEC.md` (acceptance §22, definition of done §24, storage §8.4, coverage §5, identity §4.4–4.5). Project rules: `AGENTS.md`. State of record: `ROADMAP.md`, `reports/final-status.json`, `reports/dataset_coverage.csv`.

## Measured starting point (2026-10-08, this session)

| Fact | Value |
| --- | --- |
| Catalogue / previews / no preview | 333 / 218 / **115** |
| The 115 by identity | 95 `candidate`, 5 `family_or_variant_candidate`, 1 `benchmark_platform`, 14 `resolved` (gates, author requests, Broden host timeouts, BBQ-V 403, one unreleased set, RobustBench = protocol not data) |
| The 115 by access | 17 `unreleased` paper-private sets; 43 `unverified`; 14 `source_release_unverified`; 16 `gated`; 15 `public` (adapter not started, or Broden/PATA partial); 10 other (`request_required`, `base_source_public_variant_unverified`, platform, source-page) |
| Overlap with prepared work | 34 of the 115 already link to a prepared family (`same_source_family_as`, `derived_from`): COCO ×12, ImageNet ×5, CUB ×2, SB-Syn ×2, … |
| Source evidence age | 87 audits dated 2026-09-22, 12 dated 2026-10-06, **9 entries never audited** (`custom-speech-segment-collection`, `gaussian-rubbish-examples`, `gda-adversarial-image-variants`, `laion-aesthetics`, `middlebury`, `vl-gender`, `vtab`, two `paper-2c07a8c6af8e33c2-unnamed-internet-hidden-content-*`) |
| Python 3.12 suite | **1028 passed, 1 skipped** (81 s) — equals the recorded evidence |
| Frontend / checks | 26 vitest passed; `prek run --all-files` (pinned `ty` + whitespace) passed |
| Storage | 122,381,500,416 B allocated vs 100,000,000,000 target (**+22.4 GB**); ceiling 150 GB. Largest: `work/prepared` 77.4 GB, `work/sources` 19.0 GB, Qwen weights 7.5 GB, `.venv` 6.9 GB |
| Working tree | 708 uncommitted paths since the last commit (2026-10-02). Not committed by this plan unless D1 says so |
| Broden / `images.cocodataset.org` | HEAD timed out (15 s / 10 s) this session; `huggingface.co` and Caltech answered |
| `apps/web/node_modules` | absent (retired earlier); `npm ci` restored 134 MB for verification — remove at closeout |

## Global Constraints

- "Corpus originals are read-only." Corpus root: `/home/bitwise/Documents/Media_Bias_Group/MechinterpAdversarialAttacks/Flight Package` (AGENTS.md, SPEC §4.1).
- "Never claim candidates are reviewed, implementation gaps are external blockers, or synthetic fixtures are real coverage." (AGENTS.md)
- "Do not transmit dataset contents to external models or perform unbounded downloads." (AGENTS.md) Unknown size is not permission (SPEC §8.4).
- Storage: target **100 GB**, ceiling **150 GB**, measured as unique allocated bytes (SPEC §8.4). Preview originals stay original quality; lossy AVIF only for non-preview images; originals stay retrievable.
- "Do not mark unavailable model servers, inaccessible datasets, or unexecuted tests as validated." (SPEC §23)
- "Acceptable external blockers include unavailable releases, access approval, unavailable underlying media, and restrictions on obtaining or publishing data." "Complicated format" and "not on Hugging Face" are implementation gaps. (SPEC §5)
- Accepting a gate's terms, submitting an access request, or buying data is **not** done by the agent; the user does it (`docs/dataset-authorization.md`).
- Python tooling: `uv`, `uvx ty==0.0.83`, `prek`; frontend `npm ci` from lockfile. No cluster jobs, no paid model APIs.
- `AGENTS.md` names `gpt-6.1-sol` at `xhigh` for delegated work, which this harness cannot select. The user replaced it with Sonnet 5.5 on 2026-10-08 (D2): delegates use `model: sonnet`. Reviewer recommendations are never recorded as human acceptance.
- Task 2 amendments (pre-flight rulings): `ProbeOutcome` also carries `etag: str | None` and `content_digest: str | None`; `probe_url` also takes `resolver: Callable[[str], Sequence[str]] | None = None` so tests need no DNS. Task 3 treats a URL as pinned only with (a strong ETag and a known `content_length`) or a `content_digest`.
- Any shared-contract change needs a fixture update and compatibility decision (SPEC §21). This plan changes no schema: new evidence kinds are free-form entries in the existing `evidence` list.

## Open decisions (stable IDs; work that does not depend on them continues)

| ID | Question | Status | Blocks |
| --- | --- | --- | --- |
| D1 | May the uncommitted paths be committed? | **Resolved 2026-10-08 (user):** one checkpoint commit of the current tree as-is, then one commit per completed task with the `Co-Authored-By` trailer. **No pushes.** | — |
| D2 | `gpt-6.1-sol` is unavailable to this harness. | **Resolved 2026-10-08 (user): "swap the sol for Sonnet 5.5."** Delegated implementers and reviewers use `model: sonnet` (Sonnet 5.5). A Sonnet reviewer shares a model family with the author; reports say so and never present it as human acceptance. `AGENTS.md` still names `gpt-6.1-sol`; it is the user's file and is not edited here. | — |
| D3 | Accept the Hugging Face terms for `thu-ml/MultiTrust` (and BBQ-V) on your own account? | **Open.** The agent will not accept terms. | Task 5 only |
| D4 | Retire verified retained source bodies toward 100 GB? | **Resolved 2026-10-08 (user):** produce the dry-run reclaim table first, then delete only bodies with a verified retrieval route and no protecting reference; verify cold reads after each dataset. | — |

## Review Focus

Input classes or failure modes the spec implies but no existing test pins, most likely first:

1. **Timeout recorded as a permanent gate.** Broden's host timing out must read `unreachable` (transient, retry), never `external_access_gate` and never "implementation gap". → Task 2 test.
2. **Refresh edits identity.** A "refresh" that rewrites `coverage.identity`, `release`, `preview` or `snapshot_id` would launder candidates into resolved. Only human review changes those. → Task 3 test.
3. **"Now public" without a pin.** A mutable URL with no digest/ETag must be `public_unpinned`, never integrated. → Task 2 + Task 4 gate.
4. **Retirement of a body still referenced** by a frozen selection, protected preview, or native retrieval index. → Task 8 dry-run assertion.
5. **Headline numbers drift** between `final-status.json`, `dataset_coverage.csv`, README and ROADMAP after the changes. → Task 9 test.
6. **A family-linked entry counted as having its own preview.** `preview: none` must stay `none`; the link is navigation, not coverage. → Task 6 test.

---

### Task 1: Full baseline attestation of the current tree

**Files:**
- Create: `reports/baseline-attestation-20261008.json`
- No source changes.

**Interfaces:**
- Consumes: `scripts/verify_preview_media_smoke.py`, `scripts/verify_complete_index_smoke.py` (both take the running workbench URL), `atlas serve`, `apps/web` Playwright suite.
- Produces: the numbers every later task compares against (Python 1028/1, vitest 26, smoke 218 datasets / 216 indices, browser 69).

- [ ] **Step 1:** Python and frontend baseline are already recorded in the table above; re-run them only if a later task changes code.
- [ ] **Step 2:** Start the workbench from the main env on a free port: `.venv/bin/atlas serve --port 8766 &`; wait for `GET /api/v1/capabilities` → 200.
- [ ] **Step 3:** Run `scripts/verify_preview_media_smoke.py` and `scripts/verify_complete_index_smoke.py` against it (read their `--help` for the URL flag). Expected: 0 failures; complete-index count equals the registry total for each of 216 datasets.
- [ ] **Step 4:** Run the browser suite with local Ollama as the only model server: `ATLAS_LIVE_API=http://127.0.0.1:8766 ATLAS_LINKED_JOURNEY=1 ATLAS_ANALYSIS_JOURNEY=1 npm run test:e2e --prefix apps/web`. Expected: 69 passed, 0 skipped. Any skip or failure is reported verbatim, not rerun until green without recording it.
- [ ] **Step 5:** Write the receipt (commands, counts, durations, versions, Ollama model name, "no external model send") and stop the workbench.
- [ ] **Step 6: Checkpoint** — commit `reports/baseline-attestation-20261008.json` (per D1).

---

### Task 2: Reusable source probe with honest outcome classes

**Files:**
- Create: `src/dataset_atlas/registry/source_probe.py`
- Create: `scripts/probe_sources.py`
- Test: `tests/unit/test_source_probe.py`

**Interfaces:**
- Produces:
  ```python
  ProbeStatus = Literal["reachable", "empty_response", "gated_or_forbidden", "gone",
                        "unreachable", "redirect_refused", "server_error"]
  @dataclass(frozen=True)
  class ProbeOutcome:
      url: str; status: ProbeStatus; http_status: int | None
      content_length: int | None; content_type: str | None
      etag: str | None            # raw ETag header
      content_digest: str | None  # Digest / Content-MD5 / HF X-Linked-Etag (unquoted), else None
      final_host: str | None; error: str | None
      elapsed_s: float; checked_at_utc: str
  def classify_probe(*, http_status: int | None, error: str | None, content_length: int | None,
                     content_type: str | None, redirect_refused: bool) -> ProbeStatus
  def probe_url(url: str, *, timeout: float = 15.0, attempts: int = 2,
                max_redirects: int = 4, client: httpx.Client | None = None,
                resolver: Callable[[str], Sequence[str]] | None = None) -> ProbeOutcome
  # resolver(host) -> list of IP strings; default uses socket.getaddrinfo. Tests inject a fake: no DNS in unit tests.
  ```
- Consumes: `httpx` (base dependency).

- [ ] **Step 1: Write failing tests** in `tests/unit/test_source_probe.py` using `httpx.MockTransport` (no network):
  ```python
  def test_timeout_is_unreachable_not_gated():            # Review Focus 1
      out = probe_url("https://example.org/a.zip", client=_raising(httpx.ConnectTimeout("t")), attempts=1)
      assert out.status == "unreachable" and out.http_status is None
  def test_403_is_gated_or_forbidden_and_404_is_gone(): ...
  def test_200_empty_html_is_empty_response():            # the Google Drive case in registry/datasets/e-ic.yaml
      assert _probe(200, headers={"content-length": "0", "content-type": "text/html"}).status == "empty_response"
  def test_200_with_body_is_reachable_and_reports_length_and_type(): ...
  def test_redirect_to_private_address_is_refused():
      assert _probe_redirect("http://127.0.0.1/x").status == "redirect_refused"
  def test_head_405_falls_back_to_one_byte_range_get_and_never_reads_more():
      assert recorded_range_header == "bytes=0-0"
  def test_5xx_is_server_error_and_retried_up_to_attempts(): ...
  ```
- [ ] **Step 2:** `PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_source_probe.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `probe_url`/`classify_probe`. HEAD first; on 403/405/501 retry once as `GET` with `Range: bytes=0-0` and read at most one byte. Follow redirects manually (≤ `max_redirects`), resolving each hop's host and refusing non-global addresses (`ipaddress.ip_address(...).is_global`). Never send credentials. Document the DNS-rebinding window (read-only HEAD research tool, not a fetch layer; bulk fetching stays on `storage/https.py`).
- [ ] **Step 4:** Re-run the tests → PASS; `prek run --all-files` → Passed.
- [ ] **Step 5: Implement `scripts/probe_sources.py`** — `--dataset ID ... | --blocked`, writes `reports/source-reprobe-20261008.json` (list of `ProbeOutcome` per URL, plus the registry entry each URL came from). `--blocked` selects entries whose `coverage.blockers` or `access` is gated/request/outage, and probes `source_url` plus every `url` inside `source_audit_*` evidence.
- [ ] **Step 6:** Run `scripts/probe_sources.py --blocked`. Expected: Broden's three archive URLs, BBQ-V, the MMEdit Drive links and the gated publishers each get a status. Re-run Broden twice more ≥ 10 minutes apart (schedule each as a background `sleep 600 && …` command; no foreground sleep) before calling it `unreachable` in the receipt.
- [ ] **Step 7: Checkpoint** — commit module, script, test, receipt (per D1).

---

### Task 3: Refresh stale candidate-source evidence

**Files:**
- Create: `scripts/refresh_candidate_sources.py`
- Modify: `registry/datasets/<id>.yaml` for refreshed entries (evidence + blocker text only)
- Create: `reports/candidate-source-refresh-20261008.json`, `reports/candidate-source-refresh-20261008.md`
- Test: `tests/unit/test_refresh_candidate_sources.py`

**Interfaces:**
- Consumes: `probe_url` (Task 2); `registry/datasets/*.yaml`; the `source_audit_*` evidence shape (`kind`, `url`, `note`, `checked_on`).
- Produces: per entry a disposition `unchanged | now_public_pinnable | public_unpinned | now_gated | released_after_audit | still_unreleased`, and one appended evidence item:
  `{kind: source_audit_refresh, url, probe_status, http_status, checked_on: '2026-10-08', note}`.

- [ ] **Step 1: Write failing tests:**
  ```python
  def test_refresh_never_touches_identity_release_preview_or_snapshot():   # Review Focus 2
      before = _protected_fields(entry); refresh(entry, _fake_outcomes("reachable")); 
      assert _protected_fields(entry) == before
  def test_reachable_url_without_digest_or_etag_is_public_unpinned():       # Review Focus 3
  def test_unreachable_probe_adds_evidence_but_keeps_prior_disposition(): ...
  def test_refresh_is_idempotent_for_the_same_checked_on_date(): ...
  ```
  (`_protected_fields` = `coverage.identity`, `coverage.preview`, `coverage.adapter`, `release`, `snapshot_id`.)
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `refresh(entry, outcomes) -> RefreshResult` and the driver over the 98 entries with `preview: none` and `access != unreleased` (89 audited + 9 never audited; the 17 unreleased sets are excluded). Pinned means `content_digest` is set, or `etag` is strong (does not start with `W/`) and `content_length` is not None. Write the receipt and a one-table markdown summary.
- [ ] **Step 4:** Tests → PASS. Run `.venv/bin/atlas datasets validate --all` → no errors; `git diff --stat registry/` shows evidence/blocker edits only.
- [ ] **Step 5 (research, no code):** For the nine never-audited entries, read the primary author/project pages (WebSearch/WebFetch, public pages only) and record identity, access, rights as `source_audit_*` evidence with `checked_on`. Honest outcome examples: "benchmark suite, no single release" (`vtab`), "generated by a recipe" (`gaussian-rubbish-examples`).
- [ ] **Step 6:** Run the driver; commit the receipt. **Checkpoint** (per D1).

---

### Task 4: Integrate newly accessible, pinnable public sources (per-dataset template)

Runs once per entry that Task 3 classifies `now_public_pinnable` or `released_after_audit` with a pinned file, ordered by smallest declared transfer first. Also covers Broden if Task 2 shows its host reachable. If the refresh yields none, record that and stop — do not invent integrations.

**Files (per dataset `<id>`):**
- Create/Modify: `registry/recipes/<id>.yaml`, `registry/datasets/<id>.yaml`
- Create/Modify: adapter or converter only if no existing family fits (`src/dataset_atlas/adapters/`, `src/dataset_atlas/converters/`)
- Test: `tests/unit/test_<id>_native.py`
- Create: `reports/<id>-live-verification-20261008.json`

**Interfaces:**
- Consumes: the adapter contract in `docs/adding-datasets.md` (`plan` → `prepare` → `iter_records` → `resolve_asset` → `validate`), `build_preview`, `atlas datasets index`, `atlas previews fetch --execute`.
- Produces: coverage dimensions updated independently (identity stays `candidate` unless a human resolved it), `snapshot_id`, 100 inspectable real examples (or all if fewer), complete index only after a verified final-record read.
- **Admission per pass:** total transfer ≤ 10 GB and prepared output ≤ 5 GB; anything larger needs the user's budget approval. Prefer selective range reads over full downloads.

- [ ] **Step 1:** Write the failing converter/adapter test with a small **real** fixture slice from the pinned source (identity test, schema check, media-resolution test, overlay join counts if any — SPEC §7.4). Synthetic data only for failure cases.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Add the recipe pinning each file's URL, byte length and SHA-256 (or ETag + length for ranged reads) and the adapter config; implement only the missing mapping.
- [ ] **Step 4:** Tests → PASS; `prek run --all-files` → Passed.
- [ ] **Step 5:** `atlas previews fetch --execute --dataset <id>` into the main workspace; verify 100 records, original-resolution media, sampling method/seed/population recorded.
- [ ] **Step 6:** Verify from an empty workspace (`atlas init` scratch dir) → same `snapshot_id`; record in `reports/preview-reproducibility.md` via `scripts/report_reproducibility.py --verified-from <dir>`.
- [ ] **Step 7:** Read a record beyond row 100 or run a bounded complete-index read; only then `atlas datasets index --dataset <id> --expected-count <n>`.
- [ ] **Step 8:** Update coverage dimensions (adapter `tested`, preview `complete_target`, complete-data state, rights unchanged `not_reviewed`/`metadata_only`). Write the live-verification receipt. **Checkpoint** (per D1).

---

### Task 5: MultiTrust and BBQ-V gate check (D3-dependent)

**Files:**
- Modify: `registry/datasets/multitrust.yaml`, `registry/datasets/sbbench.yaml`
- Create (only if access works): per-task adapter configs under `registry/recipes/multitrust-*.yaml`, `tests/unit/test_multitrust_native.py`

**Interfaces:**
- Consumes: `probe_url`, Hugging Face API with the researcher's own token (the project already does this), `structured_collection` adapter family.
- Produces: either a per-task adapter set with a tested preview each, or a dated receipt that access is still refused.

- [ ] **Step 1:** Request `thu-ml/MultiTrust` and the BBQ-V repo metadata with the configured token (read-only, no file bodies).
- [ ] **Step 2:** If HTTP 403 persists → record the dated gate state on both entries, add them to the D3 line of the closeout, and **stop this task**. The agent does not accept terms.
- [ ] **Step 3:** If access works → list repository files, write a task→file→format table (`reports/multitrust-task-inventory-20261008.json`), then apply Task 4's template per task, smallest first. A heterogeneous suite keeps one catalogue record linking member tasks (SPEC §4.4), not a single fake homogeneous collection.
- [ ] **Step 4: Checkpoint** (per D1).

---

### Task 6: Identity review queue for the human

**Files:**
- Create: `scripts/build_identity_review_queue.py`
- Create: `reports/identity_review_queue.md`; append `kind: identity_decision` records to `work/corpus/review_queue.jsonl`
- Test: `tests/unit/test_identity_review_queue.py`

**Interfaces:**
- Consumes: `registry/datasets/*.yaml` (`coverage.identity`, `relationships`, `evidence`), `reports/dataset_coverage.csv`.
- Produces: groups with stable IDs `IR-001…` (deterministic: sorted by group key; same input → same IDs). Each group lists member entry IDs, the paper mentions that distinguish them, the prepared release(s) they link to, the options `alias_of:<id>` / `distinct_release` / `keep_candidate`, and the decision needed. Expected groups: the COCO family (≈12 entries), ImageNet variants (5), CUB (2), Flowers/FGVC, IllusionBench, VQA, SB-Syn(+crop), MNIST derivatives, and the rest.

- [ ] **Step 1: Write failing tests:**
  ```python
  def test_queue_covers_every_candidate_and_family_entry_exactly_once(): ...
  def test_ids_are_stable_across_runs(): ...
  def test_running_the_builder_leaves_registry_bytes_unchanged():     # no identity laundering
  def test_family_link_does_not_change_preview_state():               # Review Focus 6
      assert dataset_row("ms-coco")["preview"] == "none"
  ```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement the builder (read-only over the registry; writes only the report and the queue lines, idempotently — never duplicate an `IR-` ID in the jsonl). **Step 4:** Tests → PASS.
- [ ] **Step 5:** Generate; read the markdown as the human reader would (IDs, one decision per group, no model-confidence language). **Checkpoint** (per D1).

---

### Task 7: SPEC §22.1 acceptance-traceability matrix

**Files:**
- Create: `docs/acceptance-matrix.json`, `scripts/verify_acceptance_matrix.py`, `reports/acceptance_matrix.md`
- Test: `tests/unit/test_acceptance_matrix.py`

**Interfaces:**
- `docs/acceptance-matrix.json`: `{"rows":[{"id","spec_row","condition","pytest":[node ids],"playwright":[spec files],"receipts":[report paths],"note"}]}` for the 16 rows of §22.1: Corpus, Identity, Repeated images, Overlays, Query parity, Scope, Sampling, Retrieval, Detector results, Geometry, Projections, Model context, Tools, Jobs, Publication, Installation.
- `scripts/verify_acceptance_matrix.py [--run]` exits non-zero when a named test node does not exist, or when a row has no test and no receipt; `--run` executes every named node and writes the markdown with pass/fail per row.

- [ ] **Step 1: Write failing tests:**
  ```python
  def test_every_row_names_at_least_one_existing_test_or_receipt(): ...
  def test_a_nonexistent_node_id_fails_verification(): ...
  def test_all_sixteen_spec_rows_are_present(): ...
  ```
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement the script (collect with `pytest --collect-only -q`; map node ids; check files and receipts exist).
- [ ] **Step 4:** Populate the matrix by choosing, for each row, tests that actually assert its acceptance condition (grep `tests/` and `apps/web/e2e/`). A row with no such test is recorded `gap`, and a failing test for it is written in this task. Expected honest entries: Retrieval's "exact results validate approximate indexes" is **not applicable — no approximate index ships** (SPEC §11.4); Installation cites the two clean-install receipts for the current wheel and states optional model packages are not certified by them.
- [ ] **Step 5:** `verify_acceptance_matrix.py --run` → every row passes or is an explicit `not_applicable` with a SPEC citation; write `reports/acceptance_matrix.md`. **Checkpoint** (per D1).

---

### Task 8: Storage toward the 100 GB target

**Files:**
- Create: `reports/storage-reclaim-plan-20261008.json`, `reports/storage-footprint-20261008.json`, `reports/cleanup-summary-20261008.json`
- Modify: `docs/storage.md` only if behavior changes.
- Test: `tests/unit/test_retention.py`, `tests/unit/test_storage_maintenance.py`, `tests/unit/test_columnar_retention.py` (existing).

**Interfaces:**
- Consumes: `atlas storage status|clean|compact|retire-original|retire-repacked|retire-columnar|verify-retired-preview`.
- Produces: allocated bytes below 100,000,000,000, or a measured shortfall with the exact next candidates and what each would cost in retrievability.

- [ ] **Step 1:** `atlas storage status` → record allocated bytes (expect ≈ 122.5 GB incl. the 134 MB `node_modules`).
- [ ] **Step 2:** Build the reclaim plan by **dry run only**: for each candidate (start with `work/sources/*` bodies behind a verified retrieval route and unpinned caches via `atlas storage clean`; then `atlas storage compact` for non-preview images) record bytes reclaimable, retrieval route, protecting references. Review Focus 4: assert in the plan that every candidate lists `referenced_by` = none for frozen selections, protected previews and native retrieval indices; any candidate with a reference is marked `blocked` and excluded. Run `tests/unit/test_retention.py tests/unit/test_storage_maintenance.py tests/unit/test_columnar_retention.py` → PASS before and after.
- [ ] **Step 3:** Present the table (D4). Proceed with deletion only for bodies the table marks verified; never `work/prepared` active/frozen versions, protected previews, native indices/checkpoints, or required model weights (Qwen2.5-VL, SigLIP2, MiniLM, detector weights).
- [ ] **Step 4:** Execute retirements one dataset at a time; after each run `atlas storage verify-retired-preview` and a cold read of three originals through the live media route.
- [ ] **Step 5:** `atlas storage status` again; write the footprint and cleanup receipts including hard-link accounting (shared links reported separately from logical size). If still above 100 GB, say so with the measured gap — the 150 GB ceiling holds regardless.
- [ ] **Step 6: Checkpoint** (per D1).

---

### Task 9: Release closeout with synchronized numbers

**Files:**
- Modify: `reports/dataset_coverage.csv`, `reports/source_access_report.md`, `reports/final-status.json`, `reports/release_evidence.md`, `reports/preview-reproducibility.{md,json}`, `README.md`, `ROADMAP.md`, `docs/storage.md`
- Create: `tests/unit/test_status_consistency.py`, `reports/independent-review-brief-20261008.md`
- Rebuild: `dist/dataset_atlas-<version>-py3-none-any.whl`, sdist (`scripts/build_release.py`)

**Interfaces:**
- Consumes: `scripts/report_prepared_workspace.py`, `scripts/report_reproducibility.py`, `scripts/verify_installation.py`, `scripts/verify_distribution.py`, `atlas publish validate --profile public`.
- Produces: one set of headline numbers (catalogue entries, previews, preview records, complete indices, no-preview count) identical across `final-status.json`, the CSV, README and ROADMAP.

- [ ] **Step 1: Write failing test:**
  ```python
  def test_headline_numbers_agree_across_status_csv_readme_and_roadmap():   # Review Focus 5
      csv_n = summarize_csv(); status = load("reports/final-status.json")
      assert (status["catalogue_entries"], status["tested_local_previews"], status["entries_without_preview"]) == csv_n
      assert str(csv_n[1]) in README_HEADLINE and str(csv_n[1]) in ROADMAP_HEADLINE
  ```
- [ ] **Step 2:** Run → FAIL (or PASS if nothing changed; then keep it as a guard). **Step 3:** Regenerate reports with the scripts above; update README/ROADMAP/status from the generated values, not by hand-typing counts.
- [ ] **Step 4:** Full verification on the final tree: Python 3.12 suite, Python 3.14 suite, `npm test`, `prek run --all-files`, browser suite (Task 1 command), both smoke scripts, `atlas publish validate --profile public` (only CLEVR, PAIRS, EuroSAT approved).
- [ ] **Step 5:** Rebuild wheel + sdist; run `scripts/verify_installation.py` on Python 3.12 and 3.14 and `scripts/verify_distribution.py`; record the new wheel SHA-256 in `final-status.json`.
- [ ] **Step 6:** Remove `apps/web/node_modules` (restorable with `npm ci`) and record that. Re-measure storage.
- [ ] **Step 7:** State limitations plainly: LM Studio/vLLM servers not run this pass (Ollama only); `full_v1_complete` stays **false** while any candidate lacks human-reviewed identity (Task 6 queue), gated sources lack access (D3), or paper-private sets are unreleased; `independent review` of this pass's changes is **not done** until D2 is answered — write the brief (changed files, tests, real datasets exercised, limits) and leave `review_complete` for the prior pass's scope only.
- [ ] **Step 8: Checkpoint** — final commit(s) per D1; if D1 is unanswered, append a dated section to `ROADMAP.md` and leave the tree uncommitted.

---

## Self-review

**Spec coverage.** §4 corpus/identity → Tasks 3, 6 (human review kept human). §5 coverage and blockers → Tasks 2–5, 9. §7.4 adapter tests → Task 4. §8.4 storage → Task 8. §10–14 analysis/providers → Task 1 re-verifies; LM Studio/vLLM stay a reported limitation (Task 9). §17 publication → Task 9. §22 acceptance → Task 7 plus Task 1. §23 deliverables (demo selection, runs, projection, model interaction, analysis pack, limitations report) already exist in `reports/` and `examples/`; Task 9 re-verifies them and states which review is stale. §24 definition of done → end state in Task 9 step 7. No SPEC area is left without an owner.

**Step scan.** Tasks 2, 3, 6, 7, 9 carry test names with assertions and signatures; Tasks 1, 5, 8 are verification/operation tasks with commands and pass conditions. Task 4 is a template because the set of integrable datasets is unknown until Task 3 runs; its admission limits and per-step checks are fixed.

**Type consistency.** `ProbeOutcome`/`probe_url` (Task 2) are the only cross-task code interface; Tasks 3 and 5 consume them by those names. `source_audit_refresh` is the single new evidence kind (Task 3) and Task 6 reads evidence generically.

**Proportion.** ~330 lines against a 1,560-line spec; no function body is written here.

**Honest ceiling.** This plan can close the engineering gaps and refresh evidence. It cannot make `full_v1_complete` true: 95 candidate identities need a person (SPEC §4.5), gates and author requests need the user's own acceptance, and 17 sets are unreleased by their authors.
