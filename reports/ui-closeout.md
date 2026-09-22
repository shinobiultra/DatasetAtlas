# UI release closeout — 2026-09-22

PR #1's rebuilt interface now passes its outstanding live workflows. No sub-agents were used for this closeout.

- **Ask model:** real COCO JPEG selected, context reviewed, sent to local Qwen2.5-VL-3B, response saved, then selection exported and re-imported. The refreshed [receipt](browser-linked-journey.json) identifies the image SHA-256, selection, snapshot, conversation, and immutable detector/embedding artifacts. This proves transport and persistence, not answer quality.
- **Analyze:** one real COCO record estimated and submitted through the panel to `detect.coco_v1` and `embed.siglip2`; both completed with one successful record and zero failures. [Run receipt](browser-analysis-journey.json). An explicit Refresh results action adds completed artifacts to the current view without silently changing a frozen query when a background run finishes.
- **Responsive:** real public catalogue filtering, sample selection, analysis-panel access and navigation pass at 390 px and 820 px. Navigation and filters start closed on narrow screens; catalogue filters have a close control; selection actions scroll within the status bar.
- **Metadata-only records:** their full About panel now opens and closes. Candidate records are no longer incorrectly called resolved.
- **Repeatable checks:** named overlay assertions use immutable run/artifact IDs, rather than assuming only one detector run exists. The model journey's projection locator is exact so it does not also match the accessible canvas label.
- **CI:** source acceptance checks explicitly skip absent optional acquisitions in clean environments; all content/hash assertions still execute when those inputs are installed. The 1,000-image cancellation/retry check waits up to 60 seconds for recovery on slower CI hardware, without weakening its preservation assertions.

## Validation

191 Python tests and 22 frontend tests passed locally. All 27 browser checks passed with the live API, actual analysis and local model opt-ins enabled: no browser skips. A copied clean checkout without ignored data passed 159 Python tests and skipped 32 optional acquired-source checks; those checks passed locally. Clean-checkout public publication produced 336 catalogue records and the three approved preview packs. The refreshed [installation receipt](installation-verification.json) records packaged startup separately.

## Remaining scope

Dataset support is still 336 catalogue entries and 64 local previews; remaining adapters, exact-release research, public rights and LM Studio validation stay in [ROADMAP.md](../ROADMAP.md). GQA's stalled full image download was resumed and completed at 21,817,965,542 bytes with SHA-256 `02ce5c49c793accd5305356de9c39a50f80a7aaac193b0203de30dbbc65bde62`. This acquisition does not upgrade the existing partial-media browsing snapshot; the join and snapshot conversion remain explicit work. No remote deployment or paid API was used.
