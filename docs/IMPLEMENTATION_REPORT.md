# CheckoutBench 1.0 implementation report

Date: 2026-10-13. Private repository: [devatreya/checkoutbench](https://github.com/devatreya/checkoutbench). This report distinguishes implemented integrations from measured model performance.

## Delivered

- React/TypeScript/Vite local dashboard: model selection/search, scenario preview/reset, synthetic profile selection, configurable multi-model batches, estimated spending review, live screenshots/actions, pause/resume/stop, leaderboard, scenario matrix, result inspection, replay, optional WebM videos and JSON/CSV export.
- Four original checkout presentations: Stripe-inspired Paper & Form, Razorpay-inspired Northstar, Cashfree-inspired Kinship and generic Indian commerce. Interactions include optional fields, aliases, wrong prefill, state-dependent city choices, native address autocomplete/searchable state controls, separate billing, custom payment radios, four UPI apps, non-scannable QR, legacy VPA, masked embedded card inputs, simulated 3DS-ready state, loading, modal failure/retry and a mock bank/pending handoff.
- 15 deterministic core scenarios and three disjoint holdout definitions, with three synthetic profiles and separate billing addresses. Seeded variation, required/optional definitions, initial states and success conditions are private server-side data.
- Original `index.html` Address Line 2 regression fixed: blank optional values pass, populated wrong values still fail. Optional labels and required state/city attributes now agree with validation.
- Separate loopback dashboard and checkout origins. Per-session exact request allowlist, blocked WebSockets/external endpoints, local-only fixture CSP, restricted Browser Use tool set, private deterministic evaluation and no real payment code.
- Sequential isolated browser runner with bounded action/time/token budgets; automatic retry only for pre-action, zero-cost infrastructure failures; SQLite persistence; process-restart classification; exact settings, usage, action screenshots and run records.
- OpenRouter live catalogue, pricing/capability detection, native Browser Use integration, explicit reasoning configuration, no fallback model, no LLM judge, metered requests and optional conservative spending reservations. Explicit direct OpenAI-compatible adapters are configurable in the backend.
- Genuine lazy local/remote specialist adapters: CUA-S1 safetensors option scoring; TinyClick Florence-style grounding; MAI-UI `mobile_use` actions; UI-Venus native action grammar. Each has its own capability, exact model ID and availability state. Field-classification and grounding metrics remain distinct from end-to-end scores.
- README, environment example, hardware/endpoint documentation, source research notes, startup and reference-verification scripts, dependency lockfiles and automated tests.

## Verified results

- **54/54 deterministic reference trials succeeded**: all 18 scenarios × 3 repetitions, seed 2026. **9/9 holdout trials succeeded**. Required-field accuracy, optional handling and requested payment checks passed. See [reference-verification.json](reference-verification.json).
- Reference median wall time: **1.489 seconds** on this machine; action counts ranged from 9 to 21. These numbers include browser/controller/capture overhead and are environment checks, not an AI capability or latency comparison. UI inspection occurred during part of this smoke suite.
- The automated suite passes **30 tests**, including all 18 scenarios in Chromium with recorded video, optional/required-field behavior, iframe cards, failure/retry, hidden metadata, host/path restrictions, paid-call accounting and caps, direct-provider credential gating, native specialist contracts/parsers, pause/resume/stop, deterministic exports and unavailable-versus-failure classification.
- Native Browser Use 0.11.13 executed a real Chromium input action using a **scripted test response** through `ChatOpenRouter`. The typed input was observed in the page and usage hooks were checked. This is an integration test, not a model result.
- A dashboard launch-to-result smoke test completed one additional reference run, and action replay worked. Eleven unavailable configurations (six frontier + five specialist systems) were explicitly recorded as unavailable, with no paid calls.
- TypeScript compilation and Vite production build passed. Browser UI inspection found no page JavaScript errors and no horizontal overflow at a 390-pixel mobile viewport. Dashboard screenshots are in [screenshots/](screenshots/).
- Runtime OpenRouter lookup returned **461 catalogue entries** and found all six exact requested candidate IDs. Pricing/capabilities are refreshed at runtime, not hardcoded from this observation.

## Unavailable measurements and limits

- **No OpenRouter API key was configured. No real paid inference was performed, and no frontier model ranking is claimed.** All six candidates are correctly unavailable without credentials despite being present in the catalogue.
- **No specialist checkpoints or remote inference endpoints were configured. No weights-backed specialist runs were performed.** PyTorch was not installed in the core environment; CPU host architecture was detected as Apple Silicon arm64. CUDA/MPS runtime suitability awaits the specialist dependency installation. The optional adapters are implemented and contract-tested, but real checkpoint execution still needs validation on the chosen hardware.
- The requested `kzawistowsk/TinyClick` repository currently contains a model card but no checkpoint weights. The model card refers to another repository; it is not substituted automatically.
- The local stores approximate the documented interaction patterns. They are not complete provider clones or official integrations. Cashfree-style bank handoff uses a local query-state change, not an external gateway. Actual provider sandboxes and native non-OpenAI-compatible direct provider protocols are not bundled.
- No model training or fine-tuning is included. Holdouts are withheld from the default core selector; this project supplies no training corpus containing them.
- The generic deterministic controller supplies workflow policy and uses public semantic field names for the reference/TinyClick systems. CUA-S1 determines shipping/billing field assignments, while payment details are filled by the controller. These are explicit system configurations, not interchangeable raw-model comparisons.
- Browser time is wall time minus measured inference, including setup, controller and screenshot overhead. Local model loading can occur in inference timing. Pure browser CPU latency, endpoint hosting cost, energy usage and warm-cache benchmarking are not measured.
- Local model generation runs in a worker thread. Stop cancels the run, but cannot forcibly terminate an already executing PyTorch kernel. Maximum generated tokens remain bounded.
- Optional spending caps cover metered OpenRouter/direct requests. Remote specialist configurations with unknown billing are blocked when a batch cap is set. Price estimates use catalogue/operator rates; provider-side quotas remain authoritative.
- Queue state is in memory. Results survive restarts; interrupted runs are marked blocked and the unfinished queue is not automatically resumed. The local API is intended for one operator, not shared network deployment.

## Next controlled comparison

1. Configure `OPENROUTER_API_KEY`, refresh the catalogue and run the six-model shortlist on all core scenarios with the same profile, seed, viewport and three repetitions.
2. Run separate maximum-capability and low-latency configurations. Per-model effort values are validated by the provider; unavailable settings fail explicitly.
3. Configure verified specialist weights or exact-model endpoints following [SPECIALISTS.md](SPECIALISTS.md); first run one scenario per adapter before a complete suite.
4. Compare only matched cohort IDs, inspect failures and then increase repetitions. Keep holdout outcomes separate from development/core results. Prioritize success, confidence/reliability, successful-run duration, recovery/action efficiency and then cost.

No winner can be identified from the current reference-only measurements.
