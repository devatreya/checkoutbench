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
```

The tests include a real Chromium + synthetic V21-G01 fixture negative control, with a deliberately wrong deterministic scorer. This verifies execution/evaluation integrity; it is not evidence of model accuracy.
