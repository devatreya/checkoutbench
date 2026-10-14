# CheckoutBench v2.0 implementation report

> Historical v2.0 record. The v2.1 audit found answer-derived task preferences and specialist controller assistance that prevent comparison with v2.1 model results. See [v2.1 audit](../v2.1/SOURCE_AUDIT.md). Original fixtures and results are preserved.

Implemented 13 October 2026 in the existing application. The dashboard runs on `http://127.0.0.1:8000`; isolated synthetic checkouts run on port 8001.

## Delivered scope

| Item | Delivered |
| --- | --- |
| Environment families | Nine: Stripe, Razorpay, Cashfree, generic commerce, Shopify, railway, passport appointment, eChallan, Link |
| Interface configurations | 38 distinct family/variant combinations, including responsive and fault-surface configurations |
| Shopify merchants | Six fictional merchants; 12 core merchant/layout cases, additional QR and holdout cases |
| Link interfaces | Hosted, embedded component and express returning customer |
| Railway interfaces | Dense legacy-inspired desktop and modern responsive passenger forms |
| Scenario suite | 74 total: original 15 core + 3 holdouts; new 48 core + 8 holdouts |
| New categories | 12 Shopify, 6 railway, 4 passport, 4 challan, 10 Link, 6 QR, 6 authentication core cases |
| Reference execution | Version-aware generic controller operating on visible form labels, task preferences and browser state |
| Model integrations | Existing OpenRouter, Browser Use, direct-provider, CUA-S1, TinyClick, MAI-UI and UI-Venus adapters retained |

The 38 configurations are not 38 independently built applications. Related fixtures share components while changing page progression, repeated forms, merchant extensions, authentication surfaces, payment components and responsive layout. V1 scenario identifiers and definitions remain intact.

## Workflows and evaluation

Merchant configurations include one-page, three-page and express checkout; saved-detail rollups; shipping/billing separation; shadow-root gift fields; delivery slots and conditional fields; recurring terms; warranty and shipping restrictions. Electronics includes a simulated card-authentication case.

Railway cases handle three passengers, infant berth choices, boarding versus destination, reservation preferences, fare changes and session recovery. Appointment cases validate application/centre/slot/declarations and interrupted gateway return. Challan cases cover challan, vehicle and driving-licence lookup, identity handoff, settled notices and pending/failed transaction recovery with duplicate prevention.

Link authenticates returning users before revealing saved details. New customers can decline registration; registration requires explicit task consent and entered synthetic customer/card data. Stale identity/address, expired methods, unavailable Link and reauthentication are separately evaluated. The native baseline deliberately leaves stale saved details unchanged. Native autofill is credited only for fields populated by that mechanism.

Paired experiments label A (native Link scripted test user), B (agent without Link), and C (agent with Link). Comparisons require matching scenario, seed, profile, repetition, viewport and resource budgets. Selecting the reference in B/C validates the experiment; it does not establish AI benefit.

QR images are generated using `qrcode` and independently decoded with `zxing-cpp`. Q0–Q5 include clean, small, blurred, compressed, obscured and expired fixtures. Parameters include dimensions, density, blur, contrast, compression, crop, quiet zone, error correction, expiry and delay. Display enlargement, full-resolution rendering, regeneration and allowed intent fallback are distinct actions. All payloads use reserved `.invalid` URLs; no QR can request a real payment.

The shared authentication simulator supports four/six digits, segmented inputs, countdown, resend, expiry, invalid/locked/delayed states, modal/iframe/popup/redirect surfaces and mock CAPTCHA handoff. A runner-owned test user supplies synthetic approval outside the agent browser. Handoff and simulated-completion modes have different terminal criteria.

Private scoring verifies fields, optional values, requested payment, consent, authentication, transaction count, actual blocking conditions and outcome. Added metrics include recovery, handoff, QR quality/recovery, stage completion, duplicate avoidance, native autofill, interaction savings and performance grouped by environment and difficulty dimension. Error-detection latency measures the time from a displayed error to a recovery action; it does not infer cognition.

## Dashboard and evidence

**Coverage** exposes the family/variant matrix, validation gaps, task, difficulty/payment/authentication configuration, private author criteria, interactive preview, seed/reset, test-user approval and reference execution. Private criteria are confined to the control origin and absent from the agent-facing state. Scenario and result views support version filtering. Leaderboards keep version, evaluation mode, experimental arm and cohort separate.

Run records include metadata, deterministic scoring, action history, screenshots, optional WebM and JSON/CSV exports. Existing SQLite JSON storage is extended additively.

The pre-upgrade backup is `data/backups/results-pre-v2.sqlite3`. A row-by-row comparison confirmed that all 66 original stored records remain present and byte-for-byte unchanged. New validation records are added alongside them.

## Validation evidence

- Original baseline: 30 tests passed before implementation.
- Full live-app reference run: **74/74 successful**, including v1 and v2; see [reference-verification.json](reference-verification.json).
- Link attribution rerun: **12/12 successful** after correcting native autofill attribution; see [link-reference-verification.json](link-reference-verification.json).
- Final regression: **45 passed in 296.84 seconds**; the subsequently added version/difficulty aggregation regression also passed (**46 distinct tests verified**). Updated scenarios passed 5/5. Paired Link controls matched all six expected outcomes, including the intentional native-only stale-billing failure. See [validation-summary.json](validation-summary.json) and [final-reference-verification.json](final-reference-verification.json).
- Frontend production build passed.
- Desktop/mobile fixture capture: **76 views**, zero JavaScript errors and zero document-overflow reports; see [inspection.json](screenshots/inspection.json). Contact sheets, individual views, dashboard captures and representative authentication/QR stage images are in [screenshots](screenshots/).
- Manual visual review covered every family/variant at desktop/mobile dimensions, plus iframe/popup authentication and QR states.
- Negative controls cover wrong/stale values, premature safe abort, unauthorised registration, requested-payment mismatch, QR enlargement without restored data, duplicate submissions, independent passenger validation and version/difficulty aggregation.

No paid model inference, model-weight download, real payment, live government interaction, or real account registration was performed. Holdouts were checked for fixture solvability only, without model training or tuning.

## Reproduce

```sh
.venv/bin/pytest -q
npm --prefix frontend run build
./scripts/start.sh
# In another terminal, with no benchmark running:
.venv/bin/python scripts/check.py --repeats 1 --output data/reference-verification.json
.venv/bin/python scripts/visual_v2.py
```

For paired Link validation, select the reference model, Link-only scenarios and **Paired A / B / C Link comparison**. L01 should pass all three arms; L03 deliberately fails native-only stale billing and passes B/C. This is an expected negative control, not a fixture defect.

## Boundaries and remaining optional work

These are original, workflow-inspired simulations, not production replicas. [RESEARCH.md](RESEARCH.md) maps official references to reproduced behaviours, simplifications, injected stress cases and uncertainties. Current provider eligibility, real wallet internals, government policies and production authentication timing are not inferred from these fixtures.

Optional Shopify development-store/Bogus Gateway and official Stripe sandbox connectors are not implemented or enabled. They need explicit store/account configuration and a separate network policy. Live government transactions and broader train search are outside the local benchmark.

Actual specialist-model performance is unmeasured here. Real weights/dependencies or compatible inference endpoints are still required; availability is shown in Models. CUA-S1 and TinyClick retain their deterministic workflow controller, so end-to-end results compare complete systems, not independent model capabilities. Wall time includes browser startup and evidence capture. Reference timings cannot be used to estimate model latency or establish superiority.
