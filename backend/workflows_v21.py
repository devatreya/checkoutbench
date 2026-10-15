"""Versioned facade: private semantic keys never cross the fixture boundary."""

from copy import deepcopy
import re, time
from fastapi import HTTPException
from backend import workflows as old
from backend.authentication import new_auth
from backend.evaluator.v2 import evaluate_v2


def init(s, mode="standard"):
    st = old.init(s, mode)
    st.update(
        accelerated_authenticated=False,
        gateway_open=False,
        gateway_launched=False,
        return_verified=False,
        provider_status="not_started",
        merchant_stage="address",
        saved_passenger_used=False,
        passport_step="application",
    )
    if s.get("layout") == "express" and s["family"] == "shopify":
        st["values"] = {}
        st["autofilled"] = {}
    if s.get("research_autofill"):
        st["values"].update(
            {
                k: v
                for k, v in s["expected_values"].items()
                if k in {f["key"] for f in s["fields"]}
            }
        )
        if s["research_autofill"] == "stale":
            st["values"].update(name="Old Demo Recipient", postal="999999")
        st["autofilled"] = deepcopy(st["values"])
    return st


def public(st, token):
    s = st["scenario"]
    d = old.public(st, token)
    ids = s["dom_ids"]

    def convert(f):
        row = {k: v for k, v in f.items() if k not in ("key", "when")}
        row["key"] = ids[f["key"]]
        if f.get("when"):
            row["when"] = {ids[k]: v for k, v in f["when"].items()}
        return row

    fs = d["fields"]
    if (
        s["family"] == "passport"
        and s["variant"] == "refreshed"
        and st["stage"] == "details"
    ):
        fs = [
            f
            for f in fs
            if (f["key"] in ("application", "scheme", "urgent_reason"))
            == (st["passport_step"] == "application")
        ]
    if s["family"] == "shopify" and s.get("layout") == "three-page":
        sections = (
            {"contact", "delivery", "billing"}
            if st["stage"] == "details"
            else {"shipping"}
            if st["stage"] == "shipping"
            else set()
        )
        fs = [f for f in fs if f.get("section") in sections]
    elif st["stage"] not in ("details", "shipping", "review"):
        fs = []
    d["fields"] = [convert(f) for f in fs]
    d["values"] = {ids[k]: v for k, v in st["values"].items() if k in ids}
    d.pop("completed_stages", None)
    d.pop("booking_reference", None)
    if s["family"] != "passport":
        d.pop("application_summary", None)
    d.update(
        version="2.1",
        research_density=s.get("research_density"),
        platform=s["platform"],
        os=s["os"],
        market="US / USD · Link unavailable in India"
        if s["family"] == "link"
        else "US / USD"
        if s.get("market") == "US"
        else "India / INR",
        methods=s["supported_payment_methods"],
        selected_method=st["values"].get("payment_method", ""),
        accelerated_authenticated=st["accelerated_authenticated"],
        gateway_open=st["gateway_open"],
        gateway_launched=st["gateway_launched"],
        provider_status=st["provider_status"],
        merchant_stage=st["merchant_stage"],
        saved_passenger_used=st["saved_passenger_used"],
        extension_runtime=s["extension_runtime"],
        accessibility_defect=s.get("accessibility_defect", False),
        auth_kind=s["authentication_method"],
        payment_ui=s["payment_ui"],
        payment_order=s["payment_order"],
        passport_step=st["passport_step"],
        provider_contact={
            label: st["values"].get(k, "")
            for label, k in [("Name", "name"), ("Email", "email"), ("Phone", "phone")]
        },
    )

    # Payment keys are opaque too. Labels/choices are website-visible facts, not profile mappings.
    def pf(k, label, kind="text", options=None):
        return dict(key=ids[k], label=label, kind=kind, required=True, options=options)

    d["payment_fields"] = [
        pf("cardName", "Cardholder name"),
        pf("cardNumber", "Card number"),
        pf("expiry", "Expiry (MM/YY)"),
        pf("cvv", "Security code"),
    ]
    d["method_control"] = pf(
        "payment_method", "Payment method", "select", s["supported_payment_methods"]
    )
    d["app_control"] = pf(
        "upi_app",
        "UPI application",
        "select",
        ["PhonePe", "Google Pay", "BHIM", "Paytm"],
    )
    d["bank_control"] = pf("bank", "Bank", "select", ["Demo Bank", "Sample Bank"])
    d["vpa_control"] = pf("vpa", "Legacy UPI ID (iOS exception)")
    d["consent_control"] = pf(
        "registration_consent", "Create a Link account and save my details", "checkbox"
    )
    d["saved_control"] = pf("saved_card", "Saved payment method", "select", d["cards"])
    d["qr_url"] = (
        f"/v21/{token}/qr?generation={st['qr_generation']}" if st["qr"] else None
    )
    return d


def transition(st, action, data, token):
    s = st["scenario"]
    reverse = {v: k for k, v in s["dom_ids"].items()}
    # Reject raw semantic keys, not merely ignore them.
    if any(k not in reverse for k in data.get("values", {})):
        raise HTTPException(400, "Unknown control identifier")
    translated = {
        **data,
        "values": {reverse[k]: v for k, v in data.get("values", {}).items()},
    }
    old.touch(st, translated)
    for k in ("bank", "vpa"):
        if k in translated["values"]:
            st["values"][k] = str(translated["values"][k])[:300]
    if (
        action == "application_next"
        and s["family"] == "passport"
        and st["stage"] == "details"
    ):
        actual = st["scenario"]
        st["scenario"] = {
            **actual,
            "fields": [
                f
                for f in actual["fields"]
                if f["key"] in ("application", "scheme", "urgent_reason")
            ],
        }
        try:
            if old.validate_details(st):
                st["passport_step"] = "appointment"
        finally:
            st["scenario"] = actual
        return
    if (
        action == "saved_passenger"
        and st["stage"] == "details"
        and s["family"] == "railway"
    ):
        p = s["customer_brief"]["travellers"]["1"]
        st["values"].update(
            p1_name=p["full_name"],
            p1_age=p["age"],
            p1_gender=p["gender"],
            p1_nationality=p["nationality"],
            p1_berth=p["berth"],
        )
        st["saved_passenger_used"] = True
        old.event(st, "native_saved_passenger")
        return
    if (
        action == "request_auth"
        and st["auth"]
        and st["auth"]["purpose"] == "accelerated"
    ):
        st["auth"]["requested"] = True
        st["auth"]["reported"] = True
        st["handoffs"] += 1
        return
    if (
        action == "accelerated_login"
        and st["stage"] == "details"
        and s.get("layout") == "express"
    ):
        old.begin_auth(st, "accelerated")
        return
    if (
        action == "return_auth"
        and st["auth"]
        and st["auth"]["purpose"] == "accelerated"
        and st["auth"]["status"] == "approved"
    ):
        st["auth"] = None
        st["stage"] = "details"
        st["accelerated_authenticated"] = True
        saved = {
            f["key"]: s["profile"][f["key"]]
            for f in s["fields"]
            if isinstance(s["profile"].get(f["key"]), str)
        }
        st["values"].update(saved)
        st["autofilled"].update(saved)
        old.event(st, "native_accelerated_autofill")
        return
    if action == "launch" and st["stage"] == "payment":
        st["gateway_open"] = True
        st["gateway_launched"] = True
        st["provider_status"] = "session_created"
        old.event(st, "provider_session_created")
        return
    if action == "dismiss" and st["stage"] == "payment":
        st["gateway_open"] = False
        old.event(st, "gateway_dismissed")
        return
    if action in ("continue", "address_next", "pay") and s["family"] == "generic":
        postal = st["values"].get("postal", "")
        if postal not in ("560038", "411001", "380001"):
            old.issue(
                st,
                "serviceability",
                "This fictional store delivers only to PIN 560038, 411001 and 380001.",
            )
            return
        if st["values"].get("coupon", "") not in ("", "WELCOME10"):
            old.issue(
                st, "coupon", "Coupon not recognised. Remove it or use WELCOME10."
            )
            return
    if (
        action == "address_next"
        and s["family"] == "generic"
        and st["stage"] == "details"
    ):
        actual = st["scenario"]
        st["scenario"] = {
            **actual,
            "fields": [f for f in actual["fields"] if f.get("section") != "Options"],
        }
        try:
            if old.validate_details(st):
                st["merchant_stage"] = "delivery"
        finally:
            st["scenario"] = actual
        return
    if action == "check_status" and st["stage"] == "verification":
        st["stage"] = "ledger"
        old.event(st, "transaction_verification_opened")
        old.transition(st, "check_status", translated, token)
        return
    if action == "open_verification" and st["stage"] == "ledger":
        st["stage"] = "verification"
        return
    if action == "report_challenge" and st["stage"] == "captcha":
        old.issue(st, "captcha", "Mock CAPTCHA requires user intervention.")
        action = "help"
    if (
        action == "continue"
        and s["family"] == "shopify"
        and s.get("layout") == "three-page"
        and st["stage"] == "shipping"
    ):
        if old.validate_details(st):
            st["stage"] = "payment"
            st["completed_stages"] += ["details", "review"]
        return
    if (
        action in ("show_qr", "qr_refresh", "qr_enlarge", "qr_fullsize")
        and s["family"] == "shopify"
        and st["stage"] == "details"
        and s["layout"] in ("one-page", "express")
    ):
        st["stage"] = "payment"
        try:
            _legacy(st, action, translated, token)
        finally:
            st["stage"] = "details"
        return
    if action == "pay":
        selected = st["values"].get("payment_method")
        if selected not in s["supported_payment_methods"]:
            old.issue(st, "payment", "Payment method is unavailable on this device.")
            return
        if (
            s["family"] == "shopify"
            and s.get("layout") in ("one-page", "express")
            and st["stage"] == "details"
        ):
            if s.get("layout") == "express" and not st["accelerated_authenticated"]:
                old.issue(
                    st,
                    "auth",
                    "Authenticate the accelerated session before continuing.",
                )
                return
            # Reuse business validation and retryable slot checks, without displaying an artificial review page.
            _legacy(st, "continue", translated, token)
            if st["stage"] != "review":
                return
            st["stage"] = "payment"
            st["completed_stages"].append("review")
        if selected == "card":
            number = re.sub(r"\s", "", st["values"].get("cardNumber", ""))
            expiry = st["values"].get("expiry", "")
            code = st["values"].get("cvv", "")
            if (
                not re.fullmatch(r"\d{13,19}", number)
                or not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", expiry)
                or not re.fullmatch(r"\d{3,4}", code)
            ):
                old.issue(
                    st,
                    "card_format",
                    "Check card number, expiry MM/YY and security code.",
                )
                return
        if selected == "us_bank_account":
            st["attempts"] += 1
            old.begin_auth(st, "external_bank")
            return
        if selected in ("netbanking", "cod", "upi_vpa"):
            if selected == "netbanking" and st["values"].get("bank") != "Demo Bank":
                old.issue(st, "bank", "Choose a bank.")
                return
            if (
                selected == "upi_vpa"
                and st["values"].get("vpa") != "checkoutbench@example.invalid"
            ):
                old.issue(st, "vpa", "Use the supplied synthetic VPA.")
                return
            st["completed_stages"].append("payment_prepared")
            st["stage"] = "checkout_ready"
            return
        if selected in ("upi_qr", "upi_app"):
            _legacy(st, action, translated, token)
            if st["stage"] == "gateway":
                old.begin_auth(st, "external_wallet")
            return
    if (
        action == "return_auth"
        and st["auth"]
        and st["auth"]["purpose"] == "external_wallet"
    ):
        # This suite uses handoff mode for QR; payment completion is never inferred from decoding.
        raise HTTPException(
            409, "External wallet approval is outside this handoff task"
        )
    _legacy(st, action, translated, token)
    if action == "return_auth" and st["stage"] == "gateway_return":
        st["provider_status"] = "callback_received"
        channel = (
            "handler_callback"
            if s["family"] == "razor"
            else "popup_result"
            if s["variant"] == "popup"
            else "inline_result"
            if s["variant"] == "inline"
            else "redirect_return"
        )
        old.event(
            st,
            "provider_result_received",
            channel=channel,
            cryptographic_signature="not simulated",
        )
    if action == "finish" and st["stage"] == "payment_successful_simulation":
        st["return_verified"] = True
        st["provider_status"] = "verified_success"
        old.event(st, "server_status_verified")


def _legacy(st, action, data, token):
    # Historical workflow branch identifiers remain inside the private server.
    actual = st["scenario"]
    working = {**actual, "id": actual["base_id"]}
    st["scenario"] = working
    try:
        old.transition(st, action, data, token)
    finally:
        st["scenario"] = actual


def evaluate(s, st):
    result = evaluate_v2({**s, "id": s["base_id"]}, st)
    if (
        not s["device_supported"]
        or st["values"].get("payment_method") not in s["supported_payment_methods"]
        and st["attempts"]
    ):
        result.update(success=False, failure_reason="unsupported_device_payment")
    if (
        result["success"]
        and s["expected_outcome"] == "payment_successful_simulation"
        and not st["return_verified"]
    ):
        result.update(success=False, failure_reason="unverified_transaction")
    if s.get("qr"):
        result["qr_stage_metrics"] = dict(
            generated=bool(st["qr"]),
            visual_identification="not_inferred",
            independently_decoded=bool(
                st["qr"] and st["qr"]["report"]["decoder_success"]
            ),
            independently_valid=bool(
                st["qr"]
                and st["qr"]["report"]["decoder_success"]
                and st["qr"]["expires"] > time.monotonic()
            ),
            prepared="payment_prepared" in st["completed_stages"],
            user_handoff=st["reported_handoff"],
            payment_completed=False,
        )
    return result


def tick_test_user(st):
    before = (st.get("auth") or {}).get("status")
    a = st["auth"]
    if a and a["purpose"] == "accelerated":
        actual = st["scenario"]
        st["scenario"] = {**actual, "evaluation_mode": "simulated_completion"}
        try:
            old.tick_test_user(st)
        finally:
            st["scenario"] = actual
    else:
        old.tick_test_user(st)
    after = (st.get("auth") or {}).get("status")
    if after != before and st.get("research_run_id"):
        from backend.research.measurement import observe

        observe(st["scenario"], st, "synthetic_auth_" + str(after), "user")
