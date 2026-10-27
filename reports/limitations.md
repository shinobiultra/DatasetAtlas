# Source scope, rights and interpretation

The release's software verification applies to the supported catalogue and the declared
source populations. Each dataset's release, snapshot, local preview and local index
scope are listed in [dataset_coverage.csv](dataset_coverage.csv); source pins and
population descriptions are in [catalogue-sources.json](catalogue-sources.json).

- A source release identifies available data. Paper mentions do not prove the exact
  historical experiment subset, and automated checks do not confer human or scientific
  acceptance. The registry retains those qualifications separately.
- A preview is bounded and its sampling declaration remains attached. A complete local
  index means its declared native partition can be counted and queried; it does not
  promise that every referenced media file is available or licensed for redistribution.
- FineVision and the SmolLM2 training mixture use pinned whole-source sampling populations. Their bounded
  previews and explicitly budgeted additional samples do not create complete local
  query indices for their multi-terabyte sources. Global source totals describe the
  sampling population, never the number of locally indexed examples.
- PATA retains released labels, captions and third-party image URLs as native metadata.
  Its URL list does not establish availability or redistribution rights for the images.
  MultiTrust preserves heterogeneous native task units and linked conditions; a source
  unit is not automatically one image or one question.
- The activation collection retains each native neuron's ordered original activation
  strings. Column positions do not supply ImageNet image identities.
- Public media is limited to the exact approved CLEVR, EuroSAT and PAIRS previews.
  Other locally prepared data remains subject to its own publisher terms and access.
  Gated access is distinct from permission to publish.
- Optional analysis and model conversations require explicitly installed dependencies,
  weights or a configured local provider. Browsing requires no GPU. Context approval
  states what a model receives; no external model is connected automatically.

The catalogue preserves original source material. Browsing derivatives and analysis
outputs do not replace canonical originals. Release evidence reports the checks that
were actually run; source rights and paper-use qualifications are not software failures.
