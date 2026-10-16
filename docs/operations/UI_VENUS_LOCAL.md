# UI-Venus 1.5 on the 8 GB MacBook Air

This integration runs genuine screenshot inference locally, in a persistent MLX subprocess. It shares CheckoutBench's public-task/observation/action/evaluation runner with other models. It does not change checkout fixtures, use DOM labels as model inputs, look up target selectors, or substitute reference-executor decisions. No cloud service is required or implemented.

## Exact evaluated configuration

| Item | Configuration |
| --- | --- |
| Upstream model | `inclusionAI/UI-Venus-1.5-2B` |
| Independently inspected upstream revision | `bc4c6e62a1c545e043761439be95646d801853a4` |
| Actual loaded artifact | `mlx-community/UI-Venus-1.5-2B-6bit` |
| Actual artifact revision | `95e3994ac9d74fe047cf44c072f6569db62856e7` |
| Weight SHA-256 | `2882730dbeca4c0f68131c6f98f49943bf3cc08d063a66a963c3e500d8397c84` |
| Precision | Affine 6-bit, group size 64; remaining tensors BF16 |
| Architecture | Qwen3-VL, 28 language layers; 24 vision layers; patch size 16, spatial merge 2 |
| Inference | MLX 0.31.0 / mlx-vlm 0.3.12 / mlx-lm 0.30.7 |
| Processor | Transformers 5.2.0 native Qwen3VLProcessor / Qwen2VLImageProcessorFast |
| Processor dependencies | Torch 2.10.0 and torchvision 0.25.0, only in the isolated environment |
| Native prompt source | UI-Venus `UI-Venus-1.5`, commit `192a9247ad1129279ba1d6c263d4c9e7ecef3644`, `models/navigation/utils.py` |
| Observed machine | MacBookAir10,1, Apple M1, 8 GiB unified RAM, macOS 27.0.1 |
| Python | 3.12.12 |

This is explicitly a **community quantized configuration**, not an original-precision result. The community card identifies the official source model but does not publish the exact upstream commit used for conversion. The current official revision above is a reference inspected independently, not a falsely inferred conversion source revision. `model_revision` and `checkpoint_revision` in runtime metadata identify the actual loaded conversion. `upstream_reference_revision` and `upstream_conversion_revision_status` preserve that limitation.

The official weight file is 4,877,469,712 bytes, before image activations, KV cache, browser, and operating-system memory. Loading it at original precision was not attempted on this 8 GiB machine. The selected conversion is 2,464,975,767 bytes. Its architecture matches the original model. The original safe tensor header includes separate language embeddings and output-head tensors despite its tied-embedding configuration; the conversion documents an untied-embedding workaround. Its native `chat_template.json` and `preprocessor_config.json` are byte-identical to the inspected official files. Tokenizer packaging differs and is pinned by hash. This evidence supports compatibility, not numerical equivalence to original weights.

## Installation

Keep the application/CUA environment intact. From the repository root:

```sh
.venv/bin/python -m venv .venv-venus
.venv-venus/bin/python -m pip install -r scripts/diagnostics/venus_requirements.lock.txt
.venv-venus/bin/python scripts/diagnostics/venus_setup.py
```

The smaller `venus_requirements.txt` records the intentional top-level pins; the lock records the complete tested environment. These packages are macOS/Apple Silicon specific. No CUDA dependency is required. Torch/torchvision are used by Transformers' native processor: the torch-free processor path failed because Transformers 5.2 validates the optional Qwen3 video processor even for still screenshots. All model weights and forward generation run on MLX, not PyTorch.

Setup downloads only the pinned safetensors/config/tokenizer/template files to ignored `data/models/ui-venus-1.5-2b-mlx-6bit`. It checks remote weight SHA-256 and writes local provenance. It never loads pickle or executes checkpoint-supplied Python. The reviewed `venus_artifact_manifest.json` binds all 11 files. The worker rehashes those files on each cold start and rejects a modified local manifest or checkpoint. No weights belong in Git.

The default local paths work without environment variables. Empty or whitespace-only `.env` placeholders are treated as unset, including paths and numeric settings; explicit nonempty values are preserved. Optional backend-only settings are:

```sh
UI_VENUS_BACKEND=mlx
UI_VENUS_MODEL_PATH=/absolute/checkoutbench/data/models/ui-venus-1.5-2b-mlx-6bit
UI_VENUS_PYTHON=/absolute/checkoutbench/.venv-venus/bin/python
UI_VENUS_MAX_PIXELS=1003520
UI_VENUS_INFERENCE_TIMEOUT=180
UI_VENUS_MEMORY_LIMIT_BYTES=4250000000
UI_VENUS_HISTORY_LIMIT=20
```

Unset `UI_VENUS_ENDPOINT` for this local integration. It deliberately refuses to attest a remote endpoint or silently switch backend. A future inference backend can implement the same adapter contract without changing the evaluator; no cloud infrastructure is included.

## Native inference and browser semantics

`backend/adapters/venus.py` exposes `VenusAdapter(max_tokens=...)`, async `act(image, public_task, history)`, async `close()`, `metadata()`, and `last_metrics`. Input consists of the current screenshot, an allowlisted projection of the public customer task, and recent native model action history. Internal IDs, expected values, selectors and evaluator state are not prompt inputs.

The official 1.5 web prompt is preserved, including its `<think>`, `<action>` and `<conclusion>` output format, with the checkpoint's own chat template. The system message is the upstream “You are a helpful assistant.” The executor receives only safely parsed literal arguments. Generated Python is never evaluated.

Supported native actions include `Click`, `DoubleClick`, `Hover`, `LongPress`, `Drag`, `Scroll`, `Type`, `PressEnter`, allowed browser `Hotkey`, `Wait`, `Finished` and `CallUser`. `Type` inserts text and presses Enter, as the native web prompt specifies. `Finished` declares model completion but never grants evaluator success. `CallUser` reports a handoff request; merely emitting it does not prove that the browser has reached the correct authorisation stage. `Launch`, `PressBack`, `PressHome` and `PressRecent` remain explicit unsupported capabilities in the confined browser track. Unknown syntax, multiple actions, extra arguments and off-screen coordinates are invalid outputs.

Coordinates use the native normalized **[0,1000]** space, as explicitly specified for all spatial targets in the UI-Venus 1.5 report §3.1.1. Each coordinate maps directly to the original browser viewport using `int(value * dimension / 1000)`; the inclusive endpoint 1000 maps to the last valid pixel. Values below 0 or above 1000 are rejected. This applies to Click, DoubleClick, Hover, LongPress and both Drag endpoints, regardless of image resize. The official model-specific grounding parser divides coordinates by 1000, and the official Chinese mobile navigation prompt also declares normalized coordinates. The generic navigation example instead uses resized pixels and factor 28: it is inconsistent with these model-specific sources and is not the coordinate authority. No heuristic or score-dependent coordinate selection is used.

The adapter version is `ui-venus-1.5-web-mlx-v2-normalized1000`. Image preparation remains the actual Qwen3-VL patch16 × merge2 = 32 grid, with verified `image_grid_thw`. At the diagnostic 1280×900 viewport, the observation is resized to 1184×832 under the fixed pixel budget, giving grid `[1,52,74]`. These dimensions describe the model input only; they do not define the action-coordinate denominator.

Decoding is greedy (`temperature=0`, `top_p=1`, seed 0), with chunked prefill of 256 tokens. Repetition penalty is disabled (MLX default `None`, effective factor 1.0), explicitly recorded in metadata. The upstream navigation example uses 1.05; this is a disclosed controlled-decoding difference, not a claim of identical upstream decoding. The setting was not changed in response to model results. The generation budget is the benchmark's configured `max_tokens`, not an undisclosed low cap. The initial adapter diagnostic used 256 tokens; it must not be confused with the full benchmark's protocol budget. Current-image-only observations and the last 20 native actions are recorded as the context policy.

The MLX worker is a local subprocess communicating over pipes, with no browser/DOM API or network inference endpoint. Weights stay loaded between steps. Every run closes the worker. Inference timeout or cancellation terminates the process and releases its memory, instead of leaving an uncancellable native call in a background thread. The worker requests a 4.25 GB MLX graph-evaluation memory guideline; this is not a hard allocation or process-memory cap. Torch processor, browser and OS memory are additional. The pinned MLX-VLM generation context also temporarily sets the wired-memory limit to the device's recommended working-set size (5,726,633,984 bytes here), then restores the prior setting. Neither setting proves that amount is allocated or guarantees system memory headroom. MLX cache is limited to 256 MiB. Do not run two model workers concurrently on this machine. See the [MLX memory-limit documentation](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_memory_limit.html) and [pinned MLX-VLM implementation](https://github.com/Blaizzy/mlx-vlm/blob/v0.3.12/mlx_vlm/generate.py#L180-L214).

`model_forward_seconds` records generation time for every call. `warm_inference_seconds` is null on the first, cold call and records generation time only when weights were already loaded; cold loading is recorded separately. Earlier evidence written before this timing-label correction incorrectly populated the warm field on cold calls. Preserve those records, but do not treat that field as a warm-only aggregate without filtering by `call_temperature`.

## Diagnostic reproduction and attestation

Start the ordinary local CheckoutBench application first, then capture an **unmodified** fixture:

```sh
.venv/bin/python scripts/diagnostics/venus_capture.py \
  --scenario V3-G01 --output data/research/venus/capture

.venv/bin/python scripts/diagnostics/venus_probe.py \
  --image data/research/venus/capture/input.png \
  --task data/research/venus/capture/preview.json \
  --output data/research/venus/adapter-validation \
  --click-smoke --calls 2 --max-tokens 256

.venv/bin/python scripts/diagnostics/venus_verify.py \
  --smoke data/research/venus/adapter-validation/results.json \
  --output data/research/venus/checkpoint-verification.json --register
```

`--click-smoke` asks only to click the visible Receipt email input. It is an explicitly separated adapter diagnostic, not the full customer checkout task. Omit it to probe the complete public task. The probe repeats identical inputs to measure cold/warm calls; it does **not** itself execute the generated actions or count as a multistep benchmark. Browser actions, updated observations, independent outcomes and complete pilot traces are exercised by the shared runner.

`--register` explicitly merges only the `ui-venus` record into the active `BENCH_DATA_DIR/research/checkpoint-verification.json` while preserving every other model entry. The verification CLI loads the repository `.env`, with existing environment variables taking precedence. Without `--register`, `--output` writes only standalone evidence and does not activate it in the application. Smoke generation never registers a model automatically.

`backend/adapters/venus_verification.py` provides `create_record(smoke_results_path)` and `verify_record(record)`. Attestation binds the actual inference evidence, screenshot, public task, processor dimensions, raw parsed response, exact artifact, isolated Python executable, runtime package versions, Metal hardware, prompt, adapter, worker, requirements lock and verification code. Changed evidence or bindings require new verification. A valid attestation means the local inference/plumbing contract was demonstrated; **it does not certify grounding accuracy or checkout success**.

## Actual local validation

The initial real diagnostic used an unmodified original generic checkout (`V21-G01`) and the 1280×900 browser screenshot. Both calls generated the same native action, `Click(box=(496, 233))`, from the actual image. The output contained 138 generated tokens. The first call took 24.96 s including 8.09 s cold loading and 16.45 s forward/generation; the second took 14.73 s total, with 14.63 s forward/generation. Peak MLX allocation was approximately 3.392 GB. These are measurements on this M1 Mac, not upstream card performance claims.

The initial adapter incorrectly interpreted native coordinates as pixels in the resized model image. Its mapped browser click `(536,252)` fell outside the email field. That execution and the initial seven-case pilot are **invalid adapter evidence for model performance**, superseded by the normalized-coordinate correction. The original observed 0/7 pilot outcome is preserved for audit, but must not be reported as the model's reasoning/grounding performance. Correcting the conversion is based on the official 1.5 report and model-specific implementations, not on selecting a mapping that improves scores. The native prompt, weights, fixtures, processor and decoding settings remain unchanged.

Historical evidence is retained unchanged: `adapter-smoke/click-probe`, `adapter-validation-bound`, `adapter-validation-final`, `adapter-validation-env-defaults`, and their checkpoint records. The environment-default diagnostic took 21.59 s with peak MLX allocation 3.392 GB; those resource measurements remain observations of genuine inference, while its old coordinate execution is invalid. New source-bound evidence is recorded in `data/research/venus/adapter-validation-normalized1000`, with the standalone attestation `data/research/venus/checkpoint-verification-normalized1000.json` explicitly registered in the active registry. The two fresh genuine calls took 27.46 s cold and 14.94 s warm, with peak MLX allocation 3.392 GB. Both returned `Click(box=(496,233))`, correctly mapped by adapter v2 to browser `(634,209)`. An independent fresh original V21-G01 browser capture matched the inference screenshot pixel for pixel. Executing the corrected action still missed the Receipt email field and did not focus it: this new diagnostic is a valid grounding failure under the documented coordinate contract. Before/after screenshots, target bounding box, raw action and private focus verification are preserved in that directory. The replacement seven-case pilot subsequently completed with zero verified successes; its outcomes and the separate full-run status are recorded in the [engineering report](../research/UI_VENUS_ENGINEERING_REPORT.md). This diagnostic itself is not a checkout benchmark. Model-specific unit tests use clearly marked test doubles and are not model results. Shared-runner outcomes must be read from their persisted run records. No full benchmark success is asserted by this setup document.

## Official and implementation sources

- [Official UI-Venus-1.5-2B checkpoint](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/tree/bc4c6e62a1c545e043761439be95646d801853a4)
- [Official 1.5 native web prompt and actions](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/utils.py)
- [Inconsistent generic navigation coordinate example](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/ui_venus_navi_agent.py)
- [Pinned MLX conversion card and limitations](https://huggingface.co/mlx-community/UI-Venus-1.5-2B-6bit/blob/95e3994ac9d74fe047cf44c072f6569db62856e7/README.md)
- [MLX-VLM 0.3.12 runtime](https://github.com/Blaizzy/mlx-vlm/tree/v0.3.12)

- [Official 1.5 report, normalized spatial targets §3.1.1](https://arxiv.org/html/2602.09082v1#S3.SS1.SSS1)
- [Official model-specific 1.5 grounding normalization](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/grounding/ui_venus1_5_gd.py#L167-L170)
- [Official mobile action prompt with normalized coordinate range](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/Venus_framework/processor/uivenus_processor.py#L9-L26)

The final worker timing correction is separately attested by
`data/research/venus/checkpoint-verification-final-metrics.json`, registered in
the active registry. Its new evidence directory is
`data/research/venus/adapter-validation-final-metrics/`: identical genuine native
action and normalized mapping, cold total 22.80 s, warm total 14.61 s, and warm
model-forward time 14.50 s. The cold call's warm-only metric is null. Earlier
evidence remains preserved.
