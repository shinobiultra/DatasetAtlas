# Browser smoke tests

Run `npx playwright install chromium` once, then `npm run test:e2e` from `apps/web` (or `npm run test:e2e --prefix apps/web` from the repository root). The script builds the public site and tests the published CLEVR pack through catalogue navigation, source filtering, the map, and the linked inspector.

The 10,000-point case uses a generated, clearly synthetic fixture intercepted at `/api/v1/*` by Playwright. It never enters the catalogue or a published pack. The test prints the rendered canvas point count, JavaScript canvas-command duration, pointer-up-to-selection-DOM latency, pointer-up-to-next-animation-frame latency, Chromium version, and browser/host hardware details. These are single-run engineering measurements, not GPU paint timings or dataset-analysis results.

A separate synthetic 10,000-record API fixture checks actual virtualization: bounded card/row DOM counts, 60-record data pages, and image requests only for rendered media. Tables now include thumbnails. The EXIF fixture checks pixel-space detection alignment, missing/failed/zero states, and dimension mismatch. Narrow-screen journeys exercise the catalogue and actions at 390 px and 820 px.

To additionally check evidence receipts, a real COCO detector overlay, and a small VHD H.264 video against a running local workbench, run `ATLAS_LIVE_API=http://127.0.0.1:8765 npm run test:e2e`. Those optional tests make read-only requests to the local API and save receipts in Playwright's ignored `test-results` directory. The VHD test blocks unrelated preview-media requests and fetches only the named 827,837-byte clip; it checks metadata and native playback progress, then records Chromium codec capability for MPEG-4 Visual without fetching the 223 MB control clip. Public catalogue evidence arrays are intentionally empty; the static About check verifies that state and the public source link.


To exercise real computation and image transmission through the rebuilt panels, prepare the local model recipes, start `atlas serve` and the configured local VLM, then run:

```bash
ATLAS_LINKED_JOURNEY=1 ATLAS_ANALYSIS_JOURNEY=1 \
ATLAS_LIVE_API=http://127.0.0.1:8765 \
ATLAS_REIMPORT_SELECTION_ID=selection-3153ec46eb2809fa553c58b3 \
npm run test:e2e --prefix apps/web
```

These opt-ins create saved selections, local detector/embedding runs and a model conversation. They use actual prepared COCO pixels and locally pinned models, not paid APIs. Named baseline overlays are addressed by immutable artifact/run IDs so additional runs do not invalidate the checks. Receipts are written to `reports/browser-analysis-journey.json` and `reports/browser-linked-journey.json`.
