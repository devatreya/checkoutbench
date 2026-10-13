from copy import deepcopy
from scenarios.catalog import scenario, task, SPECS
from backend.evaluator.scoring import evaluate


def complete(s):
    p = s["profile"]
    return dict(
        values={**p, **{"billing_" + k: v for k, v in p["billing"].items()}},
        method=s["method"],
        app=s["app"],
        card=p["card"],
        vpa=p["upiVpa"],
        stage="authorisation_ready",
    )


def test_optional_blank_not_penalized():
    s = scenario("T01")
    st = complete(s)
    st["values"]["address2"] = ""
    assert evaluate(s, st)["success"]
    st["values"]["address2"] = "incorrect provided landmark"
    assert not evaluate(s, st)["success"]


def test_partial_and_wrong_payment_fail():
    s = scenario("T08")
    st = complete(s)
    st["values"]["postal"] = "111111"
    r = evaluate(s, st)
    assert not r["success"] and 0 < r["required_field_accuracy"] < 1
    st = complete(s)
    st["method"] = "card"
    assert not evaluate(s, st)["success"]
    st = complete(s)
    st["stage"] = "payment"
    assert not evaluate(s, st)["success"]


def test_billing_and_cardholder_scored():
    s = scenario("T06")
    st = complete(s)
    assert evaluate(s, st)["success"]
    st["values"]["billing_city"] = "Pune"
    assert not evaluate(s, st)["success"]
    st = deepcopy(complete(s))
    st["card"]["cardName"] = "Wrong Name"
    assert not evaluate(s, st)["success"]


def test_deterministic_seeds_and_public_task():
    for spec in SPECS:
        s = scenario(spec[0], 42)
        assert s == scenario(spec[0], 42)
        public = task(s)
        assert set(public) == {"profile", "instruction"}
        assert not {
            "required_fields",
            "success_conditions",
            "initial_state",
            "seed",
            "features",
        } & set(public)
    assert scenario("T02", 42)["fields"] != scenario("T02", 43)["fields"]
    assert all("holdout" in scenario(s)["features"] for s in ("H01", "H02", "H03"))
