# CheckoutBench 1.0

A local research platform for comparing AI checkout systems on synthetic Indian delivery, UPI and test-card tasks. React/TypeScript dashboard, FastAPI, Playwright, Browser Use and SQLite. **All checkouts and payments are simulated.** No merchant accounts or payment-provider SDKs are used.

## Start locally

Requirements: Python 3.12+, Node 22+, `uv`, and a Chromium-compatible machine.

```sh
uv sync --python 3.12 --extra test --extra agent
.venv/bin/playwright install chromium
npm --prefix frontend ci
npm --prefix frontend run build
cp .env.example .env
./scripts/start.sh
```

Open **http://127.0.0.1:8000**. The isolated checkout origin is **http://127.0.0.1:8001**. Both bind only to loopback. The startup command loads `.env`. To rebuild after frontend changes, run `npm --prefix frontend run build` and restart the server. `npm --prefix frontend run dev` provides a Vite development server; use its configured API proxy.

If `uv` encounters an obsolete system interpreter on macOS, use `UV_PYTHON_PREFERENCE=only-managed uv python install 3.12`, then prefix the sync command with `UV_PYTHON_PREFERENCE=only-managed`. If Node reports a certificate-chain error on a managed Mac, use `NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem npm --prefix frontend ci` when that file contains your trusted CA bundle. Certificate verification remains enabled. The backend uses `SSL_CERT_FILE`, or `/etc/ssl/cert.pem` when available.

## Run an experiment

1. Select one or more models. The deterministic reference is a **fixture validation baseline**, not an AI model.
2. Select a scenario, all 15 core scenarios, or include the three holdouts. Pick a synthetic customer, or use each scenario's default.
3. Keep the initial three repetitions, or increase them. Advanced settings control seed, actions, timeout, output tokens, reasoning effort, video and optional batch spend cap.
4. Review the estimated API expenditure, then start. Runs execute sequentially with a new browser profile and identical 1280 × 900 viewport.
5. Watch screenshots and actions in **Live session**. Pause takes effect at the next controller/agent boundary. Stop cancels the active run and remaining queue.
6. Inspect **Results** for leaderboard, per-scenario success, action replay, videos and JSON/CSV exports. Unavailable, blocked and stopped runs are excluded from model failure rates.

No inference spending cap is imposed by default. The action and timeout limits bound execution. The planning estimate assumes 6,000 input tokens and the full output budget per step; it is explicitly an estimate. If a cap is set, OpenRouter/direct calls reserve a conservative context-window cost ceiling **before** sending each request. Provider-reported cost replaces the reservation; missing usage is estimated and interrupted/uncertain calls retain their reservation. Provider pricing can change, so a provider-side credit limit remains the final billing control. Self-hosted specialist endpoint hosting/GPU costs are outside the API-cost ledger and are marked unreported when no cost is returned. A batch cap blocks remote specialist systems whose billing cannot be bounded; use local inference or an endpoint-side quota.

## Frontier models

Set `OPENROUTER_API_KEY` in `.env` and restart. Keys are used only in the backend and never returned to the dashboard. The application queries `https://openrouter.ai/api/v1/models` and resolves **exact** IDs, prices, modalities and supported parameters at runtime. Refresh the catalogue from the model panel. Missing IDs stay unavailable; no weaker/free model is substituted. Free models may be explicitly added using catalogue search.

The six requested candidates are prelisted: GPT-6 Astra, Sol and Luna; Claude Fable 5.1, Sonnet 5.5 and Haiku 5.5. Browser Use 0.11.13's native `ChatOpenRouter` is used. No planning/judge/fallback model or unmetered extraction LLM is enabled. Browser Use performs actual browser actions, not just API completions. Its file, JavaScript-evaluation and external-navigation tools are removed.

Reasoning controls offer explicit effort values only when the catalogue advertises reasoning support. OpenRouter does not enumerate per-provider effort levels in the models response; individual values are provider-validated. Unsupported settings fail explicitly, with no automatic downgrade. Use a separate batch for a high-capability setting (`high`, or `max` if accepted by that model/provider) and a lower-latency setting. Exact parameters, provider responses, usage and prices are saved with each run.

### Explicit direct-provider adapters

For an OpenAI-compatible provider unavailable through OpenRouter, configure `DIRECT_MODELS_JSON` with an explicit model and provider credential variable. This creates an additional selectable system; it is never an automatic fallback. Example `.env` entry (replace the ID with a model actually accessible to your account):

```dotenv
DIRECT_MODELS_JSON='[{"id":"direct/my-frontier","name":"My direct frontier","model_id":"EXACT_PROVIDER_MODEL_ID","base_url":"https://YOUR_PROVIDER/v1","api_key_env":"DIRECT_PROVIDER_API_KEY","vision":true,"context_length":200000,"reasoning_levels":["low","high"],"token_parameter":"max_tokens","pricing":{"prompt":"0.000005","completion":"0.000015"}}]'
DIRECT_PROVIDER_API_KEY=
```

The endpoint must support chat completions with JSON-schema structured output. Direct pricing/capabilities are operator-supplied, not catalogue-verified. `token_parameter` may be `max_completion_tokens` when required. The direct adapter sends `reasoning_effort`; providers using another protocol need a new typed adapter. Native Anthropic direct API and official payment gateway sandboxes are not bundled.

## Specialist systems

See [docs/SPECIALISTS.md](docs/SPECIALISTS.md) for real model inference, exact remote endpoint contracts, checkpoints and hardware requirements.

| Selectable system | Model role | Controller |
| --- | --- | --- |
| CUA-S1 Forms | Field-option scoring, confidence | Generic DOM + Playwright |
| TinyClick | Screenshot coordinate grounding | Generic DOM checkout controller |
| CUA-S1 + TinyClick | Field scoring + coordinate grounding | Shared deterministic controller |
| MAI-UI-2B | Screenshot-driven next action | Native `mobile_use` action parser |
| UI-Venus-1.5-2B | Screenshot-driven next action | Native `<action>…</action>` parser |

Weights are never downloaded on application startup. Missing dependencies, weights, hardware or endpoints produce unavailable runs. Local inference is lazy and uses safetensors. CUA-S1 is not a generative LLM. The requested TinyClick repository currently has no weight files; its example mentions a different repository, which is not silently substituted.

The reference/TinyClick controller uses public form names, labels, options and the supplied profile. It has no scenario-ID branches or access to the evaluator. It supplies workflow policy and field entry for TinyClick; this is a **system comparison**, not evidence that TinyClick independently solves checkout. CUA-S1 controls delivery/billing field assignments; payment orchestration is deterministic. Model-level field and grounding scores are recorded separately from end-to-end success. GUI agents receive screenshots, the public task and action history.

Hardware planning: core reference/browser runs need no GPU; 8 GB system RAM is a practical starting point. CUA-S1 can run on CPU. TinyClick typically needs several GB of working memory. The 2B GUI systems should be planned around 8–12+ GB GPU/unified memory, depending on image/token budget; CPU fallback is slow. These are estimates, not measured requirements on this machine. CUDA/MPS/CPU detection and dependency state appear in model metadata. A configured model is marked `configured_unverified` until real inference succeeds. Local cancellation cannot forcibly interrupt a PyTorch kernel already executing; bounded generation may finish in its worker thread after Stop.

## Environments and scenarios

Four original visual environments draw on public checkout interaction patterns without copying provider code/assets or implying affiliation:

- **Paper & Form / Stripe-inspired:** contact/shipping, billing toggle, embedded card iframe, simulated 3DS preparation and validation recovery.
- **Northstar / Razorpay-inspired:** PhonePe, Google Pay, Paytm and BHIM, app switching, non-scannable QR preparation, card and legacy dummy VPA.
- **Kinship / Cashfree-inspired:** hosted layout, modal checkout, failure/retry and local mock-bank handoff with pending state.
- **The Good Store / generic Indian commerce:** dependent city choices, address suggestions, editable wrong saved address, delivery instructions and distracting fields.

| ID | Challenge |
| --- | --- |
| T01 | Standard delivery + PhonePe |
| T02 | Unfamiliar labels |
| T03 | Empty optional Address Line 2 |
| T04 | State/city dependency |
| T05 | Address autocomplete |
| T06 | Separate shipping and billing |
| T07 | Wrong prefilled details |
| T08 | PhonePe when card is preselected |
| T09 | Google Pay among four apps |
| T10 | Non-scannable QR preparation |
| T11 | Legacy synthetic UPI VPA |
| T12 | Card iframe |
| T13 | Card error then recovery |
| T14 | Modal failure then retry |
| T15 | Synonyms, distracting fields, searchable state, delayed rendering, switching |
| H01 | Holdout: unfamiliar separate billing + card |
| H02 | Holdout: redirected QR retry |
| H03 | Holdout: unfamiliar saved delivery + BHIM |

Definitions in `scenarios/catalog.py` include initial state, expected synthetic profile, target payment, required/optional fields, allowed actions, success conditions, seed and timeout. Holdouts are tagged and excluded from the default **All core** selector; no specialist model is trained here. Labels are selected deterministically from the seed. Model sampling itself is not promised deterministic.

## Evaluation and security boundary

Checkout business validation checks formats, required fields and allowed test-payment data. It does **not** compare addresses to hidden profiles. The private evaluator independently checks required-field exactness (with whitespace/case/phone normalization), optional empty-or-correct handling, requested payment/app, test-card details and the authorisation-ready stage. A plausible but wrong address may reach the UI's ready screen and still score as a benchmark failure.

Empty Address Line 2 never blocks or lowers a score. If supplied, it must match the profile's optional value. The original `index.html` bug is fixed and regression-tested. That legacy page still contains its old client-side fixture and is retained only for regression/reference; the benchmark does not serve or run it.

The control API and checkout have different loopback ports. The agent's browser route policy permits only its opaque session URL, that session's submit endpoints, and four fixture assets. Other sessions, the dashboard, model catalogue, results, arbitrary loopback ports, external websites and WebSockets are blocked. CSP also restricts fixture resources to the local origin. Neither expected customer data nor scoring results are returned by the fixture configuration. This is a controlled benchmark boundary, not a hardened isolation system for hostile code with operating-system access.

Only the documented Stripe `4242 4242 4242 4242` test card with synthetic expiry/CVV and `checkoutbench@example.invalid` VPA are accepted by new fixtures. There is no banking request, OTP prompt, UPI PIN, usable QR or approval button.

## Persistence, statistics and exports

`data/results.sqlite3` stores complete run records. `data/<run-id>/` stores step screenshots, an action JSON file and optional WebM video. API keys are never recorded. All visible personal values are fictional. Restarted active runs are marked blocked; completed results survive restarts. Queue resumption after process restart is not implemented.

Leaderboard ordering: success rate, Wilson 95% lower confidence bound, median successful duration, mean actions, cost per success. Cohort hashes include the selected scenario set, seed, profile, repeats and configuration, so unequal test conditions are not pooled. Reference systems are visibly labeled. Wilson intervals, duration standard deviation, recovery/holdout success and scenario counts are available in the API. With few trials, intervals are wide; no statistical superiority is claimed automatically.

Wall time includes setup and capture overhead. Inference time is measured separately. The `browser_interaction_seconds` field is explicitly marked as wall-minus-inference, including controller/setup overhead; it is **not pure browser CPU time**. Local loading time may be included in first inference. Each configuration gets fresh model adapters; no warm-cache latency claim is made.

```sh
curl http://127.0.0.1:8000/api/export/json -o benchmark.json
curl http://127.0.0.1:8000/api/export/csv -o benchmark.csv
.venv/bin/python scripts/check.py --repeats 3
```

Exports retain conditions and exact configuration. They are deterministic snapshots while no run is changing. Action replays are screenshots, not re-execution of recorded transactions.

## Tests

```sh
.venv/bin/pytest -q
npm --prefix frontend run build
```

Tests start separate servers on 8765/8766 and use temporary SQLite/artifact directories. They cover all 18 scenarios with browser execution and video, the original optional-field regression, partial/wrong scoring, dependent controls, iframe/retry transitions, unavailable classification, exact network allowlisting, hidden-metadata isolation, cost reservations/reconciliation, strict specialist parsers, pause/resume/stop, exports, and a **scripted-response** native Browser Use action in real Chromium. Mocked adapter tests are not benchmark model results. A genuinely paid or weights-backed run requires your credentials/checkpoints.

See [docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md), [docs/RESEARCH.md](docs/RESEARCH.md), and [docs/SPECIALISTS.md](docs/SPECIALISTS.md).

## Layout

```text
frontend/              React dashboard, Vite, TypeScript
checkout_fixtures/     Local HTML/CSS/JS checkouts + card iframe
scenarios/             Private seeded definitions and synthetic profiles
backend/adapters/      Native OpenRouter/direct and specialist inference
backend/browser/       Generic execution, extraction and allowlist
backend/evaluator/     Programmatic private scoring
backend/runner/        Sequential batches, cancellation and captures
backend/storage/       SQLite and reliability aggregation
backend/fixtures.py    Isolated checkout HTTP surface
backend/app.py         Control API, SSE and dashboard
scripts/               Startup and repeatable reference verification
tests/                 pytest + actual Playwright/Browser Use execution
```

Private GitHub repository: [devatreya/checkoutbench](https://github.com/devatreya/checkoutbench). Runtime data, environment files and installed dependencies are excluded from Git.
