"""Customer intent contract. No imports from fixtures, field schemas or evaluators."""

from copy import deepcopy


def customer_brief(profile, request):
    p = deepcopy(profile)
    first, _, last = p["name"].partition(" ")
    address = dict(
        full_address=p["address1"],
        building=p["address1"].split(",")[0],
        street="Test Road",
        locality="Sample District",
        landmark=p["address2"],
        city=p["city"],
        state=p["state"],
        postal_code=p["postal"],
        country="India",
    )
    if request.get("market") == "US":
        address.update(
            full_address="27 Example Avenue",
            building="27",
            street="Example Avenue",
            locality="Sample Quarter",
            city="New York",
            state="New York",
            postal_code="10001",
            country="United States",
        )
    billing = dict(
        full_address=p["billing"]["address1"],
        city=p["billing"]["city"],
        state=p["billing"]["state"],
        postal_code=p["billing"]["postal"],
    )
    if request.get("market") == "US":
        billing.update(
            full_address="42 Sample Street",
            city="New York",
            state="New York",
            postal_code="10002",
        )
    return dict(
        customer=dict(
            full_name=p["name"],
            given_name=first,
            family_name=last,
            email=p["email"],
            phone=p["phone"],
            shipping=address,
            billing=billing,
        ),
        test_card=dict(
            cardholder=p["card"]["cardName"],
            number=p["card"]["cardNumber"],
            expiry=p["card"]["expiry"],
            security_code=p["card"]["cvv"],
        ),
        delivery=dict(
            service="Scheduled delivery"
            if request.get("merchant") in ("groceries", "furniture")
            else "Standard shipping",
            time_window="Tomorrow 18:00–20:00",
            allow_substitutions="true",
            substitution_limit="Same price or less",
            floor="3",
            access="Lift available",
            instructions=p["instructions"],
            warranty="Standard warranty",
            insurance="false",
            gift_wrap="false",
            marketing="false",
            purchase="Recurring monthly",
            subscription_authorised="true",
            coupon="",
            gift_message="",
            loyalty="",
        ),
        travellers={
            str(i): dict(
                full_name=name,
                age=str(age),
                gender=gender,
                nationality="India",
                berth=berth,
            )
            for i, (name, age, gender, berth) in enumerate(
                [
                    (p["name"], 32, "Female", "Lower"),
                    ("Dev Sample", 35, "Male", "Upper"),
                    (
                        "Mira Sample",
                        3,
                        "Female",
                        request.get("infant_berth", "No berth"),
                    ),
                ],
                1,
            )
        },
        journey=dict(
            boarding="EXJ · Example Junction",
            destination="DMT · Demo Terminal",
            reservation="Book only if confirmed",
            insurance="Decline",
            coach="",
            maximum_fare="5000",
        ),
        appointment=dict(
            reference="DEMO-ARN-2026-0042",
            service=request.get("service", "Normal"),
            centre="Sample East Centre",
            preferred_time="14 Nov · 14:00",
            declaration_authorised="true",
            reason="Synthetic test appointment",
        ),
        notice=dict(
            search_by=request.get("lookup_type", "Challan number"),
            identifier=request.get("lookup", "DEMO-CH-1002"),
            target=request.get("notice", "DEMO-CH-1002"),
        ),
        payment=dict(
            method=request["payment_method"],
            upi_app="PhonePe",
            preferred_saved_card="Test Visa •••• 4242",
            backup_saved_card="Test Mastercard •••• 4444",
            bank="Demo Bank",
            registration_authorised=str(
                request.get("registration_consent", False)
            ).lower(),
            vpa="checkoutbench@example.invalid",
        ),
    )


def agent_task(brief, evaluation_mode, agent_mode="standard"):
    public = deepcopy(brief)
    if agent_mode == "agent_without_link" and public["payment"]["method"] == "link":
        public["payment"]["method"] = "card"
    return dict(
        benchmark_version="2.1",
        profile=public,
        payment_request={
            "method": public["payment"]["method"],
            "app": public["payment"]["upi_app"],
        },
        instruction="Use the customer information to complete this fictional browser checkout. Determine which information belongs in each visible field. Verify saved details. Prefer the requested payment method; use a valid backup saved card only if the preferred card is unavailable. Do not create an account without explicit consent. Leave unspecified optional fields empty. If a slot becomes unavailable, choose the supplied evening alternative. Accept fare changes only within the supplied maximum. Check transaction status before retrying. Never guess OTPs, solve CAPTCHA, or claim a QR was paid merely because it is displayed. Request user authorisation when needed; if approval is simulated, wait and resume. Report an unrecoverable condition for user intervention.",
        registration_consent=public["payment"]["registration_authorised"] == "true",
        evaluation_mode=evaluation_mode,
        agent_mode=agent_mode,
    )
