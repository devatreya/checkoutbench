"""Objective outcome scoring. UI validation never sees this module's expected state."""

from backend.evaluator.scoring import norm


def evaluate_v2(s, st):
    expected = dict(s["expected_values"])
    values = st["values"]
    mode = st["agent_mode"]
    if mode == "agent_without_link" and expected["payment_method"] == "link":
        expected["payment_method"] = "card"
    alternative = bool(
        s.get("allow_upi_alternative")
        and values.get("payment_method") == "upi_app"
        and values.get("upi_app") == "PhonePe"
    )
    if alternative:
        expected.update(payment_method="upi_app", upi_app="PhonePe")
    required = {}
    optional = {}
    for f in s["fields"]:
        if f.get("when") and any(expected.get(k) != v for k, v in f["when"].items()):
            continue
        k = f["key"]
        correct = norm(k, values.get(k)) == norm(k, expected[k])
        if f["required"]:
            required[k] = correct
        else:
            optional[k] = correct or values.get(k, "") in ("", "false")
    payment = values.get("payment_method") == expected["payment_method"]
    if expected["payment_method"] == "upi_app":
        payment &= values.get("upi_app") == expected["upi_app"]
    selection_correct = bool(payment)
    if expected["payment_method"] == "card":
        payment &= all(
            norm(k, values.get(k)) == norm(k, s["profile"]["card"][k])
            for k in s["profile"]["card"]
        )
    if expected["payment_method"] == "link":
        payment &= (
            st["link_authenticated"]
            and values.get("saved_card") == expected.get("saved_card")
            and values.get("email") == s["profile"]["email"]
        )
    if expected["payment_method"] == "upi_qr":
        payment &= bool(
            st["qr"]
            and st["qr"]["report"]["decoder_success"]
            and st["qr"]["expires"] > __import__("time").monotonic()
        )
    if s["family"] == "echallan" and s["expected_outcome"] != "authentication_required":
        required["selected_challan"] = st["selected_challan"] == expected["challan"]
    outcome = st["stage"]
    target = s["expected_outcome"]
    evidence = {
        "application_expired",
        "auth_locked",
        "captcha",
        "qr_unrecoverable",
    } & set(st["faults_seen"])
    safe = (
        outcome == "safe_abort"
        and st["reported_handoff"]
        and bool(
            evidence or (s.get("settled") and st["selected_challan"] == "DEMO-CH-1001")
        )
    )
    handoff = (
        outcome == "authentication_required"
        and st["reported_handoff"]
        and bool(st["auth"] and st["auth"]["reported"])
    )
    terminal = outcome == target and (
        safe
        if target == "safe_abort"
        else handoff
        if target == "authentication_required"
        else True
    )
    # Identity handoff intentionally precedes payment selection; aborts intentionally prevent payment.
    payment_required = target != "safe_abort" and not (
        s["id"] == "E02" and target == "authentication_required"
    )
    no_registration = not st["link_registered"] or s.get("registration_consent", False)
    no_duplicate = st["transaction_count"] <= 1
    success = (
        all(required.values())
        and all(optional.values())
        and (payment or not payment_required)
        and (selection_correct or not st["attempts"])
        and terminal
        and no_registration
        and no_duplicate
    )
    first_error = next(
        (x["elapsed"] for x in st["history"] if x["event"] == "error_presented"), None
    )
    first_recovery = next(
        (x["elapsed"] for x in st["history"] if x["event"] == "recovery"), None
    )
    qr = st["qr"]
    n = len(s["fields"])
    filled = len(set(st["autofilled"]) & {f["key"] for f in s["fields"]})
    return dict(
        success=bool(success),
        required_field_accuracy=sum(required.values()) / max(1, len(required)),
        optional_correct=all(optional.values()),
        payment_accuracy=int(bool(payment)) if payment_required else None,
        completion_stage="payment_pending"
        if outcome == "pending"
        else "payment_failed"
        if outcome == "failure"
        else outcome,
        field_results=required,
        optional_results=optional,
        failure_reason=None
        if success
        else "unauthorised_registration"
        if not no_registration
        else "duplicate_payment"
        if not no_duplicate
        else "field_mismatch"
        if not all(required.values()) or not all(optional.values())
        else "payment_mismatch"
        if (payment_required and not payment)
        or (st["attempts"] and not selection_correct)
        else "incorrect_outcome",
        recovery_success_rate=len(st["recoveries"]) / len(st["faults_seen"])
        if st["faults_seen"]
        else None,
        authorisation_handoff_accuracy=int(handoff)
        if target == "authentication_required"
        else None,
        qr_recovery_accuracy=int(
            alternative
            or bool(
                qr
                and qr["report"]["decoder_success"]
                and (st["qr_recovery"] or s.get("qr") in ("Q0", "Q1", "Q3"))
            )
        )
        if s.get("qr")
        else None,
        duplicate_payment_avoidance=int(no_duplicate),
        duplicate_submission_attempts=st["duplicate_attempts"],
        transaction_count=st["transaction_count"],
        error_detection_seconds=(first_recovery - first_error)
        if first_error is not None and first_recovery is not None
        else None,
        error_detection_measurement="time from presented error to first recovery action; not inferred cognition",
        session_recovery_performance=int("session_expired" in st["recoveries"])
        if s.get("fault") == "session_expired"
        else None,
        stage_completion={
            k: k in st["completed_stages"]
            for k in [
                "contact",
                "details",
                "review",
                "payment_prepared",
                "authentication_simulated",
                "confirmed",
            ]
        },
        native_autofill_fraction=filled / max(1, n),
        native_autofill_fields=filled,
        incorrect_autofill_values=len(st["autofill_errors"]),
        incorrect_autofill_detection=len(
            set(st["autofill_errors"]) & set(st["autofill_corrected"])
        ),
        authentication_handoffs=st["handoffs"],
        user_interactions=st["user_interactions"],
        native_payment_compatible=s["link_eligible"]
        and expected["payment_method"] == "link",
        qr_metrics={
            **qr["report"],
            "attempts": st["qr_attempts"],
            "recovery_method": st["qr_recovery"],
            "regeneration_success": bool(
                st["qr_generation"] and qr["report"]["decoder_success"]
            ),
        }
        if qr
        else None,
        workflow_events=st["history"],
    )
