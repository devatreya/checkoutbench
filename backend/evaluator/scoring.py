import re


def norm(key, value):
    value = str(value or "").strip().casefold()
    return (
        re.sub(r"\D", "", value)
        if key in ("phone", "postal", "cardNumber")
        else " ".join(value.split())
    )


def evaluate(s, state):
    if s.get("benchmark_version") == "2.1":
        from backend.workflows_v21 import evaluate as evaluate_v21

        return evaluate_v21(s, state)
    if s.get("benchmark_version") == "2.0":
        from backend.evaluator.v2 import evaluate_v2

        return evaluate_v2(s, state)
    p = s["profile"]
    values = state.get("values", {})
    required = {
        k: norm(k, values.get(k)) == norm(k, p[k]) for k in s["required_fields"]
    }
    optional = {
        k: not norm(k, values.get(k)) or norm(k, values.get(k)) == norm(k, p[k])
        for k in s["optional_fields"]
    }
    if "billing" in s["features"]:
        required.update(
            {
                f"billing_{k}": norm(k, values.get("billing_" + k)) == norm(k, v)
                for k, v in p["billing"].items()
                if k != "address2"
            }
        )
        optional["billing_address2"] = not norm(
            "address2", values.get("billing_address2")
        ) or norm("address2", values.get("billing_address2")) == norm(
            "address2", p["billing"]["address2"]
        )
    payment = state.get("method") == s["method"] and (
        s["method"] != "upi_app" or state.get("app") == s["app"]
    )
    details = True
    if s["method"] == "card":
        details = all(
            norm(k, state.get("card", {}).get(k)) == norm(k, v)
            for k, v in p["card"].items()
        )
    if s["method"] == "upi_vpa":
        details = state.get("vpa") == p["upiVpa"]
    ready = state.get("stage") == "authorisation_ready"
    success = (
        all(required.values())
        and all(optional.values())
        and payment
        and details
        and ready
    )
    return dict(
        success=success,
        required_field_accuracy=sum(required.values()) / len(required),
        optional_correct=all(optional.values()),
        payment_accuracy=int(payment and details),
        completion_stage=state.get("stage", "shipping"),
        field_results=required,
        optional_results=optional,
        failure_reason=None
        if success
        else (
            "field_mismatch"
            if not all(required.values()) or not all(optional.values())
            else "payment_mismatch"
            if not payment or not details
            else "incomplete"
        ),
    )
