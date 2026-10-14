# Optional official sandbox validation

Disabled by default. No credentials were configured or external sandbox requests executed during v2.1 validation. These routes are **read-only reconciliation tools**, not a second scoring pipeline or automatic payment authoriser. They cannot establish visual fidelity by themselves.

On the control origin only:

- `GET /api/sandboxes`: configuration status without secrets.
- `POST /api/sandboxes/{provider}/validate` with `{"object_id":"..."}`: inspect an existing official test object, returning only whitelisted status fields. The agent browser cannot reach these routes.

Configure environment variables locally (never commit them):

| Provider | Variables | Preconditions / evidence |
|---|---|---|
| Stripe | `BENCH_SANDBOX_STRIPE_ENABLED=1`, `BENCH_SANDBOX_STRIPE_KEY=sk_test_…` | Existing `cs_test_…` session; rejects any response without `livemode:false`. Reports payment status and hosted/embedded mode. |
| Razorpay | `BENCH_SANDBOX_RAZORPAY_ENABLED=1`, `BENCH_SANDBOX_RAZORPAY_KEY=rzp_test_…`, `BENCH_SANDBOX_RAZORPAY_SECRET=…` | Existing order created in test mode. Fixed official API with test key namespace. |
| Cashfree | `BENCH_SANDBOX_CASHFREE_ENABLED=1`, `BENCH_SANDBOX_CASHFREE_KEY=…`, `BENCH_SANDBOX_CASHFREE_SECRET=…` | Existing sandbox order. Network destination fixed to `sandbox.cashfree.com`, never production. |
| Shopify | `BENCH_SANDBOX_SHOPIFY_ENABLED=1`, `BENCH_SANDBOX_SHOPIFY_KEY=…`, `BENCH_SANDBOX_SHOPIFY_STORE=your-dev-store.myshopify.com`, `BENCH_SANDBOX_SHOPIFY_TEST_GATEWAY_CONFIRMED=1` | Reads `shop.plan.partnerDevelopment` and rejects non-development stores. Operator must configure Bogus/test gateway; the route does not prove gateway settings. No order is created. |

Use the official sample integration in an isolated browser to manually exercise provider UI, record SDK/API version and screenshot, then reconcile status through these routes. Validate Shopify extension placement/permissions, Stripe browser 3DS with its documented challenge card, Razorpay modal dismissal and callback verification, and Cashfree hosted/popup/inline return paths. Record these separately from benchmark results. Native wallet eligibility and production risk checks remain outside this test.

References: [Stripe session retrieval](https://docs.stripe.com/api/checkout/sessions/retrieve), [Razorpay order retrieval](https://razorpay.com/docs/api/orders/fetch-with-id/), [Cashfree order retrieval](https://www.cashfree.com/docs/api-reference/payments/latest/orders/get-order), [Shopify development-store flag](https://shopify.dev/docs/api/admin-graphql/latest/objects/ShopPlan).

Government portals have no validation route. Never use them for live transactional testing.
