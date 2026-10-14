# Source-to-implementation audit — CheckoutBench 2.1

Reviewed **2026-10-14**. Publication/update dates are **unknown unless specified** below; retrieval dates are not publication dates. Official documentation establishes workflows, not pixel-perfect replicas. No authenticated production payment or government interface was exercised. Government sources were partly inaccessible. All local screens, accounts, fees and faults are fictional.

## P0 evaluation validity

| Finding in v2 | Evidence | v2.1 correction |
|---|---|---|
| User preferences copied the answer key | `scenarios/v2.py:task_v2` deep-copies `expected_values` | `scenarios/customer.py` constructs an independent customer document. `task_v21` does not read field definitions, mappings, expected outcomes or fault schedules. Mutation tests poison these without changing the task. |
| Semantic matching selected answers before CUA inference | `backend/browser/v2.py:reference_v2` looks up preferences using input names | `backend/browser/v21.py` passes visible label, role, value and form title to CUA with the customer document. Its returned value drives the action. Opaque IDs are execution handles only. |
| Grounder had a corrected viewport and did not ground fills | Legacy controllers scroll the target locator into view; field filling bypasses TinyClick | All v2.1 TinyClick field and navigation clicks use predicted coordinates. Fixed scrolling is disclosed controller assistance. Private bounding-box scoring occurs after inference and never corrects coordinates. |
| Hybrid attribution incomplete | Semantic/grounding steps did not establish both-model necessity | Separate inference records and action provenance; injected wrong semantic outputs and wrong clicks affect the actual browser. Test doubles prove plumbing, not model quality. |
| Wall-minus-inference described as browser time | `backend/runner/engine.py` residual includes setup/capture/storage | Disjoint measured setup, inference, screenshot, execution and storage intervals; remaining observation/waits/teardown explicitly labelled. |
| Historical results could look comparable | Same dashboard without integrity classification | Original files/results retained. New model batches require v2.1; historical fixtures remain reference-replayable. Leaderboards partition version, platform, integrity and configuration. |

## Environment audit

### Shopify — high confidence in progression, approximate visuals

Original sources: [page layouts](https://shopify.dev/docs/api/checkout-ui-extensions/latest/targets/page-layouts), [extension API](https://shopify.dev/docs/api/checkout-ui-extensions/latest), [test orders](https://help.shopify.com/en/partners/manage-clients-stores/test-orders). Source type: **web SDK documentation**; API selector **2026-07**, publication date unspecified. Current verification also used [extension testing](https://shopify.dev/docs/apps/build/checkout/test-checkout-ui-extensions). The requested [development-store URL](https://help.shopify.com/en/partners/manage-clients-stores/development-stores/test-orders-in-dev-stores) is not used as evidence of a particular live store.

v2's `checkout_fixtures/v2.js:body/details` rendered payment on the nominal one-page form but still required Details → Review → Payment. Express used prefill without its own authentication. The open shadow root was not an extension security boundary. v2.1 keeps all native one-page sections together, gives three-page checkout Information/Shipping/Payment visibility, and requires an accelerated-session authentication step before editable saved summaries. Six merchant configurations remain. Merchant options use restricted controls in an opaque-origin sandbox; this is explicitly **not Shopify's actual SDK**. Plus placement is labelled. Shipping areas, delivery slots, gift options, warranties and subscription consent are fictional merchant rules, not universal Shopify capabilities.

### Stripe — high confidence in integration boundaries

Sources: [Checkout](https://docs.stripe.com/payments/checkout), [Payment Element](https://docs.stripe.com/payments/payment-element), [official examples](https://github.com/stripe-samples/accept-a-payment), [browser testing](https://docs.stripe.com/testing). Source type: **web SDK docs**, dates unspecified. v2 primarily reused authentication-themed merchant forms. v2.1 distinguishes a hosted page, a merchant page with an entire embedded checkout, and a separately isolated payment-collection component (`checkout_fixtures/v21.js:render/body/payment`). Tabs/accordion are local approximations; eligibility and method ordering are configured, not claimed to reproduce Stripe's ranking algorithm.

The browser test reference identifies `4000000000003220` as a 3DS-required test card; `4242424242424242` is unenrolled and does not establish a required browser challenge. v2.1 uses the former for Stripe authentication fixtures. The simulator's OTP expiry/lock/delay schedules are synthetic stress tests, not Stripe browser-card guarantees. Mobile-only challenge tables are not layout evidence. The US/USD Payment Element case includes a configured [US bank-account option](https://docs.stripe.com/payments/ach-direct-debit/accept-a-payment) alongside card; bank selection requests user handoff. Unconfigured browser wallets remain hidden. No sandbox credentials or live Stripe SDK are used in scored fixtures.

### Link — high confidence in eligibility and wallet attribution

Sources: [Link](https://docs.stripe.com/payments/link), [Payment Element integration](https://docs.stripe.com/payments/link/payment-element-link), [Checkout integration](https://docs.stripe.com/payments/link/checkout-link). Source type: **web SDK docs**, dates unspecified. Link documentation explicitly excludes India. v2's US/USD label did not fix Indian address data. v2.1 uses synthetic US addresses/ZIP codes, labels the supported market and preserves returning-user recognition, authentication, saved methods, stale billing, expired cards, consent and manual fallback.

Native autofill is credited only to actual changes from the simulated wallet. A/B/C arms remain; native-only A deliberately does not repair stale wallet data. Link, Checkout, Payment Element and the Payment Links product are not interchangeable. Cookies, SMS delivery and real account risk checks remain outside the simulation.

### Razorpay — high confidence in Standard Checkout boundary; conditional UPI support

Original v2 source was the general [documentation homepage](https://razorpay.com/docs/), insufficient to justify its shared shipping/payment form. Current sources: [Standard Checkout integration](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/), [UPI Intent](https://razorpay.com/docs/payments/payment-methods/upi/upi-intent/), and the official [2026 Intent/Collect explanation](https://razorpay.com/blog/upi-intent-vs-collect-success-rates/). SDK publication dates unspecified; official blog dated April 2026. The blog is provider guidance, not an independently obtained NPCI circular.

v2.1 separates merchant shipping from order-backed modal payment, prefilled contact, methods, dismissal, failure/retry, callback and server verification. Desktop offers QR; Android mobile web offers intent. It does not claim native-app execution, installed-app discovery, or universal iOS support. Manual VPA is not a standard desktop option. No real order, signature or gateway connection exists in scored runs.

### Cashfree — high confidence in integration/device distinctions

Sources: [overview](https://www.cashfree.com/docs/payments/overview), [hosted](https://www.cashfree.com/devstudio/preview/pg/web/checkout), [popup](https://www.cashfree.com/devstudio/preview/pg/web/popupCheckout), [inline](https://www.cashfree.com/devstudio/preview/pg/web/inlineCheckout), [Collect changes](https://www.cashfree.com/docs/payments/manage/payment-methods/upi-collect). Type: **web SDK docs**, publication dates unspecified. Collect guidance gives effective date **2026-02-28** for Android/desktop restrictions, iOS until further notice and listed category exceptions.

v2 reused a generic gateway. v2.1 has current-tab hosted navigation, a separate popup and an inline iframe, plus session launch, return verification and retry. Desktop QR/mobile intent are explicit. The iOS VPA case is an exceptional simulation, not blanket availability. Order IDs, payment responses and duplicate prevention are local. Government/statutory category exemptions must be validated for a real merchant configuration.

### Generic Indian merchant — high confidence in address convention, synthetic merchant rules

Source: [UPU India addressing guide](https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/indEn.pdf), **postal reference / historical documentation**, undated. It supports six-digit PIN and multi-level address structure, not a specific checkout UI. v1/v2 generic fixtures reused provider-like forms. v2.1 has a compact guest form, split recipient/building/street/locality, and address-book progression with separate delivery choices. Serviceability, prices, coupon handling and COD are fictional merchant policies. No commercial website is represented as a verified clone.

### IRCTC — medium browser workflow confidence; current authenticated layout unverified

v2 primary source [Rail Connect guide](https://contents.irctc.co.in/en/UserGuideIRCTC.pdf) is a **native Android app**, not desktop evidence. Replacement sources: [browser reservation guide](https://contents.irctc.co.in/en/aadhaarBookingDoc.pdf), [legacy e-ticket guide](https://contents.irctc.co.in/en/bookEticket.html). Both undated; the latter is **historical**. [Current website](https://www.irctc.co.in/eticket/) could not be retrieved. Browser guide pages 6–8 support saved passengers, details, review and gateway flow.

v2.1 renders desktop passenger rows with name/age/berth/gender/nationality, saved first passenger, boarding, booking preferences and fare summary. Legacy and `web-inspired-2026` variants are separately labelled. The latter is an informed browser approximation, **not a verified 2026 redesign**. Fare/session faults and infant policy choices are synthetic tasks, not current railway policy. No native UI is counted as mobile-web performance.

### Passport — medium workflow confidence; low authenticated-screen fidelity

Sources: [portal](https://www.passportindia.gov.in/psp/), [availability](https://www.passportindia.gov.in/psp/CheckAppointmentAvailibility), [Apply instructions](https://www.passportindia.gov.in/psp/Apply), [historical appointment PDF](https://www.passportindia.gov.in/AppOnlineProject/pdf/New_Online_Appointment_Booking_Process.pdf), [refreshed entry](https://services2.passportindia.gov.in/forms/Home/homeScreen). Dates unspecified. Public entries were JS-only or partly extractable; authenticated appointment pages were not inspected.

The official [embassy portal](https://embassy.passportindia.gov.in/) describes phased migration by region/country; this does **not** prove migration status for every domestic RPO. v2.1 distinguishes a historical application form from a refreshed web-inspired staged application/appointment flow. Reference, Normal/Tatkaal, availability, review, redirect, confirmation and expiry are represented with fictional details. Old PDF fee/eligibility rules are not copied. Refreshed screen geometry remains uncertain.

### eChallan — medium/low confidence; staging is not production

Original source: [brochure](https://parivahan.gov.in/sites/default/files/FAQDOCS/Echallan/eChallan-brochure-ver-1.0.pdf), broad system context rather than screen evidence. Current sources: [production](https://echallan.parivahan.gov.in/), [staging lookup](https://staging.parivahan.gov.in/echallan/index), [staging payment verification](https://staging.parivahan.gov.in/echallan/payment-verification). **Desktop web**, dates unspecified. Production retrieval failed; staging text was intermittent and repeat requests failed. No current production-layout claim is justified.

v2.1 separates lookup, identity approval when configured, notice ledger, pending-transaction verification route, payment and return. Paid notices stop safely; failed/pending transactions require checking before retries. Mock CAPTCHA is a synthetic handoff, never a solver. All identifiers use DEMO prefixes. No government credentials, fees or live submissions are involved.

## QR and authentication evidence boundaries

Q0–Q5 retain genuine generated images and independent ZXing decoding. Generation, decoder result, preparation, handoff and completion are separate metrics; visual identification is **not inferred** from a successful click. Desktop QR never counts as paid merely because the image decodes. OTP values are private to the runner-owned fictional user. Modal/iframe/popup/redirect, invalid/expired/delayed/locked and reauthentication paths are simulator tests.

## Remaining validation priorities

1. Validate supplied sandbox configurations against official SDKs before claiming provider fidelity beyond documented boundaries.
2. Acquire permissioned, current government web captures before asserting current-layout accuracy. Do not substitute app screenshots.
3. Freeze a fresh unseen holdout before real model comparisons. Migrated v2 holdouts are **historical regression cases**, not evidence of unseen model generalisation.
4. Run actual specialist weights/endpoints and inspect decision traces. Reference/test-double passes demonstrate execution integrity only.
