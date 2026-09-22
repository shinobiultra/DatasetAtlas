My previous mockups preserved the wrong hierarchy: **record IDs, metadata, and provenance dominated; the actual data remained secondary.** Your references make the examples the workspace, with filters and inspectors supporting them.

**I would combine these into one coherent application—not choose one screenshot and force every task into it.** Below is the replacement frontend direction. It preserves the existing functionality and backend contracts, but changes how people reach and use them.

**Paper-specific views are removed entirely.** Source citations can remain in dataset information; they do not get their own browsing mode.

# 1. How the references fit together

The mockup numbers below are the labels on your images.

| App area                      | Main reference                     | What to carry over                                                                                                   |
| ----------------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Dataset catalogue**         | **6 — Projection Drawer**          | Thumbnail-led dataset cards, useful descriptions, persistent faceted filters, compact navigation.                    |
| **Dataset page**              | **1 — Balanced Browser**           | Strong dataset identity, a short summary, immediately visible samples, and a clear route into deeper browsing.       |
| **Dataset overview**          | **8 — Card-Based Workspace**       | A useful combination of sample previews, label distributions, practical information, and notes.                      |
| **Everyday browsing**         | **5 — Table + Preview Hybrid**     | Filters on the left, actual samples in the centre, a large selected-sample preview on the right.                     |
| **Dense analytical browsing** | **7 — Compact Analyst Mode**       | Typed columns, compact rows, column controls, and an unobtrusive status/selection footer.                            |
| **Focused inspection**        | **4 — Focused Inspector**          | A large image, annotation overlays, previous/next navigation, related samples, and structured information beside it. |
| **Comparison**                | **9 — Compare View**               | Two large, equally important examples above aligned annotations and model results.                                   |
| **Embedding exploration**     | **6 — Projection Drawer**, adapted | Its projection controls and selection summary, but with a full-size sample map available as the main workspace.      |

These are **layout and interaction references**, not authoritative dataset records. Counts, licences, sample images, and model scores must come from the actual data rather than being copied from the mockups.

Some elements pictured—paid upgrades, account avatars, “Shared with me”—do not belong in our current application.

---

# 2. One consistent application shell

The app should have a recognisable frame that survives moving between browsing, inspection, comparison, and analysis.

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Dataset Atlas      Search datasets…                       Jobs  Settings  │
├─────────────────┬───────────────────────────────────┬─────────────────────┤
│ Navigation      │ Dataset / collection heading       │ Context panel       │
│                 │ Search · filters · view controls  │                     │
│ Datasets        ├───────────────────────────────────┤ Selected sample     │
│ Collections     │                                   │ OR dataset details  │
│ Runs            │                                   │ OR analysis setup   │
│                 │         Main workspace            │ OR model chat       │
│ Context filters │                                   │                     │
│                 │   Grid / Table / Map / Compare     │                     │
│ Recent datasets │                                   │                     │
├─────────────────┴───────────────────────────────────┴─────────────────────┤
│ Scope / position                     Selection actions, when applicable  │
└───────────────────────────────────────────────────────────────────────────┘
```

### Left: navigation and filters

Use the arrangement in **Mockups 4–6**: a small navigation section, then filters relevant to the current screen.

The navigation should be **Datasets, Collections, Runs**, with Settings below. Recent datasets can appear in a compact lower section.

There is no need for separate “Home,” “Explore,” “Browse,” and “Datasets” destinations that all lead to similar screens.

On the catalogue, filters describe datasets: modality, task, available annotations, access.

Inside a dataset, filters describe its samples: split, labels, image properties, and computed results.

**Do not show both sets of filters simultaneously.**

### Centre: the actual task

The centre is the largest part of the screen. It should contain images, questions, records, plots, or comparisons—not a dashboard of administrative cards.

### Right: one contextual panel

The right panel is **not permanently an About panel**.

Normally, it shows the inspected sample. An explicit action can replace it with dataset details, analysis setup, or model chat. Closing that panel restores the preceding workspace state.

Do not stack several competing drawers or dim the whole application when inspecting something. The browser must remain interactive.

### Search scopes

The header search finds **datasets**. The workspace search finds **samples within the current population**.

Give them different placeholders and positions. Do not make one field silently switch between catalogue search, metadata filtering, vector retrieval, and chat.

---

# 3. Dataset catalogue: borrow Mockup 6

This is the entry screen. It should make someone think:

> “These are the datasets available; I can immediately recognise what kind of data each contains.”

## Layout

Use a persistent filter sidebar and a three- or four-column grid of dataset cards, depending on available width. Offer a compact list alternative.

Each card contains:

* A real representative thumbnail, small contact sheet, or appropriate text/audio/table preview.
* Dataset name and a short description.
* A few useful modality/task tags.
* A compact line describing available browsing coverage.

For example, the last line could say **“100 preview images · Full data available locally”**, provided that is actually true. Do not bury the distinction between reported dataset size and available preview size.

Clicking the card opens the dataset’s samples. The star saves the **dataset**, not an individual example.

## What should not dominate

No giant welcome banner. No global donut chart. No “total storage analysed” statistic unless it helps an actual task. No default projection of the whole catalogue squeezing the cards into half the screen.

The projection drawer from Mockup 6 is a useful optional exploration pattern—not something that should open automatically.

**Use actual dataset media.** A low-resolution dataset should not be represented as though it contained pristine high-resolution stock photography.

---

# 4. Dataset page: combine Mockups 1 and 8

The dataset page should provide context without standing between the user and the samples.

## Compact dataset header

Use the top portion of **Mockup 1**:

```text
[small preview mosaic]  CLEVR
                        Short explanation of what the data contains.
                        Image + text · Visual question answering

                        [current data scope]             [About dataset]
```

Keep the dataset title, summary, and essential scope visible. Put long source descriptions, releases, licences, and technical identifiers behind **About dataset**.

Do not display the same description in the header, an About card, and a permanently open right panel.

## Two main tabs

**Samples** is the default.

**Overview** provides the card-based summary inspired by Mockup 8.

The Overview can contain a sample contact sheet, actual label distributions, useful dataset properties, available computed analyses, and notes. Its purpose is to answer “what is in here?” rather than to decorate the application.

Choose visualisations according to the data. A histogram or label-frequency bar chart may be useful; a donut should not appear just because there is room for one.

Do not render empty cards for unavailable statistics. Offer a small, specific action such as **“Compute image-size distribution.”**

## No extra “workspace” gate

Clicking a sample should immediately inspect it. Selecting Table or Map should change the current workspace.

Avoid a journey of:

> Dataset page → Open → Open workspace → Preview → finally see an image.

The browsing workspace is already open.

---

# 5. Everyday browsing: Mockup 5 is the backbone

**This should be the core interaction model of Dataset Atlas.**

Left: meaningful filters.
Centre: samples in grid or table form.
Right: the selected sample, large enough to understand.

## A. Grid mode for visual discovery

For image datasets, start with a contact sheet of reasonably large previews. For image–question datasets, include the question beneath the image and a clearly labelled answer when the current viewing mode allows it.

Cards should show only a few selected fields. All metadata remains available in the inspector.

Image presentation should preserve the whole image by default. Cropping for visual neatness must not hide the very content the researcher is trying to inspect.

Grid density can be adjustable, but the initial layout should favour **recognisable examples**, not fifty tiny thumbnails.

## B. Table + preview for systematic inspection

Use Mockup 5 almost directly.

A visual-question-answering table might start with:

```text
Select | Thumbnail | Question | Answer | Split
```

A detection dataset might use:

```text
Select | Thumbnail | Labels | People detected | Split
```

Record IDs should be available, but **not consume the first prominent content column by default**.

The right panel shows the selected image, complete question/text, annotations, and optional computed results.

Remove duplicate presentation columns through the dataset’s field mappings. For example, do not show both “Question / text” and an identical “question” column by default. Keep the original source field accessible through the column picker.

## C. Dense table mode for analytical work

Borrow the compactness and typed headers of **Mockup 7** when the user chooses a dense layout or the dataset is primarily textual/tabular.

This mode should have adjustable columns, sortable numeric fields, readable missing values, and an optional inspector.

Compact means more useful rows—not smaller and smaller typography.

## Filtering

Keep commonly used facets visible in the left sidebar. Put less common fields under expandable groups.

For computed fields, the interface should communicate their origin:

```text
Source annotations
Image properties
Person detector · run name
NudeNet · run name
Imported probe results · run name
```

A generic **“Confidence”** filter is too ambiguous. A score should belong to a named output and run.

Applied filters appear as removable chips above the results. Their scope remains visible in one short status line—not several large warning banners.

## Inspection and selection are different

This interaction distinction is important:

**Click a row/card:** inspect it.
**Click its checkbox:** add it to the selected set.
**Open/expand:** enter focused inspection.

Opening ten different examples must not accidentally select ten examples.

When records are selected, reveal a compact action bar:

```text
12 selected    Save selection    Compare    Analyze    Ask model    Export
```

Selecting all visible records and selecting all matching records must be separate, explicit operations.

If some selected records fall outside a new filter, show that fact rather than silently discarding them.

---

# 6. Focused inspector: use Mockup 4

This is for actually looking at the data, not merely checking that a row exists.

## Composition

The main image should occupy most of the available centre area. Keep the right inspector for annotations and metadata. Allow the left filter sidebar to collapse for more space.

Above the media: previous/next controls, position within the current results, and basic viewing controls.

Below the media: relevant text/questions and a filmstrip.

The filmstrip should have an honest label:

**Matching samples** means the current query’s neighbours in browsing order.
**Similar samples** means results from an identified similarity search.

Do not present arbitrary adjacent examples as semantic neighbours.

## Media controls

Provide Fit, actual-size inspection where supported, zoom, and overlay toggles. Offer access to the original and the input representation used by a selected analysis.

A researcher should be able to tell whether they are viewing the original, a thumbnail, a crop, or a processed model input.

## Right-panel structure

Use three consistent sections or tabs:

**Annotations · Model outputs · Metadata**

Keep questions and other primary task content visible near the media rather than burying them in a raw record.

Selecting an annotation highlights its region. Selecting a region identifies the corresponding annotation. Model detections remain separate from source annotations.

Raw JSON belongs in an expandable technical section under Metadata—not in the first screenful.

## Returning to browsing

Closing focused inspection restores the previous grid/table/map, filters, scroll position, and inspected record.

This should feel like looking more closely at something, not navigating away and starting over.

---

# 7. Compare: use Mockup 9

The layout is already strong: **two substantial media panels above aligned information**.

## Top half: A and B

Each side shows the dataset, sample identity, relevant question, and image. Keep both sides visually equal.

Samples are pinned until explicitly replaced. Changing a filter must not silently replace one side of the comparison.

Allow independent navigation, with an optional linked mode for an actual paired dataset.

For clean/adversarial or original/edited pairs, show the relationship explicitly. For arbitrary examples, simply show A and B.

## Bottom half: aligned evidence

Use the same vocabulary as the inspector:

**Annotations · Model outputs · Metadata**

Align comparable fields across the two sides, with an optional **Differences only** toggle.

A model score must identify its run. Differences should only be computed for meaningfully comparable values—not between two unrelated scores that happen to be numeric.

## Pair-specific tools

For compatible aligned image pairs, expose blink, wipe, or difference-image inspection.

Do not show a pixel-difference tool as though it were meaningful for unrelated scenes.

“Ask about these two” should open model chat with A and B attached, while preserving the comparison.

The default remains two examples. Do not begin with a complicated multi-panel comparison manager.

---

# 8. Projection and embeddings: adapt Mockup 6 deliberately

The reference shows a projection beside the catalogue. **For our main research workflow, I would change the object being projected: samples, not dataset cards.**

Mapping dataset descriptions could be a separate later feature.

## Quick projection drawer

The drawer pattern is useful for a quick look at an existing projection, its legend, and the current selection. Include an **Expand** action.

## Full map workspace

For serious exploration, the projection belongs in the centre:

```text
┌────────────────────────────────────────────────────────────────┐
│ Projection: [existing run]    Colour by: [field]    [Create…]     │
│ Scope: current embedding population / displayed subset         │
├──────────────┬──────────────────────────────┬───────────────────┤
│ Filters      │                              │ Selected sample   │
│              │        Large projection      │ or selection      │
│              │                              │ summary           │
│              │                              │                   │
├──────────────┴──────────────────────────────┴───────────────────┤
│ Selected examples: actual thumbnails / text previews            │
└────────────────────────────────────────────────────────────────┘
```

The map should use most of the working area. A tiny decorative scatterplot is not sufficient for inspecting clusters and outliers.

## Linked behaviour

Click a point to inspect its sample. Lasso points to select them. Open that selection in Grid or Table without losing its identities.

Changing the colour field must not recompute the embedding or projection.

Filtering can hide or fade points. **Refit on this selection** is a separate action.

The colour selector includes source labels, detector results, quality properties, cluster assignments, and imported mechanistic signals. Each field retains its origin.

A selection summary should show computed counts and distributions, with representative examples. It should not automatically invent an AI-written explanation of what the cluster “means.”

If the map displays a subset, state that plainly.

---

# 9. Features not pictured: extend the same patterns

The following are proposed additions for the functionality we already specified, rather than features directly shown in your references.

## A. Running detectors and other analyses

Use a right-side **Analyze** panel launched from the current selection or population.

Its initial structure should be:

```text
Analyze 100 images

Analysis
[Detect objects / NudeNet / Embed / Project / Cluster / Import…]

Input
[Original images]
[Current selection]

Model or recipe
[Choose…]

Output
[Human-readable run name]

Estimated resources and coverage
[Run analysis]
```

Reveal specialised controls after choosing the operation. Do not show every embedding, detector, and projection parameter in the same form.

For a projection, choose an existing embedding run or explicitly create one. For a detector, show the relevant model/input settings.

After completion, the result becomes available in the existing column picker, filters, inspector, and map colour selector.

**NudeNet does not get its own mini-application.** It adds inspectable boxes and derived fields to the same browsing experience.

Uncomputed, failed, and completed-with-no-detections remain visually distinct.

## B. Asking a model

Reuse the right-panel pattern for **Ask model**, leaving the selected examples visible.

At the top:

```text
Attached: 3 samples
Provider: [configured endpoint]
Mode: Explore / Evaluate
Context: Images · Questions · Selected outputs
[Review what will be sent]
```

Then the conversation.

The context review must make it clear whether labels, captions, filenames, or detector results are included.

A text-only model gets a visible **“No image input”** indication. It can work from selected textual evidence without pretending it saw the images.

Answers contain clickable sample references that open the ordinary inspector.

Tool-assisted search can be enabled through a clear scope control such as **This selection / Search this dataset**. Tool activity is expandable, not displayed as a wall of technical logs.

Starting expensive jobs or transmitting additional data remains an explicit user action.

## C. Runs

Use a straightforward list:

```text
Run name | Analysis | Input population | Status | Coverage | Actions
```

Clicking a completed run opens its results in the relevant existing workspace: detector columns in the browser, coordinates in Map, model responses in their inspector.

A small job indicator provides progress without replacing the page. No giant operational dashboard is needed.

## D. Collections

A collection is a saved dataset list or a saved set of examples, with a name and optional notes.

Show a contact sheet, the dataset identities involved, and a count with its unit. Opening it uses the same browser.

Saving a collection should not imply cloud hosting or collaboration infrastructure. Sharing can begin with an explicit export.

These are user-created collections—not paper-specific views under another name.

## E. Settings and sources

Use a simple settings screen with **Data sources, Models, Storage, Appearance**.

Data sources show configured local/remote locations and access status. Models show configured endpoints and tested capabilities. Storage shows cache usage and cleanup controls.

Do not expose these settings in every dataset toolbar.

## F. About dataset

This is where the previous implementation’s metadata belongs.

Use a concise summary, useful counts, source links, access information, and licences. Put release hashes, source receipts, and raw manifests in expandable technical details.

Preserve the evidence; **stop making it compete with the examples**.

---

# 10. Visual language to carry through all screens

The references share a fairly specific visual direction: **blue selection states, neutral surfaces, compact controls, clear panel divisions, and generous media areas**.

I would use the following as proposed starting values, not measurements extracted from the screenshots:

| Element            | Direction                                                                          |
| ------------------ | ---------------------------------------------------------------------------------- |
| Background         | Very light neutral grey; white working surfaces                                    |
| Sidebar            | Slightly differentiated neutral surface                                            |
| Accent             | One clear blue for primary actions and selected states                             |
| Annotation colours | Additional colours only where they distinguish labels/outputs                      |
| Typography         | System sans-serif; approximately 14 px primary UI text and 12–13 px secondary text |
| Dataset heading    | Approximately 26–28 px, not an oversized marketing heading                         |
| Navigation width   | Around 220–240 px, collapsible                                                     |
| Inspector width    | Around 340–400 px, resizable                                                       |
| Controls           | Consistent 32–36 px desktop height                                                 |
| Dense rows         | Around 36–44 px; thumbnail rows taller                                             |
| Corners            | Modest 8–12 px rounding                                                            |
| Dividers           | Fine, quiet separators rather than borders around everything                       |
| Shadows            | Reserved mainly for floating controls and drawers                                  |
| Spacing            | Consistent small spacing scale, with larger separation between functional sections |

**The important density rule:** compact chrome, readable data, large enough media.

Do not recreate the earlier green tint, oversized blank cards, or endless rounded containers. Do not add fake macOS window controls inside the website.

Keep the identity and component styling consistent. The app should not acquire a different logo, navigation scheme, or button treatment when switching to Compare.

---

# 11. Interaction rules that make the visual design work

These should be part of the frontend contract, not postponed as polish.

**View switching preserves state.** Grid, Table, and Map share the current population and selection.

**Inspection does not change selection.** Clicking through examples should be safe.

**One contextual panel at a time.** Inspector, About, Analyze, and chat reuse a slot rather than accumulating.

**Dataset information and sample information remain distinct.** The right panel must identify which it is showing.

**Scope is compact but always accessible.** Use a concise status line and expandable explanation, not permanent paragraphs of warnings.

**Missing data gets a useful state.** “Original image unavailable—showing cached preview” is better than a blank card. “No projection yet—create or load one” is better than an empty plot.

**Unavailable capabilities get an explanation.** A public viewer may inspect published results without being able to run a model. The interface should explain the relevant limitation when needed, not fill the screen with disabled controls.

**Keyboard navigation works.** Previous/next, open inspection, close panel, and selection actions should work without a mouse. Search shortcuts should match the user’s platform.

**The layout adapts rather than crushes.** When space is insufficient, collapse filters or convert the inspector to a drawer. Do not shrink the central image to preserve three permanent columns.

---

# 12. How I would direct the implementation agents

This should be a **frontend restructuring**, not another backend rewrite or a superficial theme change.

| Step                                            | Deliverable                                                                                                               |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **1. Establish the shell**                      | Shared typography, spacing, blue accent, navigation, toolbar, resizable panels, and status/selection bar.                 |
| **2. Fix one real browsing workflow**           | Use the existing CLEVR data: actual image previews, one question column, answers, useful filters, and a sample inspector. |
| **3. Add the catalogue and dataset overview**   | Apply the card and summary patterns from Mockups 6, 1, and 8.                                                             |
| **4. Complete inspection and comparison**       | Focused media view, annotation overlays, A/B comparison, and preserved navigation state.                                  |
| **5. Integrate existing analysis capabilities** | Map, detector outputs, analysis setup, model chat, Runs, and settings within the same shell.                              |
| **6. Validate against the references**          | Review screenshots at normal desktop sizes using real records, including missing-data and loading states.                 |

The first milestone should not be “every screen has prettier cards.” It should be:

> **Open CLEVR → see images immediately → filter examples → inspect a full image and question → move to the next example → select two → compare them.**

Then test a text-only dataset, an annotation-heavy dataset, and a dataset with model outputs. That will establish whether the design is reusable rather than merely a polished CLEVR demo.

### Copyable frontend-agent brief

```text
Use the seven user-supplied mockups as the visual and interaction references.

Primary synthesis:
- Mockup 6: catalogue cards and faceted sidebar.
- Mockup 1: dataset header and samples-first dataset page.
- Mockup 8: optional dataset overview content.
- Mockup 5: default table/grid + sample-preview browsing.
- Mockup 7: dense analytical table mode.
- Mockup 4: focused media inspector.
- Mockup 9: A/B comparison.

Use one consistent application shell and component system.
Preserve existing backend contracts and real functionality.

Prioritise actual media, questions, annotations, filters, and inspection.
Do not place raw IDs, JSON, release hashes, or source receipts in the
primary visual hierarchy.

Use a neutral, blue-accented design matching the supplied references.
Do not reuse the earlier green mockups as the design foundation.

Keep dataset information separate from sample inspection.
The right panel normally inspects the selected sample; About, Analyze,
and Ask model replace it only when explicitly opened.

Inspection and bulk selection are different interactions.
Preserve query, selection, and scroll state across views.

Do not copy illustrative counts, licences, predictions, or stock images
from the mockups into real dataset records.
Do not invent scores or show unscoped "Confidence" columns.

Paper-specific views are removed completely.
Do not introduce account, subscription, upgrade, or cloud-sharing UI.

Build and review the real browsing-to-inspection-to-comparison flow
before expanding the rest of the interface.
```

**The resulting product should feel like Mockup 5 while browsing, Mockup 4 while examining something closely, and Mockup 9 while comparing—not like a metadata administration page with an image viewer attached.**

