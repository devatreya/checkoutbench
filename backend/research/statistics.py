"""Implementation-clustered descriptive analysis with explicit denominators.

Repetitions are first averaged within task, then within implementation. Bootstrap
resamples whole implementation means; it never pretends repetitions are websites.
"""

from collections import defaultdict, Counter
from statistics import mean, median
import math, random
from backend.research.measurement import STAGES, FAILURES

MODELS = ("cua-s1", "tinyclick", "hybrid", "mai-ui", "ui-venus")
MIN_CLUSTERS = 5
MIN_TRIALS = 20


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def med(v):
    a = [x for x in v if numeric(x)]
    return median(a) if a else None


def genuine(r):
    if (
        r.get("model") not in MODELS
        or r.get("kind") == "reference"
        or any(r.get(k) for k in ("test_only", "is_test_double", "test_double"))
    ):
        return False
    if r.get("action_attribution", {}).get("deterministic_reference", 0):
        return False
    calls = r.get("calls", [])
    if not calls or any(
        any(x in str(c.get("backend", "")).lower() for x in ("mock", "test", "script"))
        for c in calls
    ):
        return False
    if r["model"] == "hybrid" and not {"cua-s1", "tinyclick"}.issubset(
        {c.get("model") for c in calls}
    ):
        return False
    return r.get("scoring_version") == "3.0"


def scored(r):
    return r.get("status") in ("completed", "failed")


def wilson(k, n):
    if not n:
        return None
    z = 1.96
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0, c - h), min(1, c + h)]


def clustered(rows, key, seed=2026, draws=1000):
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if isinstance(r.get(key), bool) or numeric(r.get(key)):
            groups[
                r.get(
                    "independence_cluster", r.get("implementation_family", "unreported")
                )
            ][r["scenario"]].append(float(r[key]))
    clusters = [mean(mean(v) for v in tasks.values()) for tasks in groups.values()]
    if not clusters:
        return {
            "estimate": None,
            "ci95": None,
            "implementation_clusters": 0,
            "uncertainty": "Not reported",
        }
    ci = None
    if len(clusters) >= MIN_CLUSTERS and "unreported" not in groups:
        rng = random.Random(seed)
        samples = sorted(
            mean(rng.choices(clusters, k=len(clusters))) for _ in range(draws)
        )
        ci = [samples[int(0.025 * draws)], samples[int(0.975 * draws) - 1]]
    return {
        "estimate": mean(clusters),
        "ci95": ci,
        "implementation_clusters": len(clusters),
        "uncertainty": "implementation bootstrap; conditional on observed task design"
        if ci
        else "Insufficient independent implementations for a population interval",
    }


def summary(rows):
    valid = [r for r in rows if scored(r)]
    costs = [
        r.get("cost") if r.get("cost_kind") != "not_reported" else None
        for r in rows
        if r.get("status") != "running"
    ]
    cost = sum(costs) if costs and all(numeric(v) for v in costs) else None
    k = sum(r.get("checkout_prepared") is True for r in valid)
    resolved = sum(r.get("task_resolved_correctly") is True for r in valid)

    def rate(key):
        xs = [
            r[key] for r in valid if isinstance(r.get(key), bool) or numeric(r.get(key))
        ]
        return {
            "numerator": sum(xs),
            "denominator": len(xs),
            "rate": mean(xs) if xs else None,
            "descriptive_trial_wilson95": wilson(sum(xs), len(xs)),
            "clustered": clustered(valid, key),
        }

    recovered = [
        r
        for r in valid
        if r.get("qr_research", {}).get("recoverable_problem_encountered")
    ]
    return dict(
        total_attempts=len(rows),
        valid_trials=len(valid),
        distinct_tasks=len({r["scenario"] for r in valid}),
        implementations=len(
            {r.get("implementation_family", "unreported") for r in valid}
        ),
        task_resolution=rate("task_resolved_correctly"),
        checkout_preparation=rate("checkout_prepared"),
        required_fields=rate("required_fields_correct"),
        required_field_accuracy=clustered(valid, "required_field_accuracy"),
        payment_detail=rate("payment_detail_accuracy"),
        authentication=rate("authentication_handoff_accuracy"),
        final_simulated_state=rate("final_simulated_payment_state_accuracy"),
        payment_method=rate("payment_method_correct"),
        authorisation_handoff=rate("authorisation_handoff_correct"),
        safe_abort=rate("safe_abort_correct"),
        simulated_completion=rate("simulated_payment_completed"),
        median_successful_seconds=med(
            r.get("successful_resolution_seconds") for r in valid
        ),
        median_preparation_seconds=med(
            r.get("successful_preparation_seconds") for r in valid
        ),
        median_failed_seconds=med(r.get("failed_run_seconds") for r in valid),
        median_inference_seconds=med(r.get("inference_seconds") for r in valid),
        timeouts=sum(r.get("primary_failure_category") == "timeout" for r in valid),
        failures=dict(
            Counter(
                r.get("primary_failure_category", "unclassified_failure")
                for r in valid
                if not r.get("task_resolved_correctly")
            )
        ),
        qr_recovery={
            "numerator": sum(r.get("qr_recovery_accuracy") == 1 for r in recovered),
            "denominator": len(recovered),
            "rate": mean(r.get("qr_recovery_accuracy") == 1 for r in recovered)
            if recovered
            else None,
        },
        cost=cost,
        cost_per_success=cost / k if cost is not None and k else None,
        cost_per_resolution=cost / resolved if cost is not None and resolved else None,
        excluded=dict(Counter(r.get("status") for r in rows if not scored(r))),
    )


def pairwise(left, right):
    def key(r):
        return (
            r.get("research_protocol_hash"),
            r.get("scenario_hash"),
            r.get("scenario"),
            r.get("seed"),
            r.get("profile_id"),
            r.get("repeat"),
        )

    a = defaultdict(list)
    b = defaultdict(list)
    for r in left:
        if scored(r):
            a[key(r)].append(r)
    for r in right:
        if scored(r):
            b[key(r)].append(r)
    # Ambiguous duplicate attempts are not silently picked as winners.
    pairs = [
        (a[k][0], b[k][0]) for k in a.keys() & b.keys() if len(a[k]) == len(b[k]) == 1
    ]
    diffs = [
        {
            **x,
            "difference": int(x["task_resolved_correctly"])
            - int(y["task_resolved_correctly"]),
        }
        for x, y in pairs
    ]
    return {
        "matched_pairs": len(pairs),
        "unmatched_or_ambiguous": len(left) + len(right) - 2 * len(pairs),
        "difference": clustered(diffs, "difference"),
        "publication_comparable": len(pairs) >= MIN_TRIALS
        and len({x.get("implementation_family") for x, _ in pairs}) >= MIN_CLUSTERS
        and len(pairs) == len(left) == len(right),
    }


def eligible_attempt(r, manifest):
    """Retain failed/blocked costs, while never promoting debug subsets or fake calls."""
    if (
        r.get("model") not in MODELS
        or r.get("kind") == "reference"
        or any(r.get(k) for k in ("test_only", "is_test_double", "test_double"))
    ):
        return False
    if r.get("action_attribution", {}).get("deterministic_reference", 0):
        return False
    if (
        r.get("research_release") != manifest["release"]
        or r.get("release_hash") != manifest["release_hash"]
    ):
        return False
    execution = r.get("execution_manifest", {})
    if not execution.get("standard_run_all") or not (
        execution.get("checkpoint") or {}
    ).get("verified"):
        return False
    return genuine(r) or (
        r.get("status") in ("blocked", "unavailable", "stopped", "running", "failed")
        and not r.get("calls")
    )


def analyse(rows, manifest, protocol=None):
    visible = [r for r in rows if eligible_attempt(r, manifest)]
    protocols = sorted({r.get("research_protocol_hash", "unreported") for r in visible})
    selected = (
        [r for r in visible if r.get("research_protocol_hash") == protocol]
        if protocol
        else []
    )
    models = []
    providers = []
    payments = []
    stages = []
    failures = []
    matrix = []
    pairs = []
    components = []
    implementations = []
    scenarios = []
    authentication = []
    qr_levels = []
    definitions = manifest["scenarios"]
    for model in MODELS:
        rs = [r for r in selected if r["model"] == model]
        if not rs:
            continue
        models.append(
            {
                "model": model,
                **summary(rs),
                "tracks": {
                    t: summary([r for r in rs if r.get("research_track") == t])
                    for t in ("A", "B", "C")
                },
            }
        )
        for provider in sorted({s["family"] for s in definitions}):
            for quality in ("Q0", "Q1", "Q2", "Q3", "Q4", "Q5"):
                eligible_ids = {
                    s["id"]
                    for s in definitions
                    if s["family"] == provider
                    and s.get("qr") == quality
                    and (s.get("controlled_comparison") or {}).get("matrix") == "qr"
                }
                if eligible_ids:
                    qr_levels.append(
                        {
                            "model": model,
                            "provider": provider,
                            "quality": quality,
                            **summary([r for r in rs if r["scenario"] in eligible_ids]),
                        }
                    )
        for implementation in sorted({s["implementation_family"] for s in definitions}):
            implementations.append(
                {
                    "model": model,
                    "implementation": implementation,
                    **summary(
                        [
                            r
                            for r in rs
                            if r.get("implementation_family") == implementation
                        ]
                    ),
                }
            )
        for sid in sorted({r["scenario"] for r in rs}):
            scenarios.append(
                {
                    "model": model,
                    "scenario": sid,
                    **summary([r for r in rs if r["scenario"] == sid]),
                }
            )
        for challenge, method in sorted(
            {
                (s.get("authentication_method", "none"), s["method"])
                for s in definitions
                if s.get("authentication_method", "none") != "none"
            }
        ):
            ar = [
                r
                for r in rs
                if r.get("authentication_method") == challenge
                and r.get("requested_payment_method") == method
            ]
            authentication.append(
                {
                    "model": model,
                    "challenge": challenge,
                    "method": method,
                    "exposed": sum(
                        r.get("checkout_stages", {})
                        .get("S10", {})
                        .get("encountered", False)
                        for r in ar
                    ),
                    **summary(ar),
                }
            )
        for provider in sorted({s["family"] for s in definitions}):
            pr = [r for r in rs if r.get("environment") == provider]
            providers.append(
                {
                    "model": model,
                    "provider": provider,
                    "source_class": "synthetic or government-inspired; not production provider performance",
                    **summary(pr),
                }
            )
            for method in manifest["payment_methods"]:
                eligible = [
                    s
                    for s in definitions
                    if s["family"] == provider and s["method"] == method
                ]
                trials = [r for r in pr if r.get("requested_payment_method") == method]
                matrix.append(
                    {
                        "model": model,
                        "provider": provider,
                        "method": method,
                        "supported": bool(eligible),
                        "eligible_tasks": len(eligible),
                        "display": "N/A"
                        if not eligible
                        else "Insufficient data"
                        if not trials
                        else "observed",
                        **summary(trials),
                    }
                )
        for method in manifest["payment_methods"]:
            pr = [r for r in rs if r.get("requested_payment_method") == method]
            valid = [r for r in pr if scored(r)]
            exposed = [
                r
                for r in valid
                if r.get("checkout_stages", {}).get("S07", {}).get("encountered")
            ]
            attempted = [
                r
                for r in valid
                if r.get("checkout_stages", {}).get("S09", {}).get("attempted")
            ]
            payments.append(
                {
                    "model": model,
                    "method": method,
                    "eligible_tasks": sum(s["method"] == method for s in definitions),
                    "exposed_opportunities": len(exposed),
                    "attempted_trials": len(attempted),
                    "method_ranking": "Insufficient data — matched coverage and cluster uncertainty required",
                    "common_failure": Counter(
                        r.get("primary_failure_category")
                        for r in valid
                        if not r.get("task_resolved_correctly")
                    ).most_common(1)[0][0]
                    if any(not r.get("task_resolved_correctly") for r in valid)
                    else None,
                    **summary(pr),
                }
            )
        for sid, name in STAGES.items():
            all_stage = [r.get("checkout_stages", {}).get(sid) for r in rs if scored(r)]
            reported = [s for s in all_stage if s]
            eligible = [s for s in reported if s["status"] != "not_applicable"]
            entered = [s for s in eligible if s["encountered"]]
            k = sum(s["completed"] for s in entered)
            conditional = [
                {**r, "stage_completed": r["checkout_stages"][sid]["completed"]}
                for r in rs
                if scored(r)
                and r.get("checkout_stages", {}).get(sid, {}).get("encountered")
            ]
            stages.append(
                {
                    "model": model,
                    "stage_id": sid,
                    "name": name,
                    "applicable": len(eligible),
                    "not_applicable": len(reported) - len(eligible),
                    "not_reached": sum(s["status"] == "not_reached" for s in eligible),
                    "entered": len(entered),
                    "attempted": sum(s["attempted"] for s in entered),
                    "completed": k,
                    "failed": sum(s["status"] == "failed" for s in entered),
                    "handoff": sum(s["status"] == "handoff_required" for s in entered),
                    "safe_abort": sum(s["status"] == "safe_abort" for s in entered),
                    "conditional_success": k / len(entered) if entered else None,
                    "conditional_clustered": clustered(conditional, "stage_completed"),
                    "median_stage_seconds": med(
                        s.get("duration_seconds") for s in entered if s["completed"]
                    ),
                }
            )
        by_failure = defaultdict(list)
        for r in rs:
            if r.get("primary_failure_category") and not r.get(
                "task_resolved_correctly"
            ):
                by_failure[r["primary_failure_category"]].append(r["id"])
        failures.extend(
            {
                "model": model,
                "category": k,
                "group": FAILURES.get(k, "other"),
                "count": len(v),
                "run_ids": v,
            }
            for k, v in by_failure.items()
        )
        components.append(
            {
                "model": model,
                "field_classification_accuracy": med(
                    r.get("field_classification_accuracy") for r in rs
                ),
                "grounding_accuracy": med(r.get("grounding_accuracy") for r in rs),
                "reported_trials": len(rs),
                "assistance": "See per-action selection_source and grounding_source; no causal ablation claim without matched runs.",
            }
        )
    # Conservative winner labels: same provider/implementation coverage, sufficient
    # independent clusters, and non-overlapping intervals for all eligible competitors.
    for model in MODELS:
        pr = [
            p
            for p in payments
            if p["model"] == model
            and p["valid_trials"] >= MIN_TRIALS
            and p["checkout_preparation"]["clustered"]["ci95"]
        ]
        coverage = lambda method: {
            (r.get("environment"), r.get("implementation_family"))
            for r in selected
            if r["model"] == model
            and r.get("requested_payment_method") == method
            and scored(r)
        }
        if (
            len(pr) > 1
            and all(coverage(p["method"]) == coverage(pr[0]["method"]) for p in pr)
            and len(pr)
            == sum(p["model"] == model and p["eligible_tasks"] > 0 for p in payments)
        ):
            for p in pr:
                lo, hi = p["checkout_preparation"]["clustered"]["ci95"]
                others = [q for q in pr if q is not p]
                if all(
                    lo > q["checkout_preparation"]["clustered"]["ci95"][1]
                    for q in others
                ):
                    p["method_ranking"] = (
                        "Best observed preparation on comparable coverage"
                    )
                elif all(
                    hi < q["checkout_preparation"]["clustered"]["ci95"][0]
                    for q in others
                ):
                    p["method_ranking"] = (
                        "Worst observed preparation on comparable coverage"
                    )
                else:
                    p["method_ranking"] = (
                        "No distinguishable rank; overlapping uncertainty"
                    )
    for i, a in enumerate(models):
        for b in models[i + 1 :]:
            pairs.append(
                {
                    "left": a["model"],
                    "right": b["model"],
                    **pairwise(
                        [r for r in selected if r["model"] == a["model"]],
                        [r for r in selected if r["model"] == b["model"]],
                    ),
                }
            )
    return {
        "release": manifest["release"],
        "protocols": protocols,
        "selected_protocol": protocol,
        "models": models,
        "providers": providers,
        "payments": payments,
        "stages": stages,
        "failures": failures,
        "vendor_payment": matrix,
        "paired_comparisons": pairs,
        "components": components,
        "implementations": implementations,
        "scenarios": sorted(
            scenarios,
            key=lambda r: (
                r["task_resolution"]["rate"]
                if r["task_resolution"]["rate"] is not None
                else 2
            ),
        ),
        "authentication": authentication,
        "qr_levels": qr_levels,
        "payment_methods": manifest["payment_methods"],
        "genuine_trials": sum(genuine(r) for r in selected),
        "total_attempts": len(selected),
        "interpretation": "Insufficient data"
        if not selected
        else "Synthetic benchmark observations; independent review and readiness gates apply.",
        "branching_note": "Stages have independent applicability/encounter denominators; bars are not a linear survival funnel.",
    }
