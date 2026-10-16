"""Reproducible synthetic research bundles. No credentials or model weights."""

import csv, io, json, hashlib, zipfile, html, subprocess
from pathlib import Path
from threading import Lock

PLOT_LOCK = Lock()
from backend.research.protocol import release, readiness, source_hashes, runtime_identity
from backend.research.statistics import analyse, genuine, eligible_attempt
from backend.research.schema import StageEvent
from scenarios.research import ROOT, scenario_research

CATEGORIES = {
    "overall": "models",
    "core": "models",
    "resilience": "models",
    "complex": "models",
    "vendors": "providers",
    "payment-methods": "payments",
    "stages": "stages",
    "failures": "failures",
    "qr-recovery": "qr_levels",
    "authentication": "authentication",
    "accuracy-latency": "models",
    "components": "components",
}
# Deliberate allowlist: arbitrary endpoint payloads, task URLs, config/env, auth tokens never enter public exports.
RUN_FIELDS = "canonical_id public_id display_name description observation_track outcome_category genuine_inference_call_count invalid_model_output_count invalid_model_output_rate invalid_model_output_denominator inference_failure_rate unsupported_action_count inference_failure_count runtime_source_hash runtime_binding_hash id model scenario environment benchmark_version research_release release_hash scenario_hash research_protocol_hash implementation_family independence_cluster research_track research_split seed profile_id repeat status timestamp scoring_version task_resolved_correctly checkout_prepared authorisation_handoff_correct simulated_payment_completed safe_abort_correct payment_method_correct payment_detail_accuracy authentication_handoff_accuracy final_simulated_payment_state_accuracy required_fields_correct required_field_accuracy requested_payment_method authentication_method primary_failure_category secondary_failure_categories failed_stage successful_preparation_seconds successful_resolution_seconds failed_run_seconds wall_seconds inference_seconds cold_model_loading_seconds warm_inference_seconds latency_breakdown action_attribution fallback_policy field_classification_accuracy grounding_accuracy qr_research qr_recovery_accuracy checkout_stages stage_events events field_results optional_results workflow_events cost cost_kind execution_manifest".split()


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def chart(title, rows, metric="task_resolution"):
    """Publication SVG rendered with Matplotlib; no invented observations."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (
        PLOT_LOCK,
        plt.rc_context(
            {
                "svg.hashsalt": "checkoutbench-v3",
                "svg.fonttype": "none",
                "font.size": 10,
            }
        ),
    ):
        fig, ax = plt.subplots(figsize=(12, max(3, 1.6 + len(rows) * 0.48)))
        ax.set_title(
            title + " · synthetic benchmark", loc="left", pad=22, fontweight="bold"
        )
        if not rows:
            ax.axis("off")
            ax.text(
                0.02,
                0.65,
                "TEMPLATE — no eligible genuine model evaluations",
                transform=ax.transAxes,
                fontsize=15,
            )
            ax.text(
                0.02,
                0.38,
                "Run the frozen protocol before making performance claims.",
                transform=ax.transAxes,
            )
        else:
            labels = []
            for i, r in enumerate(rows):
                labels.append(
                    " · ".join(
                        str(r[k])
                        for k in (
                            "model",
                            "provider",
                            "method",
                            "stage_id",
                            "challenge",
                            "quality",
                            "category",
                        )
                        if r.get(k)
                    )
                )
                v = r.get(metric, {}) or {}
                c = v.get("clustered", {}) or {}
                point = c.get("estimate", v.get("rate"))
                interval = c.get("ci95")
                if point is None:
                    ax.text(0.01, i, "Not reported", va="center", color="#687482")
                    continue
                ax.barh(i, point, color="#446756", height=0.55)
                if interval:
                    ax.errorbar(
                        point,
                        i,
                        xerr=[
                            [max(0, point - interval[0])],
                            [max(0, interval[1] - point)],
                        ],
                        color="#182c24",
                        capsize=3,
                        fmt="none",
                    )
                ax.text(
                    1.02,
                    i,
                    f"{point:.1%} · n={v.get('denominator', r.get('valid_trials', 0))}"
                    + ("" if interval else " · CI unavailable"),
                    va="center",
                    fontsize=8,
                )
            ax.set_yticks(range(len(labels)), labels)
            ax.invert_yaxis()
            ax.set_xlim(0, 1.6)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
            ax.spines[["top", "right"]].set_visible(False)
            ax.set_xlabel(
                "Observed rate · cluster intervals where available; repeats are not independent sites"
            )
        fig.tight_layout()
        out = io.StringIO()
        fig.savefig(
            out,
            format="svg",
            metadata={"Date": None, "Creator": "CheckoutBench / Matplotlib"},
        )
        plt.close(fig)
        return out.getvalue()


def bundle(rows):
    m = release(verify=True)
    from backend.research.official import dataset
    a = dataset(rows)
    ready = readiness()
    selected = a["runs"]
    files = {
        "manifest.json": dump(m),
        "analysis.json": dump({**a, "runs": [{k: r[k] for k in RUN_FIELDS if k in r} for r in selected]}),
        "readiness.json": dump(ready),
        "stage-event.schema.json": dump(StageEvent.model_json_schema()),
        "runs.json": dump([{k: r[k] for k in RUN_FIELDS if k in r} for r in selected]),
        "scenarios.json": dump([scenario_research(sid) for sid in m["scenario_ids"]]),
    }
    for name, key in CATEGORIES.items():
        rs = a[key]
        if name in ("core", "resilience", "complex"):
            rs = [
                {
                    "model": r["model"],
                    **r["tracks"][
                        {"core": "A", "resilience": "B", "complex": "C"}[name]
                    ],
                }
                for r in rs
            ]
        metric = (
            "checkout_preparation"
            if name in ("core", "payment-methods")
            else "qr_recovery"
            if name == "qr-recovery"
            else "authentication"
            if name == "authentication"
            else "task_resolution"
        )
        files[f"leaderboards/{name}.json"] = dump(rs)
        # Long-form CSV preserves nested denominators and CI instead of flattening ambiguous scores.
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["row", "data_json"])
        for i, r in enumerate(rs):
            writer.writerow([i, json.dumps(r, sort_keys=True)])
        files[f"leaderboards/{name}.csv"] = output.getvalue()
        if name == "stages":
            rs = [
                {
                    **r,
                    "task_resolution": {
                        "rate": r["conditional_success"],
                        "denominator": r["entered"],
                        "clustered": r["conditional_clustered"],
                    },
                }
                for r in rs
            ]
        if name == "failures":
            total = sum(r["count"] for r in rs)
            rs = [
                {
                    **r,
                    "task_resolution": {
                        "rate": r["count"] / total if total else None,
                        "denominator": total,
                    },
                }
                for r in rs
            ]
        if name == "components":
            rs = [
                {
                    **r,
                    "task_resolution": {
                        "rate": r["field_classification_accuracy"],
                        "denominator": r["reported_trials"],
                    },
                }
                for r in rs
            ]
        files[f"charts/{name}.svg"] = chart(name.replace("-", " ").title(), rs, metric)
    files["charts/accuracy-latency.svg"] = scatter(a["models"])
    files["REPORT.md"] = f"""# CheckoutBench {m["release"]} research report

Status: **{ready["status"]}**. {len(selected)} eligible genuine model trials.

## Research question
Which checkout fields, interactions, payment preparations and recoveries can lightweight specialist systems perform with their documented controller assistance?

## Design
{m["scenario_count"]} synthetic tasks, {m["environment_count"]} environment labels, {m["implementation_count"]} client implementation families, three research tracks. Shared widgets and engine constrain independence. No production-provider claim.

## Models and methodology
See model-provenance.json, per-run execution manifests, methodology and protocol. Exact checkpoints and genuine inference required. Safe stops, handoffs and simulated payments remain separate outcomes.

## Results
{"No eligible results. All graphics are templates; no winner or performance claim is supported." if not selected else "See analysis.json and long-form leaderboards. Report track scores separately; inspect paired comparisons before any superiority claim."}

## Uncertainty and limitations
Cluster-bootstrap intervals require five independent clusters. Repeats do not increase website count. Current clients share an engine and are conservatively one inference cluster. Missing costs are unknown. Human review, independent holdout and official sandbox evidence must be assessed in readiness.json.

## Reproduction
Verify bundle SHA256SUMS.json. Follow REPRODUCING.md with pinned dependencies, exact model revisions and the frozen scenario/settings manifest. Independent reproduction has not occurred.

## Outstanding blockers
""" + "".join(f"- {b}\n" for b in ready["blockers"])
    files[
        "X-THREAD.md"
    ] = """# Technical thread template — NOT a performance announcement

1. Research question: can small specialist systems prepare checkouts reliably across fields, payment methods and recovery tasks?
2. Design: [verified task / implementation counts], three tracks, synthetic environments. Providers are inspirations, not production measurements.
3. Results: [insert verified track scores, sample sizes and clustered intervals]. No genuine results → leave this as a template.
4. Payments: [insert comparable payment preparation and recovery evidence]. OTP/3DS are authentication dimensions.
5. Failure stages: [insert encounter denominators and linked run evidence].
6. CUA vs TinyClick vs hybrid: [insert matched comparison only after both components genuinely execute].
7. Limits: shared infrastructure, synthetic profiles, pending human review/holdout/sandbox evidence. No real money moved.
8. Reproduce: [release + protocol + checkpoint hashes + repository URL].
"""
    for name in (
        "model-provenance.json",
        "ground-truth-reviews.json",
        "sealed-commitments.json",
        "validation-evidence.json",
    ):
        path = ROOT / "research" / name
        if path.exists():
            files[name] = path.read_text()
    for folder in ("docs/research", "docs/operations", "scenarios"):
        for p in (ROOT / folder).rglob("*"):
            if p.is_file() and p.suffix in (".md", ".json", ".py"):
                files[str(p.relative_to(ROOT))] = p.read_text()
    # Source payload describes the actual audited runtime, while manifest.json
    # retains its immutable historical source identity.
    files["runtime-identity.json"] = dump(runtime_identity(m))
    files["runtime-source-hashes.json"] = dump(source_hashes())
    for name in ("runtime-binding.json", "scenario-integrity-baseline.json"):
        path = ROOT / "research" / name
        if path.exists():
            files[name] = path.read_text()
    for name in source_hashes():
        files["source/" + name] = (ROOT / name).read_text()
    for name in ("pyproject.toml", "uv.lock", "frontend/package-lock.json"):
        if (ROOT / name).exists():
            files[name] = (ROOT / name).read_text()
    from backend.storage.database import DATA

    artifacts = DATA.resolve()
    for r in selected:
        refs = {
            e.get("screenshot")
            for e in r.get("stage_events", []) + r.get("events", [])
            if isinstance(e.get("screenshot"), str)
        }
        for ref in refs:
            if not ref.startswith("/artifacts/"):
                continue
            relative = Path(ref.removeprefix("/artifacts/"))
            if not relative.parts or relative.parts[0] != r["id"]:
                continue
            path = (artifacts / relative).resolve()
            if (
                artifacts not in path.parents
                or path.suffix.lower() not in (".png", ".jpg", ".webp")
                or not path.is_file()
            ):
                continue
            files["artifacts/" + str(relative)] = path.read_bytes()
    files["SHA256SUMS.json"] = dump(
        {
            k: hashlib.sha256(v.encode() if isinstance(v, str) else v).hexdigest()
            for k, v in files.items()
        }
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in sorted(files.items()):
            info = zipfile.ZipInfo(k, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, v)
    return out.getvalue()


def scatter(rows):
    points = [
        r
        for r in rows
        if r.get("median_successful_seconds") is not None
        and r["task_resolution"]["rate"] is not None
    ]
    if not points:
        return chart("Accuracy versus successful completion time", [])
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (
        PLOT_LOCK,
        plt.rc_context({"svg.hashsalt": "checkoutbench-v3", "svg.fonttype": "none"}),
    ):
        fig, ax = plt.subplots(figsize=(10, 5))
        for r in points:
            x = r["median_successful_seconds"]
            y = r["task_resolution"]["rate"]
            ax.scatter(x, y, s=55)
            ax.annotate(
                f"{r['model']} (n={r['valid_trials']})",
                (x, y),
                xytext=(6, 6),
                textcoords="offset points",
            )
        ax.set(
            xlabel="Median successful resolution time (seconds)",
            ylabel="Observed task-resolution fraction",
            ylim=(-0.05, 1.1),
            title="Synthetic accuracy versus speed · descriptive observations",
        )
        ax.grid(alpha=0.2)
        fig.tight_layout()
        out = io.StringIO()
        fig.savefig(
            out,
            format="svg",
            metadata={"Date": None, "Creator": "CheckoutBench / Matplotlib"},
        )
        plt.close(fig)
        return out.getvalue()
