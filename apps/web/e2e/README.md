# Browser checks

Install Chromium once with `npx playwright install chromium`, then run from the
repository root:

```bash
ATLAS_PYTHON="$PWD/.venv/bin/python" npm --prefix apps/web run test:e2e
```

The suite builds the approved public site and starts a fresh local workspace for
preparation/setup journeys. The public paths exercise real approved previews.
Separate, clearly synthetic fixtures test 10,000-point maps, eligible-point
selection, long-grid/table virtualization, narrow layouts and media geometry.
Synthetic fixtures never enter the catalogue or publication packs.

Performance receipts state the rendered population, canvas-command duration,
pointer-to-selection/next-frame latency, browser and host details. They are
single-run engineering measurements. Screenshots, traces and test artifacts are
kept under ignored Playwright output; they are not public release receipts.

## Optional native journeys

For read-only checks against a prepared local workspace:

```bash
ATLAS_LIVE_API=http://127.0.0.1:8765 npm --prefix apps/web run test:e2e
```

These checks require the named native snapshots and artifacts. Media reads use the
local API and its source rules. A missing optional source or run is an explicit
skip, not a successful native check.

Computation and model-transmission journeys need separate explicit opt-ins:

```bash
ATLAS_ANALYSIS_JOURNEY=1 ATLAS_LINKED_JOURNEY=1 \
ATLAS_LIVE_API=http://127.0.0.1:8765 \
ATLAS_LINKED_PROVIDER=YOUR_CONFIGURED_LOCAL_PROVIDER \
npm --prefix apps/web run test:e2e
```

Prepare pinned local model recipes and start the intended local provider first.
These opt-ins create saved selections/runs and send approved context to that local
provider. Existing immutable artifacts used by a journey are not freshly recomputed
unless the test explicitly starts a run. Historical model output retains its exact
snapshot and provenance; it does not prove a service is currently available.

Set `ATLAS_REIMPORT_SELECTION_ID` to an existing local selection to exercise the
repeat-import path without a model request. Keep detailed receipts and source data
in ignored workspace/test output. [Release evidence](../../../reports/release_evidence.md)
contains only the verified aggregate release summary.
