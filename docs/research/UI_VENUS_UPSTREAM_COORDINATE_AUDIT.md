# UI-Venus 1.5 upstream coordinate audit

Audit date: 2026-10-17. Scope: the released `inclusionAI/UI-Venus-1.5-2B` checkpoint, its native navigation actions, grounding examples, and Qwen3-VL preprocessing. This investigation used primary sources and source history before reading the local adapter. No model inference, benchmark scores, or CheckoutBench outcomes were used to choose a coordinate mapping. Only this report was written by this investigation.

## Finding

**Normalized `[0,1000]` coordinates have the strongest upstream support for native UI-Venus 1.5 navigation, including `Click(box=(x,y))`.** This rests on an explicit statement covering all spatial targets, a released navigation executor that divides by 1000, and the Qwen3-VL convention. The grounding implementation independently agrees. However, the official lightweight navigation helper implements resized-image pixel coordinates. That conflict is real and must remain visible; describing every upstream example as consistent would be incorrect.

The evidence supports this mapping for an uncropped, full-viewport screenshot of original size `W × H`:

```text
x_viewport = x_native * W / 1000
y_viewport = y_native * H / 1000
```

Rounding and clipping are executor policies. The normalized frame does not prescribe a particular last-pixel convention. A screenshot that has been cropped, padded, or captured at a different scale from browser coordinates needs a separate image-to-viewport transform.

## Revisions and provenance

| Source | Pinned revision | Why this pin matters |
| --- | --- | --- |
| Official 2B model | [`bc4c6e62a1c545e043761439be95646d801853a4`](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/tree/bc4c6e62a1c545e043761439be95646d801853a4), 2026-02-11 | Current model head returned by the Hugging Face API during the audit. |
| Initial checkpoint upload | [`ec90e72c203ec062b42bb7ad94dce34318b49a86`](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/commit/ec90e72c203ec062b42bb7ad94dce34318b49a86), 2026-02-09 | Subsequent visible history entries are README updates. See [model history](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/commits/bc4c6e62a1c545e043761439be95646d801853a4). This audit did not download or compare weights. |
| Official 1.5 repository branch | [`192a9247ad1129279ba1d6c263d4c9e7ecef3644`](https://github.com/inclusionAI/UI-Venus/tree/192a9247ad1129279ba1d6c263d4c9e7ecef3644), 2026-04-08 | The live repository default is now `UI-Venus-2`; an unqualified default-branch link can mix releases. |
| Initial 1.5 source release | [`c6ce41fa2e97bd4a45378cf81761161c435b22ea`](https://github.com/inclusionAI/UI-Venus/commit/c6ce41fa2e97bd4a45378cf81761161c435b22ea), committed 2026-02-11 | Navigation helper, grounding class, and normalized mobile policy were all present together. Author date is 2026-02-09; committer date is 2026-02-11. |
| Official 1.0 comparison | [`497e2cd9b0c131e4685de23598f51e2da4dd7562`](https://github.com/inclusionAI/UI-Venus/tree/497e2cd9b0c131e4685de23598f51e2da4dd7562) | Earlier helper introduced in [`01ca24a13210ed244f2e63824bb83eabf05ea644`](https://github.com/inclusionAI/UI-Venus/commit/01ca24a13210ed244f2e63824bb83eabf05ea644), 2025-08-17. |
| UI-Venus technical report | [arXiv:2602.09082v1](https://arxiv.org/html/2602.09082v1), 2026-02-09 | Versioned paper, rather than an unspecified latest revision. |
| Qwen3-VL repository | [`96588727e44c78b25ba03ea03b8e12f7e64fd0da`](https://github.com/QwenLM/Qwen3-VL/tree/96588727e44c78b25ba03ea03b8e12f7e64fd0da), 2026-01-30 | Official cookbooks and utility implementation at the head observed during this audit. |
| Transformers 4.57.1 | [`8cb5963cc22174954e7dca2c0a3320b7dc2f4edc`](https://github.com/huggingface/transformers/tree/8cb5963cc22174954e7dca2c0a3320b7dc2f4edc) | Version recorded in the released model configuration; annotated tag resolved to this commit. |

## What the release actually says

The [UI-Venus report §3.1.1](https://arxiv.org/html/2602.09082v1#S3.SS1.SSS1) explicitly maps all spatial targets into normalized `[0,1000]` space following Qwen3-VL. [Appendix A.1, Table 8](https://arxiv.org/html/2602.09082v1#A1.SS1) defines `Click(box=(x,y))` as a point click, alongside drag endpoints, long press, hover, and double click. Thus `box` is a native parameter name; its two values are not a four-coordinate rectangle. The same report describes a unified checkpoint built by merging grounding, web, and mobile specialists. It does not document a web-only exception to normalization.

The released [navigation prompt and parser](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/utils.py#L4) declare the native action and XML response structure. `parse_answer` parses numbers and returns them without rescaling. The web prompt itself contains no numeric coordinate-range instruction. Consequently, the action spelling establishes syntax, but syntax alone cannot establish units. This also means a claim that `/1000` appears in the official web prompt would be false.

Crucially, the official **navigation** framework supplies direct corroboration beyond grounding: [its mobile policy lines 186–221](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/Venus_framework/policy/ui_venus_policy.py#L186) describes model output as a 1000-by-1000 coordinate system, computes `int(x * width / 1000)` and the analogous y expression, then applies this to clicks, long presses, and swipe endpoints. Its [processor prompt](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/Venus_framework/processor/uivenus_processor.py#L11) describes top-left `(0,0)` and bottom-right `(999,999)`. These files already coexist in the initial 1.5 release. This is evidence against explaining the discrepancy simply as “grounding normalizes, navigation uses pixels.”

The [1.5 grounding class lines 130–170](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/grounding/ui_venus1_5_gd.py#L130) parses the model's point or rectangle-center output and divides each coordinate by 1000, returning `[0,1]` fractions. The raw model point and returned point therefore use different units. Its refusal marker `[-1,-1]` bypasses normalization. This is a grounding task with its own prompt and output grammar; using that prompt would change the task mode and would not reproduce native navigation.

The [2B model card](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/README.md) identifies a unified Qwen3-VL-based model and gives serving instructions, but does not itself specify the click coordinate conversion. The paper and pinned implementation are needed to interpret it.

## Why the resize example differs

The competing implementation is [navigation helper lines 81–110 and 124–155](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/ui_venus_navi_agent.py#L81). It estimates resized dimensions with `smart_resize(..., factor=28, ...)`, then multiplies each parsed coordinate by original dimension divided by estimated resized dimension. This implements **resized-image pixel** semantics, not normalized-1000 semantics. Its clamp can conceal an overlarge transformed point. The helper estimates dimensions separately; the model wrapper receives the image path.

The exact [runner defaults](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/runner.py#L36) are `min_pixels=3136` and `max_pixels=12845056`, in both `ModelConfig` and CLI arguments. With `smart_resize(original_height, original_width, factor=28, ...)` returning `(resized_height,resized_width)`, the helper computes `int(x * original_width / resized_width)` and its height analogue, then clamps inclusively to the original width/height. These defaults differ from the released checkpoint's processor configuration and from the local adapter's budget.

Source comparison supplies a plausible explanation. The pinned [1.0 helper](https://github.com/inclusionAI/UI-Venus/blob/497e2cd9b0c131e4685de23598f51e2da4dd7562/models/navigation/ui_venus_navi_agent.py#L81) and 1.5 helper differ only by adding the explicit `factor=28` argument. Their `ui_venus_navi_vllm.py` files are byte-identical. The latter calls `process_vision_info` without a Qwen3 image-patch argument. The [1.5 file history](https://github.com/inclusionAI/UI-Venus/commits/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/ui_venus_navi_agent.py) shows only the initial release; no later coordinate repair appears there.

**Inference:** the helper preserves an earlier Qwen2-era pixel conversion while the 1.5 checkpoint and other code use Qwen3 conventions. The content identity and factor mismatch support that explanation strongly. They do not prove maintainer intent: the 1.5 source release introduces the files as additions, rather than preserving a direct Git ancestry from 1.0. No retrieved maintainer statement explains this inconsistency. It should be called an inconsistent or apparently stale example, rather than a confirmed upstream bug acknowledgement.

## Processor semantics and why resize does not define output units

The released [model configuration](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/config.json) declares `Qwen3VLForConditionalGeneration`, vision patch size 16 and spatial merge size 2. Its [preprocessor configuration](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/preprocessor_config.json) records `Qwen3VLProcessor`, patch size 16, merge size 2, and image-size area bounds 65,536 and 16,777,216. The image processor's `Qwen2VLImageProcessorFast` class name denotes a reused implementation, not a statement that this Qwen3 checkpoint predicts Qwen2-style coordinates.

In [Transformers 4.57.1 image preprocessing lines 203–215](https://github.com/huggingface/transformers/blob/8cb5963cc22174954e7dca2c0a3320b7dc2f4edc/src/transformers/models/qwen2_vl/image_processing_qwen2_vl_fast.py#L203), resize divisibility is `patch_size * merge_size`: **32** for this checkpoint. The [Qwen3 processor](https://github.com/huggingface/transformers/blob/8cb5963cc22174954e7dca2c0a3320b7dc2f4edc/src/transformers/models/qwen3_vl/processing_qwen3_vl.py#L162) constructs image tensors and grid metadata and expands visual token placeholders. Its text postprocessor delegates to tokenizer decoding at lines 287–314. Neither operation interprets the generated `Click` numbers or converts their units. Spatial normalization is a learned/output convention with executor postprocessing, separate from image tensor normalization and visual-token resizing.

The official [Qwen3-VL usage documentation](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/README.md#new-qwen-vl-utils-usage) specifies image patch size 16 for Qwen3 versus default 14 for Qwen2.5, corresponding to factors 32 and 28. It warns that `qwen-vl-utils` already resizes images and recommends avoiding duplicate processor resizing. The pinned [utility source](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/qwen-vl-utils/src/qwen_vl_utils/vision_process.py#L93) confirms that default 14 and calculates its resize factor from patch size times merge size. Therefore, estimating a 28-pixel grid does not establish the final Qwen3 tensor dimensions; runtime/version-dependent additional processing may intervene.

Specifically, the [Venus vLLM wrapper](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/ui_venus_navi_vllm.py#L22) attaches its configured min/max to the image message, invokes `process_vision_info` without `image_patch_size`, and sends the resulting image to vLLM. Its separately loaded `AutoProcessor` has min/max attributes changed, but that object is used for chat templating; those settings are not forwarded as vLLM `mm_processor_kwargs`. An initial factor-28 utility resize followed by vLLM's Qwen3 factor-32 preprocessing is therefore possible. This audit did not execute vLLM or establish its exact final image dimensions. The helper's own `smart_resize` call does not itself alter the image.

There is also explicit Qwen semantic evidence. The [official 2D grounding cookbook, opening cell](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/cookbooks/2d_grounding.ipynb) states that Qwen3 changes from Qwen2.5 absolute coordinates to relative 0–1000 coordinates. The [official computer-use cookbook, code cells 6 and 11](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/cookbooks/computer_use.ipynb) uses a 1000-by-1000 tool frame and divides output coordinates by 1000 before multiplying by the displayed image dimensions, despite separately resizing that image. The [Qwen3 technical report §3.2.4](https://arxiv.org/html/2511.21631v1#S3.SS2.SSS4) independently describes the normalized convention. Qwen's action schema is different from Venus's; this corroborates coordinate semantics, not Venus syntax.

For normalized coordinates on a complete image, mapping first into resized image pixels and then back to the original cancels the resize scale:

```text
(x_native / 1000 * resized_width) * original_width / resized_width
= x_native / 1000 * original_width
```

The inconsistent helper omits the first `/1000 * resized_width` step because it assumes raw output already represents resized pixels. Resize dimensions and output coordinate units must therefore be recorded separately.

## Certainty and remaining limits

| Assessment | Confidence / limitation |
| --- | --- |
| The official intended 1.5 spatial convention is normalized 0–1000. | High: explicit paper statement, grounding parser, and released navigation policy agree. |
| Native `Click(box=(x,y))` is a point action. | High: paper action table and native navigation prompt/parser agree. |
| The lightweight helper assumes resized pixels. | Certain from its arithmetic. It conflicts with the declared contract and another navigation implementation. |
| Stale 1.0 code explains that helper. | Strong inference from file comparison and Qwen's convention change; not a maintainer-confirmed explanation. |
| Every actual 2B generation obeys the convention perfectly. | Unproven; no inference performed. Documentation establishes the contract, not model compliance on every output. |
| Exact rounding, whether 999 or 1000 represents the last point, and clipping behavior are unified upstream. | No: paper says `[0,1000]`, mobile prompt says 0–999, and executors differ. `/1000` is corroborated; last-pixel handling is a local policy. |
| The same contract can be inferred solely from processor class or architecture. | No. A fine-tune could change output conventions. Here the Venus-specific paper and navigation implementation supply the necessary evidence. |

## Local adapter comparison, read after the upstream conclusion

Only after reaching the conclusion above, this audit read `backend/adapters/venus.py` on `codex/scenario-identity-ui-venus`. Its `ui-venus-1.5-web-mlx-v2-normalized1000` adapter parses native actions and directly scales by original viewport dimensions divided by 1000. That agrees with the strongest upstream contract; it does not reproduce the conflicting lightweight helper. Its 32-pixel preprocessing grid agrees with the released patch/merge configuration. Its clamp of the inclusive endpoint to `W-1` or `H-1` is an explicit local executor choice, rather than a verbatim upstream requirement.

This source audit does not certify community quantization provenance, MLX processor equivalence, effective runtime image geometry, browser screenshot scale, or benchmark quality. Those require separate artifact/runtime verification. None should be inferred from a good or bad CheckoutBench score.

## Additional native prompt and tokenization cross-check

This follow-up was a read-only source and tokenizer check on 2026-10-17. It did not load a model, execute a forward pass, run inference, interrupt the root agent's diagnostic, or select any prompt format from scores. **No native message-format defect was observed in the checked path.** That conclusion is narrower than numerical equivalence between MLX and the original model runtime.

The [official navigation wrapper lines 49–79](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/ui_venus_navi_vllm.py#L49) builds a system message containing `You are a helpful assistant.`, followed by a user message whose content is **text first, image second**. It calls `processor.apply_chat_template(..., tokenize=False, add_generation_prompt=True)`. The local `scripts/diagnostics/venus_worker.py` lines 77–81 uses that same role structure, content order, and template flags; the adapter supplies the matching system string. Passing the image separately to preprocessing supplies pixels for the template's visual placeholder; it does not itself introduce another image message.

By comparison, the [official grounding class lines 79–100](https://github.com/inclusionAI/UI-Venus/blob/192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/grounding/ui_venus1_5_gd.py#L79) uses **image first, text second**, without the navigation wrapper's system message. It uses the same `tokenize=False` and `add_generation_prompt=True` flags. These are documented examples for different task modes, rather than proof of a universal required content order. Replacing navigation order with grounding order would depart from the released navigation example. This audit does not establish that alternative content orders are behaviorally equivalent.

The local artifact's `tokenizer_config.json.chat_template` field was compared directly with [the released checkpoint field at `bc4c6e62a1c545e043761439be95646d801853a4`](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/tokenizer_config.json): they are identical, and both specify `bos_token=null`. Their [`tokenizer.json` postprocessor](https://huggingface.co/inclusionAI/UI-Venus-1.5-2B/blob/bc4c6e62a1c545e043761439be95646d801853a4/tokenizer.json) fields are also identical: a ByteLevel postprocessor with no BOS/EOS insertion template. The chat template preserves user content order, emits the visual-token placeholder, and appends the assistant generation prefix when requested.

The local worker passes `add_special_tokens=True` to `prepare_inputs`. A synthetic, tokenizer-only probe rendered the saved template with one system message and a text-then-image user message, then encoded it with the local pinned tokenizer using both special-token flag settings. The token IDs were identical: 34 tokens, with one visual-start token, one image-pad token, one visual-end token, and the expected assistant prefix. Thus the flag did not duplicate message or visual boundary tokens in this tokenizer check. This result is specific to the pinned tokenizer; it is not a general recommendation to enable extra special tokens after chat templating. Nor does this limited probe establish equality of all processed image tensors or full model inputs across runtimes.

The installed `mlx-vlm==0.3.12` [generation source](https://github.com/Blaizzy/mlx-vlm/blob/739f4ab7d4b6eb236221a909e3a2b6a11daf31c1/mlx_vlm/generate.py#L449) checks for already-supplied `input_ids`. When they exist, `stream_generate` consumes them and skips its own `prepare_inputs` call. Consequently, the local `generate(prompt=template, **inputs)` does not tokenize or process the supplied image a second time through that branch. The corresponding [input utility](https://github.com/Blaizzy/mlx-vlm/blob/739f4ab7d4b6eb236221a909e3a2b6a11daf31c1/mlx_vlm/utils.py#L906) handles preparation separately. Both installed files were compared byte-for-byte with tag `v0.3.12`, resolved to commit `739f4ab7d4b6eb236221a909e3a2b6a11daf31c1`; both match.

For reproducibility, SHA-256 hashes of the exact local files read for this cross-check were:

| File | SHA-256 |
| --- | --- |
| `scripts/diagnostics/venus_worker.py` | `a72dda444c0d9772e5b1ec937c207bcab19cb41ba9e2c50573db674a932614b0` |
| Installed MLX `generate.py` | `e31be68da39dcc7812fe1d399d9902cc7c419738add4ac8096d7be59305799de` |
| Installed MLX `utils.py` | `50de30176bdccc429ec7af1693ca7f0fbae11431ab43b6b672782b6c5b3592d4` |
| Local artifact `tokenizer.json` | `be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506` |
| Local artifact `tokenizer_config.json` | `eb29d5b4084a1b88c2b2f653f8f3a3832fabbf00ba9751e494c45bf9c5475943` |

The local artifact revision is `mlx-community/UI-Venus-1.5-2B-6bit@95e3994ac9d74fe047cf44c072f6569db62856e7`. The package lock records Transformers 5.2.0 and tokenizers 0.22.2. The original checkpoint configuration records Transformers 4.57.1 and its serving instructions specify minimum versions. Matching template fields, tokenizer behavior in this probe, and generation control flow do not prove processor implementation equivalence, quantization equivalence, or equal model predictions.
