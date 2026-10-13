# Specialist inference

CheckoutBench implements four distinct inference adapters in `backend/adapters/specialists.py`. They do not download weights, invent decisions, or fall back to another model. Missing dependencies, checkpoints, incompatible hardware and failed endpoints raise `SpecialistUnavailable`; invalid output raises `SpecialistOutputError`. The runner should record unavailable infrastructure separately from model failures.

| Class | Async call | Model role |
| --- | --- | --- |
| `CuaS1Adapter` | `score_fields(elements, profile)` | Parallel field/option classification |
| `TinyClickAdapter` | `ground(PIL_image, instruction)` | Screenshot grounding |
| `MaiUIAdapter` | `act(PIL_image, task, history)` | GUI action generation |
| `VenusAdapter` | `act(PIL_image, task, history)` | GUI action generation |

Every adapter exposes `last_metrics` (inference seconds, checkpoint ID, backend; generation adapters also expose token usage where supplied). First-call timing includes lazy loading. The benchmark should disclose cold versus warm model execution. Remote monetary cost is unknown unless separately supplied by the serving infrastructure; do not interpret absent pricing as zero. `specialist_catalog()` returns configured/unavailable states without loading models or probing remote servers. `configured_unverified` explicitly means that successful inference has not yet been demonstrated. `detect_hardware()` reports CPU, CUDA and Apple MPS availability.

## Configure local inference

Install optional inference dependencies in the backend environment. MAI/UI-Venus require a Transformers release with `Qwen3VLForConditionalGeneration` (upstream specifies `transformers>=4.57.0`); PyTorch and Pillow are also required. CUA-S1 requires the `cua_s1` package installed from the official [Cua repository](https://github.com/trycua/cua/tree/main/libs/cua-s1/python), plus safetensors. TinyClick's Florence custom implementation can require a separate Transformers environment; serving it remotely avoids dependency conflicts.

Set absolute paths to weights that you have obtained and audited:

```sh
CUA_S1_MODEL_PATH=/absolute/models/cua-s1-forms
TINYCLICK_MODEL_PATH=/absolute/models/TinyClick
MAI_UI_MODEL_PATH=/absolute/models/MAI-UI-2B
UI_VENUS_MODEL_PATH=/absolute/models/UI-Venus-1.5-2B
```

Each prefix supports `_DEVICE=auto|cpu|cuda|mps` (CUDA device indices also work). Auto chooses CUDA, then MPS, then CPU. All loading uses `local_files_only=True`, safetensors only, and no pickle. CUA-S1 invokes the upstream `load_checkpoint`, which validates the JSON sidecar and SHA-256 tensor signature. Do not use any historical `cua-s1-forms.pt` file.

TinyClick's older Florence auto loader needs locally available model/processor code. `TINYCLICK_TRUST_LOCAL_CODE=1` explicitly enables the Transformers custom-code loader after you have reviewed that code. This does not download missing files; ensure the complete local model and code dependencies are present. The adapter never automatically changes to a different repository ID.

The original requested [kzawistowsk/TinyClick repository](https://huggingface.co/kzawistowsk/TinyClick/tree/main) contained only README and attributes when inspected on 2026-10-13. Its model card example names `Krystianz/TinyClick`, while the paper names `Samsung/TinyClick`; the linked SamsungLabs source repository returned 404. These are reported provenance blockers, not silently interchangeable checkpoints. The implemented postprocessor accepts Florence location tokens for a point or bounding box, maps 1000 bins to pixels using bin centers, and uses a bounding box center for clicking. This follows the Florence quantization convention and paper's point/box-center metric; it has not been verified against the inaccessible TinyClick utility or live weights. If using another artifact, explicitly record its exact origin/revision in the experiment configuration before interpreting it as the requested model.

## Hardware and compatibility

These are capacity estimates, not measured model performance:

| Model | Raw weight footprint | Practical guidance |
| --- | --- | --- |
| CUA-S1 706K | About 3 MB FP32 | CPU is appropriate; no GPU needed |
| TinyClick 270M | About 1.1 GB FP32 | CPU possible; budget several GB for processor/activations |
| MAI-UI 2B | About 4 GB FP16, 8 GB FP32 | GPU/MPS recommended; allow substantial additional memory for image tokens and KV cache |
| UI-Venus 2B | About 4 GB FP16, 8 GB FP32 | Same; 8–12+ GB free memory is a useful starting estimate, not a guarantee |

CPU visual generation uses FP32. CUDA uses BF16 when supported, otherwise FP16; MPS uses FP16. Eager attention avoids an implicit FlashAttention dependency. Device availability is not proof that every operator or memory requirement is supported. Runtime load or operator failures become unavailable runs. No CPU/MPS/CUDA weights-backed compatibility results are claimed here. Local PyTorch generation runs off the event loop with serialized access per adapter. Cancelling an awaiting coroutine cannot interrupt an already running native generation call; max generation tokens bounds output, but use a separate model server/process when strict inference cancellation is required.

The official MAI and Venus serving path uses an OpenAI-compatible vLLM service (upstream specifies `vllm>=0.11.0`). vLLM is primarily the CUDA/Linux deployment route; this application does not claim standard vLLM support for Apple MPS.

## Remote endpoints

Use `_ENDPOINT`, optional `_API_KEY`, and optional `_SERVED_MODEL` for the corresponding prefix. Endpoint credentials stay on the backend. Remote configuration takes precedence over the local path and a failed remote call never falls back locally. The service must honor the exact requested model and return actual inference. Authentication headers and response bodies are not included in errors.

MAI/UI-Venus `_ENDPOINT` is the OpenAI-compatible base URL, including `/v1`, for example `http://127.0.0.1:8001/v1`. The adapter posts vision messages to `/chat/completions`. `_SERVED_MODEL` can match a vLLM alias; it must refer to the same checkpoint, and should be recorded alongside the canonical model ID. The caller must preserve the adapter's screenshot dimensions (particularly for UI-Venus); a remote server that changes image dimensions internally needs matching processor configuration for correct coordinates.

CUA-S1 `_ENDPOINT` has a custom option-scoring contract:

```json
POST /score
{"model":"cua-ai/cua-s1-forms","contexts":["TASK ...\nFORM ...\nELEMENT ..."],"options":["fill Shipping name: Synthetic Customer","check","click","skip"]}
```

The service returns `{"probabilities":[[0.8,0.1,0.05,0.05]]}`: exactly one finite, normalized distribution per element, with one entry per supplied option. Each element is independent; options consist of flattened profile entities followed by the three fixed actions. The implementation uses actual upstream `ChoiceExample`, byte collation and a single forward pass followed by softmax. It never asks this model to generate text.

TinyClick `_ENDPOINT` receives `POST /ground` with `model`, `image` (PNG data URL) and `instruction`. It returns `{"generated_text":"<loc_500><loc_250>"}` from actual Florence inference. The adapter validates and converts that output. This custom service is an integration contract; the application does not install or launch such a server.

## Input, output and controller boundaries

CUA elements use `id` (opaque browser target), `label`, `role`, `value`, optional `checked`, and optional visible `form_title`. A profile is a nested dict of customer data; flattening only supplies candidate values. Do not pass evaluator fields, hidden expected values, private scenario keys, or scenario-specific answers. Each output contains `element_id`, `action` (`fill/check/click/skip`), selected `value`, selected `entity_key`, confidence and full distribution. Confidence is an uncalibrated softmax probability. The controller determines execution order and applies only appropriate visible browser actions.

TinyClick requires an instruction from the deterministic controller and returns a click point, not a plan. CUA-S1 and TinyClick therefore measure different component capabilities. The hybrid combines the real field scorer and real grounding model; neither is replaced with reference-executor decisions.

MAI uses the official `mobile_use` JSON tool-call envelope and a 0–999 coordinate system. Venus uses its version-1.5 function grammar inside `<action>` tags and screenshot-pixel coordinates. Venus images are explicitly resized on multiples of 32 (the actual checkpoint has patch size 16 and merge size 2) with a configurable `UI_VENUS_MAX_PIXELS` (default 1,003,520), then mapped back to the original browser screenshot. The local processor does not resize Venus again. Upstream navigation code still uses factor 28, which conflicts with the published Qwen3-VL processor configuration; this adapter uses the actual checkpoint grid and tracks the resulting dimensions explicitly. The browser prompt is adapted to the checkout allowlist while retaining each model's native action grammar; this is not claimed to reproduce upstream benchmark prompts or published scores.

Both GUI adapters return normalized `action` with applicable `x/y`, `text`, `direction`, `key`, `start/end`, and `raw` output. Venus `Type` includes `submit=True` because its official web action presses Enter after typing. The executor must implement that flag or explicitly record the semantic deviation. MAI drag/swipe/long-press and Venus hover/double-click/drag are parsed when present. App launching and system navigation outside the controlled browser action space are rejected. Venus expressions are parsed with `ast.literal_eval` over argument literals; generated code is never executed. Invalid, ambiguous, multi-action or off-screen coordinates are rejected. Model `done` is only an action declaration: the private programmatic evaluator decides actual completion.

No weights-backed specialist inference was run during implementation because checkpoints and endpoints were not configured. Parser and contract checks are useful plumbing validation, not model benchmark results.

## Primary sources consulted

- [CUA-S1 model card: safe loading and option contract](https://huggingface.co/cua-ai/cua-s1-forms)
- [CUA-S1 upstream implementation](https://github.com/trycua/cua/blob/main/libs/cua-s1/python/src/cua_s1/model.py) and [schema](https://github.com/trycua/cua/blob/main/libs/cua-s1/python/src/cua_s1/schema.py)
- [TinyClick requested model card](https://huggingface.co/kzawistowsk/TinyClick) and [official paper](https://arxiv.org/html/2410.11871v2)
- [MAI-UI model](https://huggingface.co/Tongyi-MAI/MAI-UI-2B), [official prompts](https://github.com/Tongyi-MAI/MAI-UI/blob/main/MAI-UI/src/prompt.py), and [action/coordinate parser](https://github.com/Tongyi-MAI/MAI-UI/blob/main/MAI-UI/src/mai_naivigation_agent.py)
- [UI-Venus model and serving instructions](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B), [1.5 action format](https://github.com/inclusionAI/UI-Venus/blob/UI-Venus-1.5/models/navigation/utils.py), and [coordinate transforms](https://github.com/inclusionAI/UI-Venus/blob/UI-Venus-1.5/models/navigation/ui_venus_navi_agent.py)
