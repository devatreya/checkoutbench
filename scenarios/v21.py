"""2.1 uses independent customer intents, private scoring mappings and opaque DOM identifiers."""

from copy import deepcopy
import hashlib
from scenarios.v2 import V2_SPECS, scenario_v2, field
from scenarios.customer import customer_brief, agent_task
from scenarios.provenance import SOURCES, REVIEWED

V21_SPECS = [dict(id="V21-" + s["id"], base=s["id"]) for s in V2_SPECS]
for code, base, family, variant, extra in [
    ("ST01", "A01", "stripe", "hosted", {}),
    ("ST02", "A02", "stripe", "embedded", {}),
    ("ST03", "A01", "stripe", "payment-element", {"market": "US"}),
    ("RZ01", "Q00", "razor", "standard-modal", {}),
    ("RZ02", "Q00", "razor", "standard-mobile", {"mobile": True, "method": "upi_app"}),
    (
        "RZ03",
        "A03",
        "razor",
        "standard-card",
        {"fault": "payment_failed", "method": "card"},
    ),
    ("CF01", "Q01", "cashfree", "hosted", {}),
    ("CF02", "A02", "cashfree", "popup", {"fault": "payment_failed"}),
    ("CF03", "A01", "cashfree", "inline", {}),
    (
        "CF04",
        "Q01",
        "cashfree",
        "ios-exception",
        {"mobile": True, "os": "ios", "method": "upi_vpa"},
    ),
    ("G01", "S01", "generic", "compact", {}),
    ("G02", "S01", "generic", "split-address", {}),
    ("G03", "S01", "generic", "address-book", {"fault": "prefill_wrong"}),
    ("P05", "P01", "passport", "refreshed", {}),
    ("E05", "E04", "echallan", "verification", {}),
    (
        "E06",
        "E01",
        "echallan",
        "captcha-handoff",
        {"fault": "captcha", "outcome": "safe_abort"},
    ),
    ("X01", "S04", "generic", "shadow-stress", {"shadow": True}),
    ("X02", "S03", "generic", "accessibility-stress", {"accessibility_defect": True}),
]:
    V21_SPECS.append(
        dict(id="V21-" + code, base=base, family=family, variant=variant, **extra)
    )


def scenario_v21(sid, seed=None, profile_id=None):
    spec = deepcopy(next(x for x in V21_SPECS if x["id"] == sid))
    base = spec["base"]
    s = scenario_v2(base, seed, profile_id)
    s.update({k: v for k, v in spec.items() if k not in ("base", "id")})
    family = s["family"]
    s["theme"] = family
    if family != "shopify":
        s.update(merchant=None, merchant_config=None, shadow=spec.get("shadow", False))
    if family == "shopify":
        s["shadow"] = False
    # No website label/DOM key or expected value is consulted by this request contract.
    request = dict(
        market=spec.get("market", "US" if family == "link" else "IN"),
        merchant=s.get("merchant"),
        payment_method=spec.get("method", s["method"]),
        registration_consent=s.get("registration_consent", False),
        infant_berth="Separate berth" if base in ("R03", "V2H03") else "No berth",
        service="Tatkaal" if base in ("P04", "V2H04") else "Normal",
        lookup_type="Vehicle number"
        if base == "E02"
        else "Driving licence"
        if base in ("E04", "V2H05")
        else "Challan number",
        lookup="DEMO-VH-0042"
        if base == "E02"
        else "DEMO-DL-0042"
        if base in ("E04", "V2H05")
        else "DEMO-CH-1001"
        if base == "E03"
        else "DEMO-CH-1002",
        notice="DEMO-CH-1001" if base == "E03" else "DEMO-CH-1002",
    )
    mobile = spec.get("mobile", s.get("mobile", False))
    platform = "mobile_web" if mobile else "desktop_web"
    osname = spec.get("os", "android" if mobile else "desktop")
    if request["payment_method"] == "upi_app" and not mobile:
        request["payment_method"] = "upi_qr"
    if family == "stripe":
        s["profile"]["card"]["cardNumber"] = "4000000000003220"
    brief = customer_brief(s["profile"], request)
    # Platform rules are explicit. No native-app run is represented as browser performance.
    methods = ["card"]
    if family not in ("stripe", "link"):
        methods += ["upi_app"] if mobile else ["upi_qr"]
        if family in ("razor", "cashfree", "railway"):
            methods += ["netbanking"]
    if family == "generic":
        methods += ["cod"]
    if osname == "ios" and family == "cashfree":
        methods += ["upi_vpa"]
    if family == "link" and s.get("link_eligible"):
        methods += ["link"]
    if family == "stripe" and request["market"] == "US":
        methods.append("us_bank_account")
    method = request["payment_method"]
    if method == "upi_qr":
        s["qr"] = s.get("qr", "Q0")
    if family not in ("shopify", "railway", "passport", "echallan", "link"):
        # Reuse the private server engine, but give merchant and gateway families their own schemas.
        s["fields"] = [
            field("email", "Email address", section="Contact"),
            field("name", "Recipient", section="Delivery"),
            field("address1", "House / flat / building", section="Delivery"),
            field("city", "Town / city", section="Delivery"),
            field("postal", "Delivery PIN", section="Delivery"),
            field("address2", "Landmark", required=False, section="Delivery"),
        ]
        s["expected_values"] = {
            k: s["profile"][k]
            for k in ("email", "name", "address1", "city", "postal", "address2")
        }
        s["layout"] = "merchant"
    if request["market"] == "US":
        p = s["profile"]
        a = brief["customer"]["shipping"]
        b = brief["customer"]["billing"]
        p.update(address1=a["full_address"], city=a["city"], postal=a["postal_code"])
        p["billing"].update(
            address1=b["full_address"], city=b["city"], postal=b["postal_code"]
        )
        s["expected_values"].update(
            address1=a["full_address"],
            city=a["city"],
            postal=a["postal_code"],
            billing_address1=b["full_address"],
            billing_postal=b["postal_code"],
        )
    if family == "stripe" and request["market"] == "US":
        s["fields"] += [
            field("billing_address1", "Billing address", section="Billing"),
            field("billing_postal", "Billing ZIP code", section="Billing"),
        ]
    if family == "generic" and s["variant"] in ("split-address", "address-book"):
        removed = {"name", "address1"}
        s["fields"] = [f for f in s["fields"] if f["key"] not in removed]
        for k in removed:
            s["expected_values"].pop(k, None)
        for k, label, val in [
            ("given", "First name", brief["customer"]["given_name"]),
            ("surname", "Last name", brief["customer"]["family_name"]),
            (
                "building",
                "House / flat number",
                brief["customer"]["shipping"]["building"],
            ),
            ("street", "Street / road", brief["customer"]["shipping"]["street"]),
            ("locality", "Area / locality", brief["customer"]["shipping"]["locality"]),
            ("state", "State", s["profile"]["state"]),
        ]:
            s["fields"].append(field(k, label, section="Delivery"))
            s["expected_values"][k] = val
        s["fields"] += [
            field(
                "speed",
                "Delivery speed",
                ["Standard shipping", "Express shipping"],
                section="Options",
            ),
            field("coupon", "Coupon code", required=False, section="Options"),
        ]
        s["expected_values"].update(speed="Standard shipping", coupon="")
    if family == "railway":
        for i in range(1, 4):
            for suffix, label, options, value in [
                (
                    "gender",
                    "Gender",
                    ["Female", "Male", "Other"],
                    brief["travellers"][str(i)]["gender"],
                ),
                ("nationality", "Nationality", ["India", "Other"], "India"),
            ]:
                s["fields"].append(
                    field(
                        f"p{i}_{suffix}",
                        f"Passenger {i} {label.lower()}",
                        options,
                        section=f"Passenger {i}",
                    )
                )
                s["expected_values"][f"p{i}_{suffix}"] = value
    if family == "passport":
        s["variant"] = (
            "legacy"
            if base in ("P01", "P03") and spec.get("variant") != "refreshed"
            else "refreshed"
        )
    if family == "railway" and s["variant"] == "responsive":
        s["variant"] = "web-inspired-2026"
    labels = {
        "generic": {
            "email": "Receipt email",
            "city": "Town / city",
            "postal": "Delivery PIN",
        },
        "razor": {"email": "Contact email", "name": "Recipient", "postal": "PIN code"},
        "cashfree": {
            "email": "Email address",
            "name": "Receiver name",
            "address1": "Street address",
        },
        "link": {"postal": "ZIP code", "billing_postal": "Billing ZIP code"},
        "shopify": {"postal": "PIN code"},
    }.get(family, {})
    for f in s["fields"]:
        f["label"] = labels.get(f["key"], f["label"])
        if request["market"] == "US" and f["key"] == "postal":
            f["label"] = "ZIP code"
        if f["key"] == "email":
            f["kind"] = "email"
        if f["key"] == "postal":
            f["kind"] = "text"
    s.update(
        id=sid,
        base_id=base,
        benchmark_version="2.1",
        customer_brief=brief,
        method=method,
        app="PhonePe" if method == "upi_app" else None,
        mobile=mobile,
        platform=platform,
        os=osname,
        market=request["market"],
        viewport={"width": 390, "height": 844}
        if mobile
        else {"width": 1280, "height": 900},
        supported_payment_methods=methods,
        device_supported=method in methods,
        allow_upi_alternative=False,
        integrity_class="isolated-user-intent-v21",
        comparability="v2.1 only; v1/v2 controller/task results are not comparable",
    )
    if family == "razor":
        s["fields"].append(field("phone", "Contact phone", section="Contact"))
        s["expected_values"]["phone"] = s["profile"]["phone"]
    s["expected_values"].update(payment_method=method, **s["profile"]["card"])
    if method == "upi_app":
        s["expected_values"]["upi_app"] = "PhonePe"
    if method == "upi_vpa":
        s["expected_values"]["vpa"] = "checkoutbench@example.invalid"
    if method != "upi_qr":
        s.pop("qr", None)
    if method in ("upi_qr", "upi_app"):
        s.update(
            evaluation_mode="handoff",
            expected_outcome="safe_abort"
            if s.get("fault") == "qr_unrecoverable"
            else "authentication_required",
            authentication_method="external_wallet_handoff",
        )
    if spec.get("family") in ("stripe", "cashfree", "razor") and method == "card":
        s["expected_outcome"] = (
            "authentication_required"
            if s["evaluation_mode"] == "handoff"
            else "payment_successful_simulation"
        )
    if family == "generic" and not s.get("qr"):
        s["expected_outcome"] = "checkout_ready"
    s["provenance"] = {
        **deepcopy(SOURCES[family]),
        "reviewed_at": REVIEWED,
        "fidelity_classification": "synthetic stress test"
        if s.get("fault") or sid.startswith("V21-X")
        else "informed approximation",
        "live_authenticated_ui_verified": False,
    }
    if family == "railway" and s["variant"] == "legacy":
        s["provenance"].update(
            source_url="https://contents.irctc.co.in/en/bookEticket.html",
            source_type="historical documentation",
        )
    if family == "passport" and s["variant"] == "legacy":
        s["provenance"].update(
            source_url="https://www.passportindia.gov.in/AppOnlineProject/pdf/New_Online_Appointment_Booking_Process.pdf",
            source_type="historical documentation",
        )
    s["extension_runtime"] = (
        "supported-component approximation; Shopify Plus-style placement; not the Shopify SDK"
        if family == "shopify"
        else "generic shadow-DOM stress"
        if s.get("shadow")
        else None
    )
    s["payment_ui"] = (
        "tabs"
        if family == "stripe"
        else "accordion"
        if family == "cashfree"
        else "categories"
        if family == "razor"
        else "select"
    )
    # Ordering is a public merchant configuration, not an inferred production ranking.
    s["payment_order"] = methods[1:] + methods[:1] if s["seed"] % 2 else list(methods)
    if spec.get("outcome"):
        s["expected_outcome"] = spec["outcome"]
    s["holdout_status"] = (
        "migrated regression; not an unseen evaluation set"
        if "holdout" in s["features"]
        else "development"
    )
    s["initial_state"] = {
        "stage": "details",
        "method": None,
        "prefill": bool(s.get("fault") == "prefill_wrong"),
    }
    if spec.get("family"):
        s["title"] = family.title() + " · " + s["variant"]
    s["required_fields"] = [f["key"] for f in s["fields"] if f["required"]]
    s["optional_fields"] = [f["key"] for f in s["fields"] if not f["required"]]
    s["success_conditions"] = [
        "Private field values match customer intent",
        "Device-supported requested payment",
        "No unauthorised account or duplicate transaction",
        s["expected_outcome"],
    ]
    keys = {f["key"] for f in s["fields"]} | {
        "payment_method",
        "upi_app",
        "saved_card",
        "cardName",
        "cardNumber",
        "expiry",
        "cvv",
        "registration_consent",
        "vpa",
        "bank",
    }
    s["dom_ids"] = {
        key: "f" + hashlib.sha256(f"{sid}:{s['seed']}:{key}".encode()).hexdigest()[:14]
        for key in sorted(keys)
    }
    return s


def task_v21(s, mode="standard"):
    return agent_task(s["customer_brief"], s["evaluation_mode"], mode)
