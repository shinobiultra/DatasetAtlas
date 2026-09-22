# Remaining implementation roadmap

Updated 2026-09-22. SPEC.md remains the acceptance contract. The complete catalogue-wide request is **not finished**: 333 catalogue entries, 79 with real local previews, 254 without previews, and 74 canonical full-population indices. An index covers its explicitly pinned population, not all historical releases or an unidentified paper subset.

Implemented since the UI closeout:

- Workbench and CLI preparation plans with explicit download/output budgets, pinned source files, isolated execution, persistent progress, cancellation, resumable downloads, retry, and atomic version activation. Older snapshots remain available to frozen selections.
- A shared Arrow/Parquet shard adapter, official Oxford Pets and DTD adapters, and original-file acquisition recipes. Additional author-linked source releases are planned on request; a source plan is not evidence of tested adapter coverage.
- Full acquired populations for AlgoPuzzleVQA (1,800), IlluChar (4,125), WMDP (3,668), Oxford Pets (7,349), DTD (5,640), CounterFact (21,919), PuzzleVQA (2,000), NaturalBench (1,900), Senator Tweets (99,693), ConceptARC (176), MMMU-dev (150), Waterbirds (11,788), SimpleVQA (2,225), and EXAMS-V (21,291).
- GQA's 132,062 validation-balanced questions now join to the verified complete official image archive, with zero missing referenced images. Other GQA question splits remain outside that snapshot.
- Complete-scope exact filtered similarity beyond 1,000 eligible records, safe-view display derivatives, bounded decoded-media caching, streaming cache checksums, worker CPU/wall-time/RSS limits and verified Linux cgroup memory caps where available.
- Preparation uses a modal. The dataset header adapts to the remaining centre width when both side panels are open, so sample controls remain reachable.
- Every active prepared version is now produced by committed code: `atlas datasets preparation --refresh-metadata` re-derives a completed version's coverage and evidence from its receipt, and `atlas datasets prune` lists or removes failed, duplicate and unreferenced versions (hard-link aware; versions a saved selection references are pinned).

Remaining work:

1. **Finish acquisition and adapter coverage.** 254 entries still have no prepared preview. Some have executable on-demand plans but are untested; many still lack a format-specific recipe. Accessible examples include CUB, ChartQA, and additional multimodal benchmarks. This is implementation work, not an external access restriction.
2. **Finish exact release reconciliation.** All 64 papers have full-text mention inventories and all 332 canonical corpus groups have research dispositions, but that does not resolve every source, revision, variant, or split. Preserve uncertain identities and source evidence. Do not merge similarly named populations without evidence. Two pairs are the *same* release under two catalogue IDs with byte-identical recipes — `dtd`/`describable-textures-dataset` and `oxfordpet`/`pets` — and should be resolved as aliases rather than prepared twice.
3. **Support the largest remote releases selectively.** FineVision's native shards total about 4.65 TB; DataComp metadata is about 340 GB. Current acquisition plans enforce available disk space and reject oversized copies. Selective remote Parquet reads, remote indexing, and broader mounted-source setup still need integration with this preparation workflow.
4. **Complete remaining media and release populations.** SVO-Probes and JailBreakV retain media gaps; several existing entries cover selected official splits or representations. ViSU-Text, ZeroBench, Winoground and other actual gates require authorized access. Source uncertainty and access gates do not excuse accessible adapter gaps.
5. **Broaden provider and publication evidence.** Local vLLM image/text/tool integration passes. LM Studio is not live-tested. Only the existing CLEVR, PAIRS and EuroSAT public media packs are approved; additional publication requires source-specific review. No remote site deployment has been performed.

Validation and exact acquisition receipts: `reports/on-demand-preparation.json`, `reports/on-demand-live-verification.json`, and `reports/on-demand-implementation.md`. No sub-agents or paid APIs were used for this implementation.
