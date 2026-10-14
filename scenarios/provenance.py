"""Author-facing source records; unknown dates remain null, not guessed."""

REVIEWED = "2026-10-14"
SOURCES = {
    "shopify": dict(
        provider_reference="Shopify web checkout / 2026-07 extension documentation",
        source_url="https://shopify.dev/docs/api/checkout-ui-extensions/latest/targets/page-layouts",
        source_type="SDK",
        source_date=None,
        reference_version="2026-07",
        confidence="high for progression; medium for local extension approximation",
    ),
    "stripe": dict(
        provider_reference="Stripe hosted Checkout, embedded Checkout and Payment Element",
        source_url="https://docs.stripe.com/payments/checkout",
        source_type="SDK",
        source_date=None,
        confidence="high for integration boundaries; approximate styling",
    ),
    "link": dict(
        provider_reference="Link in supported US/USD checkout; unavailable in India",
        source_url="https://docs.stripe.com/payments/link",
        source_type="SDK",
        source_date=None,
        confidence="high for authentication/autofill; synthetic accounts",
    ),
    "razor": dict(
        provider_reference="Razorpay Standard Checkout web integration",
        source_url="https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/",
        source_type="SDK",
        source_date=None,
        confidence="high for launch/handler; UPI configuration remains conditional",
    ),
    "cashfree": dict(
        provider_reference="Cashfree web checkout and UPI device rules",
        source_url="https://www.cashfree.com/docs/payments/manage/payment-methods/upi-collect",
        source_type="SDK",
        source_date=None,
        confidence="high; effective Collect change dated 2026-02-28",
    ),
    "generic": dict(
        provider_reference="Fictional merchant; UPU Indian addressing conventions",
        source_url="https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/indEn.pdf",
        source_type="historical documentation",
        source_date=None,
        confidence="high for PIN/address conventions; merchant flow is synthetic",
    ),
    "railway": dict(
        provider_reference="IRCTC browser reservation guide; live 2026 authenticated UI not inspected",
        source_url="https://contents.irctc.co.in/en/aadhaarBookingDoc.pdf",
        source_type="desktop web",
        source_date=None,
        confidence="medium; undated browser guide, current layout unverified",
    ),
    "passport": dict(
        provider_reference="Passport browser application instructions; refreshed workflow approximation",
        source_url="https://www.passportindia.gov.in/psp/Apply",
        source_type="desktop web",
        source_date=None,
        confidence="medium workflow; low authenticated-screen fidelity",
    ),
    "echallan": dict(
        provider_reference="eChallan staging lookup and payment-verification pages",
        source_url="https://staging.parivahan.gov.in/echallan/payment-verification",
        source_type="desktop web",
        source_date=None,
        confidence="medium; staging text available intermittently, production inaccessible",
    ),
}
