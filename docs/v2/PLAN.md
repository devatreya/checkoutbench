# CheckoutBench v2 implementation plan

## Audit (2026-10-13)

The current application uses FastAPI on two origins, a React dashboard, private Python scenario definitions, Playwright browser execution, and SQLite JSON records. T01–T15 and H01–H03 are the existing suite. The fixtures implement dynamic cities, autocomplete, optional fields, separate billing, wrong prefill, card iframes, gateway retry, and authorisation preparation. QR is a placeholder. There is no OTP simulator, merchant suite, government flow, Link wallet, or versioned leaderboard. Screenshots, action JSON and optional WebM are saved per run. Specialist dependencies/weights are unavailable; adapter contract tests are not inference validation.

Preserve original definitions and results. Add v2 as separate definitions, routes and deterministic state machines; retain all model integrations. Keep public checkout state separate from private expected values and author tools. Fix version grouping and explicit outcome scoring rather than treating every terminal state as paid.

1. Run existing tests and capture baseline.
2. Build six Shopify-inspired merchants with stable native fields and merchant extensions, one-/three-page and express structures.
3. Build hosted, embedded and express Link with returning/new identity, consent, stale details and three labelled experimental arms.
4. Add legacy/responsive railway, appointment and challan flows.
5. Implement independently decoded QR fixtures and shared OTP/3DS simulator, including reference user handoff.
6. Register seeded v2 core and sealed holdout configurations, public tasks and private criteria.
7. Integrate runner, metadata, versioned results, coverage/preview/reference/reset controls.
8. Validate deterministic reference paths, negative scoring, regression, browser isolation, desktop/mobile rendering; publish evidence and limitations.

No model tuning on holdouts and no paid inference. Live third-party integrations remain separately configured, optional work; local mode never contacts payment/government services.
