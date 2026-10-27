# Interface architecture

The frontend is a single application shell that survives moving between browsing,
inspection, comparison and analysis. It follows the [shared contracts](contracts.md): native examples form the
workspace, supported by filters, inspection, provenance and explicit population scope.

## Shell

```
┌──────────────────────────────────────────────────────────────────┐
│ Dataset Atlas   Search datasets…                     Public/Work  │  topbar
├───────────┬──────────────────────────────┬───────────────────────┤
│ Datasets  │ Dataset heading · tabs        │ Context panel         │
│ Collectio…│ Toolbar · filter chips · scope│  Sample inspector     │
│ Runs      ├──────────────────────────────┤  or About dataset     │
│           │                              │  or Analysis          │
│ Filters   │  Grid · Table · Map · Compare │  or Ask model         │
│           │                              │                       │
├───────────┴──────────────────────────────┴───────────────────────┤
│ Scope / position                        Selection actions         │  statusbar
└──────────────────────────────────────────────────────────────────┘
```

Three rules keep this stable:

- **The header search finds datasets; the workspace search finds samples.** They
  have different placeholders and positions and never swap meaning.
- **Exactly one contextual panel is open.** Inspector, About, Analyze and Ask model
  share one slot. Closing About returns to the sample it replaced.
- **The status bar is owned by the app grid**, so it always spans the window. The
  dataset workspace renders its selection bar into that host through a portal.

## Files

| Area | Location |
| --- | --- |
| Design tokens and stylesheets | `src/styles/{tokens,base,shell,views}.css` |
| Primitives, icons, media | `src/ui/` |
| Hash router, formatting, hooks | `src/lib/` |
| Catalogue | `src/catalogue/CataloguePage.tsx` |
| Dataset workspace and its views | `src/dataset/` |
| Contextual panels | `src/panels/` |
| Runs, Collections, Settings | `src/pages/` |

`src/dataset/model.ts` holds the shared workspace vocabulary: the filter clause
shape, the accumulating pager, detector run states, and the scope summary.

## Interaction contract

| Gesture | Effect |
| --- | --- |
| Click a card or row | Inspect it in the context panel. Never changes the selection. |
| Tick its checkbox | Add it to the selection. Never changes what is inspected. |
| Open / double-click / <kbd>Enter</kbd> | Focused inspection takes the centre. |
| <kbd>/</kbd> | Focus the record search. <kbd>j</kbd>/<kbd>k</kbd> move, <kbd>x</kbd> selects, <kbd>Esc</kbd> closes the panel. |

Grid, Table and Map share one population, one selection and one set of filters.
Closing focused inspection restores the previous view and its scroll position.
Selecting every loaded record and selecting every matching record are separate,
explicitly labelled actions, and the second is refused above a stated limit
rather than silently truncated.

## Honesty rules the interface enforces

These are not presentation choices; the components implement them.

- **Coverage is stated per deployment.** `coverageState()` in `src/lib/format.ts`
  answers "what can *this* build show?". A public build never repeats the
  workbench's preview claim; an entry prepared locally but not published reads
  "Metadata only here — a preview exists in the local workbench".
- **Availability and publication are separate.** The retained catalogue has working
  native source paths. A fresh workspace may still need source access or preparation;
  a static build may expose only metadata because the native data is not approved
  for publication. The interface states that reason and the available action.
- **Detector outcomes stay distinct.** Not computed, failed, partial, completed with
  detections and completed with none are five different states, each rendered with
  its run label and extraction threshold beside the media it describes.
- **Box overlays are geometry-checked.** The overlay SVG is pinned to the same
  rectangle as the image and letterboxes identically; when a detector's input size
  differs from the displayed representation the boxes are hidden and the mismatch is
  named. See `e2e/media.spec.ts`.
- **Counts name their population.** The scope line and every overview chart state
  the unit, the scope and the matched count, and report missing values separately.
  Sampling is never applied to a population count.
- **The filmstrip distinguishes "matching samples"** (browsing order) from a
  similarity result, which requires a named embedding run.
- **Comparison only compares comparable values** — present on both sides with the
  same type — and says when no relation between A and B is recorded.

## Performance

Grid and table are virtualized: only the visible window exists in the DOM, and
media is requested for what is on screen. Paging is automatic on scroll; the map
pulls its whole population up to a plotted-point ceiling because a projection is
only meaningful over the population it covers.

The browser tests use explicit 10,000-record/point synthetic fixtures to measure
DOM size, media requests, canvas commands and selection-to-next-frame latency.
Results include browser and hardware metadata and live in ignored test output.
They are engineering measurements, not GPU paint timings or native dataset
coverage. See the [browser checks](../apps/web/e2e/README.md) and the
[current release evidence](../reports/release_evidence.md).

The dataset header's Results picker chooses which named runs join browsing queries.
It starts with source data alone and permits up to 32 result snapshots at once.
Older runs remain selectable regardless of total history. Turning a run off clears
its dependent filters, sort and colour; detector inspection and projection selection
can still inspect all compatible runs. This prevents accumulated history from
breaking unrelated source browsing or silently choosing an arbitrary subset of runs.
