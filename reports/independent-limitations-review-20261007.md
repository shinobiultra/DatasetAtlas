# Independent limitations review — 2026-10-07

Initial review checkpoint: 2026-10-07 05:44 UTC (14:44 JST). The later addendum below supersedes its open items where explicitly closed. Reviewer: one authorized `gpt-6.1-sol` agent using `xhigh` reasoning. This is a scoped review of the shared working tree, not a release attestation. The lead still owns the combined-tree checks, packaging, status reconciliation and release evidence.

## Scope and privacy boundary

I read contributor instructions, SPEC acceptance and release requirements, shared contracts, ROADMAP, implementation code, synthetic tests and aggregate receipts. I did not inspect original dataset records, native source inventories or annotation lines, prepared native records, media, underlying corpus files/PDFs, model conversations, browser pixels/DOM or traces. One later registry-configuration read exposed embedded corpus-mention excerpts; this scope deviation was reported to the lead, and those excerpts were not used or reproduced in findings. Further registry inspection uses whitelisted configuration fields. I acquired no sources, spawned no further agents and edited no implementation or shared documentation. Native integrity statements below are attributed to aggregate receipts, not independent inspection of native content. The preceding [2026-10-06 review](independent-limitations-review-20261006.md) remains historical evidence with its failures and limitations intact.

## Outcome of the final requested code review

The retained-result regression is repaired at this checkpoint. `registry/artifacts.py` searches active and retained version packs; the API discovers an old result after a newer snapshot becomes active; the read-only worker searches only approved datasets/snapshots when bindings exist. Conflicting immutable contents under one result ID are refused. A synthetic old/new version test resolves and aggregates the old result in `s1`, then refuses it when the approved record binding is changed to `s2`. Direct invocation of the production API endpoint functions independently confirmed the old-result lookup and exact frozen-context join while `s2` was active. This was an endpoint-function check with zero provider requests, not an HTTP transport or browser check.

I found a resource regression during this recheck: the retained index read a complete pack before applying its encoded-artifact cache limit, bypassing the existing interactive pack size guard. A sparse synthetic file of 100,000,001 bytes and a patched `Path.read_bytes` proved the read was reached before refusal, without allocating or reading the large body. The lead added a pre-read 100 MB guard; the new refusal regression passes. The same stat guard is now present in the direct metadata pack loaders in `api/tools.py` and `providers/tool_worker.py`.

The final `storage/video.py` repair checks actual decoded AVI frames instead of trusting frame-count headers. It incrementally drains capped stdout/stderr, counts frame receipts, enforces frame/pixel/timeline ceilings, and counts decoded 16-bit PCM bytes for audio. Decoder input permits only local file/pipe protocols. Cancellation and absolute deadlines are polled while pipes are open and after pipe EOF; failure kills and reaps the subprocess group. The generated 10,001-frame AVI with forged one-frame headers is refused. A generated child that closes both pipes before sleeping is cancelled before its delayed marker write. Display rendering verifies exact decoded frame parity; its final MP4 probe receives the rendering deadline and cancellation callback. The stated audio proof is native MP3/AAC packet copying, not an independent waveform or perceptual equivalence result.

Preparation dataset leases now carry a plan ID. Status recovery accepts a held lease only for the queried plan, or the explicit legacy PID fallback. A different plan for the same dataset no longer keeps a dead preparation falsely running. The corrected readable lease mode preserves a live writer whose PID is invisible to the observer. Both synthetic regressions pass.

### Independent tests and retained failures

The final independently run subset was:

```text
.venv/bin/python -m pytest -q \
  tests/unit/test_retained_artifact_lookup.py \
  tests/unit/test_ucf101.py tests/unit/test_archive_variants.py \
  tests/unit/test_preparation.py::test_running_writer_lease_survives_an_invisible_pid \
  tests/unit/test_preparation.py::test_another_plan_lease_does_not_keep_a_dead_plan_running \
  tests/unit/test_conversation_jobs.py \
  -k 'not discoverable and not actual_provider_socket and not completed_async_job_api'
```

Result: **20 passed, 3 deselected, 2 dependency warnings in 2.02 s**. This includes generated real FFmpeg clips, header-forging refusal, process cancellation after EOF, retained-result aggregation/version refusal, conflicting result IDs, the oversized retained-pack guard, plan-specific leases and provider probe/admission regressions. Separate direct endpoint-function checks passed retained-result lookup and frozen-context joining.

Preserved intermediate failures matter:

- The first retained-result worker run returned record metadata correctly but failed its assertion for prediction value `42` (**18 passed, 1 failed, 3 deselected**). `get_records` intentionally returns record metadata. The corrected test uses the registered prediction field through `aggregate`; it passes.
- An earlier lease repair used a write-only handle for reading lease ownership; the matching-live-plan test failed (**16 passed, 1 failed, 2 deselected**) before the handle was changed to readable append mode. The final lease tests pass.
- The original AVI header and post-EOF cancellation defects were demonstrated with generated fixtures before repair. Their passing regressions do not erase the earlier defects.
- This reviewer's sandbox forbids listening sockets. The real loopback provider cancellation test could not start its server; API/TestClient execution also hung in this environment. Those checks are deselected here, not represented as independent passes. Production socket, HTTP and browser behavior requires the lead's current receipts.

The lead's current focused log is [retained-results-and-native-regressions-final-20261007.log](../work/retained-results-and-native-regressions-final-20261007.log). It had no completed pytest summary when inspected at this checkpoint. The independently observed 20-test result above therefore stands separately.

## Other software findings reviewed today

| Boundary | Reviewed correction and practical limit |
| --- | --- |
| Model context and result fields | Explicit selected result IDs join by compatible snapshot/unit; dotted registered prediction fields resolve; initial context and outgoing approved tools retain frozen record versions. An unrelated compatible group may remain a native record when no selected result applies. |
| Detector threshold views | Counts deduplicate original image SHA; extraction and display thresholds are separate. Threshold views transform existing detections and do not establish new detector accuracy. |
| Registered imported vectors | Loading recomputes space/schema/dimension/unit/normalization and subject bindings; float32-overflow inputs are refused while raw imported values remain preserved. Retrieval and downstream analyses use explicitly registered compatible spaces. This does not make arbitrary external vectors scientifically comparable. |
| Conversation jobs | Admission is shared by probes, synchronous calls and jobs; cancellation/deadlines apply to internal and cross-process lock waits; terminal receipt-write failures release slots; shutdown cancels tracked jobs. UI polling retries after transient failures. |
| Probe races | Provider revision/CAS prevents a late probe from restoring an older configuration. Synthetic admission and configuration-race checks pass. |
| Selected tool results | Approved result allowlists, run bindings, snapshot/unit compatibility and declared subjects are checked. Production metadata tools execute in a bounded disposable process; arbitrary injected test backends retain a separate legacy fallback. |
| Publication | The API uses an approved fixed profile/output and a build lock. Publication permission remains file- and dataset-specific; accessible native sources do not acquire redistribution approval. |
| UCF101 and archive variants | Synthetic joins preserve three folds and class labels; unexpected/duplicate split rows refuse. Annotation count/size limits precede expansion; directory/subtree pins bind the chosen mirror. Native-source equality to an official release or historical paper population is a separate unresolved inference. |

Earlier detector/import checks independently passed **19 tests** with two integration tests deselected; earlier job cancellation/cleanup checks passed their scoped synthetic subsets. These are feature-boundary checks, not a claim that today's complete frontend, package and acceptance matrix have all been rerun.

## Remaining actionable implementation and release work

1. **Bound retained history as a whole.** The 64 MB setting limits encoded cached artifact residency. It does not bound Python RSS, total results returned from all versions/jobs or `/artifacts` response size. Selected-result lookup currently loads the global retained artifact collection before selecting IDs. Add snapshot/ID-specific lookup and measured pagination or an aggregate response ceiling before claiming a whole-request or whole-history memory ceiling. The new 100 MB guard closes the individual-pack read regression, not this broader resource limit.
2. **Reconcile and attest the combined final tree.** Final full Python/frontend/browser checks, wheel/source identity and clean-install evidence must cover the source after today's features and repairs. Historical installation/browser successes cannot certify the newer tree. The visible final-status and ROADMAP checkpoints still mix dated evidence with subsequently added capabilities; synchronization is ordinary remaining release work, not an external blocker.
3. **Complete source-to-active-preview proof where only acquisition exists.** German Spoken Wikipedia indexing is now reported complete, but that does not prove all-language joining, activated audio previews or browser playback/seek. Require the preparation snapshot, measured original memberships and current API/browser receipt before closing that item. Newly integrated public mirrors likewise need their scoped activation and original-byte receipts; complete annotation indexing alone does not mean every referenced media original is present.
4. **Keep source implementation separate from access.** Planned or missing public recipes, native format support, bounded acquisitions, adapter joins and performance proof remain software/execution work where sources are available. Gated licensed access, publisher-unreleased sources and human rights decisions are separate blockers. Exact historical release/subset reconciliation is often a scientific or identity decision, not an acquisition failure.

No additional severe defect was reproduced in the repaired video, retained-result identity/snapshot lookup or plan-lease scope. This is a bounded review conclusion; it does not certify every adapter, every stored artifact or adversarial native population.

## Coverage, reproducibility and storage: dated evidence only

The synchronized **02:13–02:14 UTC Oct7** receipts report 333 catalogue entries, 212 prepared previews, 20,732 preview records, 209 declared complete-scope indices and 121 entries without previews. They retain `full_v1_complete: false`. These are the morning checkpoint, not final counts for the later native integrations. In [preview-reproducibility.json](preview-reproducibility.json), **57 recipes** have current-recipe verified source reproduction; 153 are planned, 86 have no recipe, 18 are gated, 17 unreleased and 2 need larger budgets. The 212-preview reproducibility feasibility count is not 212 independently verified fresh acquisitions. Historical successes remain useful provenance, but cannot certify a changed recipe or absent/mismatched immutable manifest binding.

The observed Oct7 earlier full Python log reports **884 passed, 1 skipped, 2 warnings**. The visible frontend/browser numbers still refer to earlier evidence, before the later feature changes. The Oct6 final package/browser/runtime review remains explicitly historical. Final receipts should supersede these dated figures without deleting failures.

Individual later aggregate receipts are stronger than extrapolating those morning counts:

- [UCF101 preparation](ucf101-native-integration-preparation-20261007.json) reports a completed snapshot with **13,320 native rows and 100 previews**, with 53,880,481 downloaded bytes for this bounded preparation. [Display parity](ucf101-native-video-display-parity-20261007.json) reports **143 exact decoded frames** for a measured original/display pair. This verifies that pair, not full-population decoding, all browser codecs or official publisher/mirror byte equality.
- [Spoken Wikipedia audio acquisition](spoken-wikipedia-native-audio-index-acquisition-20261007.json) reports completion at **05:28 UTC**, 13,643,411,287 network bytes under a 20 GB acquisition budget, no retained full TAR bodies and zero external model requests. It is acquisition/index evidence; active all-language audio coverage remains conditional on the further proof above.
- [Local provider probes](local-provider-current-probes-20261007.json) report supported text, structured output and tools using generated benign inputs; image capability results have their own earlier timestamps. Text/image embeddings remain unknown. Capability probes and successful small journeys are functional checks, not model accuracy, deadline reliability over arbitrary requests or scientific evaluation.
- The public-mirror directory audit explicitly leaves publisher/mirror equality unverified. Pinned directory hashes, ETags, native member counts and scoped decoding proofs support the declared mirror, not an inferred historical paper population.

[Storage footprint](storage-footprint-current-20261007.json) at **02:14:49 UTC** measured **129,182,580,736 allocated bytes**, no measurement errors, a 100 GB target and 150 GB ceiling. That checkpoint meets the ceiling with approximately 20.817 GB headroom and misses the target by 29.183 GB. It is not a current post-cleanup write/fsync or filesystem-quota proof. Hard links are counted once; unconfigured symlink targets and directory metadata are excluded, and reflink sharing may be counted repeatedly. Final storage claims need the later footprint and an actual write/fsync receipt.

## Scientific, identity and rights limits that remain explicit

Catalogue coverage and successful software do not settle paper-used release identity, protocol, split membership, annotations or redistribution rights. LAION covers one original annotation shard, not all linked original images or the complete LAION400M release. Places365 validation does not identify an otherwise unresolved paper population. Objaverse metadata differs from the paper's rendering population. Large sampled/sharded distributions, source-listed absent media and gated/unreleased populations retain their declared boundaries.

Availability/decoding-conditioned media previews are not valid estimates of full-population prevalence. Even zero observed exclusions does not enumerate the available-media population. Saved sample IDs and original-byte proofs establish reproducible inspected membership, not representativeness. Native joins, exact annotations, sampling disclosures, partial outputs and failed calls must remain visible in exports and published evidence.

Detector/model/vector/projection results are computational artifacts with provenance. This review found no evidence that the new features completed a frozen, independent TRAIN/DEV/TEST protocol, held-out accuracy study or validated population inference. Choosing thresholds, prompts, runs or imported spaces is a methodological choice that needs scientific review when making research claims. Only explicitly approved public packs may be published; other public access, local authorization or successful downloads do not substitute for rights review. No remote deployment was requested or attested here.

## Reviewed source fingerprints at this checkpoint

| File | SHA-256 |
| --- | --- |
| `src/dataset_atlas/registry/artifacts.py` | `c2346986435b915b69b4cc3bcf850f377b7c5938ac7cf5e503c674e9af991007` |
| `src/dataset_atlas/api/tools.py` | `7ee539ae56cdffeac38b56e4376ac02c537054643423da8aeb1fd5f635edce2c` |
| `src/dataset_atlas/providers/tool_worker.py` | `d692b3a2a140886cc65c9afb0c7750201984e50e1358cdbf6cecf2a036b0a56a` |
| `src/dataset_atlas/storage/video.py` | `24c311a261398b3f299072aaaa039b4d6a618b8c5a0775f01b2e89cfa3a6ba7f` |
| `src/dataset_atlas/preparation/slots.py` | `4ef40238c0153b43fe7f7bc0d56b0b5dd6dfa0887019a71ef751713e61ddec9f` |
| `tests/unit/test_retained_artifact_lookup.py` | `8f425a3f6210cbb8ee1021dd3fd55ced44733e5b7a647bcc12bf2f6240ca4e3d` |

These fingerprints delimit the reviewed source. Later changes require their own checks; this report must not be used to certify a different final wheel or source tree.

## Addendum — 2026-10-07 06:02 UTC (15:02 JST)

### Resource and audio closures

The response-bound issue above is **closed for unique serialized artifact contents**: `merge_artifacts` now refuses a unique encoded total above 100 MB, while identical duplicate IDs are charged once and conflicting contents remain refused. A separate synthetic low-budget check independently exercised both refusal and duplicate accounting. Selected-result resolution now performs individual job lookups and requests only the selected retained artifact IDs, rather than loading global job result history. The direct tool pack loaders retain their 100 MB pre-read guards.

The cache and response limits are not a Python RSS ceiling. Retained packs are still parsed whole, and unfiltered listing builds its artifact collection before the final merge checks its total. Peak parsing/history memory and serialization overhead are outside the encoded-content guarantee. Explicit IDs reduce unrelated result aggregation; they do not provide an on-disk ID index that avoids scanning all retained pack files. These are remaining performance boundaries, not evidence that an over-budget result response is returned successfully.

`storage/audio.py` now reuses the bounded subprocess runner for the probe and actual PCM decode, shares an absolute deadline, counts actual channel samples without retaining PCM, and propagates cancellation through the pipe-EOF wait. Independently run FFHQ/retained-result/Spoken Wikipedia synthetic tests passed **15 tests, 2 deselected, 2 dependency warnings in 1.68 s**. The two deselections avoid API/TestClient tests in this sandbox. A first broader run reached its synthetic API test and was interrupted after it hung; it is not counted as a pass. The audio subset includes the forged MP3 duration/count fixture and cancellation after pipe EOF with the subprocess leader still alive.

### Two new reproducible findings awaiting repair

1. **Decoder descendants may survive an exited leader.** In `storage/video.py::_bounded`, final cleanup calls `killpg` only while the subprocess leader is alive. A generated leader starts a child that inherits the pipes, then exits successfully. A 0.15 s deadline refuses the operation, but cleanup sees the exited leader and skips the group kill; the child writes a marker at 0.5 s. This was independently reproduced without native inputs. Attempt the group kill on deadline/cancellation/failure even after leader exit, tolerate a missing group, and add the exit-before-descendant regression. The existing pipe-EOF test does not cover this case. Because audio now shares the runner, the cleanup limitation applies to that runner's general process-group guarantee too; no native FFmpeg orphan was observed.
2. **Failed FFHQ transfers are omitted from adapter accounting.** `FFHQAdapter.resolve_asset` adds `fetcher.bytes_fetched` only after `fetch()` returns. Two distinct mocked transfers each received 5 bytes and then failed; an 8-byte adapter transfer allowance still admitted the second call, simulated traffic reached 10 bytes, and the adapter counter remained zero. Add the received-byte counter in `finally` for successful, failed and cancelled attempts. An ordinary fetch `ValueError` aborts production preparation, so this demonstration does not establish automatic continuing after that error or a successful native activation over budget. It establishes incorrect failed-transfer accounting and an adapter-level budget weakness on later/recoverable calls.

Both findings were sent to the lead with safe reproductions. Until current code and regressions are checked, they remain open here. No implementation was edited by the reviewer.

### FFHQ route and provenance review

The new converter streams the publisher metadata map, preserves each native metadata object, checks the declared population count and unique numeric IDs, validates the Drive URL layout, binds each media reference to native file/pixel MD5 and byte size, and preserves other native source references without substituting thumbnails or in-the-wild images. The adapter confines network access to its explicit HTTPS host, bounds individual images at 5 MB, requires native 1024×1024 PNG dimensions, checks file MD5/length and decoded pixel MD5, then reports SHA-256 for the retained original. Synthetic URL/path refusal and original/pixel checksum checks pass. Factory and converter registration are present.

[FFHQ metadata shape](ffhq-native-metadata-shape-20261007.json) and [conversion](ffhq-native-conversion-20261007.json) report **70,000 native metadata entries** and the pinned source SHA-256. They are annotation/source evidence. At this checkpoint preview preparation is still running; I do not count FFHQ as completed original-media preview coverage. Only fetched, validated originals receive an actual-byte proof. Historical paper subset/preprocessing identity and redistribution/external-provider approval remain unresolved. This review did not inspect the metadata body or any native image.

### Updated aggregate evidence and remaining release boundary

The lead's completed [Python log](../work/python-full-final-reviewed-20261007.log) reports **940 passed, 1 skipped, 2 warnings in 68.74 s**, before the FFHQ addition and subsequent runner repairs. The completed [browser log](../work/browser-current-native-and-analysis-20261007.log) reports **62 passed**, with **3 skips** reported by the lead. Frontend tests remain **26 passed**. These are stronger current functional checkpoints, but final source/wheel identity and full-suite evidence must still cover the later changes. Earlier failed browser control attempts remain historical; the focused corrected control check passes.

- [Local analysis/conversation journey](browser-runtime-linked-journey-20261007.json) passes at 05:52:22 UTC: 16 projection points filter to 1 and return to 16; the projection digest remains unchanged; selected prediction columns survive exchange; external model requests are zero. This is a real local functional proof, not held-out accuracy or prevalence evidence.
- [UCF101 browser proof](browser-ucf101-native-20261007.json) passes original-byte range access, muted playback and seeking for the declared 13,320-row/100-preview mirror snapshot. Its scope explicitly leaves official publisher equality and paper membership unverified.
- [Static filtering performance](browser-preview-filter-performance-20261007.json) passes the 200 ms target on a generated 10,000-record index: 4.4 ms cold and at most 2.2 ms across the recorded warm measurements. It excludes pack download, DOM rendering and GPU paint; it is an engineering fixture, not native coverage or proof of every SPEC performance target.
- Spoken Wikipedia's earlier open activation item is now **closed for the declared pinned three-language route**: [conversion](spoken-wikipedia-native-audio-conversion-20261007.json) names Dutch/English/German and 738,234 native sentence records; [preparation](spoken-wikipedia-native-audio-preparation-20261007.json) completes snapshot `spoken-wikipedia-4135cd833dc468a535dd4f9c` with 100 previews; [browser audio proof](browser-spoken-wikipedia-native-audio-20261007.json) passes muted playback/seek at 05:56:28 UTC. Originals are whole-article audio parts linked to sentence annotations. This does not establish sentence clips, paper-specific alignment, full-population decoding, perceptual quality or audible human confirmation.

The morning catalogue/reproduction/storage numbers above remain dated. No later synchronized overall counts, post-cleanup storage/fsync or final installed-wheel receipt was inspected for this addendum. `full_v1_complete` remains false; scientific, source identity and rights limitations remain open even when an adapter or functional journey passes.

| Newly reviewed file | SHA-256 at 05:59 UTC |
| --- | --- |
| `src/dataset_atlas/registry/artifacts.py` | `230807a8f0609683f5b37b2983d89c565479f8cab2e13bbb278eba25529f6bb3` |
| `src/dataset_atlas/api/app.py` | `a617b1ad1c59b176e61a9279f1126fb0ce6f2fb21bb04d8600cb4f20081fa896` |
| `src/dataset_atlas/storage/audio.py` | `c1d2ed13b280021dbdcb4766c7c356412e060d9effa7833515fb6a84a1a7d6cb` |
| `src/dataset_atlas/adapters/ffhq.py` | `3ff5145d9e0c3ad0192181df59e231c91ceef71e84be3299b4f3b3899073d877` |
| `src/dataset_atlas/converters/ffhq.py` | `4aebf30ff535e2bd928fc5b8a5bf6585fd3e69c45914d01d16fac8b72b1cae59` |
| `tests/unit/test_ffhq.py` | `c766c1dd7365d816e152bbb5ebf48cb5e132440f077f67e6e03c08b68c28f79f` |

## Addendum — 2026-10-07 06:16 UTC (15:16 JST)

This addendum closes the two reproduced findings in the preceding addendum and two additional EmoSet/range findings discovered during review. Their original demonstrations and earlier failures remain above as historical evidence.

### Independently verified closures

- **Exited-leader descendants:** the shared subprocess runner now attempts process-group termination even after the leader has exited. The generated inherited-pipe descendant no longer writes its delayed marker after the deadline. This closes the general runner cleanup defect affecting audio/video use.
- **FFHQ failed-transfer accounting:** received bytes are added in `finally`, including failed/cancelled fetches. The new regression confirms a failed attempt consumes the remaining allowance and a second over-budget attempt is refused before fetching.
- **Hash-range cache-lock cancellation:** I reproduced a held cache writer causing a read to return after cancellation. The repair uses nonblocking lock attempts, a 30 s absolute wait bound, cancellation on every poll and checks before commit/return. The competing-lock cancellation regression passes.
- **EmoSet retry after index creation:** I reproduced cancellation during row conversion after the native ZIP index completed, followed by refusal to retry the same output because the index already existed. The converter now reuses only a complete bounded index with the exact format, whole-source SHA, source length, complete remote manifest and measured SQLite checksum. Cancellation/retry succeeds, the synthetic original remains byte-exact, and a tampered index is refused.

The independently executed final scoped command was:

```text
.venv/bin/python -m pytest -q \
  tests/unit/test_ffhq.py tests/unit/test_ucf101.py \
  tests/unit/test_emoset.py tests/unit/test_hash_ranges.py \
  tests/unit/test_indexed_zip.py
```

Result: **30 passed in 1.97 s**. The prior scoped checkpoints were 28 passed before the cache-lock regression and 29 passed before the resume regression. Tests use generated media/archives, mocked transports and generated subprocesses; they establish no native coverage by themselves. No further severe defect was reproduced in this final scoped review.

### EmoSet implementation and integrity boundary

The converter pins a complete measured source SHA-256, builds full-file block hashes and a ZIP member index that checks all native member CRCs and SHA-256 values, then preserves the native split rows, annotation objects, label maps and unknown attributes. It rejects duplicate identities/memberships, absent references, image-ID/emotion join disagreements, missing/ambiguous protocol tables, overlarge protocol/annotation members and undeclared orphan populations. It does not extract arbitrary native member paths to the filesystem.

`EmoSetAdapter` resolves safe JPEG member names through the checksum-verified index, validates JPEG format and pixel bounds, and returns the measured original member SHA. `indexed_zip.py` selects hash-pinned ranges when a complete-block manifest exists, checks its source SHA binding, forwards cancellation and accounts received transfer bytes in `finally`, including failure. Returned ZIP payloads are bounded by compressed/decompressed lengths and checked against the native member SHA. Hash-range reads require exact HTTP 206 length/range and identity encoding; full fetched blocks are verified, including bytes outside the requested member slice. Ignored ranges, changed/truncated blocks and over-budget complete-block transfers refuse. Cold-original retrieval after deleting a synthetic source is byte-exact.

These checks protect a later retrieval against the locally measured original. They are not an independent publisher checksum. Full-source acquisition, local hashing, byte-exact member retrieval and paper population identity remain different claims. Synchronous socket/DNS/cache operations also retain their configured timeout boundaries; polling cancellation does not prove instantaneous interruption of every underlying system call. Final data/storage policy claims must stay within the measured source, output, cache and process limits, rather than treating an encoded response/cache budget as an RSS ceiling.

### Updated native and release receipts

- [FFHQ preparation](ffhq-native-integration-preparation-20261007.json) is now **completed**, snapshot `ffhq-95a360eb6cb9aeafd49b43dd`, **70,000 indexed metadata entries / 100 original PNG previews**, with **134,147,613 transferred bytes** reported for this preparation. It supersedes the earlier pending-preview statement. File/pixel MD5 checks and retained SHA are implemented and synthetically verified; this reviewer did not inspect native files or independently perform their live API/browser checks. Other unfetched PNGs remain unverified originals; public/external rights and exact historical paper subset stay unresolved.
- [EmoSet conversion](emoset-native-conversion-20261007.json) passes **118,102 records**, released split counts **94,481 / 5,905 / 17,716**, and **236,208 native member CRC/SHA checks**. It explicitly reports `publisher_checksum_checked: false`; whole-source SHA is locally measured from the author-linked acquisition.
- [EmoSet preparation](emoset-native-integration-preparation-20261007.json) is now **completed**, snapshot `emoset-a6a9d1bc6fbf0747d4a3a61b`, **118,102 indexed rows / 100 previews**, with **115,343,360 transferred bytes** reported for the preparation. The failed first-attempt receipt remains historical; the lead identified its missing recipe format field before retry. At this checkpoint no separate current EmoSet live-original/API/browser or post-retirement verification receipt was inspected. Completed preparation is not a blanket attestation that cold retrieval after native source retirement or every original is currently accessible.
- The completed [full Python checkpoint](../work/python-complete-native-20261007.log) reports **954 passed, 1 skipped, 2 warnings in 74.70 s**, before the last cache-lock and resume repairs. The lead's [cache-lock focused check](../work/hash-range-cancel-final-20261007.log) reports **11 passed**. The independently observed 30-test final subset above covers the later scoped changes. A final full suite, source/wheel identity, clean installation, synchronized overall counts and storage/fsync proof remain required before final release closure.

| File after the reviewed repairs | SHA-256 at 06:16 UTC |
| --- | --- |
| `src/dataset_atlas/storage/video.py` | `c77f1f3b879bc326c3da6b852e42c43a8f52b49c060f2552e031feac51f686f2` |
| `src/dataset_atlas/adapters/ffhq.py` | `61cc832f4273a44d3e76e237b7fa6744e4360007728c9b18733f7d3180003e56` |
| `src/dataset_atlas/storage/hash_ranges.py` | `a3befd52a74b72c0bc1c9a6e836993e97274c436d02e603b6959441922a7adfc` |
| `src/dataset_atlas/storage/indexed_zip.py` | `be175f26215b6677bc63addee8b6acf29409b177bab62fb548ebec3417e9e86d` |
| `src/dataset_atlas/converters/emoset.py` | `469d0f366e0a7d3ae92355f3f7e7cf94b1cb07270ed330aa94b0fd2ddb9bb9e5` |
| `src/dataset_atlas/adapters/emoset.py` | `de836f000663fe6949eef1f14485cf8082ebf67bd8e73043f80a39a2eaf6c007` |
| `tests/unit/test_emoset.py` | `653d86ee8c52e4c85948e87cb79de1f00fbc27a2dfcbb534e3309d5024cafd54` |

The catalogue-wide, scientific, source identity and redistribution limits above remain in force. These additions do not change `full_v1_complete` to true.

## Addendum — 2026-10-07 06:50 UTC (15:50 JST)

This checkpoint reviews the new CIFAR-C source-retirement route from implementation, generated fixtures and aggregate receipts only. No tracked/native registry configuration, canonical native rows, source inventories or media were read. The separate adversarial helper uses a fake registry and generated arrays, archives and packs under `/tmp`; it is not native coverage. Only this review report was changed.

### CIFAR-C defects reproduced and closed

The earlier implementation had five unsafe acceptance or exclusion paths. The lead repaired them before any native CIFAR-C deletion:

1. **Wrong writer identity:** retirement took a generic lease rather than the actual dataset's lease, permitting an active preparation of that dataset to coexist. The current lease uses the actual dataset ID. An independently held synthetic `cifar-10-c` writer slot causes retirement to refuse before loading registry data.
2. **Missing retained snapshot:** a retained pack naming the same source could be skipped when its snapshot directory was absent. The current implementation refuses that condition and preserves the source.
3. **Unhashed physical dependency:** a same-dataset retained version physically using the source, without declaring its verified SHA, was silently excluded. A generated execute probe deleted the source while leaving that version without a route. The repair detects the physical dependency and refuses retirement without a verified identity.
4. **False canonical integer metadata:** fractional severities were accepted through integer truncation; a generated execute probe retired the source despite false native row metadata. Severity, original index and label now require exact integer types, reject booleans, and satisfy their declared native bounds without truncation.
5. **External index symlink:** an existing valid index reached through a symlink outside the configured original-access base passed direct cold probes; retirement deleted the generated source, but the installed route then refused the outside-base index. Index symlinks and resolved paths outside the configured base now refuse. Existing receipts must be regular, non-symlink files no larger than 2 MB before reading.

The first unsafe demonstrations remain historical failures; their deletions affected only generated `/tmp` sources. Independently rerunning the four adversarial data/path cases against current code now produces **refusal and source preservation in every case**. The actual-dataset writer exclusion also passes. The lead added corresponding committed regressions.

New CIFAR-C routes additionally pin the exact receipt SHA-256. `read_original_route` bounds and verifies those receipt bytes before selecting a reader; offsets and complete-source block pins therefore cannot be silently replaced in the bound receipt. Existing route formats retain their prior behavior.

The independent final scoped suite was:

```text
.venv/bin/python -m pytest -q \
  tests/unit/test_cifar_ranges.py tests/unit/test_corruptions.py \
  tests/unit/test_hash_ranges.py tests/unit/test_indexed_zip.py \
  tests/unit/test_indexed_tar.py
```

Result: **27 passed in 0.56 s**. The earlier 22-test run preceded the final indexed-TAR route check. No remaining severe destructive-retirement defect was reproduced in the reviewed current scope. This conclusion does not attest an actual native deletion or replace the lead's native execution receipts.

### Retrieval, membership and resource boundary

The index records physical offsets into native uncompressed TAR/NPY data, requires C-order `uint8` RGB arrays of 32×32 pixels, and binds full-source SHA, length and complete 1 MiB block hashes. Resuming a plan recomputes the complete manifest against the still-present source. Every retained canonical row is checked against the native corruption, severity, original index, label, row reference and unique membership; count equality then establishes coverage of the declared native population for that version. Retained previews require protected originals and exact native RGB equality. Pinning the active preview alone does not certify an older preview.

Cold retrieval fetches checksum-verified complete source blocks and returns a **lossless PNG encoding of the native RGB array row**. It preserves native pixels without resize or normalization; the PNG is a generated representation, not a publisher-issued PNG file. Protected existing preview PNG bytes remain a separate byte-exact obligation. Source and decoded output bounds, approved transfer limits, hardlink coverage, source identity rechecks and normalized shared-dependency checks are present. Unknown or uncovered dependencies refuse deletion. Retrieval remains conditional on the pinned remote source being available and satisfying its range/block checks; passing a cold probe does not promise indefinite upstream availability.

[CIFAR-10-C read-only plan](cifar-10-c-native-source-retirement-plan-20261007.json) reports **1,900,000 canonical version rows**, **200 protected-preview memberships**, two retained snapshots and three cold probes. [CIFAR-100-C read-only plan](cifar-100-c-native-source-retirement-plan-20261007.json) reports **950,000 version rows**, **100 protected-preview memberships**, one retained snapshot and three cold probes. Together these are **2,850,000 retained version-row checks / 300 protected-preview memberships / six cold probes**, with **6,291,456 reported transferred bytes**. The duplicated CIFAR-10-C snapshot means the version-row sum is not a distinct native population count. Both receipts are `verified_plan`; actual native execution and post-retirement verification were still pending at this checkpoint.

### Reconciled aggregate evidence

- [Six-source integrity](native-six-source-integrity-20261007.json), completed at 06:16 UTC, reports all checks passed for Open Images, MIT States, UCF101, FFHQ, EmoSet and Spoken Wikipedia: **41,620 / 63,440 / 13,320 / 70,000 / 118,102 / 738,234** indexed records respectively, with **100 previews each**. It reports **1,097,803,310 index bytes** and **686,138,292 preview bytes** verified. These are declared snapshot integrity checks, not paper identity or redistribution decisions.
- [Exhaustive FFHQ/EmoSet native parity](ffhq-emoset-exhaustive-native-parity-20261007.json) passes all **70,000 FFHQ native metadata objects** and **118,102 EmoSet native split/annotation objects**. Native annotation equality is stronger than a row-count comparison; it does not verify every unfetched image or supply an independent publisher checksum for EmoSet.
- [Post-retirement originals](native-post-retirement-originals-20261007.json), passed at 06:31 UTC, verifies sampled originals for EmoSet and PHASE with their original bodies absent. This supersedes the earlier pending EmoSet post-retirement statement for the receipt's sampled checks. It is not exhaustive cold retrieval of their full populations.
- [Preview-media smoke](preview-media-smoke-final-20261007.json), checked at 06:16 UTC, covers **217 dataset entries**, with **169 `ok` media entries**, **48 without media assets** and **zero reported failures**. [Complete-index smoke](complete-index-smoke-final-20261007.json) covers **213 indices**, all `ok`, with zero failures. Smoke coverage and source completeness remain different claims.

The lead reports a **960 passed / 1 skipped** full Python checkpoint before the latest CIFAR-C repairs. The independent 27-test subset above covers the current scoped changes; final full-source tests, rebuilt/installed wheel identity, synchronized overall status and post-cleanup storage/write/fsync evidence remain pending. Earlier full-suite/browser failures and their dates are retained above. `full_v1_complete` remains false, and the scientific, identity and rights limitations remain open.

| Current reviewed file | SHA-256 at 06:49 UTC |
| --- | --- |
| `src/dataset_atlas/storage/cifar_ranges.py` | `84bcfeed1db13b1605e0828502869d2c58671e11aa31fe4de91c84e9573689d2` |
| `src/dataset_atlas/storage/indexed_tar.py` | `d1fdf5e78065b6c3e4d5d6b3a05417f0fe0e7c5129a88881127afe2df714e9ca` |
| `src/dataset_atlas/cli/__init__.py` | `2f0c590e62d22bd176cf4092d8c3b4e7ff30882943944cf972a6473c0b192ce0` |
| `tests/unit/test_cifar_ranges.py` | `30608824eb0fe070bd751680e8ebdb24bd2e14e17e77a3de4f433b308a52bf5b` |

## Addendum — 2026-10-07 07:13 UTC (16:13 JST)

### Frozen asset-field correction

The snapshot-specific asset-fields endpoint previously passed a list of records to `materialize_records`, whose contract requires a `Pack`, and attempted to construct an unsupported `dtype='unknown'`. Current code passes `materialize_records(frozen, 'asset')` and constructs valid `FieldDescriptor` instances with `unit='asset'` and the existing default string dtype. The new committed regression gives old/new snapshots disjoint generated asset metadata and checks the requested snapshot's fields rather than the active version's fields.

I independently exercised the actual endpoint function with a fake registry and generated old/new packs under `/tmp`, without TestClient, sockets, tracked/native registry YAML or native media. The old snapshot returns only its old asset metadata field; active lookup returns only its new field. Both descriptors validate with the asset unit, and a missing snapshot refuses. **The direct synthetic boundary check passed**, with zero registry YAML reads and zero network requests. This establishes the endpoint's argument/descriptor and snapshot behavior; it is not a socket/browser proof. No remaining concrete defect was reproduced for this correction.

### Actual retirement and post-retirement receipts

[CIFAR-10-C retirement](cifar-10-c-native-source-retirement-20261007.json) and [CIFAR-100-C retirement](cifar-100-c-native-source-retirement-20261007.json) now both report `executed`, superseding the prior pending-execution statement. Their verified version-row and protected-preview counts remain **1,900,000 / 200 / two snapshots** and **950,000 / 100 / one snapshot** respectively. Reported freed unique source bytes total **5,836,944,896**. This reviewer did not perform those native mutations or inspect their source contents.

[CIFAR post-retirement originals](cifar-native-post-retirement-originals-20261007.json), passed at 06:58 UTC, reports both original bodies absent and **six native RGB-equal checks**, of which **four are non-preview rows**. The generated PNG/native RGB distinction in the preceding addendum still applies. [EmoSet/PHASE post-retirement originals](native-post-retirement-originals-20261007.json), also passed at 06:58 UTC, now checks **six non-preview members**, three per dataset, with native member SHA equality and original bodies absent. These receipts close the scoped cold-retrieval-after-retirement checks; they remain sampled availability proofs rather than exhaustive future retrieval guarantees.

The refreshed [preview-media smoke](preview-media-smoke-final-20261007.json) reports **217 dataset entries / 507 asset checks / zero failures**, with 169 media-bearing entries and 48 entries without media assets. [Complete-index smoke](complete-index-smoke-final-20261007.json) now reports **214 indices / zero failures**, superseding the preceding 213-index checkpoint.

The lead reports clean-wheel install checkpoints for Python **3.12.14** and **3.14.2**, and full Python checkpoints of **966 passed / 1 skipped** and **963 passed / 4 skipped** respectively, before this last asset-fields regression. A rebuilt wheel and final full-suite repeats must include the API correction; they remain pending here. No later synchronized overall completeness, storage/fsync or package-source identity receipt is certified by this addendum. Scientific, identity, rights and catalogue-wide limitations remain open, and `full_v1_complete` remains false.

| File at this checkpoint | SHA-256 at 07:13 UTC |
| --- | --- |
| `src/dataset_atlas/api/app.py` | `042d234b1a27b0512e63ce8975f1480a4db646af9bd1f56d2bc8248e408100d7` |
| `tests/unit/test_frozen_snapshot_media.py` | `d8afcc0e15a5a977909fc573c2f9be6ea05c0ac3d9a3fe2b488c87726a3134e8` |

## Addendum — 2026-10-07 07:34 UTC (16:34 JST)

The lead added the PATA public metadata route while final receipts were being prepared. This review covers only the new converter, preparation helper, CLI hook, generated fixtures and the aggregate metadata receipt. No native annotations, image URLs from native records, images or tracked registry YAML were inspected.

### PATA implementation and remaining reproduced defects

The converter preserves source-row ordinal and exact native line endings, separates the four native label components without breaking scene names containing underscores, retains duplicate upstream label identities as distinct source rows, joins exact caption objects, and refuses duplicate/unjoined caption groups or malformed label/URL rows. The preparation route binds fixed author revision, native file sizes and SHA-256 values; uses an actual PATA writer lease; validates workspace-contained source/output directories; refuses source symlinks; bounds download and index output; builds source-hash/ordinal identities; and compares every canonical `record_json` against its generated native-row conversion. URLs remain metadata, with no media mapping or third-party fetch. Independently running `tests/unit/test_pata_metadata.py` passed **10 tests in 0.15 s**.

Additional execute/resume probes used generated source pins, 4,934 generated rows where applicable and a fake registry. They made zero network requests and read no registry YAML. The following concrete issues were sent to the lead and remain **open until their repairs are independently checked**:

1. **Converted-output hardlink can destroy a retained input.** A generated `converted/pata-metadata.jsonl` hardlink to the pinned annotation input passes the symlink check. `write_rows` opens the output with `w` before the lazy input iterator opens the input, truncating their shared inode. Preparation then refuses the malformed join, but the original generated input is already zero bytes. Conversion must use a new exclusive temporary inode and atomic replacement, or refuse output/input inode aliases before opening. Protecting only symlinks is insufficient.
2. **Resume accepts an incompatible manifest scope.** After successful generated preparation, changing only its manifest's `population_scope` to `preview` still allows retry to report completed and 4,934 exact native checks. The active index therefore remains incompatible with complete-population requests. Resume must require the expected complete scope, unit, release and registered field descriptors, in addition to dataset/snapshot/count identity. Safe probe: `/tmp/atlas-review-pata-resume-20261007.py`.
3. **Resume checks canonical JSON without checking query columns.** Rewriting the generated Parquet `source.media_available` column to true, updating its valid file checksum/size, and retaining byte-equivalent canonical record JSON still passes all 4,934 native checks. The query column contradicts the native/canonical false values. Resume verification must recompute/compare the expected base, search and registered query columns as well as `record_json`, or rebuild and verify a deterministic index. Safe probe: `/tmp/atlas-review-pata-columns-20261007.py`. No such corruption was observed in the real native preparation; this is a reproduced acceptance defect in the code.
4. **Initial source pin does not bind later reads.** A generated conversion wrapper changes the annotation input after initial SHA/size validation while retaining its size, valid syntax and 4,934-row count. Real conversion and later exact row comparison then both read the changed source; preparation completes while the receipt still declares the original source SHA. Recheck source length, SHA and identity before activation, or hold stable source descriptors across the reads. Safe probe: `/tmp/atlas-review-pata-source-change-20261007.py`. This injects a generated source change; no native source was changed or inspected.

[PATA metadata integration](pata-native-metadata-integration-20261007.json), completed at 07:27 UTC, reports **4,934 exact native record checks**, the fixed author revision and **zero native image previews**. Native pins total **759,949 bytes**; the recorded run reused retained files and reports zero downloaded bytes. This closes an implementation gap for public author metadata, subject to the code repairs above. It establishes neither third-party image accessibility/rights nor historical paper membership, demographic self-identification or image inspection coverage.

Before this PATA addition, the newest attested logs independently showed **967 passed / 1 skipped / 2 warnings** on Python 3.12, **964 passed / 4 skipped / 2 warnings** on Python 3.14, **67 browser checks passed**, and **26 frontend tests passed**. Both clean-install receipts pass for the same wheel SHA `1827fd279187d4d9b8e5c9ee379efc4eb77607108df44ba01bf4f457438d5b56`, Python 3.12.14 and 3.14.2, at 07:18 UTC. These are historical checkpoints before the newly reviewed PATA code; the lead will regenerate the suites and package. The final source-identity receipt and refreshed final overall status/storage were not yet saved when these checks were read. Final release closure remains pending; `full_v1_complete` remains false.

## Addendum — 2026-10-07 07:39 UTC (16:39 JST)

**All four PATA findings above are independently closed for the current reviewed implementation.** Their unsafe generated demonstrations remain preserved in the preceding addendum.

- Conversion now creates an exclusive output inode in a private temporary directory, verifies any retained derived output before reuse and applies an explicit converted-output budget. The generated hardlink case refuses without changing input bytes. Successful creation makes the retained derived file read-only; total converted-plus-Parquet bytes are checked against the output allowance.
- Resume requires the complete expected dataset/release/snapshot/unit/population/count and exact field descriptors. The generated preview-scope retry now refuses; committed regressions also cover release, unit and descriptor changes.
- Every stored base, registered query and search column is compared against the expected native/canonical record, in addition to exact `record_json` equality. The rewritten-checksum boolean-column probe now refuses.
- Both source SHA-256 values and lengths are checked again before activation. The generated conversion-time source-change probe now refuses, with no new active version written.

The independent current command `.venv/bin/python -m pytest -q tests/unit/test_pata_metadata.py` passed **17 tests in 2.76 s**. The three separate generated resume/column/source-change scripts all refuse, and the generated hardlink probe confirms source preservation. These checks use fake/generated inputs only and establish no native image coverage. No remaining concrete severe defect was reproduced in the scoped PATA review. The fixed pins still establish metadata identity, while the image, demographic, paper-membership and rights limitations above remain unchanged.

| File after PATA repairs | SHA-256 at 07:39 UTC |
| --- | --- |
| `src/dataset_atlas/converters/pata.py` | `d6f24e462d16a79d9bb58df4440a0f45ecbc7cb96e4b0c0a72f059b9a4fb239e` |
| `src/dataset_atlas/preparation/pata.py` | `b28ad22e94c909f61324f2d3407f86a2467e5218401e87a798eb0ea24c1a5d81` |
| `src/dataset_atlas/cli/__init__.py` | `56c479fce771a52405cc5cd1087010436b8899a74e4445fa4aa182f7097d6fc4` |
| `tests/unit/test_pata_metadata.py` | `f8984c32b83ed763298c7877fab14a9a95e1f1e95087cf8c96c615819241bef6` |

Final combined test, package/install, overall status/source identity and storage receipts remain pending after this addition. Earlier checkpoints must not certify the later PATA source automatically.

## Addendum — 2026-10-07 08:00 UTC (17:00 JST)

The lead requested a code-only review of the exploratory inert FACTOID reader and metadata-only browser opening. No native pickle, native schema values, annotations, records or UI contents were inspected. FACTOID has **no registered/activated native dataset route or completed semantic coverage proof** at this checkpoint.

### Inert reader: safety scope and open semantic findings

`neutral_pickle.py` interprets source GLOBAL/STACK_GLOBAL/REDUCE/NEWOBJ/BUILD instructions as trusted `Symbol`/`Node` data. It imports no source-referenced module, invokes no source callable and installs no source class state. Unknown opcode families refuse. The generated `os.system` serialization remains inert and cannot write a marker. Numeric buffers, shapes, column placement and literal depth have explicit checks; unknown native value constructors refuse. I found no serialized-callable execution path in the reviewed implementation. Independently running `tests/unit/test_factoid_inert.py` passed **9 tests in 0.03 s**.

Three additional generated cases were reproduced and sent to the lead. They remain **open until fixed and independently rechecked**:

1. A pre-cancelled small stream `gzip(b'N.')` returns successfully because cancellation/deadline checks occur only every 10,000 opcodes. Check before parsing, around bounded reads and before STOP/return, rather than relying only on the periodic opcode checkpoint.
2. A malformed `gzip(b'\x85.')` accepts TUPLE1 with an empty stack as an empty tuple. Enforce opcode stack arity and expected container types before applying operations; accepting malformed syntax can manufacture values that the serialized stream did not supply.
3. `literal(b'x')` equals `literal({'_atlas_native_type': 'bytes', 'hex': '78'})`. A literal dictionary can therefore collide with a typed envelope. Escape reserved-key dictionaries or use an unambiguous tagged representation before describing the envelopes as lossless.

The converter currently models only a restricted DataFrame layout. It does not preserve all DataFrame attributes, axis metadata or native dtype descriptors. Numeric arrays are flattened to Python values; source type/layout metadata is not a complete retained DataFrame representation. Shared/cyclic object graphs also need an explicit preservation/refusal policy, and recursive literal expansion/JSON serialization occurs before the per-record encoded-byte check. The stated process memory/time cap must remain part of the execution contract; the parser's literal/opcode/memo bounds alone are not an 8 GB RSS guarantee. The lead's native inert syntax probe reports **82,115,458 opcodes / approximately 1.13 GB decoded**, within its separately imposed 8 GB process cap, but semantic conversion refuses the native column-label contract. Syntax success establishes neither full annotation conversion nor an original/native equality result. This remains an implementation experiment, not an external-access blocker or native coverage.

### Metadata-only browser opening

The workbench now treats an actually local complete index as browsable even when its media/preview coverage is partial. With zero preview records, DatasetPage loads complete metadata and compatible artifacts directly, binds the complete snapshot/unit/fields, and enables queries only after complete scope is selected. It omits the unavailable preview scope option. The static browser still requires an approved nonempty preview. This addresses PATA's absent-preview-pack opening failure without claiming image coverage.

The new `apps/web/e2e/metadata-index.spec.ts` uses a generated local metadata dataset and asserts complete-scope queries, visible exact indexed count, and zero preview-pack/preview-field requests. I inspected its source rather than native browser DOM or pixels; the lead reports the generated browser check passed. No concrete defect was reproduced in the requested metadata-only opening logic. A final frontend/browser/package rerun must include these changes, and the final status/source/storage receipts remain pending.

| Newly reviewed file | SHA-256 at 08:00 UTC |
| --- | --- |
| `src/dataset_atlas/converters/neutral_pickle.py` | `548f3b3a91c7c7fa0b33d9f07a1b884ce5fe37ef02f8b44a87e9eb6f4636a759` |
| `src/dataset_atlas/converters/factoid.py` | `2c8f84eba3f4913f208094e4d189920167252e184903cd3dbf48c3da211104cd` |
| `tests/unit/test_factoid_inert.py` | `dd776da963da07d4cd337b0da7429c8f23e668948ae1a29ca62aec07584ff79e` |
| `apps/web/src/dataset/model.ts` | `73d2d962343766346e680bd798a2a2e5ef60d8c08d6dbb1c7a0c78b804b87b75` |
| `apps/web/src/dataset/DatasetPage.tsx` | `2dfc027012ecd2f09f15d77d02562ec729d1f2800f616b7535ab97ecd23d054f` |
| `apps/web/e2e/metadata-index.spec.ts` | `c0bf38eebd2ee1537bc412d181b5a84929726570fd827427ef07956c4f1ae4b8` |

## Addendum — 2026-10-07 08:07 UTC (17:07 JST)

### FACTOID excluded from production; experiment findings closed

The lead retained FACTOID only under `work/experiments/factoid-inert-20261007` and removed its reader/converter/tests from `src` and the production test tree. I independently confirmed no production Python references to the experiment, no converter autoload entry, wheel packaging restricted to `src/dataset_atlas`, an sdist include list that excludes `work`, and normal pytest collection restricted to `tests`. **No FACTOID native index or preview was activated.** PATA and metadata-only browsing remain the shipping additions.

The archived reader now checks cancellation/deadline at entry, bounded-read checkpoints and STOP; validates opcode stack arity and container types; and escapes dictionaries containing the reserved envelope key. My three generated boundary cases now refuse small-stream cancellation and tuple underflow, and distinguish bytes from a literal reserved-key dictionary. The archived suite independently passed **19 tests in 0.11 s**. Its first moved-tree rerun failed collection because of a stale relative sibling import; the lead repaired the import and the successful rerun follows it. That failure remains historical archive-reproducibility evidence, not a production failure.

The later [exploratory conversion receipt](factoid-inert-conversion-probe-20261007.json), checked at 07:59 UTC, reports **4,150 rows**, **2,811,398,468 output bytes**, **102.96 s** and **5,729,140,736 peak RSS bytes**, with `native_index_activated: false`. The lead reports an independently imposed 8 GB process address-space cap for that probe. It supersedes the earlier column-contract refusal as an experimental cell-value conversion result; it does not establish complete DataFrame metadata, dtype, shared-object or original semantic parity. The experiment therefore remains an **implementation gap**, not a completed native dataset route or an external access blocker. Promotion would require a fixed interpretation contract, complete native parity, proven isolated resource/cancellation behavior and normal preparation/API/reproducibility integration.

[Exploratory-body retirement](factoid-exploratory-body-retirement-20261007.json), executed at 08:03 UTC, reports all unreferenced probe bodies absent, **3,180,718,186 logical bytes / 3,180,728,320 allocated bytes** retired with per-file SHA/inode evidence. No local whole-source or converted body remains; re-acquisition is conditional on the pinned upstream source remaining available. This cleanup adds no native coverage. The reviewer inspected only aggregate receipt fields and experiment code/tests.

| Archived experiment file | SHA-256 at 08:07 UTC |
| --- | --- |
| `work/experiments/factoid-inert-20261007/neutral_pickle.py` | `1e44998d02e71b89074d080045a3a4de98a3e1448a745b06eecb5b21da04af1c` |
| `work/experiments/factoid-inert-20261007/factoid.py` | `37424c1bd7ace3b2ea2a7acee6299b718ab8015a1f60c031c8f9a611ab17712c` |
| `work/experiments/factoid-inert-20261007/test_factoid_inert.py` | `9ddabeb6103a8bfceba64d95688be5cd9eb62a004de555d6ef53bbf4b3965471` |

The code-only metadata-browser conclusion above stands. Final combined shipping-source tests, package/install/source identity and synchronized status/storage receipts are still forthcoming. `full_v1_complete` remains false.

## Final release addendum — 2026-10-07 08:20 UTC (17:20 JST)

**The permitted final aggregate receipts agree. No concrete release-identity or aggregate-count discrepancy was found.** This checkpoint supersedes the earlier statements that final combined shipping tests, packaging, installation and status/storage evidence were pending. Earlier failures and their scoped repairs remain preserved above. This is a verified working release with remaining V1 scope; `full_v1_complete` is **false**.

The final check was restricted to production code, test-summary footers and the expressly permitted aggregate status, identity, storage, cleanup, index-smoke, installation, distribution and workbench-state receipts. No native records, source bodies, images, audio, conversations, browser DOM or pixels were inspected in this final check. The earlier disclosed scope deviation remains part of this report. Dataset-level native assertions below are reported aggregate evidence, rather than independent reviewer inspection of native records.

### Current counts and validation

[Final status](final-status.json) reports **333 catalogue entries, 217 tested local previews, 21,232 verified preview records, 215 canonical complete-scope indices and 116 entries without a preview**. The index smoke receipt reports **215 successful index queries**, agreeing with that index count. **83 current-recipe preview recipes** have fresh-workspace verification; this is a subset, not a claim that every catalogue item or preview has current fresh-source reproduction. PATA's metadata-only reproduction does not inflate that preview-recipe count. Its complete metadata index contains **4,934 records and zero image previews**.

The current attested log summaries independently agree with the final status:

| Check | Final result |
| --- | --- |
| Python 3.12.14 | **984 passed, 1 skipped, 2 warnings** |
| Separate Python 3.14.2 environment | **981 passed, 4 skipped, 2 warnings** |
| Frontend | **26 passed** |
| Browser | **68 passed, zero skips** |
| Pinned `prek` / scoped `ty` checks | **Passed** |

The Python 3.12 skip is the optional VHD11K native archive that is not retained. Python 3.14 also skips two LanceDB checks and one UMAP check because those optional dependencies are absent in that separate environment. These omissions are explicit; the 3.14 result does not establish those optional integrations. The reviewer read summary footers rather than browser traces, native fixture contents or model replies. Local analysis/conversation and native-browser journeys are engineering acceptance evidence, not held-out scientific accuracy or population-prevalence evaluation.

### Frozen source, archives and clean installs

[Source identity](closeout-source-identity-20261007.json) describes the dirty working tree with a **2,006-entry production-source manifest**. Its canonical manifest digest independently agrees with the declared digest. The reviewer independently checked size/SHA identity for **446 permitted code files** and hashes for **13 expressly permitted receipt/log attestations**, with **zero discrepancies**. The remaining manifest entries and the native PATA attestation were deliberately not read or hashed by this reviewer. The lead separately reports rechecking all **2,020 source/evidence hashes**, with zero mismatches; that broader check is attributed evidence, not a reviewer-native-content claim.

| Final archive | Recorded SHA-256 |
| --- | --- |
| `dataset_atlas-0.2.0-py3-none-any.whl` — 39,408,162 bytes | `b3b00fc4ebb5c0d04fdeddcafdd419976f39a41063a3893e315c4f59a96d9441` |
| `dataset_atlas-0.2.0.tar.gz` — 39,353,210 bytes | `e9c43920ca9ebf41dd88d08c968e3c5caf3d4036fd90199275c1904614f81fc0` |

Both [Python 3.12 clean installation](installation-verification.json) and [Python 3.14 clean installation](installation-verification-python314-20261007.json) pass and record the exact wheel SHA above. Both report a fresh **333-entry catalogue**, passing archive inspection and **nine HTTP routes returning 200**. [Distribution/source parity](distribution-source-parity-closeout-20261007.json) reports **2,462 archive members compared against the frozen production source, zero mismatches**, and the same wheel SHA. Its attested receipt hash independently matches source identity. This reconciles the final package after the frozen asset-fields, PATA and metadata-browser repairs. It does not certify omitted optional model packages or publication rights for every locally prepared dataset.

### Storage and quiet runtime

[Final storage](storage-footprint-final-20261007.json) and [cleanup summary](cleanup-summary-20261007.json) agree on **116,566,290,432 allocated bytes** across the configured measurement roots. This is **16,566,290,432 bytes above the 100 GB target** and **33,433,709,568 bytes below the 150 GB ceiling**. Net reduction from the recorded **129,183,100,928-byte baseline** is **12,616,810,496 bytes**; the arithmetic agrees. The storage receipt has zero recorded errors. Gross retired archive bytes are not added to that net reduction. Logical bytes include hardlinked paths and are a different metric from the allocated-byte ceiling. These are point-in-time measurements; this report write can add a few metadata blocks. The lead reports an actual write/fsync probe passed; the reviewer did not repeat that probe or read its separately unlisted receipt.

[Post-cleanup workbench state](workbench-final-state-20261007.json) passes with **zero active analysis jobs, zero conversation jobs and zero preparations**. Final status reports no active acquisition. The workbench remains running. The recorded PATA complete query returns **HTTP 200 with exactly 4,934 matches**; the frozen asset-fields route also returns HTTP 200. These are aggregate HTTP observations; response records and UI contents were not read by the reviewer.

### Remaining scope

No severe concrete defect remains reproduced and unresolved in the requested scoped reviews; this is not a universal audit of every adapter. FACTOID remains an **unregistered experiment excluded from production** with no activated native index or preview. Complete DataFrame semantics, native canonical/query parity and production isolation remain implementation work. MultiTrust per-task native adapters and other public recipe/native-format gaps likewise remain software work, not external blockers.

Historical paper population/release identity, independently verified source identity where only self-measured hashes exist, upstream availability after source retirement, publisher/licensing gates, unarchived PATA images and dataset-specific publication review remain separate acceptance boundaries. PATA author metadata does not establish image rights, image accessibility or demographic self-identification. Preview counts and availability-conditioned samples do not support population-prevalence claims. Approved packaged examples do not grant publication rights for all 217 local previews. Human scientific and rights review is still required for those claims. The current receipts substantiate the local working release and its exact package identity while explicitly preserving incomplete catalogue-wide V1 acceptance.

## Resumed FACTOID review — 2026-10-07 08:48 UTC (17:48 JST)

The lead resumed FACTOID production integration after the release checkpoint above. This addendum reviews only `converters/factoid.py`, `converters/neutral_pickle.py` and generated `test_factoid_inert.py` fixtures. **The earlier frozen package/test attestation does not certify these new production files.** No native source body, schema value, row, filename, media, conversation or UI was inspected. The lead reports bounded native conversion in progress, with no native index activated or preparation recipe registered; its native semantic result is not established by this review.

Independently running `.venv/bin/python -m pytest -q tests/unit/test_factoid_inert.py` passed **27 generated tests in 0.09 s**. The new code retains the byte-identical original, frame attributes/axis/dtype metadata and exact float32 payloads, supports reversible integer-column runs, refuses cycles and uses an isolated child with 8 GB address-space / 360 s CPU / 480 s outer wall limits. GLOBAL/REDUCE/BUILD remain inert data; no source-referenced class or callable execution path was found. These are useful mechanisms, but the following synthetic findings remain **open pending repair and independent recheck**:

1. **Cached canonical values can bypass their immutable semantic pin** (`factoid.py:345–364`). A generated two-row conversion was edited, and its file SHA/count/row digest were updated in the retained manifest. The original `native_values_sha256` and `metadata_sha256` claims and the caller's exact original semantic pins were unchanged. Resume accepted the rewritten value. It compares claimed semantic hashes without recomputing the expanded native-value digest or actual metadata hash. Recompute those hashes, bind every row's metadata hash and cross-check the proof/adapter configuration before acceptance.
2. **Resume accepts a cache missing every required derived file** (same function). Clearing `derived_sources` and deleting the retained original, frame metadata and conversion proof still yields successful resume. Require a complete fixed role/path/size/checksum contract, rather than validating only the manifest's present entries. Required original bytes must independently match the source pin; metadata/proof pointers must match the validated files.
3. **Cached validation can ignore cancellation or block indefinitely** (`factoid.py:353–364`). Cancellation arriving during `digest_existing` returns successful resume because that whole-row parser has no callback or final guard. Replacing the generated row file with a FIFO blocks its open until an external reviewer alarm; cached entries are not required to be regular files. Validate bounded regular non-symlink files through safe nonblocking handles, check cancellation while digesting/expanding rows and before returning, and apply explicit validation resource limits. Current cache parsing runs in the parent, outside the new child's CPU/memory/wall limits.
4. **Valid bytearrays lose native type and shared identity** (`neutral_pickle.py:90,125–128`). Protocol-5 `BYTEARRAY8` becomes immutable `bytes`. A generated repeated bytearray retains neither its mutable type nor a shared-container memo identity. Preserve an unambiguous bytearray envelope and identity, or explicitly refuse this unsupported type.
5. **Reused memo slots collide as object identities** (`neutral_pickle.py:119–129`). A legal generated serialization reuses memo slot zero for two independent lists, each actually referenced through GET. The lists are distinct but both become `shared_object` with `native_memo: 0`. Refuse memo-slot overwrite or distinguish its generations; a memo address alone is not a globally stable object identity when reuse is accepted.
6. **Structured metadata is still incomplete** (`factoid.py:121–149`). Generated changes to frame/manager/axis/block/placement constructor kinds produce identical metadata. Additional BUILD state on a `_frombuffer` array is silently ignored. Retain all accepted constructor kind/state/placement metadata and shared relationships, or reject unsupported states. The retained original preserves the serialization bytes, but that fact does not establish completeness of the derived structured metadata interpretation. The lead already identified constructor-kind completion as pending work.

All these demonstrations use small generated fixtures in `/tmp/factoid-review-boundaries-20261007.py`; their safe reproduction and code locations were sent to the lead. They establish concrete implementation gaps, not evidence of a native record defect. Whole-source hashes do not cure incomplete interpretation or self-declared cached semantic hashes. Every auxiliary proof/manifest write also needs a pre-write allowance check if the output ceiling is intended to bound temporary allocation; the current total allowance is checked after those writes.

| Reviewed file | SHA-256 at 08:48 UTC |
| --- | --- |
| `src/dataset_atlas/converters/factoid.py` | `4c218b52454dc2b352e2b20596c0eea1b988c4d363644fb37bc2d93b912b8c74` |
| `src/dataset_atlas/converters/neutral_pickle.py` | `6ed7c424bd54df271613ed5c70fe03bf6d13a2111e051a5c9e417bc12a34350f` |
| `tests/unit/test_factoid_inert.py` | `7e5fd00017020cc0561fa335d9d00b24a93e8d46df2ea65aff5f9a4a881f8ac1` |

FACTOID remains unverified native integration at this checkpoint. Activation would require the repairs above, current native semantic parity, bounded preparation/API integration and refreshed combined release evidence. Historical paper membership, provenance and rights remain independent acceptance questions even after those software requirements pass.

## FACTOID repair recheck — 2026-10-07 09:00 UTC (18:00 JST)

**The concrete FACTOID findings above are closed for the current scoped implementation and generated boundaries.** Native coverage and overall release closure remain separate. This recheck used only the two converter modules and generated tests/probes; no native source, annotation, row, schema value, filename, browser state or conversation was inspected.

The first repaired checkpoint independently passed **35 generated tests**. Recomputing the expanded value digest and metadata SHA closes the original fixed-pin row-tampering case. Required original/metadata/proof roles, paths, sizes, source SHA and adapter pointers are now validated. Regular files are opened with `O_NOFOLLOW|O_NONBLOCK`, FIFO/symlink/oversize inputs refuse, and native-sized cached validation runs in a separately bounded subprocess. Parent cancellation checks kill/reap that child, and validation checks rows and the final return boundary. Bytearrays retain a distinct native envelope and actual shared memo identity; memo-slot overwrite refuses. Constructor kind/placement metadata and unknown `_frombuffer` BUILD-state refusal close the previously demonstrated metadata collisions.

Additional generated probes then reproduced four remaining boundaries: a fully self-consistent rewritten cache when caller semantic pins were absent; replacement of the shared result manifest after child validation; missing shared ndarray-node memo identity; and a `Counter` NEWOBJ being interpreted as REDUCE counts. The lead added regressions, and the reviewer independently observed the intermediate **35 passed / 3 failed** checkpoint for the first three boundaries. Those failures are retained as historical evidence. The Counter case used only a known benign stdlib constructor in a generated serialization, never native deserialization.

Current repairs now:

- Require explicit trusted immutable `metadata_sha256` and `native_values_sha256` pins for cached resume. A new conversion supplies the pins produced in its private worker stage; an old unpinned cache refuses instead of attesting its own semantic hashes.
- Return a bounded `validated-result.json` written in the private validation request directory. The parent no longer rereads the shared manifest after validation. Changing that manifest at the exact previous race point does not change the returned validated path/count/digest.
- Retain actual shared memo identities for frame, manager, axis, block and ndarray nodes, as well as buffer identities. The generated ndarray identity probe now retains the declared actual memo ID.
- Validate supported constructor kinds before interpreting values: Counter/datetime, arrays/dtypes, manager/axis/block/partial require their supported REDUCE routes; the DataFrame accepts only supported empty-argument REDUCE/NEWOBJ construction. The generated Counter NEWOBJ and array NEWOBJ cases refuse instead of manufacturing values. Unknown array BUILD state also refuses.

The current independent command `.venv/bin/python -m pytest -q tests/unit/test_factoid_inert.py` passes **40 tests in 1.06 s**. Separate generated probes in `/tmp/factoid-review-closures-20261007.py` confirm unpinned-cache refusal, private validated-result handoff, bytearray type/memo preservation, memo-reuse refusal, ndarray memo retention, Counter NEWOBJ refusal and unexpected array-state refusal. The earlier unsafe reproductions remain in the previous addendum and `/tmp` review scripts. No remaining severe concrete defect was reproduced in this requested recheck; this is not a proof that every pandas serialization layout or source-defined constructor is supported.

The converter now has a **4,000,000,000-byte total output ceiling**, with separate per-record/metadata/proof/manifest bounds and pre-write auxiliary allowance checks. Both conversion and cache validation use **8,000,000,000-byte address-space**, **360 s CPU soft / 370 s hard** and **480 s outer wall** limits. Address space is not an RSS measurement. Cancellation and guarded failure remove private partial stages. Input/source and code-contract checks are repeated before successful conversion completion; the original is copied byte-identically and retained read-only. These mechanisms remain subject to the native acceptance and integration proofs below.

The lead reports a preceding 4 GB-bounded native run produced **4,150 rows / 17,288,900 checked cells**, a **6,495,717-byte maximum record** and **2,385,847,137 total output bytes**. This is attributed aggregate evidence supplied by the lead. The earlier smaller-budget refusal remains historical. That successful run predates the latest constructor/metadata guards, so it does **not** certify this exact current source. A fresh current-contract native run, complete semantic/parity checks, registered preparation/API/query integration and combined package/test/source identity refresh are still required. No native index or recipe activation is asserted here. Scientific paper membership, rights and source identity interpretations remain independent of successful engineering conversion. Catalogue-wide `full_v1_complete` remains false.

| Current reviewed file | SHA-256 at 09:00 UTC |
| --- | --- |
| `src/dataset_atlas/converters/factoid.py` | `2c95b48ebe558a7f5b6fe0b05efb01976337c8eb6b3a68c306ec47d335ef80cb` |
| `src/dataset_atlas/converters/neutral_pickle.py` | `d655db055c01cd9f728748781c8bb75956d5817d6bcd5acebfae3a6ab1c59443` |
| `tests/unit/test_factoid_inert.py` | `f0d8ca3b1e1debe6e03c3da519b07b72de44afff12469873c330752023ea0b03` |

## FACTOID outer-stop lifecycle recheck — 2026-10-07 09:04 UTC (18:04 JST)

The lead's additional generated lifecycle test exposed a boundary outside the preceding 40-test checkpoint: `start_new_session=True` placed the inert conversion/validation child outside the outer preparation process group, allowing it to survive that group's SIGKILL. This failure remains historical; the earlier 40 tests did not certify the outer-stop boundary.

`_launch_worker` now uses **`start_new_session=False`**, so the fixed inert worker inherits the preparation group. Direct callback cancellation or the local deadline uses `process.kill()` on its exact child and `wait(timeout=5)` to reap it. The reviewed worker interprets passive source data and launches no source callable or subprocess, which is the scope supporting exact-child direct cancellation. Any later worker subprocess capability would require renewed descendant-lifecycle review.

The independent current suite passes **41 generated tests in 1.09 s**. The new regression starts a generated parent in its own group, launches a sleeping generated child through the actual launcher, kills the outer group and checks that the child is no longer executing. Existing direct conversion/cache-cancellation regressions still confirm reaping. This closes the reproduced surviving-worker case; no native process contents, files or logs were inspected. The lead reports current normal preparation in progress with trusted final semantic pins. Current native activation/parity and updated combined release attestation remain unclaimed and pending.

| Current lifecycle-reviewed file | SHA-256 |
| --- | --- |
| `src/dataset_atlas/converters/factoid.py` | `6785404fe1f785a3cc85f9592fb8e227bba59ba96758650440109cb5acb8ba0e` |
| `src/dataset_atlas/converters/neutral_pickle.py` | `d655db055c01cd9f728748781c8bb75956d5817d6bcd5acebfae3a6ab1c59443` |
| `tests/unit/test_factoid_inert.py` | `85bf19bdeeb9590d8a9b71d1e1a13f957d2f99536b1fc17c91712107096bc19d` |

## FACTOID production checkpoint — 2026-10-07 09:44 UTC (18:44 JST)

**FACTOID is now an activated production route for the pinned author user-row population**, according to the expressly permitted aggregate receipts. The former unregistered-experiment and pending-activation statements above are historical. This checkpoint does not claim catalogue-wide SPEC completion, universal pandas semantics, publication rights or historical paper-population identity. Only code and whitelisted aggregate receipt fields were reviewed; no native files, metadata values, user rows/posts, browser DOM/pixels/traces or model conversations were inspected.

### Native/reproduction evidence, attributed to the receipts

[Native population verification](factoid-native-population-verification-20261007.json), checked at 09:17 UTC, reports **4,150 native user rows, 17,288,900 native cells checked, 4,150 exact canonical-record comparisons, 83,000 materialized source-field comparisons and 4,150 search-text comparisons**. Its **100-record preview**, preview identities and exact snapshot were reproduced. The source pin is the **369,319,718-byte author serialization**; this is a user-row population, not a count of independent users' posts or conversations. Metadata and expanded-value digests are separately pinned.

[Empty-workspace preparation](factoid-empty-workspace-preparation-20261007.json) completes with **4,150 indexed rows** in approximately **302 s**, under explicit **400 MB acquisition / 7 GB prepared-output allowances**. Its recipe SHA agrees with population verification. The preparation allowance includes the complete index and retained derivatives; it is distinct from the converter's 4 GB output ceiling. That receipt's `preview_count` is null, so the reviewer uses the separately verified preview count rather than inferring one from it.

[HTTP verification](factoid-http-final-20261007.json) reports dataset, preview-pack and complete-query **HTTP 200**, **100 preview records** and an exact complete-query population of **4,150**. [FACTOID browser verification](browser-factoid-native-20261007.json), checked at 09:29 UTC, reports native-user inspection and complete-scope opening passed. These native assertions are attributed aggregate proofs produced by the lead; the reviewer did not inspect the underlying users, source annotations or UI. Snapshot and recipe identifiers agree across the relevant receipts. The reports support engineering integration of this pinned release, not an independent scientific accuracy, demographic or prevalence result.

### Current code and release checks

The converter/neutral-reader/test SHA values still match the preceding lifecycle-reviewed checkpoint. Independently rerunning the generated FACTOID suite passes **41 tests in 1.21 s**. All reported concrete preservation/cache/cancellation cases remain closed for those reviewed boundaries.

The generic preparation pack writer now calls `atomic(..., compact=True)`. The helper only removes JSON indentation/separator whitespace and retains `ensure_ascii=False`; it does not omit fields, shorten native strings, alter typed envelopes or change record ordering. The output reservation still uses the larger pretty-serialized byte estimate, making that check conservative. FACTOID's separate `literal-runs-v1` compression remains reversible and is inverse-checked per row; mutable/container values are not merged into runs merely because they compare equal. These two distinct forms of compact output must not be described as lossy text/media compression.

| Reviewed pack-write implementation | SHA-256 |
| --- | --- |
| `src/dataset_atlas/preparation/__init__.py` | `35e46b84ad57bde4280fa7923de241d54c6bea81941794eac84b73105bf8aa9e` |
| `src/dataset_atlas/preparation/worker.py` | `acfc88b21b66ab082089b6eb5f4647d633bad5e5265e5c0bd7f5e391a537152c` |

The permitted current log summaries independently report **1,026 passed / 1 skipped / 2 warnings on Python 3.12.14** and **1,023 passed / 4 skipped / 2 warnings on Python 3.14.2**. The lead reports **26 frontend tests and pinned `prek` checks passed**. The separate [3.12 clean install](installation-factoid-final-python312-20261007.json) and [3.14 clean install](installation-factoid-final-python314-20261007.json) both pass for the exact wheel **`062a3a5e0d72d34c3c7af0e777fc96810bafda1763ef1e951fd540472c9adf3e`**, with fresh **333-entry catalogues**. Both receipts explicitly show no optional model packages installed, so these clean environments do not certify those optional processors. The older default installation receipts still identify wheel `b3b00fc4…` and remain historical evidence.

**Current full-browser acceptance is still open at this checkpoint.** The lead preserved an initial **67/69** browser result while repairing runtime/provider failures. The newer `work/browser-factoid-verified-final-20261007.log` footer currently records **68 passed / 1 failed**; the failing code test is `e2e/factoid.spec.ts:6:1`. Only summary counts and the code test identifier were read, not assertion bodies, native source values or model replies. That current failure was promptly reported to the lead. The earlier passing 09:29 FACTOID receipt does not automatically certify this later full run. The synchronized final status and fresh distribution/source-identity attestation remain pending after these resumed changes.

### Counts, scope and read deviation

Current aggregate status agrees with **333 catalogue entries / 218 tested previews / 21,332 preview records / 216 complete-scope indices / 115 entries without preview**. The lead clarifies **84 recipe-bound fresh proofs** comprise **79 category-verified proofs plus five retained historical proofs whose actual recipe SHA still matches**. This is not 84 newly executed fresh runs in the resumed pass. It must not be inflated by generic planned verification or metadata-only PATA reproduction. `full_v1_complete` remains **false**; status is `implementation_resumed`, with current validation, runtime restoration and final rebuild/status synchronization flags still pending when read.

The authorized aggregate [lead read-deviation receipt](lead-native-audit-read-deviation-20261007.json) records that a lead tool read exposed a pre-existing native class/row-selection audit in model context. It states further verification is restricted to whitelisted aggregates and the independent reviewer was not sent those contents. The reviewer did not read the original audit. **Zero native-content exposure cannot be claimed for this resumed lead pass.** This deviation is retained separately from the reviewer scope and from engineering test results.

FACTOID source/model analysis remains passive and local; source code is not executed or hydrated into new third-party posts. Its verified canonical population and pinned annotation interpretation close the reviewed native-integration implementation gap for this release. Paper membership, source/publication rights and dataset-specific scientific claims remain human acceptance questions. Other public adapter/recipe gaps remain software work; publisher/licensed/unreleased-source gates and unresolved identities remain separate. Passing this integration cannot establish full SPEC completion or authorize publication of native user material.

## Wide-record query repair — 2026-10-07 09:54 UTC (18:54 JST)

The current full-browser FACTOID failure exposed a real default-page implementation defect, not a source/access blocker. The permitted [page probe](factoid-complete-ui-page-probe-20261007.json) records small **3/10-row requests returning HTTP 200**, while the default **60-row request returned HTTP 500**. The lead identified DuckDB top-k sorting of wide native `record_json` envelopes as the memory failure. That red evidence remains preserved alongside the passing earlier small-page/standalone browser receipts.

The scoped `queries/parquet.py` repair sorts **IDs and the required materialized sort/filter keys**, then fetches the selected envelopes through parameterized, bounded ID batches. Each batch is reordered against the selected key sequence, so physical Parquet fetch order cannot change the requested SQL order. Result joins remain query-local, require exact selected artifact IDs/snapshot/unit compatibility, and their predictions are attached to the corresponding keyed record. Sort tie-breaking and source/random sample ordering remain unchanged. The byte budget still counts combined encoded canonical record and prediction payloads, with a **32 MB page bound**; this is not a guaranteed process-RSS or total HTTP-envelope bound.

The cursor advances by **the number of records actually emitted**, not the original requested count or fetched batch size. A separate generated 80-record/500 KB-envelope probe independently confirms contiguous byte-shortened pages with no skipped/repeated records. The existing seeded/random parity, result-filter/join, snapshot/unit and byte-shortened pagination tests pass. The new generated **256-record × 500 KB** regression requests 60 sorted records at **64 MB / one DuckDB thread**, checks exact first/second-page order and confirms all original synthetic envelopes survive. A four-thread 64 MB case still refuses; its OOM is now surfaced as an actionable `ValueError`, rather than a raw server error.

The first scoped run passed **15 tests in 2.17 s**. Independent review then reproduced an additional cancellation gap: `snapshot.interrupt()` between ID selection and the first payload SELECT was lost because only an in-flight SQL interruption was recorded. `/tmp/parquet-wide-query-review-20261007.py` preserves that generated demonstration. The lead added a durable **per-active-connection cancellation Event**, set it in `interrupt()`, and checks it between statements, batches and yielded rows and before accepting results. The original probe now raises `ValueError` as intended. An intermediate rerun had **15 passed / 1 failed** because an older private fixture still treated `_active` as a set; the fixture was updated to map its connection to an Event and assert that it is set. That failure remains historical. The current independent suite passes **16 tests in 2.50 s**. No remaining concrete ordering/cursor/join/cancellation defect was reproduced within this scoped repair.

[Repaired native page receipt](factoid-complete-ui-page-repair-20261007.json) reports **HTTP 200, exactly 4,150 matches, 53 returned records, a continuation cursor, 31,987,211 response bytes and 6.04 s**. This is attributed native aggregate evidence; the reviewer did not read its records or UI. It demonstrates a functioning bounded default page. It does **not** demonstrate a two-second response target.

The repaired ID-only path applies to **non-stratified** queries. Wide stratified sampling still uses the prior record-envelope/window path and may refuse under its resource budget; it is not certified by this default-page repair. Query memory limits describe DuckDB, not all Python/result-table allocations. The lead is rerunning the full Python/browser suites and final package/identity evidence after the query changes. The earlier wheel/test receipts do not automatically certify this later code. Full SPEC acceptance remains incomplete.

| Current scoped query file | SHA-256 at 09:54 UTC |
| --- | --- |
| `src/dataset_atlas/queries/parquet.py` | `dffc257705e52aa18c27ef1ab5a413635627fe453da15b9670981b2bbe090c04` |
| `tests/unit/test_parquet_queries.py` | `4696bd9f0ae980e1194f9d02fee5d4ce2bb6d7a244411209bd4d097c510d8c71` |

## Final attributable closeout — 2026-10-07 10:03 UTC (19:03 JST)

At the lead's graceful-close request, this documentation-only addendum records the final supplied aggregate outcomes. **No further probing, native reads, package-inventory inspection or test runs were performed by the reviewer.** These outcomes are explicitly attributed to the lead and the named receipts/logs. They supersede the preceding pending combined suite/browser/package checkpoint; historical failures and the independently reviewed code boundaries remain preserved above.

| Final reported check | Outcome |
| --- | --- |
| `work/python-factoid-final-current-20261007.log` — Python 3.12.14 | **1,028 passed / 1 skipped / 2 warnings** |
| `work/python314-factoid-final-current-20261007.log` — Python 3.14.2 | **1,025 passed / 4 skipped / 2 warnings** |
| `work/browser-factoid-verified-final-20261007.log` | **All 69 browser checks passed**, captures disabled |
| Frontend / pinned checks | **26 frontend tests passed; `prek` passed**, as reported earlier in this resumed checkpoint |
| `reports/complete-index-smoke-factoid-attested-20261007.json` | **216 index queries passed** |
| Current clean-install receipts for Python 3.12 / 3.14 | **Both passed for the same final wheel** |
| `reports/distribution-source-parity-factoid-final-20261007.json` | **2,478 archive/source members; zero mismatches** |

The exact final wheel SHA is **`74656ccf74f6427c9fbed57c13cee63e338eddf4e8307f23839f04d1aad8ea64`**, reported in `installation-factoid-current-python312-20261007.json` and `installation-factoid-current-python314-20261007.json`. It supersedes the preceding resumed wheel `062a3a5e…`. A final sdist-only rebuild corrected documentation links without changing that final wheel. The lead reports the later Places browser failure was an asynchronous response-hash-listener teardown race; waiting for listener teardown with `removeAllListeners('response', {behavior: 'wait'})` was followed by the full successful 69-test rerun. The earlier browser failures are not erased or retroactively called passes.

Current reported catalogue counts remain **333 entries / 218 tested previews / 21,332 preview records / 216 indices / 115 entries without preview**. Documentation now describes **84 recipe-matching reproduction proofs: 79 verified categories plus five historical proofs whose actual recipe SHA still matches**. It does not describe 84 newly rerun recipes in this resumed pass. Native FACTOID correctness remains attributed to the aggregate parity/reproduction receipts discussed above, rather than reviewer access to user material.

The refreshed final configured-root allocated footprint is reported as **122,381,500,416 bytes (122.38 GB)**, with **6,801,600,512 bytes (approximately 6.80 GB) net reduction** from the retained baseline. It remains **above the 100 GB target and below the 150 GB ceiling**. These final point-in-time figures supersede the earlier **122.03 GB / approximately 7.15 GB reduction** checkpoint: original-media caches filled after browser reads. The lead reports an actual write/fsync probe passed and `workbench-factoid-final-state` records **zero active jobs**. All other final tests, wheel identity and 2,478-member parity outcomes are reported unchanged. The reviewer performed no fresh runtime/storage probe or inventory read during this correction.

**`full_v1_complete` remains false.** The reviewed working release, current engineering validations and FACTOID integration do not establish catalogue-wide historical identities, unresolved source/licensing availability, dataset-specific publication rights, all remaining public native adapters or scientific validity. The wide stratified path and the unmet two-second wide-page performance target remain explicit implementation/resource limitations. The lead's recorded native-audit exposure deviation and the reviewer's earlier disclosed scope deviation remain part of the closeout; passing suites do not remove them. This is the verified checkpoint supplied for graceful closure, not a claim that the full SPEC objective is achieved.
