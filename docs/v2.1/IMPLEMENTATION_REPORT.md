# CheckoutBench 2.1 implementation report

Implementation reviewed 2026-10-14. **74 new versioned scenarios** across nine families coexist with 18 v1 and 56 v2 scenarios. Existing scenario definitions and historical result JSON are retained. No model shortlist changes, paid model benchmark, real payment, or government transaction was performed.

## Completed validity corrections

- Independent customer document (`scenarios/customer.py`) and versioned task builder (`scenarios/v21.py`) replace answer-derived preferences. Poisoning expected answers, outcome, fields and opaque mappings cannot change the task.
- Website state exposes visible values and opaque action handles. Cross-version legacy data routes reject v2.1 sessions. The browser cannot access the dashboard, scoring modules, other sessions, files, official payment APIs or sandbox administration.
- CUA selects profile candidates using visible semantics; invalid choices and skipped choices remain in its classification denominator. Private classification happens after execution. TinyClick predicts every field/navigation click from the current screenshot; its erroneous coordinate is executed, without target-locator scrolling or coordinate repair. Bounding boxes are private post-inference measurements only.
- Hybrid calls are individually attributed to CUA and TinyClick. Deterministic lifecycle navigation, TinyClick-only semantic assistance, native wallet autofill and AI actions are separately labelled. Neither specialist is represented as an autonomous general browser agent.
- Timing separates model calls, browser setup, model screenshot, artifact capture/storage, execution and controller computation. Residual observation/wait/teardown is labelled. Browser Use does not expose all component intervals; those are null, not fabricated zeros. Inference includes lazy loading/client processing; cold/warm performance needs controlled future experiments.
- Version/platform/integrity/configuration partitions prevent pooled legacy/new scores. New model batches use v2.1; historical versions are reference-replayable. Reference results are fixture checks, never AI scores.

## Completed workflow corrections

| Family | Implemented behavior | Boundary |
|---|---|---|
| Shopify | Six merchants, true one-page versus three-page progression, separate accelerated authentication, editable saved summaries, sandboxed merchant options | Supported-control approximation with opaque-origin isolation; not Shopify's SDK; Plus-style placement explicit |
| Stripe | Hosted, whole-checkout iframe and isolated Payment Element; tabs and configured ordering, browser-required test card, return verification | US Payment Element includes card/bank choice; unconfigured wallets hidden; real SDK/eligibility not validated |
| Link | US/USD addresses and ZIP, recognition, auth, saved/expired methods, stale billing, consent, manual fallback, A/B/C comparison | Native fill credit belongs to the wallet. Native-only stale data intentionally fails |
| Razorpay | Merchant order then modal, contact prefill, categories, dismissal/relaunch, retry, handler-result event and status verification | Synthetic order/callback; no real signature validation |
| Cashfree | Hosted navigation, popup and inline iframe; session state, failure retry and verified return | Desktop QR/mobile intent; VPA is an iOS exception case |
| Generic | Compact guest form, split name/building/street/locality, staged address-book form, serviceability/COD/coupon controls | Fictional merchant rules; not a production merchant replica |
| Railway | Legacy and 2026 web-inspired passenger tables, gender/nationality, saved passenger, boarding/preferences/fare/review/payment | Browser guide replaces Android app evidence. Current authenticated layout unknown |
| Passport | Legacy versus refreshed staged application/appointment, conditional Tatkaal declaration, availability, review, redirect and expiry | Historical workflow evidence; refreshed geometry and current policy unverified |
| eChallan | Lookup, configured identity approval, paid/pending/unpaid ledger, separate verification URL, payment/return, mock CAPTCHA handoff | Staging evidence intermittent; not a production portal clone |

Q0–Q5 retain independently decoded QR images. Metrics distinguish generation, independent validity, preparation, handoff and completion. QR/intent tasks stop at user handoff. A displayed/decoded QR never earns payment-completion credit. Invalid/expired/delayed/locked OTP, modal/iframe/popup/redirect and reauthentication remain runner-owned simulations.

## Evidence

- [Source audit and exact references](SOURCE_AUDIT.md).
- [Versioned reference results](reference-verification.json).
- [Test and evidence summary](validation-summary.json).
- [Before/after screenshots](SCREENSHOTS.md), including the corrected desktop railway layout.
- [Historical preservation proof](history-preservation.json): all **163 original rows** match their pre-change JSON byte-for-byte; identical aggregate SHA-256. Backup is local/ignored.
- [Optional sandbox configuration](SANDBOX_VALIDATION.md): disabled-by-default, read-only test-object validation, separate from scoring. No optional credentials were supplied or used.

Negative controls execute wrong CUA values and wrong TinyClick coordinates, require both hybrid calls, retain invalid predictions in accuracy, and reject stale billing, wrong card, wrong fields and unverified completion. Real specialist weights/endpoints were not available; these are contract/execution tests, not evidence of actual model quality.

## Remaining priorities

1. **Before capability claims:** configure and run actual specialist checkpoints/endpoints; record exact artifact revisions, hardware, cold/warm runs and model traces. Different controller assistance must remain visible in comparisons.
2. **Before production-fidelity claims:** permissioned current government-web screenshots and actual official SDK sandbox walkthroughs are still needed. Source confidence is explicit; no authenticated current government UI was verified. Sandbox routes only reconcile test objects and cannot validate screen geometry by themselves.
3. **Before generalisation claims:** freeze a fresh unseen suite. Migrated v2 holdouts are historical regression cases, not a pristine unseen evaluation set. No model was trained or tuned here.
4. Broader provider methods, real SMS/wallet cookies, installed-app routing, real callback signatures and risk/eligibility behavior remain outside local simulation. US bank selection is a handoff boundary, not a completed ACH transfer.

Passing reference executors establishes local solvability and regression coverage. It does **not** make the benchmark research-grade or establish production realism.
