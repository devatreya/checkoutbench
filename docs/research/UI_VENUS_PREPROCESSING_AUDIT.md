# UI-Venus screenshot preprocessing and coordinate audit

Audit date: 2026-10-17. This report describes the **pre-edit v2 runtime**; the [integrated audit](UI_VENUS_COORDINATE_AUDIT.md) records subsequent v3 CSS-scale capture and geometry safeguards. References to “current” below mean the audited v2 snapshot, not the later runtime. Scope: the pinned local MLX adapter, browser capture/execution path, retained desktop smoke calls, and retained desktop/mobile full-run calls. This audit performed **CPU processor operations only**: no model construction, weight loading, model forward pass, or token generation. Runtime source and original evidence were not edited.

## Findings

The adapter's prepared image reaches MLX-VLM without an additional spatial transform. The pinned official image processor and the MLX-VLM wrapper produce **bit-identical pixel tensors and token IDs** on the same prepared image, for both desktop and mobile. No crop, padding, device-pixel-ratio multiplication, patch14 substitution, or hidden second resize was found in the inspected path.

There is one deliberate preprocessing difference from the pinned official asset's defaults: the adapter imposes a 1,003,520-pixel cap, whereas the official asset permits 16,777,216 pixels. Consequently a 1280×900 screenshot becomes 1184×832 in this adapter; direct official-default processing would produce 1280×896. On mobile, both routes produce 384×832 from 390×844. The cap is a resolution choice that may affect model quality, but it does not require a different coordinate interpretation.

The retained `Click(box=(496,233))` misses the Receipt email input under all three investigated interpretations: normalized 0–1000, prepared-image pixels, and original-image pixels. Changing coordinate units alone cannot make that retained action hit the input. This finding does not establish the cause of the model's output or exclude sensitivity to image resolution, quantization, or model implementation.

## Reproducible evidence

Ignored audit evidence is under `data/research/venus/coordinate-audit/preprocessing/`:

- `compare_processors.py`: standalone CPU comparison, with both Torch and MLX explicitly on CPU and offline asset loading. It uses `AutoProcessor.from_pretrained` and `mlx_vlm.utils.prepare_inputs`; it never invokes `load`, `load_model`, `generate`, or a model class.
- `processor-comparison.json`: dimensions, grid shapes, tensor hashes/differences, software versions, and source hashes.
- `processor-comparison.stdout.jsonl` and `processor-comparison.stderr.log`: execution output; the successful comparison emitted no stderr.
- `desktop-prepared.png` and `mobile-prepared.png`: derived images; originals remain in place.
- `official-assets-manifest.json`, `official-preprocessor_config.json`, and `official-config.json`: small files fetched from the exact pinned upstream revision, including hashes and URL provenance. The official revision has no `processor_config.json` (HTTP 404, retained in the manifest).
- `installed-source-manifest.json` and `installed-*`: copies and hashes of the relevant installed Transformers/MLX-VLM processor source.
- `retained-coordinate-evidence.json`: original evidence hashes, coordinate calculations, frozen/runtime source comparisons, and the inventory used for the geometry census.

Reproduction from repository root:

```sh
.venv-venus/bin/python data/research/venus/coordinate-audit/preprocessing/compare_processors.py
```

Versions used: Transformers 5.2.0, MLX-VLM 0.3.12, MLX 0.31.0, Torch 2.10.0, Torchvision 0.25.0, Pillow 12.3.0, NumPy 2.5.4. This compares the **pinned official asset configuration under the installed interpreter**, not a separately installed Transformers 4.57.1 interpreter named in the upstream model config.

## End-to-end coordinate path

1. [`backend/runner/engine.py:497`](../../backend/runner/engine.py#L497) launches Chromium with the scenario viewport and `device_scale_factor=1`. Desktop defaults to 1280×900; mobile scenarios use 390×844. The retained screenshot dimensions agree with those CSS viewports. No DPR conversion is needed before mouse execution.
2. [`backend/browser/visual.py:126`](../../backend/browser/visual.py#L126) calls `page.screenshot()` with no `full_page` or `clip` override, opens the PNG as RGB, saves the original observation, and passes that image to the adapter.
3. [`backend/adapters/venus.py:180`](../../backend/adapters/venus.py#L180) rounds/resizes to multiples of 32 (patch16 × spatial merge2), within the configured pixel cap. [`venus.py:317`](../../backend/adapters/venus.py#L317) performs a single RGB Pillow resize, serializes a PNG, and records its hash. For RGB images the installed Pillow default resampling is BICUBIC. There is no crop or padding operation here.
4. [`scripts/diagnostics/venus_worker.py:67`](../../scripts/diagnostics/venus_worker.py#L67) explicitly sets `processor.image_processor.do_resize=False`. The worker decodes the prepared PNG, confirms the supplied dimensions, constructs the native chat template, and calls `prepare_inputs` with one PIL image and no `resize_shape`.
5. MLX-VLM's Qwen3-VL module exports no custom `ImageProcessor`; it retains the Transformers `Qwen2VLImageProcessorFast` configured for Qwen3-VL. In `prepare_inputs`, the optional uniform-size batching branch is inactive for one image. The wrapper calls the HF processor and converts its outputs to MLX arrays; it does not crop or resize this image.
6. [`venus_worker.py:82`](../../scripts/diagnostics/venus_worker.py#L82) verifies `image_grid_thw` against `[grid_w*16,grid_h*16] == image.size`. This would reject an unexpected grid or resize. Temporal patch2 duplicates the still image for patchification; it does not double spatial dimensions. Merge2 reduces visual token count by four, without halving the coordinate canvas.
7. [`venus.py:96`](../../backend/adapters/venus.py#L96) maps native coordinates directly by `min(width-1, int(x*width/1000))` and the analogous height expression. `model_size` validates metadata, but does not supply a second scale. Positive coordinates therefore truncate by less than one CSS pixel; native 1000 maps to the final visible pixel.
8. [`visual.py:141`](../../backend/browser/visual.py#L141) validates the result against the **original screenshot**. [`visual.py:70`](../../backend/browser/visual.py#L70) then passes it directly to `page.mouse.click`; there is no browser executor scaling. The Venus branch in [`backend/browser/execution.py`](../../backend/browser/execution.py) delegates to this visual loop.

The current adapter, worker, visual loop, execution bridge, and runner engine are byte-identical to their copies in `data/research/venus/normalized1000-runtime/`, as recorded in `retained-coordinate-evidence.json`. This connects the inspected path to the frozen normalized1000 runtime rather than relying only on current source.

## Official asset versus adapter preparation

The downloaded official [`preprocessor_config.json`](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/preprocessor_config.json) is byte-identical to the local community artifact's file. It specifies patch16, temporal patch2, merge2, RGB mean/std 0.5, minimum area 65,536 and maximum area 16,777,216. The community artifact's nested processor config agrees on these image settings. The class name `Qwen2VLImageProcessorFast` does **not** imply patch14: the pinned configuration overrides that class default to 16. The upstream model's `vision_config` independently specifies patch16 and spatial merge2.

| Route | Desktop image / grid THW | Mobile image / grid THW |
| --- | --- | --- |
| Original screenshot | 1280×900 | 390×844 |
| Official asset defaults | 1280×896 / `[1,56,80]` | 384×832 / `[1,52,24]` |
| Official processor with adapter cap | 1184×832 / `[1,52,74]` | 384×832 / `[1,52,24]` |
| Adapter prepared + worker no-resize | 1184×832 / `[1,52,74]` | 384×832 / `[1,52,24]` |

Desktop prepared area is 985,088 pixels (3,848 raw spatial patches; 962 merged image tokens). Mobile prepared area is 319,488 pixels (1,248 raw patches; 312 merged image tokens). Both patch dimensions are even and satisfy merge2. Fast processor output shapes are `[3848,1536]` and `[1248,1536]`, respectively: 1536 = 3 RGB channels × temporal2 × 16×16.

Aspect ratio changes by +0.0601% desktop and −0.1183% mobile because independent dimensions must lie on the 32-pixel grid. This is a slight global stretch, not an offset or lost strip. Mapping normalized positions back by the original dimensions undoes that stretch. An exact inverse of the returned patch tensor reconstructed the entire prepared RGB canvas, with only float arithmetic error (maximum 5.92e−8); temporal duplicates were exact. There was no discarded, shifted, reordered, or padded spatial region.

Enabling official resize on an already prepared image yields exactly the same tensor as disabling it. Processing the original with the official fast resizer and the adapter cap produces the same geometry but tiny interpolation differences from the adapter's Pillow resizer:

| Case | Fraction of normalized channel values differing | Maximum normalized difference | Mean normalized absolute difference |
| --- | ---: | ---: | ---: |
| Desktop | 0.0118094% | 0.0156863 (two RGB levels of 255 before normalization) | 9.29e−7 |
| Mobile | 0.0406901% | 0.00784317 (one RGB level of 255 before normalization) | 3.19e−6 |

These differences are measured; they should not be equated with a proven absence of model-output sensitivity. They provide no geometric explanation for a roughly 100-pixel vertical miss.

## Retained observations and action miss

The derived desktop PNG exactly reproduces the image hash recorded by both normalized1000 smoke calls and both final-metrics calls:

```text
0283a568bb0a540e6ee60f4eae22c56ef2a89fa2f7f91cef82d56d9e09be722d
```

All four calls report original 1280×900, prepared 1184×832, grid `[1,52,74]`, and native `Click(box=(496,233))`. The earlier `adapter-validation-final` and `adapter-validation-env-defaults` calls used the same prepared image and native output, but the superseded pixel parser returned `(536,252)` instead of `(634,209)`. Thus the parser change altered execution coordinates, not the model observation or native prediction.

The retained browser verification records a Receipt email target at `(119,309.875)` with size `550×49.25`, and confirms that the original fixture pixels equal the inference screenshot. The normalized target rectangle is x=92.969–522.656, y=344.306–399.028. The native y=233 lies above it.

| Interpretation of retained native `(496,233)` | Executed CSS point | Vertical distance above target top | Inside target |
| --- | --- | ---: | --- |
| Normalized 0–1000 | `(634,209)` | 100.875 px | No |
| Pixels on 1184×832 prepared image | `(536,252)` | 57.875 px | No |
| Pixels on original 1280×900 screenshot | `(496,233)` | 76.875 px | No |

A read-only census of all 174 locally retained full-normalized1000 `actions.json` files found 325 calls with recorded image geometry: 272 desktop calls all used 1280×900 → 1184×832 / `[1,52,74]`; 53 mobile calls all used 390×844 → 384×832 / `[1,52,24]`. These are retained files, including attempts, **not** a replacement accepted-run population or benchmark score denominator. No third geometry appeared among calls with these fields.

## Implications and limits

No runtime correction is justified by the preprocessing evidence alone. Keep the original evidence and normalized coordinate policy intact while investigating native output quality. An isolated official-default-resolution comparison could test sensitivity to the adapter's pixel cap. Any such run must be labeled a changed observation configuration, and it must not silently replace the retained benchmark evidence.

This audit confirms the spatial path and processor equivalence on the measured desktop and mobile observations. It does not validate the community conversion's numerical fidelity, MLX-VLM model-layer implementation, cross-version model behavior, or the model's general grounding ability. It also does not infer a new coordinate contract from whether a transformed click happens to land near one target.
