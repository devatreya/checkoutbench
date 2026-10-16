# CUA model-to-browser execution

CheckoutBench observes public visible field semantics, asks CUA-S1-Forms to choose an action/value from the synthetic customer document, and executes that choice with Playwright. Deterministic navigation advances the checkout. Private evaluator answers are never returned to the model or used to repair its predictions.

## Progress and failures

The V2.1/V3 harness compares visible headings, field values, checked states, options, required/read-only state and enabled actions across browser operations. Three equivalent actions without a meaningful change stop the run with `failure_reason=no_progress`. Repeated error messages and counters do not reset this budget. Successful transitions and field changes reset it. Observation exhaustion also produces explicit no-progress diagnostics.

The harness reobserves after every action and before navigation. It checks field identity again after asynchronous inference; predictions for stale observations remain in the trace but are not executed against replacement controls. Invalid select choices remain recorded without repeatedly calling the model for the same unchanged field. Unknown actions and incompatible field actions fail explicitly.

A wrong email remains wrong, required skips remain blank, and browser failures produce a single failed action record. Diagnostic stops do not consume the browser action budget. A `no_progress` stop is not itself proof of a harness defect: invalid model-selected fields can prevent a valid deterministic submit from advancing.

Runs contain:

- `calls`: actual model input fields/customer profile, outputs, backend and timings. Deterministic test doubles are labeled `test-double`.
- `semantic_decisions`: original prediction metadata, prior value, field role, call index and execution status, including skips and stale observations.
- `events`: requested browser action, selection/grounding source, observed post-action value, execution status and screenshot.
- `no_progress` and `harness_diagnostics`: bounded retry count, state fingerprint and public validation evidence.
- `failure_attribution`: separate model field-decision, browser execution, controller, infrastructure and validation indicators. Repeated validation submissions do not add semantic samples.

These traces contain synthetic customer data. Local run records and screenshots stay in ignored `data/`; do not publish arbitrary real customer inputs.

## Reproduce

Use the repository's existing virtual environment and pinned local CUA installation. Do not start a second server on the same ports. Stop the current idle server before starting the updated checkout:

```sh
./scripts/start.sh
```

In another terminal in the repository, verify the checkpoint and perform genuine cold/warm inference:

```sh
.venv/bin/python -m scripts.research.verify_models --model cua-s1
```

The verification must report `verified: true`. Run one real evaluation using the same original scenario, seed, action budget and timeout:

```sh
curl --fail http://127.0.0.1:8000/api/batches \
  -H 'Content-Type: application/json' \
  -d '{"models":["cua-s1"],"scenarios":["V21-G01"],"repeats":1,"seed":2026,"max_steps":80,"timeout":180,"infrastructure_retries":0,"video":false}'
```

Poll `GET /api/state` until `running` is false. Find the returned batch ID in `GET /api/diagnostics/results`. Single-scenario runs are diagnostic evaluations, not the official 174-scenario results dataset. Raw records are in `data/validation/results.sqlite3`; screenshot paths in each event are served under `/artifacts/validation/`.

Run the deterministic software controls separately:

```sh
.venv/bin/pytest -q tests/test_harness.py tests/test_v21.py
RUN_CUA_REAL=1 CUA_S1_MODEL_PATH="$PWD/data/research/checkpoints/cua-s1" \
  .venv/bin/pytest -q tests/test_cua_fidelity.py tests/test_adapters.py
```

The tests include a real Chromium + synthetic V21-G01 fixture negative control, with a deliberately wrong deterministic scorer. This verifies execution/evaluation integrity; it is not evidence of model accuracy.

## Integrated real-model result (2026-10-16)

| Evidence | Original preserved run | Integrated rerun |
| --- | --- | --- |
| Run ID | `6c30aaa4aebf45b0b57c84ea4f1756f1` | `f2519521adf94466845df33b97e2a22e` |
| Scenario / seed | V21-G01 / 2026 | V21-G01 / 2026 |
| Genuine inference calls | 7 | 7 |
| Browser actions | 80 | 4 |
| Review submissions / validation errors | 79 | 3 |
| Final stage | Details | Details |
| Checkout success | False | False |
| Stop reason | `max_steps` | `no_progress` |
| Field-value accuracy | 0/7 | 0/7 |

The integrated screenshot confirms that `Receipt email` contains `Near Sample Park`, and required delivery fields remain empty. The first action executes the selected `customer.shipping.landmark` value; six later decisions are skips, including a second observation of the incorrect email. Playwright then performs exactly three deterministic Review clicks. The independent evaluator rejects the checkout. Browser execution and infrastructure error flags are false. The bounded controller stop is functioning as intended; the remaining checkout failure is caused by invalid model field decisions.

The seven decisions cover six distinct fields. The empty optional Landmark skip is acceptable to checkout completion, but is not a correct assignment of the document's nonempty landmark. Exact entity-identity accuracy remains unscored because the scenario does not supply private entity-key truth; it is not inferred from matching strings. These distinctions are recorded in `semantic_report` (`semantic-2`).

Pinned revision: `4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332`. Verified weights SHA-256: `05954c1caf51c2fb6c13ea4acbfc88a2e7653dea192252bb51dc89e76a356ddc`. The integrated run uses local float32 inference on MPS and `path-v2`; all seven outputs are marked `actual_model`, with exact context, candidates, byte encodings and full probability distributions. Cold/warm verification and a separate CPU regression also invoke real weights. See the [model fidelity audit](../research/CUA_MODEL_FIDELITY.md) for loader checks, original-decision replay and candidate-order controls.

The original database record and all 82 artifacts were verified byte-identical after integration. Preservation manifests and full new run traces are in ignored `data/research/harness-integration/`. New screenshots remain under `data/validation/f2519521adf94466845df33b97e2a22e/`.

The source freeze was refreshed to include the integrated harness and semantic protocol. The scenario manifest and all 174 scenario IDs remain unchanged. This does not approve publication, independent ground-truth review, or an official model comparison.

### Local runtime note

During the combined suite, this Mac repeatedly marked virtual-environment `.pth` files hidden, causing Python to ignore the editable CUA package path. The local installation was changed to a regular wheel from the same audited upstream source, without dependency upgrades. Installed loader bytes and model weights still match their verified hashes. All 52 adapter/fidelity tests then passed in a fresh process, including genuine inference. This was an environment import failure, not a model prediction or checkout failure.

If an editable installation is affected by the same macOS behavior, install the audited checkout normally (substitute its path):

```sh
uv pip install --python .venv/bin/python --no-deps --reinstall /path/to/pinned-cua/libs/cua-s1/python
.venv/bin/python -m scripts.research.verify_models --model cua-s1
```

A fresh-server replay after the installation repair (`082b01a7bc1345cbb83a97859f97ca74`) reproduced all seven selected decisions, four browser actions, three validation errors, and the same `no_progress` failure. Both genuine runs remain preserved.

The complete regression run subsequently exposed a provider refresh race in V21-ST03: rapid retries could invalidate its in-flight public UI poll after the server had advanced to authentication. The harness now waits up to an additional 600 ms for an unchanged navigation action to produce a visible transition before retrying. The three-attempt bound remains unchanged. A deterministic delayed-refresh test and five successful ST03 reference replays verify this fix. General action-unavailable feedback is distinguished from invalid form fields in failure attribution.

The final-source genuine replay (`83167839dfc94537b7d6352b8a7ee0df`) again produced seven actual model calls, four browser actions, three validation errors and `no_progress`, with the same incorrect decisions and screenshot. All earlier runs remain intact.
