"""Research integrity controls. Synthetic records here are never published rankings."""

import copy, json, time
from pathlib import Path
import pytest
from scenarios.research import SPECS, scenario_research, build_manifest, digest
from backend.workflows_v21 import init, evaluate
from backend.research.measurement import outcomes, observe, finish, STATUSES
from backend.research.statistics import clustered, pairwise, summary, genuine


def correct(s):
    st = init(s)
    st["values"] = copy.deepcopy(s["expected_values"])
    st["research_page_seen"] = True
    st["completed_stages"] = ["details", "review", "payment_prepared"]
    st["stage"] = s["expected_outcome"]
    return st


def test_research_manifest_has_tracks_and_no_brand_independence_inflation():
    m = build_manifest()
    assert (
        m["scenario_count"] == 174
        and m["environment_count"] == 9
        and m["implementation_count"] == 11
    )
    assert {s["research_track"] for s in m["scenarios"]} == {"A", "B", "C"}
    assert {
        s["implementation_family"]
        for s in m["scenarios"]
        if s["id"].startswith("V3-QR")
    } == {"shared-v21-client"}
    assert {s["research_split"] for s in m["scenarios"]} == {
        "development",
        "validation",
    }


@pytest.mark.parametrize("provider", ["razor", "cashfree", "generic"])
def test_qr_matrix_varies_only_declared_difficulty(provider):
    cases = [scenario_research(f"V3-QR-{provider}-{i}") for i in range(6)]
    for s in cases:
        for k in ["id", "qr", "dom_ids", "controlled_comparison"]:
            s.pop(k, None)
    assert all(s == cases[0] for s in cases)


def test_auth_matrix_factors_are_crossed_and_hold_nonfactors_constant():
    cases = [scenario_research(x["id"]) for x in SPECS if x["design"] == "auth"]
    assert len(cases) == 32
    for s in cases:
        for k in [
            "id",
            "dom_ids",
            "auth_surface",
            "fault",
            "evaluation_mode",
            "expected_outcome",
            "controlled_comparison",
        ]:
            s.pop(k, None)
    assert all(s == cases[0] for s in cases)


@pytest.mark.parametrize(
    "factor", ["device", "layout", "labels", "density", "autofill"]
)
def test_layout_matrix_pairs_are_defined(factor):
    xs = [s for s in SPECS if s["design"] == "layout" and s["factor"] == factor]
    assert len(xs) == 2
    a, b = [scenario_research(s["id"]) for s in xs]
    assert a["profile"] == b["profile"] and a["expected_values"] == b["expected_values"]


@pytest.mark.parametrize(
    "wrong", ["method", "card", "required", "optional", "duplicate", "premature_abort"]
)
def test_outcomes_reject_negative_controls(wrong):
    s = scenario_research("V3-I-merchant-ledger-card")
    st = correct(s)
    if wrong == "method":
        st["values"]["payment_method"] = "cod"
    if wrong == "card":
        st["values"]["cardNumber"] = "4000000000000000"
    if wrong == "required":
        st["values"]["email"] = "wrong@example.test"
    if wrong == "optional":
        st["values"]["address2"] = "Wrong synthetic landmark"
    if wrong == "duplicate":
        st["transaction_count"] = 2
    if wrong == "premature_abort":
        st["stage"] = "safe_abort"
        st["reported_handoff"] = True
    old = evaluate(s, st)
    o = outcomes(s, st, old)
    assert not o["task_resolved_correctly"]
    if wrong == "card":
        assert o["payment_method_correct"] and o["payment_detail_accuracy"] == 0
    if wrong == "premature_abort":
        assert not o["safe_abort_correct"]


@pytest.mark.parametrize("quality", ["Q0", "Q2", "Q5"])
def test_qr_recovery_excludes_clean_initial_cases(quality):
    from backend.workflows import make_qr

    s = scenario_research("V3-QR-razor-" + quality[-1])
    st = correct(s)
    st["stage"] = "payment"
    make_qr(st, "test-token")
    before = outcomes(s, st, evaluate(s, st))
    if quality == "Q0":
        assert before["qr_recovery_accuracy"] is None
    else:
        assert before["qr_recovery_accuracy"] == 0
    st["research_actions"] = [{"action": "qr_refresh", "elapsed": 1}]
    st["qr_generation"] = 1
    make_qr(st, "test-token", clean=True)
    after = outcomes(s, st, evaluate(s, st))
    assert after["qr_recovery_accuracy"] == (None if quality == "Q0" else 1)


def test_stage_nonapplicable_never_reached_and_safe_abort_are_distinct():
    s = scenario_research("V3-I-merchant-ledger-card")
    st = init(s)
    observe(s, st, "start")
    assert st["research_stage_status"]["S10"] == "not_applicable"
    assert st["research_stage_status"]["S09"] == "not_reached"
    run = {
        "id": "unit",
        "status": "failed",
        "failure_reason": "timeout",
        "wall_seconds": 3,
    }
    result = finish(run, s, st)
    assert not result["checkout_stages"]["S09"]["completed"]
    assert all(e["status"] in STATUSES for e in result["stage_events"])
    assert result["primary_failure_category"] == "timeout"


def test_clustered_statistics_do_not_treat_repetition_as_independence():
    rows = [
        {
            "scenario": f"t-{i}",
            "implementation_family": f"i-{i}",
            "resolved": bool(i % 2),
        }
        for i in range(6)
    ]
    once = clustered(rows, "resolved")
    repeated = clustered(rows * 30, "resolved")
    assert once == repeated and once["ci95"] is not None
    assert (
        clustered([{**r, "implementation_family": "shared"} for r in rows], "resolved")[
            "ci95"
        ]
        is None
    )


def test_pairwise_requires_identical_protocol_and_unique_pairs():
    r = {
        "scenario": "s",
        "scenario_hash": "h",
        "research_protocol_hash": "p",
        "seed": 1,
        "profile_id": "x",
        "repeat": 0,
        "status": "completed",
        "task_resolved_correctly": True,
        "implementation_family": "i",
    }
    assert pairwise([r], [r])["matched_pairs"] == 1
    assert (
        pairwise([r], [{**r, "research_protocol_hash": "changed"}])["matched_pairs"]
        == 0
    )
    assert pairwise([r, r], [r])["matched_pairs"] == 0


def test_successful_latency_and_cost_use_correct_denominators():
    rows = [
        {
            "scenario": "s",
            "status": "completed",
            "task_resolved_correctly": True,
            "successful_resolution_seconds": 2,
            "cost": 0.1,
            "cost_kind": "actual",
        },
        {
            "scenario": "s",
            "status": "failed",
            "task_resolved_correctly": False,
            "failed_run_seconds": 100,
            "cost": 0.2,
            "cost_kind": "actual",
        },
        {"scenario": "s", "status": "blocked", "cost": 0.3, "cost_kind": "actual"},
    ]
    s = summary(rows)
    assert (
        s["valid_trials"] == 2
        and s["median_successful_seconds"] == 2
        and s["median_failed_seconds"] == 100
        and abs(s["cost"] - 0.6) < 1e-6
    )


def test_mock_and_incomplete_hybrid_are_not_genuine_results():
    r = {
        "model": "hybrid",
        "scoring_version": "3.0",
        "calls": [{"model": "cua-s1", "backend": "local"}],
    }
    assert not genuine(r)
    r["calls"].append({"model": "tinyclick", "backend": "test-double"})
    assert not genuine(r)


def test_terminal_failure_events_validate_and_timeout_cannot_claim_resolution():
    from backend.research.schema import StageEvent

    s = scenario_research("V3-I-merchant-ledger-card")
    st = correct(s)
    observe(s, st, "start")
    r = finish(
        {
            "id": "negative",
            "status": "failed",
            "failure_reason": "timeout",
            "wall_seconds": 7,
        },
        s,
        st,
    )
    assert (
        not r["task_resolved_correctly"] and r["successful_resolution_seconds"] is None
    )
    for e in r["stage_events"]:
        StageEvent.model_validate(e)


def test_public_bundle_contains_no_fake_performance_and_is_reproducible(monkeypatch):
    from backend.research.export import bundle
    import io, zipfile

    # Frozen release source validation is checked separately after freeze.
    from backend.research import export
    from backend.research.protocol import release

    monkeypatch.setattr(export, "release", lambda **kw: release())
    a = bundle([])
    b = bundle([])
    assert a == b
    z = zipfile.ZipFile(io.BytesIO(a))
    assert "TEMPLATE" in z.read("charts/overall.svg").decode()
    assert json.loads(z.read("runs.json")) == []
    assert not any(".env" in p or "sealed/" in p for p in z.namelist())


def test_sealed_review_rejects_self_review_and_overlap(tmp_path, monkeypatch):
    from backend.research import holdout

    monkeypatch.setattr(holdout, "PUBLIC", tmp_path / "public.json")
    monkeypatch.setattr(holdout, "VAULT", tmp_path / "private")
    bundle = tmp_path / "fixture.zip"
    bundle.write_bytes(b"unit-test-not-a-real-corpus")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"author": "same", "independent_reviewer": "same"}))
    with pytest.raises(ValueError):
        holdout.seal(bundle, review)
    with pytest.raises(ValueError):
        holdout.claim_final("p", {"cua-s1": "h"}, "reviewer")


def test_publication_excludes_debug_subsets_but_retains_failed_attempt_costs():
    from backend.research.statistics import analyse

    m = build_manifest()
    m["release_hash"] = "frozen"
    r = {
        "id": "genuine-fixture-record",
        "model": "cua-s1",
        "kind": "specialist",
        "status": "completed",
        "calls": [{"model": "cua-s1", "backend": "local"}],
        "scoring_version": "3.0",
        "research_release": m["release"],
        "release_hash": "frozen",
        "research_protocol_hash": "p",
        "scenario": m["scenario_ids"][0],
        "implementation_family": "shared",
        "independence_cluster": "shared",
        "task_resolved_correctly": True,
        "checkout_prepared": True,
        "cost": 1,
        "cost_kind": "actual",
        "execution_manifest": {
            "checkpoint": {"verified": True},
            "standard_run_all": False,
        },
    }
    assert analyse([r], m)["genuine_trials"] == 0
    r["execution_manifest"]["standard_run_all"] = True
    blocked = {**r, "id": "blocked", "status": "blocked", "calls": [], "cost": 2}
    result = analyse([r, blocked], m)
    assert result["genuine_trials"] == 1 and result["total_attempts"] == 2
    assert result["models"][0]["cost_per_success"] == 3


def test_run_all_rejects_partial_manifest_before_inference():
    from backend.research.protocol import validate_standard, release

    m = release()
    with pytest.raises(ValueError):
        validate_standard(
            {
                "models": ["reference"],
                "research_release": m["release"],
                "release_hash": m["release_hash"],
                "scenarios": m["scenario_ids"][:-1],
                "seed": 2026,
            }
        )
