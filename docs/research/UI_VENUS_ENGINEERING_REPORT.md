# Scenario identity, integrity, and local UI-Venus evaluation

This implementation preserves the canonical benchmark and adds a genuine local UI-Venus execution path. Software validation, adapter smoke, representative pilot and full coverage are separate evidence classes. None certifies publication readiness or independent external validity.

## Implemented changes

- `scenarios/identity.py` and `identities.json` provide explicit, collision-checked mappings for all 322 current and historical tasks. Public aliases resolve to original canonical IDs before fixture generation. API/display overlays never rewrite stored historical rows or canonical task objects.
- Frontend coverage, preview, review, live execution and result views use public IDs and descriptive simulated/provider-inspired titles. Run details identify observation channels, failure categories, inference backend, checkpoint and quantization.
- The dedicated Venus adapter uses the documented 1.5 native web prompt/action grammar, an isolated MLX worker, exact checkpoint hashes and a pinned runtime. Validated actions use the shared browser runner; objective scoring remains independent.
- The shared screenshot loop persists original observations, native responses, exact public prompts, action history and execution outcomes. It rejects malformed/off-screen actions, distinguishes unsupported capabilities and inference errors, terminates stalls, and never treats a model's completion assertion as task success.
- Frozen task/release hashes remain unchanged. An explicit reviewed runtime binding records changed execution sources. Official protocol selection separates runtime/checkpoint configurations, including quantization, image/context settings and prompt/code hashes. Historical identity shapes remain compatible.
- Research exports retain canonical reproducibility metadata and use a public field allowlist consistently, including nested analysis records.

Delegation: one agent owned scenario identities/frontend, one owned the native model/local runtime, and a reviewer audited fixture integrity and implemented runner lineage/failure classification. The lead integrated shared execution, protocol/publication boundaries, evaluations and final review. Agent-written tests use labelled doubles; those are never counted as model inference.

## Naming and benchmark integrity

The 322 mappings include all 174 active tasks. Examples are `V3-G01`→`GENERIC-01`, `V3-ST03`→`STRIPE-03`, and `V3-R02`→`IRCTC-02`. Historical variants receive distinct `CLASSIC`, `FOUNDATION`, or `LEGACY` names. Canonical and public namespaces cannot overlap and duplicate aliases fail validation.

All 322 default canonical scenario hashes match the pre-edit baseline. All 41 protected original files, including the frozen release and checkout fixtures, remain byte-identical. The sole original catalog change resolves aliases before the unchanged canonical generator. See [the integrity audit](SCENARIO_VENUS_INTEGRITY_AUDIT.md) and [identity contract](../SCENARIO_IDENTITIES.md).

Recent CUA label/candidate-format transformations were isolated diagnostics. No model accommodation was found in canonical tasks, so no fixture reversion or score-oriented adjustment was made. The original CUA failure record and 82 associated artifacts are retained unchanged.

## Local runtime and observation contract

Observed hardware: Apple M1 MacBookAir10,1 with 8 GiB unified memory, macOS 27.0.1, Python 3.12.12. Original weights alone occupy 4,877,469,712 bytes; original precision was not loaded. The evaluated artifact is `mlx-community/UI-Venus-1.5-2B-6bit` at `95e3994ac9d74fe047cf44c072f6569db62856e7`, affine 6-bit/group 64 with mixed BF16 tensors. It is a community conversion, with the conversion's precise upstream commit unreported; the independently inspected official revision is not falsely presented as that source commit.

The subprocess uses MLX 0.31.0/MLX-VLM 0.3.12 and the native Transformers 5.2 processor. It verifies all pinned artifact files before loading. The requested 4.25 GB MLX memory limit is a graph-evaluation guideline, not a hard allocation or process-memory cap. MLX-VLM temporarily uses the device's recommended wired working-set limit during generation (5,726,633,984 bytes here). Browser, processor and OS memory require additional headroom. Only one model worker runs at a time. Cancellation terminates the worker. The [local operation guide](../operations/UI_VENUS_LOCAL.md) links the pinned implementation and MLX API documentation.

The model receives a screenshot, public synthetic customer task and native action history. It receives no DOM labels, selectors or expected-answer mappings. DOM telemetry is used only for the shared stall monitor and private verification. The screenshot track therefore differs from CUA's field semantics plus deterministic navigation; a direct claim of equal assistance would be incorrect.

See [reproducible local setup](../operations/UI_VENUS_LOCAL.md) for precise revisions, dependencies, preprocessing, prompts, supported/unsupported actions, decoding and attestation commands.

## Phase A: actual adapter validation

The corrected adapter's unmodified generic-form screenshot produced the same
genuine native click on cold and warm inference. Cold elapsed **27.46 s**, warm
**14.94 s**, and peak MLX allocation approximately **3.392 GB**. Native
`Click(box=(496,233))` maps to browser `(634,209)` using the documented normalized
contract. Independent execution on a fresh, pixel-identical screenshot missed
the email input and did not focus it. This is a valid grounding failure for the
corrected configuration alongside successful load/infer/parse/execute plumbing.

Evidence: `data/research/venus/adapter-validation-normalized1000/`; exact
attestation: `data/research/venus/checkpoint-verification-normalized1000.json`.
A final timing-only worker correction was re-attested at `data/research/venus/checkpoint-verification-final-metrics.json`, with evidence in `adapter-validation-final-metrics/`. It produced the same native action: cold total 22.80 s, warm total 14.61 s, warm model-forward time 14.50 s. The cold call correctly records no warm-only timing. This final record is registered for the pilot and full run.

The original pixel-coordinate and environment-default smoke records are retained
as superseded adapter-development evidence. Repeated saved-image calls establish
inference reproducibility, not multi-step checkout competence.

## Phase B: initial pilot invalidated by an adapter contract error

Plan: `research/ui-venus-pilot-plan.json`. One trial per case, seed 2026/default scenario profile, canonical viewports, 80 actions, 180 seconds, 256 output tokens, greedy generation, no infrastructure retries. The token cap is diagnostic and differs from the full evaluation.

| Public scenario | Initial adapter observation (invalid evaluation) | Genuine calls | Executed actions | Elapsed seconds |
| --- | --- | ---: | ---: | ---: |
| GENERIC-01 | No progress | 3 | 3 | 62.7 |
| SHOPIFY-01 | No progress | 5 | 5 | 116.0 |
| IRCTC-02 | Rejected by incorrect pixel bounds | 1 | 0 | 37.0 |
| STRIPE-03 | Rejected by incorrect pixel bounds | 2 | 1 | 63.2 |
| RAZORPAY-01 | Rejected by incorrect pixel bounds | 3 | 2 | 78.8 |
| CASHFREE-01 | Rejected by incorrect pixel bounds | 6 | 5 | 154.4 |
| RAZORPAY-QR-REGRESSION-00 | Rejected by incorrect pixel bounds | 3 | 2 | 71.4 |

Observed historical result: 0/7 successful checkouts, 23 genuine calls, 18 executed actions. **These are not valid model-performance measurements.** The initial parser labelled five outputs invalid, but its coordinate bounds were wrong; that rate cannot be attributed to the model. No output-token truncation, task timeout, inference error or unsupported-capability termination was observed. Required-field accuracy was 0 in each case. Optional fields were left untouched; this is not evidence of successful form completion.

Local evidence: `data/research/venus/pilot-report-01/`, `data/research/venus/pilot/validation/`, and an exact source/binding snapshot at `data/research/venus/pilot-runtime/`. The first generic case overlapped part of a software-test run, so use the separate smoke measurements for local performance characterization; pilot latency is descriptive, not a controlled hardware comparison.

### Coordinate correction and required rerun

The pinned generic navigation example scales resized-image pixels, but the
[official UI-Venus 1.5 report, section 3.1.1](https://arxiv.org/html/2602.09082v1#S3.SS1.SSS1)
specifies normalized 0–1000 targets for its unified action space. The dedicated
1.5 grounding implementation divides predictions by 1000, and the official
Venus framework action prompt independently describes normalized coordinates.
The generic example is inconsistent with these model-specific sources; its
literal code ancestry is not established.

The adapter now follows the documented normalized contract, without
any scenario-specific coordinate offset, prompt tuning or fixture edits. The
initial pilot's original rows, raw outputs, screenshots and runtime are retained.
An exclusion sidecar prevents reporting its historical failure classifications
as model reasoning or grounding performance. The exact seven-case plan must be
rerun under the corrected adapter before full coverage starts.

## Phase B: corrected seven-case pilot

The same predefined cases were rerun under adapter `ui-venus-1.5-web-mlx-v2-normalized1000` and the final timing-fixed worker. All seven intended trials completed: **0/7 successful checkouts**, five no-progress model failures, one evaluation timeout, and one invalid native action. There were 35 completed genuine generations from 36 attempted calls, 34 executed actions, no inference failures and no token-limit truncations. The invalid action predicted `y=1100`, outside the documented native range. Required-field correctness was **0/53**. All seven optional-field checks passed because those fields were left untouched; this does not establish successful checkout.

| Public scenario | Corrected outcome | Genuine calls | Executed actions | Elapsed seconds |
| --- | --- | ---: | ---: | ---: |
| GENERIC-01 | no_progress | 3 | 3 | 59.6 |
| SHOPIFY-01 | no_progress | 5 | 5 | 109.8 |
| IRCTC-02 | no_progress | 4 | 4 | 102.2 |
| STRIPE-03 | invalid_model_action | 5 | 4 | 129.7 |
| RAZORPAY-01 | no_progress | 6 | 6 | 150.0 |
| CASHFREE-01 | timeout | 6 | 6 | 182.2 |
| RAZORPAY-QR-REGRESSION-00 | no_progress | 6 | 6 | 160.8 |

Total trial time was 894.3 seconds; median completed model-call time was 23.75 seconds. Peak MLX allocation was 3.392 GB. These are observations on this machine, not a controlled hardware comparison. The reviewed first trace shows three identical ineffective clicks, correctly mapped from normalized coordinates, with unchanged screenshot hashes and no private task inputs; the shared stall monitor terminated it at three repeats. No further adapter defect was found in that review.

The sanitized summary is `research/venus/pilot-summary.json`; complete private traces remain in `data/research/venus/pilot-normalized1000/validation/` and `data/research/venus/pilot-normalized1000-report/`. The exact runtime snapshot is `data/research/venus/normalized1000-runtime/`. The server began before the implementation commit, so its recorded source commit is the baseline; the complete changed execution identity is retained by the exact runtime source/binding hashes and snapshot.

## Phase C: full coverage

Plan: `research/ui-venus-full-plan.json`, all 174 active scenarios, one trial each, 8,192 output tokens, 80 actions, 180 seconds, no retries. The user confirmed that the machine could remain powered and awake; AC power was subsequently observed. This remained a separate diagnostic study throughout execution and did not replace the official dataset.

Batch `fd3f7e5e664d4bafa9f94c29d4ead6ab` finished on 17 October 2026. All 174 unique planned case attempts reached terminal records. Every record matches its frozen canonical scenario hash and viewport, the declared execution settings, the same checkpoint attestation, and the reviewed runtime binding. All execution manifests identify implementation commit `3d03a06a7ca41a71869f08a70765a0bfb17365dc`; documentation commits during execution did not change runtime sources.

| Terminal outcome | Cases |
|---|---:|
| Independently verified successful completion | 0 |
| Evaluation timeout | 168 |
| No-progress model failure | 4 |
| Invalid native model action | 1 |
| Infrastructure/inference failure | 1 |
| Unsupported capability | 0 |

There were 492 attempted model calls: 325 completed genuine responses, 166 cancelled calls, and one inference failure. Of the 174 cases, 162 had at least one completed genuine response and 12 had none. The latter retain declared configuration and execution bindings but no completed worker-reported runtime measurements. **Complete coverage of case attempts does not mean every case produced a model response or completed its checkout.**

The runner recorded 322 executed actions. The invalid-output rate was 1/325 completed genuine responses (0.31%); the inference-failure rate was 1/492 attempted calls (0.20%). No completed response reported token-budget truncation; partial-token and truncation information is unavailable for cancelled calls. Final required-field checks were correct in 13/1,252 checks, with mean per-case accuracy 1.20%. These are final-state checks and can include supplied autofill; they are not counts of fields correctly entered by the model. Optional-field checks passed in 174/174 cases because optional inputs were left untouched, which does not establish checkout competence.

Total recorded trial time was 32,220.5 seconds (8.95 hours). Median completed call time was 57.69 seconds. The 162 completed cold calls had median loading time 23.68 seconds; the 163 completed warm calls had median model-forward time 37.78 seconds. Cancelled calls cannot supply complete stage timings. The largest reported MLX allocation among completed responses was 3,392,391,229 bytes (3.392 GB); peaks during cancelled or crashed generations are unknown. The 180-second task budget excludes some setup/teardown accounting, so recorded wall time can exceed it; the maximum recorded trial time was 207.77 seconds.

The infrastructure failure occurred in `LAYOUT-AUTOFILL-STALE`: the native worker exited with a Metal command-buffer GPU timeout before returning a response. The full error remains in the private run record and `infrastructure-failure-review.json`. Its cause is unresolved; it is not counted as a model reasoning failure. Later trials continued with fresh workers. The evaluation client exited successfully after saving all records, and no Venus worker remained after completion.

The [sanitized full summary](../../research/venus/full-summary.json) includes every case's outcome, response coverage, exact configuration and evidence hashes. Complete private traces remain under `data/research/venus/full-normalized1000/validation/`, and reports under `data/research/venus/full-normalized1000-report/`. The runtime source hash is `2a508b5aa668fec3083fe1d8cc1397391bbd8701d7d549f744e60550a277a91f`, with binding `0eb881e5edd6b7b12245a8d421f4263d87a595cf8c49ccc6978db2a7ff028412`. No official leaderboard result or original-precision performance claim is made.

Resource observations during the run show active paging and compression, with sampled kernel pressure alternating between normal and warning. No critical flag was sampled; sparse sampling cannot rule out intervening spikes. A five-second sample recorded approximately 204 MiB of swap-in and 88 MiB of swap-out. Later observations included much lower prefill throughput: an early 2,470-token prompt processed at about 179 tokens/s, versus about 25 tokens/s for another prompt of the same token count. These are system-wide resource observations and individual call measurements, not a controlled causal comparison. Memory contention plausibly contributes to the slowdown; thermal throttling and App Nap have not been established.

Read-only process reviews found one active model worker and browser tree, with earlier workers disappearing between trials. No accumulating task-owned workers, browser trees, or concurrent diagnostic inference were identified. Peak MLX allocation around 3.392 GB on completed responses is not total system memory or a measured peak for cancelled generations. The local evidence directory retains `runtime-memory-review.json`, `runtime-latency-review.json`, and periodic `runtime-resources.jsonl` snapshots.

The full study measures completion by this quantized local system within a fixed 180-second task budget. A timeout before any completed response is not evidence of a model reasoning error. The summary distinguishes attempted cases, cases with completed genuine responses, cancelled calls, and independently verified successes. It cannot establish hardware-independent model accuracy or attribute the timeout distribution solely to the model.

## Validation and remaining limits

Before edits: 123 relevant tests passed, including explicitly enabled genuine CUA checks, and the frontend production build passed. The complete software run exercised 325 tests: 322 passed initially and three failed because legacy browser tests hardcoded the default port. Those test URLs now derive from the actual preview origin, and all three passed on rerun. The final coordinate/metrics/protocol regression suite passed 138 tests (including three added metrics cases). The final frontend production build passed. The existing four CUA Transformer warnings remain. Browser reference sweeps validate benchmark software and are not UI-Venus performance evidence.

Final preservation checks confirmed all 322 canonical scenario hashes, 41 protected files, both historical databases, the original CUA failure record and all 82 associated artifacts remained unchanged. The completed run retained its exact reviewed runtime identity. Secret scans found no known secret values or credential-pattern matches in the files selected for publication; model weights, environments, secrets and raw traces remain ignored.

The integration adds no cloud service and makes no external payment. Local API charges are zero; energy cost is not measured. Peak MLX allocation is not total system RAM. Quantization, community conversion provenance, synthetic environments, shared implementation ancestry and one trial per case limit generalization claims.

The next experimental step should address memory headroom and measure inference under controlled resource conditions, then repeat a separately declared pilot without changing canonical fixtures. Any alternate precision, prompt or context experiment requires a separate declared configuration and evidence set.
