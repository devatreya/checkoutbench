# CUA-S1-Forms fidelity and measurement audit

This work uses base CheckoutBench commit `67e1ba7`, an isolated worktree, the
existing Python environment and the existing checkpoint. It does not modify the
browser/controller, start servers, or run a checkout benchmark. These are
**development diagnostics**, not official evaluation or holdout results.

## Findings

The original validation run `6c30aaa4aebf45b0b57c84ea4f1756f1`
(`V21-G01`, seed 2026, profile `aditi`) contains seven real local calls and seven
recorded decisions over six unique controls. Its **0/7 field-value accuracy is
correct**: one wrong fill, followed by six skips, including a second email
observation retaining the wrong value. Required decision accuracy is 0/6;
Landmark's empty skip is acceptable for the optional field (1/1), but does not
match the document's nonempty landmark. It remains incorrect in strict scoring.
There are no unknown/unscored decisions. Five other expected controls have no
recorded classification decisions. This is not complete checkout coverage.

The historical record has no entity indices or distributions. Exact historical
entity identity accuracy is therefore unavailable. Wrong/nonmatching values
establish the seven assignment failures, but a replay's probabilities must not
be presented as historical probabilities.

Real CPU inference through the adapter reproduced the original seven-action
pattern: first email selects `customer.shipping.landmark` (probability about
0.3806); re-observing that model-selected value yields skip (1.0); the other
five fields skip. No fallback or semantic repair was applied. The default
`path-v2` state/hint corrections do not change these text-field results.

| Hypothesis | Evidence and conclusion |
| --- | --- |
| Incorrect option syntax | Historical `fill label: value` and final `check`, `click`, `skip` match upstream. Candidate labels are verbose lower-case paths, unlike the short document labels commonly sampled by upstream. This is distribution shift, not a malformed option list. |
| Input distribution | CheckoutBench supplies all 75 scalar entities, including delivery, payment, travellers and appointments. Upstream's pinned generator samples document synonyms and shuffles entities. A descriptive sample of seeds 0–999 produces 6–31 entities (median 17); this is not a reconstruction of the checkpoint's training corpus. Familiar synthetic controls work, whereas unfamiliar checkout labels frequently fail. |
| Candidate overload | Separate synthetic controls with 3 versus 75 entities keep the same correct email/name/city predictions. Quantity alone does not explain failure; confusable semantics and label representation remain plausible contributors. No actual benchmark candidates were pruned. |
| Truncation | Checkpoint limits are 224 UTF-8 context bytes and 96 bytes per option. None of the retained development or control inputs were truncated. Unicode boundary tests confirm byte truncation, including split codepoints, matches the upstream collator. |
| Role/state | Text fields use official `Edit`. Checkbox state was wrong when the controller supplied only value=`"true"`; the legacy adapter rendered unchecked. Corrected input changes a real checked-checkbox prediction from check to skip. Placeholder hints were omitted; they now use upstream's syntax when supplied. Select values remain observed value text, not a new list of select alternatives. Upstream synthesis creates its ordinary fields as Edit, so ComboBox/RadioButton generalization is not established. |
| Index decoding | Every entity remains in insertion order; fixed actions occupy the last three indices. Unit tests cover every action offset, duplicates and ties. Real candidate reversal remaps the same chosen entities, with only floating-point tolerance differences. No decoding defect was found. |
| Checkpoint limitation | Pinned weights, loader, configuration, eval mode and softmax are correct. Generic alternative serialization changes predictions but does not solve checkout classification. A familiar correctly filled email control is sometimes filled again rather than skipped. Confidence is uncalibrated and can be near 1.0 on incorrect skips. |

## Versions and adapter interface

`CuaS1Adapter.score_fields(elements, profile)` and the six original output keys
are preserved. `value` is always the original selected scalar converted to text;
`entity_key` is the original dotted path. Fixed actions have null value/key.
`check` means set checked true, **not** uncheck. CUA has no fixed uncheck option.

Constructor options:

- `input_protocol="path-v2"` (default): preserves historical candidates, order and
  labels; fixes checkbox state, includes visible `placeholder`, and normalizes
  equivalent text/AX roles. Explicit `checked` takes precedence over `value`.
  Bool and `"true"`/`"false"` are supported. Unknown state defaults to unchecked,
  as upstream does; unknown nonempty string states are rejected.
- `input_protocol="path-v1"`: historical serializer for comparisons, including
  its checkbox-state and placeholder limitations.
- `input_protocol="document-v2"`: experimental generic document formatting, e.g.
  `customer.shipping.city` becomes `City (customer / shipping)`. Every parent
  qualifier and original entity is preserved. No target-dependent lookup,
  synonym dictionary, deduplication or filtering is used. This is **not the
  default**, since limited development evidence does not establish a net benefit.
- `diagnostics=True`: opt into exact inputs, which can contain sensitive data.

Added output keys: `selected_index` (zero-based), `candidate_count` (entities,
excluding the three fixed actions), `input_protocol`, and `inference_kind`.
The latter is `actual_model` only after the local forward path executes;
remote output is `remote_unverified`, and an overridden path defaults to
`unverified` unless a test double explicitly labels itself `test_double`.
This is execution provenance, not a security attestation against monkeypatching.

With diagnostics enabled, `model_input` contains `context`, `options`,
`entity_keys`, `context_encoding`, and `option_encodings`. Each encoding has
`byte_length`, `limit`, `truncated`, and exact unpadded `byte_ids` (UTF-8 bytes + 1).
Encoding limits are null for unverified remote services. The complete
probability vector is always in `distribution`; it aligns exactly with options.
Probabilities must be finite, in [0,1], and sum to 1 within 1e-5. No normalization
or repair is applied to invalid remote output.

`last_metrics` adds protocol, inference kind and `model_forward_seconds`.
`inference_seconds` is call wall time including queue/import/load/collation;
`cold_model_loading_seconds` covers the loader and identity hashing;
`warm_inference_seconds` is warm call wall time. Forward time includes transfer
of probabilities back to CPU. `checkpoint_identity` retains tensor/sidecar
hashes and `model_config` retains the loaded config.

Candidate construction continues to accept ordered nested dicts with string,
integer and finite float leaves. Empty strings and duplicates remain; bool,
null and list leaves are unsupported, as before. Callers must supply the public
customer document, never an entire private scenario.

## Measurement API for integration

`backend.evaluator.semantic.decision_report(s, decisions)` is private,
post-inference and never imported by the adapter. `grade_decisions(s, decisions)`
still returns a list of booleans for the runner, now rejecting role-incompatible
check/click actions even when the measured value happens to equal truth.

The report has `scoring_version="semantic-2"` and explicitly counts **decision
attempts**. Repeated observations count again. It does not drop a prediction
because execution failed or an observation became stale: those statuses are
retained separately, since they do not erase the model's decision. Unknown
handles and missing truth are unscored with reasons. Unobserved fields are
reported separately and are not silently treated as scored successes/failures.

- `field_classification_accuracy`: historical normalized effective-value match,
  now requiring a compatible action. A skip on an already-correct value can
  still be correct. This is not an exact entity-identity metric.
- `strict_assignment_accuracy`: correct fill/check assignments only; skips are
  not assignments. It retains all scored decision attempts in the denominator.
- `strict_entity_accuracy`: exact entity-key match against optional private
  `s["expected_entity_keys"]` (field key → key or list of allowed keys). Skips
  fail when an entity is expected. Fills lacking recorded entity keys or fields
  lacking private identity truth are unscored, with explicit entity coverage.
  Do not infer identity from equal-valued candidates. Do not send this mapping
  to inference. Empty identity coverage returns null, not 0% or 100%.
- Required accuracy and counts, optional acceptability and acceptable empty
  skips, wrong-value selections, skips, invalid actions, repeat/unique counts,
  unobserved fields, inference kinds and execution statuses are separate.
- `rows` preserves confidence, distribution, index, protocol, source and status
  when recorded, without copying expected or actual customer values.

For integration, retain controller `value` as its effective/measured value,
`before_value`, `role`, and the prediction's entity/probability metadata.
Persist `decision_report(...)` alongside the existing aggregate; do not rename
its historical value metric as strict identity accuracy. The browser owner can
enable diagnostics for local synthetic runs and retain `model_input` in the
ignored local trace. These additions change the system/scoring protocol and
must not be silently pooled with prior official result configurations.

## Reproduce

The worktree reuses the original environment and weights read-only. From this
worktree (substitute your local paths when integrating):

```sh
RUN_CUA_REAL=1 \
CUA_S1_MODEL_PATH=/Users/devatreya/Desktop/checkout_benchmark_sandbox/data/research/checkpoints/cua-s1 \
/Users/devatreya/Desktop/checkout_benchmark_sandbox/.venv/bin/python -m pytest tests/test_cua_fidelity.py tests/test_adapters.py -q

/Users/devatreya/Desktop/checkout_benchmark_sandbox/.venv/bin/python -m scripts.research.cua_diagnostics \
  --model-path /Users/devatreya/Desktop/checkout_benchmark_sandbox/data/research/checkpoints/cua-s1 \
  --original-db /Users/devatreya/Desktop/checkout_benchmark_sandbox/data/validation/results.sqlite3 \
  --include-sensitive --output data/model-fidelity/new-exact.json \
  --summary-output data/model-fidelity/new-summary.json
```

The CLI refuses checkpoint/sidecar/loader hash mismatches and uses the actual
adapter local forward path, ignoring endpoint configuration. Default cases are
fixed development examples G01/S01/ST03 (seed 2026, aditi), plus separately
labelled synthetic contract, count, order and warm-repeat controls. Each field
is scored alone, matching the original controller. A first-field selected-value
revisit is an explicitly synthetic observation, not a browser replay. Public
case inputs can be supplied with `--input`: a JSON object mapping names to
`{"elements": [...], "profile": {...}}`. No evaluator truth is accepted in that
case envelope. Fixture projection only reads customer_brief and visible field
label/kind/options-presence/section; it never uses private field keys or values.

Exact reports require `--include-sensitive`; they include the complete serialized
strings, unpadded bytes, probabilities and top indices. Files are exclusively
created with mode 0600 and never overwrite evidence. Console output omits values.
Default file output and `--summary-output` remove raw strings/bytes and retain
hashes, candidate keys, full distributions and top alternatives. Do not commit
exact customer/payment data. No results database is written.

The committed [evidence](../../research/cua-fidelity-evidence.json) contains the
redacted final diagnostic run, including original-run denominator audit, 142
actual calls and original/corrected/experimental distributions. Exact local
artifacts remain under ignored `data/model-fidelity/`. Early exploratory runs
also remain there; no evaluation data was removed. Tests exercise all twelve
requested areas; unit doubles are explicitly labelled and separate from the
opt-in pinned model smoke.

## Audited sources and identity

- [Pinned model card](https://huggingface.co/cua-ai/cua-s1-forms/blob/4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332/README.md).
- Official source at [trycua/cua 6d82b3b](https://github.com/trycua/cua/tree/6d82b3b1b21813ad047f966ab1384a1258c16170/libs/cua-s1/python/src/cua_s1): `schema.py`, `model.py`, `planner.py`, `synth.py`, `concepts.py`, `checkpoint.py`.

Model revision: `4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332`.
Weights SHA-256: `05954c1caf51c2fb6c13ea4acbfc88a2e7653dea192252bb51dc89e76a356ddc`.
Sidecar SHA-256: `62d31e2f9a001a8e9b6f8534c5194d07ebdd3f9d62ef1ac281906622992650ca`
(also verified against the pinned Hugging Face file).
The audited loader validates safetensors/config consistency and uses eval mode;
there is no pickle or replacement architecture. The sidecar signature is a
SHA-256 integrity digest, not an authenticated publisher signature. Independent
pinned hashes establish identity. Config `hf_model` is unused legacy metadata
for this tinyx architecture; no Qwen model is loaded. Architecture: 706,048
parameters, float32, width/rank 128, two context layers, four heads, 224/96 bytes.

The model card's reported accuracy is not a CheckoutBench measurement. This
small development audit establishes reproducible failures after valid input
construction, not the exact causal decomposition of training-distribution
shift or generalization to other checkout tasks.

## Validation record

Final focused run: **52 passed**, including the explicit real-model smoke.
Only upstream Transformer nested-tensor optimization warnings were emitted.
Targeted syntax/import checks (`ruff --select E4,E7,E9,F,I`) and
`git diff --check` pass. Broader lint rules flag existing unrelated specialist
code; that code is outside this change. No browser fixture or shared server was
started by this worktree.

The retained final diagnostic run executed 142 forward calls. Its three cold
loader timings were approximately 46.1, 9.9 and 13.3 ms; warm call median was
10.95 ms on this CPU/runtime. These are diagnostic observations, not controlled
cross-model latency measurements. Candidate-order controls were identical by
entity key (maximum probability difference 0.0 in this run).
