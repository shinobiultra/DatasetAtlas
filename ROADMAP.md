# Remaining implementation roadmap

Updated 2026-09-23. SPEC.md remains the acceptance contract. The complete catalogue-wide request is **not finished**: 333 catalogue entries, 143 with prepared local previews, 190 without previews, and 138 canonical full-population indices. An index covers its explicitly pinned population, not all historical releases or an unidentified paper subset.

Implemented since the UI closeout:

- Native PHANTOM is locally authorized and indexed, with explicit missing-source-media states; all eleven Visual Genome annotation tables are indexed through bounded disk-backed joins. Caltech101, DreamBooth, GVIL, IllusoryVQA, EMNIST, MMBench, T2I-CompBench and further populations now have real preview evidence. Exact native memberships and source defects remain in the acquisition receipts.

- Full TextVQA, VizWiz, ChartQA, HatefulIllusion, OmniSpatial, PMC-VQA V1, Flowers-102, CUB-200-2011 and CIFAR-10-C populations, with bounded original media on request. Exact scope and live evidence: `reports/selective-acquisition-20260923.md`.

- Workbench and CLI preparation plans with explicit download/output budgets, pinned source files, isolated execution, persistent progress, cancellation, resumable downloads, retry, and atomic version activation. Older snapshots remain available to frozen selections.
- A shared Arrow/Parquet shard adapter, official Oxford Pets and DTD adapters, and original-file acquisition recipes. Additional author-linked source releases are planned on request; a source plan is not evidence of tested adapter coverage.
- Full acquired populations for AlgoPuzzleVQA (1,800), IlluChar (4,125), WMDP (3,668), Oxford Pets (7,349), DTD (5,640), CounterFact (21,919), PuzzleVQA (2,000), NaturalBench (1,900), Senator Tweets (99,693), ConceptARC (176), MMMU-dev (150), Waterbirds (11,788), SimpleVQA (2,225), and EXAMS-V (21,291).
- GQA's 132,062 validation-balanced questions now join to the verified complete official image archive, with zero missing referenced images. Other GQA question splits remain outside that snapshot.
- Complete-scope exact filtered similarity beyond 1,000 eligible records, safe-view display derivatives, bounded decoded-media caching, streaming cache checksums, worker CPU/wall-time/RSS limits and verified Linux cgroup memory caps where available.
- Preparation uses a modal. The dataset header adapts to the remaining centre width when both side panels are open, so sample controls remain reachable.
- Every active prepared version is now produced by committed code: `atlas datasets preparation --refresh-metadata` re-derives a completed version's coverage and evidence from its receipt, and `atlas datasets prune` lists or removes failed, duplicate and unreferenced versions (hard-link aware; versions a saved selection references are pinned).

Remaining work:

- **Keep the storage footprint bounded as coverage grows.** The current pass is
  within the requested 50–150 GB range, including configured model weights; 100 GB
  remains the target. Original-quality preview pins, full-dimension AVIF browsing
  copies, a shared on-demand cache, verified ZIP/TAR original retrieval and shared
  preparation admission limits are implemented. Actual receipts are in
  `reports/storage-footprint-native-20260923.json` and
  `reports/retained-media-live-verification.json`. New preparations sample randomly
  over their complete population; older source-order previews still need migration.
  Application admission limits are not a filesystem quota; continue measuring
  external model/cache roots and maintenance output as coverage expands.

1. **Finish acquisition and adapter coverage.** 190 entries still have no prepared preview. Some have executable on-demand plans but are untested; many still lack a format-specific recipe. Accessible remaining examples include additional multimodal benchmarks and large source collections. This is implementation work, not an external access restriction.
2. **Finish exact release reconciliation.** All 64 papers have full-text mention inventories and all 332 canonical corpus groups have research dispositions, but that does not resolve every source, revision, variant, or split. Preserve uncertain identities and source evidence. Do not merge similarly named populations without evidence. The confirmed DTD, Oxford Pets and OK-VQA duplicate IDs have been resolved as aliases; uncertain family/variant references remain distinct.
3. **Support the largest remote releases selectively.** FineVision's native shards total about 4.65 TB; DataComp metadata is about 340 GB. Current acquisition plans enforce available disk space and reject oversized copies. Selective remote Parquet indexing is implemented with real multi-shard verification; catalogue-wide large-source coverage and broader mounted-source setup remain incomplete.
4. **Complete remaining media and release populations.** SVO-Probes and JailBreakV retain media gaps; several existing entries cover selected official splits or representations. ViSU-Text, ZeroBench, Winoground and other actual gates require authorized access. Source uncertainty and access gates do not excuse accessible adapter gaps.
5. **Broaden provider and publication evidence.** Local vLLM image/text/tool integration and LM Studio image/text integration pass. LM Studio capabilities are recorded per tested model; its current model rejects tools, structured output and embeddings. Only the existing CLEVR, PAIRS and EuroSAT public media packs are approved; additional publication requires source-specific review. No remote site deployment has been performed.

Validation and exact acquisition receipts: `reports/on-demand-preparation.json`, `reports/on-demand-live-verification.json`, and `reports/on-demand-implementation.md`. No sub-agents or paid APIs were used for this implementation.
