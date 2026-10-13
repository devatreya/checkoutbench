# Implementation research

Reviewed 2026-10-13. These are interaction references, not claims of provider integration. All runtime payment behavior is original local simulation code.

- [Stripe accept-a-payment](https://github.com/stripe-samples/accept-a-payment) distinguishes hosted Checkout, embedded components and custom payment flows. We model contact/address collection and an isolated card iframe; no Stripe script is loaded.
- [Stripe one-time Checkout](https://github.com/stripe-samples/checkout-one-time-payments) informed the hosted order-summary layout and success-stage separation.
- [Stripe test cards](https://docs.stripe.com/testing) documents the `4242424242424242` test number. The fixture accepts only that number and fixed synthetic expiration/CVV. It never sends them anywhere except the isolated local session.
- [Razorpay standard checkout integration](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/) describes checkout options, callbacks and payment failures. The local Northstar fixture provides contact details, method/app selection and recoverable states. The QR is deliberately non-scannable and no UPI deep link is generated.
- [Cashfree web checkout preview](https://www.cashfree.com/devstudio/preview/pg/web/checkout) informed hosted/modal presentation and a separate payment handoff. The mock-bank stage stays on the fixture origin with a query-state transition; it is not a real gateway redirect.
- [Browser Use source](https://github.com/browser-use/browser-use) and the installed 0.11.13 source were inspected for native `ChatOpenRouter`, `extra_body`, callbacks, allowed domains, tool exclusions and browser lifecycle. Native browser execution is exercised with a scripted LLM response in the integration suite.
- [OpenRouter models API](https://openrouter.ai/docs/guides/overview/models) supplies exact IDs, pricing, input modalities and supported parameters. Runtime catalogue lookup, rather than model names in this document, determines availability. Request hooks save response-reported provider, model, token usage and cost. Effort support beyond the general reasoning capability is provider-validated.
- Specialist source and native inference contracts are documented separately in [SPECIALISTS.md](SPECIALISTS.md).

No proprietary logos/assets or payment SDKs are included. Optional actual provider sandboxes were not implemented, so the local default cannot move money.
