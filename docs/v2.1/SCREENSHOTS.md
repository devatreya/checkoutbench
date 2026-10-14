# Before/after visual evidence

[Machine-readable inspection](screenshots/inspection.json) covers **112 fixture captures** (initial and selected payment stages) at 1280×900 and 390×844, plus the dashboard. Both widths are responsive-layout checks; resizing a desktop scenario does **not** convert its payment policy into a mobile scenario. `V21-RZ02` and explicitly mobile scenarios supply mobile-web policy. No native-app benchmark is implied.

| Environment | Before (v2) | After (v2.1) | Visible correction |
|---|---|---|---|
| Railway | [App-inspired cards](../v2/screenshots/railway-responsive-1280.png) | [Browser passenger rows](screenshots/railway-web-inspired-2026-1280.png) | Name, age, berth, gender, nationality; saved passenger; separate journey summary. Current authenticated IRCTC layout remains unverified. |
| Shopify one-page | [v2 beauty](../v2/screenshots/shopify-beauty-1-1280.png) | [One-page and extension sandbox](screenshots/shopify-beauty-1-1280.png) | Contact, delivery, merchant options and payment coexist; no artificial review screen. |
| Stripe | [Shared authentication form](../v2/screenshots/stripe-stripe-1280.png) | [Embedded checkout](screenshots/stripe-embedded-1280.png), [isolated payment component](screenshots/stripe-payment-element-payment-1280.png) | Separate component boundaries; configured payment choices. |
| Razorpay | [v2 QR form](../v2/screenshots/razor-qr-0-1280.png) | [Order-backed modal](screenshots/razor-standard-modal-payment-1280.png) | Gateway launched after merchant shipping; contact prefill, categories, dismissal. |
| Cashfree | [v2 QR form](../v2/screenshots/cashfree-qr-1-1280.png) | [Hosted](screenshots/cashfree-hosted-payment-1280.png), [popup](screenshots/cashfree-popup-payment-1280.png), [inline at narrow width](screenshots/cashfree-inline-payment-390.png) | Separate navigation/window/iframe paths. |
| Generic merchant | [Shared form](../v2/screenshots/generic-generic-1280.png) | [Split address](screenshots/generic-split-address-1280.png), [address book](screenshots/generic-address-book-1280.png) | Independent address structure and progression. |
| Passport | [v2 appointment](../v2/screenshots/passport-appointment-1280.png) | [Legacy](screenshots/passport-legacy-1280.png), [refreshed approximation](screenshots/passport-refreshed-1280.png) | Separate application and appointment stages; no current-fee claim. |
| eChallan | [v2 lookup](../v2/screenshots/echallan-lookup-1280.png) | [Lookup](screenshots/echallan-lookup-1280.png) | Initial lookup retained; verification is now a separate route, tested through Playwright. |

[Source-fidelity dashboard](screenshots/coverage-desktop.png) shows provenance and experimental classification. Screenshots establish local rendered behavior, not equivalence to authenticated production sites.
