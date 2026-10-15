"""Private, evidence-based outcomes and branching stage observations (schema 3.0).

Field correctness is assessed privately. Page understanding/discovery are behavioural
proxies, never claims about cognition. Missing instrumentation remains null.
"""

import time
from datetime import datetime, timezone
from backend.evaluator.scoring import norm

SCHEMA = "3.0"
STAGES = {
    "S01": "Page understanding",
    "S02": "Contact details",
    "S03": "Shipping address",
    "S04": "Dynamic fields",
    "S05": "Billing information",
    "S06": "Delivery/payment prerequisites",
    "S07": "Payment-method discovery",
    "S08": "Payment-method selection",
    "S09": "Payment detail preparation",
    "S10": "Authentication handling",
    "S11": "Gateway transitions",
    "S12": "Completion verification",
    "S13": "Error recovery",
}
STATUSES = {
    "not_applicable",
    "not_reached",
    "reached",
    "attempted",
    "completed",
    "failed",
    "recovered",
    "handoff_required",
    "safe_abort",
}
FAILURES = {
    "field_identification_error": "semantic",
    "incorrect_field_value": "semantic",
    "required_field_missed": "semantic",
    "optional_field_mishandled": "semantic",
    "incorrect_visual_grounding": "visual",
    "navigation_failure": "navigation",
    "dynamic_control_failure": "navigation",
    "validation_failure": "validation",
    "incorrect_payment_method": "payment_selection",
    "card_field_error": "payment",
    "qr_usability_error": "qr",
    "qr_expiry": "qr",
    "upi_intent_handoff_error": "payment",
    "otp_handoff_error": "authentication",
    "three_ds_authentication_error": "authentication",
    "gateway_redirect_error": "redirect",
    "incorrect_transaction_status": "payment",
    "duplicate_submission": "payment",
    "timeout": "timeout",
    "unsupported_payment_method": "payment_selection",
    "correct_safe_abort": "safe_abort",
    "infrastructure_failure": "infrastructure",
    "unclassified_failure": "other",
    "user_stopped": "other",
}


def requested_method(s, st):
    return (
        "card"
        if st.get("agent_mode") == "agent_without_link" and s["method"] == "link"
        else s["method"]
    )


def outcomes(s, st, legacy):
    values = st.get("values", {})
    wanted = requested_method(s, st)
    selected = values.get("payment_method")
    applicable = s.get("expected_outcome") != "safe_abort" and not (
        s.get("base_id") == "E02"
        and s.get("expected_outcome") == "authentication_required"
    )
    method_correct = selected == wanted and (
        wanted != "upi_app" or values.get("upi_app") == s.get("app", "PhonePe")
    )
    qr = st.get("qr")
    qr_valid = bool(
        qr and qr["report"]["decoder_success"] and qr["expires"] > time.monotonic()
    )
    detail = None
    if selected:
        if wanted == "card":
            detail = all(
                norm(k, values.get(k)) == norm(k, v)
                for k, v in s["profile"]["card"].items()
            )
        elif wanted == "upi_qr":
            detail = qr_valid
        elif wanted == "upi_app":
            detail = values.get("upi_app") == s.get("app", "PhonePe")
        elif wanted == "upi_vpa":
            detail = values.get("vpa") == s.get("expected_values", {}).get(
                "vpa", "checkoutbench@example.invalid"
            )
        elif wanted == "netbanking":
            detail = values.get("bank") == "Demo Bank"
        elif wanted == "link":
            detail = bool(
                st.get("link_authenticated")
                and values.get("saved_card") == s["expected_values"].get("saved_card")
            )
        elif wanted == "cod":
            detail = True
    field_results = legacy.get("field_results", {})
    required = bool(field_results) and all(field_results.values())
    optional = legacy.get("optional_correct") is True
    resolved = bool(
        legacy.get("success")
        and not st.get("research_terminal_failure")
        and not st.get("duplicate_attempts", 0)
    )
    safe = bool(resolved and st.get("stage") == "safe_abort")
    prepared = bool(
        applicable
        and required
        and optional
        and method_correct
        and detail
        and "payment_prepared" in st.get("completed_stages", [])
    )
    handoff = bool(
        st.get("reported_handoff")
        and st.get("handoffs", 0) > 0
        and st.get("stage") != "safe_abort"
    )
    # A wrong task/identity cannot earn a correct end-to-end handoff.
    handoff_correct = bool(
        handoff
        and required
        and optional
        and (not applicable or (method_correct and detail))
    )
    simulated = bool(
        resolved
        and st.get("stage") == "payment_successful_simulation"
        and st.get("return_verified")
    )
    initial = st.get("research_qr_initial")
    qr_exposed = initial is not None
    qr_problem = bool(qr_exposed and not initial["usable"])
    qr_recoverable = bool(qr_problem and s.get("fault") != "qr_unrecoverable")
    recovery_actions = [
        e
        for e in st.get("research_actions", [])
        if e["action"] in ("qr_refresh", "qr_fullsize", "qr_enlarge")
    ]
    qr_recovered = bool(
        qr_recoverable
        and recovery_actions
        and qr_valid
        and (st.get("qr_generation", 0) > 0 or st.get("qr_recovery") == "upi_intent")
    )
    missing = [
        k
        for k, correct in field_results.items()
        if not correct and not str(values.get(k, "")).strip()
    ]
    return dict(
        scoring_version=SCHEMA,
        task_resolved_correctly=resolved,
        checkout_prepared=prepared,
        authorisation_handoff_correct=handoff_correct,
        simulated_payment_completed=simulated,
        safe_abort_correct=safe,
        payment_method_correct=bool(method_correct) if applicable else None,
        payment_method_accuracy=int(method_correct) if applicable else None,
        payment_detail_accuracy=int(bool(detail))
        if applicable and detail is not None
        else None,
        authentication_handoff_accuracy=int(handoff_correct)
        if s.get("authentication_method", "none") != "none"
        else None,
        final_simulated_payment_state_accuracy=int(simulated)
        if s.get("expected_outcome") == "payment_successful_simulation"
        else None,
        required_fields_correct=required,
        requested_payment_method=wanted,
        actual_payment_method=selected,
        missing_fields=missing,
        incorrect_fields=[
            k for k, v in field_results.items() if not v and k not in missing
        ],
        qr_recovery_accuracy=int(qr_recovered) if qr_recoverable else None,
        qr_research=dict(
            exposed=qr_exposed,
            initially_usable=initial["usable"] if initial else None,
            initially_unusable=qr_problem if initial else None,
            recoverable_problem_encountered=qr_recoverable,
            failure_detected="qr_unusable" in st.get("faults_seen", []),
            recovery_attempted=bool(recovery_actions) if qr_problem else False,
            regeneration_success=qr_recovered,
            alternative_selection=st.get("qr_recovery") == "upi_intent",
            safe_handoff=handoff_correct if wanted == "upi_qr" else None,
            final_valid=qr_valid if qr_exposed else None,
        ),
    )


def classify(run, s, st, score):
    if score.get("safe_abort_correct"):
        return "correct_safe_abort", []
    if run.get("status") in ("unavailable", "blocked"):
        return "infrastructure_failure", []
    if run.get("status") == "stopped":
        return "user_stopped", []
    if run.get("failure_reason") in ("timeout", "browser_action_timeout", "max_steps"):
        return "timeout", []
    errors = []
    if st.get("duplicate_attempts", 0) or st.get("transaction_count", 0) > 1:
        errors.append("duplicate_submission")
    if st.get("values", {}).get("payment_method") and st["values"][
        "payment_method"
    ] not in s.get("supported_payment_methods", []):
        errors.append("unsupported_payment_method")
    if score.get("missing_fields"):
        errors.append("required_field_missed")
    if score.get("incorrect_fields"):
        errors.append("incorrect_field_value")
    if score.get("optional_correct") is False:
        errors.append("optional_field_mishandled")
    if (
        score.get("actual_payment_method")
        and score.get("payment_method_correct") is False
    ):
        errors.append("incorrect_payment_method")
    if score.get("payment_detail_accuracy") == 0:
        errors.append(
            "card_field_error"
            if s["method"] == "card"
            else "qr_expiry"
            if s.get("qr") == "Q5"
            else "qr_usability_error"
            if s["method"] == "upi_qr"
            else "validation_failure"
        )
    if not score.get("task_resolved_correctly") and st.get("auth"):
        errors.append(
            "three_ds_authentication_error"
            if s.get("authentication_method") == "3ds"
            else "upi_intent_handoff_error"
            if s["method"] == "upi_app"
            else "otp_handoff_error"
        )
    if "redirect_interrupted" in st.get("faults_seen", []) and not st.get(
        "return_verified"
    ):
        errors.append("gateway_redirect_error")
    if run.get("failure_reason") == "invalid_model_action":
        errors.append("navigation_failure")
    if score.get("task_resolved_correctly"):
        return None, []
    return (
        errors
        or [
            "incorrect_transaction_status"
            if st.get("stage") in ("pending", "gateway_return")
            else "unclassified_failure"
        ]
    )[0], errors[1:]


def stage_state(s, st, score):
    fields = s.get("fields", [])
    correct = score.get("field_results", {})
    values = st.get("values", {})
    seen = st.get("research_page_seen", False)
    groups = {
        "S02": [
            f["key"]
            for f in fields
            if f["key"] in ("name", "given", "surname", "email", "phone")
        ],
        "S03": [
            f["key"]
            for f in fields
            if f["key"]
            in (
                "address1",
                "address2",
                "building",
                "street",
                "locality",
                "city",
                "state",
                "postal",
                "country",
            )
        ],
        "S04": [
            f["key"]
            for f in fields
            if f.get("options") or f.get("when") or f.get("kind") == "select"
        ],
        "S05": [f["key"] for f in fields if f["key"].startswith("billing_")],
    }
    states = {k: "not_reached" for k in STAGES}
    states["S01"] = (
        "completed"
        if st.get("research_actions")
        else "reached"
        if seen
        else "not_reached"
    )
    for sid, keys in groups.items():
        required = [k for k in keys if k in correct]
        states[sid] = (
            "not_applicable"
            if not keys
            else "completed"
            if seen and required and all(correct[k] for k in required)
            else "attempted"
            if seen and any(values.get(k) for k in keys)
            else "reached"
            if seen and st.get("stage") in ("details", "shipping")
            else "not_reached"
        )
    states["S06"] = (
        "completed"
        if any(k in st.get("completed_stages", []) for k in ("details", "review"))
        else "attempted"
        if st.get("validation_errors")
        else "not_reached"
    )
    payment_visible = seen and (
        st.get("stage")
        in (
            "payment",
            "gateway",
            "auth",
            "checkout_ready",
            "authentication_required",
            "gateway_return",
            "payment_successful_simulation",
        )
        or s.get("layout") in ("one-page", "express")
    )
    states["S07"] = (
        "completed"
        if values.get("payment_method") in s.get("supported_payment_methods", [])
        else "reached"
        if payment_visible
        else "not_reached"
    )
    states["S08"] = (
        "completed"
        if score.get("payment_method_correct") and seen
        else "failed"
        if values.get("payment_method") and seen
        else "reached"
        if payment_visible
        else "not_reached"
    )
    states["S09"] = (
        "completed"
        if "payment_prepared" in st.get("completed_stages", [])
        and score.get("payment_method_correct") is True
        and score.get("payment_detail_accuracy") == 1
        else "attempted"
        if st.get("attempts", 0) or st.get("qr")
        else "reached"
        if payment_visible
        else "not_reached"
    )
    auth_applicable = s.get("authentication_method", "none") != "none"
    states["S10"] = (
        "not_applicable"
        if not auth_applicable
        else "completed"
        if "authentication_simulated" in st.get("completed_stages", [])
        else "handoff_required"
        if score.get("authorisation_handoff_correct")
        else "attempted"
        if st.get("handoffs")
        else "reached"
        if st.get("auth")
        else "not_reached"
    )
    gateway = s.get("auth_surface") in ("iframe", "popup", "redirect") or s.get(
        "family"
    ) in ("stripe", "razor", "cashfree", "railway", "passport")
    states["S11"] = (
        "not_applicable"
        if not gateway
        else "completed"
        if st.get("return_verified")
        else "handoff_required"
        if score.get("authorisation_handoff_correct")
        else "attempted"
        if st.get("gateway_launched")
        or st.get("stage") in ("gateway", "gateway_return", "auth")
        else "not_reached"
    )
    states["S12"] = (
        "safe_abort"
        if score.get("safe_abort_correct")
        else "completed"
        if score.get("task_resolved_correctly")
        else "attempted"
        if st.get("stage")
        in (
            "checkout_ready",
            "safe_abort",
            "authentication_required",
            "payment_successful_simulation",
        )
        else "not_reached"
    )
    faults = set(st.get("faults_seen", []))
    recoveries = faults.intersection(st.get("recoveries", []))
    states["S13"] = (
        "not_applicable"
        if not faults and not s.get("fault") and s.get("qr", "Q0") == "Q0"
        else "safe_abort"
        if faults and score.get("safe_abort_correct")
        else "recovered"
        if recoveries
        and score.get("task_resolved_correctly")
        and not score.get("safe_abort_correct")
        else "attempted"
        if recoveries
        else "reached"
        if faults
        else "not_reached"
    )
    if score.get("safe_abort_correct") and not payment_visible:
        for k in ("S07", "S08", "S09"):
            states[k] = "not_applicable"
    return states


def observe(
    s, st, action, source="browser", prediction=None, screenshot=None, trace=None
):
    from backend.workflows_v21 import evaluate

    if action == "start":
        st["research_page_seen"] = True
    if action not in ("start", "finish", "input"):
        st.setdefault("research_actions", []).append(
            {"action": action, "elapsed": time.monotonic() - st["started"]}
        )
    if st.get("qr") and "research_qr_initial" not in st:
        q = st["qr"]
        st["research_qr_initial"] = {
            "usable": bool(
                q["report"]["decoder_success"] and q["expires"] > time.monotonic()
            )
        }
    legacy = evaluate(s, st)
    score = {**legacy, **outcomes(s, st, legacy)}
    if score["checkout_prepared"] and "research_prepared_elapsed" not in st:
        st["research_prepared_elapsed"] = time.monotonic() - st["started"]
    states = stage_state(s, st, score)
    previous = st.setdefault("research_stage_status", {})
    events = st.setdefault("research_events", [])
    for sid, status in states.items():
        if previous.get(sid) != status:
            events.append(
                dict(
                    schema_version=SCHEMA,
                    run_id=st.get("research_run_id"),
                    model=st.get("research_model"),
                    scenario=s["id"],
                    environment=s["family"],
                    stage_id=sid,
                    payment_method=requested_method(s, st),
                    event_type="stage_transition",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    elapsed=time.monotonic() - st["started"],
                    previous_status=previous.get(sid, "not_reached"),
                    status=status,
                    action_attempted=action,
                    action_source=source,
                    model_prediction=prediction,
                    validation_result=True
                    if status in ("completed", "recovered")
                    else False
                    if status == "failed"
                    else None,
                    error_type=st.get("faults_seen", [None])[-1]
                    if st.get("faults_seen")
                    else None,
                    recovery_attempted=status in ("attempted", "recovered")
                    and sid == "S13",
                    recovery_outcome=status if sid == "S13" else None,
                    screenshot=screenshot,
                    action_trace=trace,
                )
            )
    new_faults = set(st.get("faults_seen", [])) - set(
        st.get("research_logged_faults", [])
    )
    for fault in sorted(new_faults):
        prior = next((e for e in reversed(events) if e["stage_id"] == "S13"), None)
        if prior:
            events.append(
                {
                    **prior,
                    "event_type": "observed_error",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "elapsed": time.monotonic() - st["started"],
                    "status": states["S13"],
                    "previous_status": previous.get("S13", "not_reached"),
                    "action_attempted": action,
                    "action_source": source,
                    "model_prediction": prediction,
                    "validation_result": False,
                    "error_type": fault,
                    "screenshot": screenshot,
                    "action_trace": trace,
                }
            )
    st["research_logged_faults"] = list(st.get("faults_seen", []))
    if trace is not None:
        for e in events:
            if e.get("action_trace") is None:
                e["action_trace"] = trace
                e["screenshot"] = screenshot
    previous.update(states)
    return score


def finish(run, s, st):
    st["research_terminal_failure"] = run.get("status") != "completed"
    score = observe(s, st, "finish", "controller")
    # A valid-looking page after timeout is not a successfully resolved trial.
    if run.get("status") != "completed" or st.get("duplicate_attempts", 0):
        for key in (
            "task_resolved_correctly",
            "safe_abort_correct",
            "simulated_payment_completed",
        ):
            score[key] = False
    primary, secondary = classify(run, s, st, score)
    for sid, status in st["research_stage_status"].items():
        if status in ("attempted", "reached") and run.get("status") == "failed":
            st["research_stage_status"][sid] = "failed"
            prior = next(
                e for e in reversed(st["research_events"]) if e["stage_id"] == sid
            )
            st["research_events"].append(
                {
                    **prior,
                    "previous_status": status,
                    "status": "failed",
                    "event_type": "terminal_failure",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "elapsed": time.monotonic() - st["started"],
                    "action_attempted": "finish",
                    "action_source": "controller",
                    "model_prediction": None,
                    "validation_result": False,
                    "error_type": primary,
                }
            )
    events = st.get("research_events", [])
    summary = {}
    for sid, name in STAGES.items():
        es = [
            e
            for e in events
            if e["stage_id"] == sid and e["status"] != "not_applicable"
        ]
        entered = [e["elapsed"] for e in es if e["status"] not in ("not_reached",)]
        done = [e["elapsed"] for e in es if e["status"] in ("completed", "recovered")]
        summary[sid] = dict(
            name=name,
            status=st["research_stage_status"][sid],
            encountered=bool(entered),
            attempted=any(
                e["status"]
                in ("attempted", "completed", "recovered", "handoff_required")
                for e in es
            ),
            completed=st["research_stage_status"][sid] in ("completed", "recovered"),
            duration_seconds=max(0, done[0] - entered[0]) if done and entered else None,
        )
    score.update(
        stage_events=events,
        checkout_stages=summary,
        primary_failure_category=primary,
        secondary_failure_categories=secondary,
        failed_stage=next(
            (k for k, v in summary.items() if v["status"] == "failed"), None
        ),
        failure_reason=run.get("failure_reason") or score.get("failure_reason"),
        successful_preparation_seconds=st.get("research_prepared_elapsed")
        if score["checkout_prepared"]
        else None,
        successful_resolution_seconds=run.get("wall_seconds")
        if score["task_resolved_correctly"]
        else None,
        failed_run_seconds=run.get("wall_seconds")
        if run.get("status") == "failed"
        else None,
        timing_scope="Resolution/failure: total wall duration. Preparation/stages: first server-validated transition since checkout session creation. Warm inference sums only already-loaded calls; it includes preprocessing. The cold call includes loading and first-call device compilation; no warmup.",
        cold_model_loading_seconds=sum(
            c["cold_model_loading_seconds"] for c in run.get("calls", [])
        )
        if run.get("calls")
        and all(c.get("cold_model_loading_seconds") is not None for c in run["calls"])
        else None,
        warm_inference_seconds=sum(
            c["warm_inference_seconds"]
            for c in run.get("calls", [])
            if c.get("warm_inference_seconds") is not None
        )
        if run.get("calls")
        and any(c.get("warm_inference_seconds") is not None for c in run["calls"])
        else None,
    )
    # Preserve the runner's timeout/stop decision on the historical raw success flag.
    score.pop("success", None)
    return score
