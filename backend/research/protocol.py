"""Frozen manifests, review gates and reproducible execution records."""

import hashlib, json, platform, subprocess, sys
from pathlib import Path
from scenarios.research import ROOT, RELEASE, build_manifest, digest, scenario_research
from backend.storage.database import DATA

FROZEN = ROOT / "research/release.json"


def source_hashes():
    paths = [
        p
        for folder in ("backend", "scenarios", "checkout_fixtures", "scripts/research")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in (".py", ".js", ".css", ".html")
    ]
    paths += [
        ROOT / p
        for p in ("pyproject.toml", "uv.lock", "research/model-provenance.json")
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }


def freeze():
    m = build_manifest()
    m["source_hashes"] = source_hashes()
    m["source_hash"] = digest(m["source_hashes"])
    m["release_hash"] = digest(m)
    FROZEN.write_text(json.dumps(m, indent=2) + "\n")
    return m


def release(verify=False):
    if not FROZEN.exists():
        raise ValueError("Research release has not been frozen")
    m = json.loads(FROZEN.read_text())
    if verify and (
        build_manifest()["manifest_hash"] != m["manifest_hash"]
        or source_hashes() != m["source_hashes"]
    ):
        raise ValueError(
            "Frozen research release differs from source; audit and freeze a new release before execution"
        )
    return m


def review_status(manifest):
    path = ROOT / "research/ground-truth-reviews.json"
    reviews = json.loads(path.read_text()) if path.exists() else []
    # Latest dated review entry supersedes earlier approvals, including disputes.
    reviews = list({r.get("scenario_hash"): r for r in reviews}.values())
    accepted = {
        r["scenario_hash"]
        for r in reviews
        if r.get("decision") == "approved"
        and r.get("reviewer_kind") == "independent_human"
        and r.get("reviewer")
        and all(
            r.get("checks", {}).get(k) is True
            for k in (
                "understandable",
                "data_available",
                "solvable",
                "unambiguous",
                "optional_fields",
                "payment_appropriate",
                "authentication_respected",
                "negative_controls",
            )
        )
    }
    pending = [
        s["id"] for s in manifest["scenarios"] if s["scenario_hash"] not in accepted
    ]
    return {
        "approved": len(manifest["scenarios"]) - len(pending),
        "pending": pending,
        "independent_human_review_complete": not pending,
    }


def checkpoint_records():
    path = DATA / "research/checkpoint-verification.json"
    return json.loads(path.read_text()) if path.exists() else {}


def readiness():
    m = release()
    reviews = review_status(m)
    verified = checkpoint_records()
    checks = {
        "frozen_sources_match": m["source_hashes"] == source_hashes(),
        "ground_truth_independently_reviewed": reviews[
            "independent_human_review_complete"
        ],
        "all_four_checkpoints_verified": all(
            verified.get(k, {}).get("verified")
            for k in ("cua-s1", "tinyclick", "mai-ui", "ui-venus")
        ),
        "genuine_hybrid_smoke": verified.get("hybrid", {}).get("verified", False),
        "sealed_holdout_independently_validated": False,
        "official_sandbox_browser_validation": False,
        "independent_reproduction": False,
    }
    ev = ROOT / "research/validation-evidence.json"
    e = json.loads(ev.read_text()) if ev.exists() else {}
    if e.get("release_hash") != m["release_hash"]:
        e = {}
    checks.update(
        regression_passed=e.get("regression_passed", False),
        measurement_negative_controls_passed=e.get(
            "measurement_negative_controls_passed", False
        ),
        cluster_statistics_tested=e.get("cluster_statistics_tested", False),
        controlled_matrices_tested=e.get("controlled_matrices_tested", False),
    )
    external_path = ROOT / "research/external-validation.json"
    external = json.loads(external_path.read_text()) if external_path.exists() else {}
    if external.get("release_hash") == m["release_hash"] and external.get(
        "independent_reviewer"
    ):
        for key in (
            "sealed_holdout_independently_validated",
            "official_sandbox_browser_validation",
            "independent_reproduction",
        ):
            record = external.get(key, {})
            checks[key] = (
                record.get("passed") is True
                and bool(record.get("evidence_sha256"))
                and bool(record.get("reviewed_at"))
            )
    checks["historical_data_preserved"] = e.get("historical_data_preserved", False)
    checks["stage_events_and_denominators_tested"] = e.get(
        "stage_events_and_denominators_tested", False
    )
    checks["sufficient_independent_coverage"] = (
        bool(external.get("independent_coverage_approved"))
        and external.get("release_hash") == m["release_hash"]
    )
    pilot = all(
        checks[k]
        for k in (
            "frozen_sources_match",
            "ground_truth_independently_reviewed",
            "all_four_checkpoints_verified",
            "genuine_hybrid_smoke",
            "regression_passed",
            "measurement_negative_controls_passed",
            "cluster_statistics_tested",
            "controlled_matrices_tested",
            "historical_data_preserved",
            "stage_events_and_denominators_tested",
        )
    )
    return {
        "status": (
            "READY FOR EXTERNAL VALIDATION"
            if pilot
            and checks["sealed_holdout_independently_validated"]
            and checks["official_sandbox_browser_validation"]
            and checks["sufficient_independent_coverage"]
            and e.get("controlled_public_run_reviewed")
            else "READY FOR CONTROLLED PUBLIC BENCHMARK"
            if pilot
            and checks["sealed_holdout_independently_validated"]
            and checks["official_sandbox_browser_validation"]
            and checks["sufficient_independent_coverage"]
            else "READY FOR PILOT"
            if pilot
            else "NOT READY"
        ),
        "checks": checks,
        "blockers": [k for k, v in checks.items() if not v],
        "human_review": reviews,
        "checkpoints": verified,
        "scope": "Synthetic benchmark only; no external validity or reproduction claim",
        "release": m["release"],
    }


def validate_standard(config):
    m = release(verify=True)
    if (
        config.get("research_release") != m["release"]
        or config.get("release_hash") != m["release_hash"]
    ):
        raise ValueError("Frozen release/hash required")
    if config["scenarios"] != m["scenario_ids"]:
        raise ValueError(
            "Run All requires the entire ordered active manifest; no subsets or sealed cases"
        )
    if config["seed"] != m["seed"] or config.get("profile") is not None:
        raise ValueError(
            "Frozen scenario seed and scenario-default profiles are required"
        )
    if config.get("agent_mode", "standard") != "standard":
        raise ValueError(
            "Run All uses standard mode; ablations use separate developer protocols"
        )
    records = validate_checkpoints(config["models"])
    for model in config["models"]:
        required = ["cua-s1", "tinyclick", "hybrid"] if model == "hybrid" else [model]
        if model != "reference" and any(
            not records.get(k, {}).get("verified") for k in required
        ):
            raise ValueError(
                f"{model}: verified checkpoint and genuine inference smoke evidence required"
            )
    return m


def execution_manifest(config, s, model, browser_version=None):
    settings = {
        k: v
        for k, v in config.items()
        if k not in ("models", "scenarios", "spending_cap")
    }
    m = release()
    return {
        "benchmark_version": "3.0",
        "fixture_engine_version": "2.1",
        "research_release": m["release"],
        "release_hash": m["release_hash"],
        "scenario_hash": digest(s),
        "independence_cluster": "shared-synthetic-engine",
        "implementation_family": s.get("implementation_family", "shared-v21-client"),
        "research_track": s.get("research_track"),
        "research_split": s.get("research_split"),
        "research_protocol_hash": digest(
            {"settings": settings, "release_hash": m["release_hash"]}
        ),
        "execution_manifest": {
            "standard_run_all": config.get("research_release") == m["release"]
            and config.get("scenarios") == m["scenario_ids"],
            "settings": settings,
            "scenario_manifest_hash": m["manifest_hash"],
            "source_hash": m["source_hash"],
            "checkpoint": checkpoint_records().get(model),
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "browser_version": browser_version,
            "adapter_hash": m["source_hashes"].get("backend/adapters/specialists.py"),
            "warmup": "none; new adapter per trial",
            "precision": "recorded by inference backend; missing values are not inferred",
            "quantisation": None,
            "cost_calculation": "actual reported / estimated / unknown as labelled per call",
            "sequential": True,
        },
    }


def validate_checkpoints(models):
    """Revalidate local binding at execution time; a past smoke is not a permanent flag."""
    from backend.adapters.specialists import SPECS, detect_hardware
    from scripts.research.verify_models import sha, runtime_versions
    import os

    records = checkpoint_records()
    for model in models:
        if model == "reference":
            continue
        required = ["cua-s1", "tinyclick", "hybrid"] if model == "hybrid" else [model]
        for key in required:
            r = records.get(key, {})
            if not r.get("verified"):
                raise ValueError(
                    f"{key}: exact checkpoint and real inference verification required"
                )
            if key == "hybrid":
                continue
            prefix = SPECS[key][0]
            device = os.getenv(prefix + "_DEVICE", "auto")
            if device == "auto":
                device = detect_hardware()["device"]
            if (
                str(device).removesuffix(":0")
                != str(r.get("device")).removesuffix(":0")
                or r.get("runtime_versions") != runtime_versions()
            ):
                raise ValueError(f"{key}: device/runtime changed; verify again")
            path = os.getenv(prefix + "_MODEL_PATH", "")
            if os.getenv(prefix + "_ENDPOINT"):
                raise ValueError(
                    f"{key}: verified local evidence cannot attest a remote endpoint"
                )
            root = Path(path)
            if root.is_file():
                root = root.parent
            if not path or digest(str(root.resolve())) != r.get("binding_hash"):
                raise ValueError(
                    f"{key}: checkpoint configuration changed; verify again"
                )
            if sha(ROOT / "backend/adapters/specialists.py") != r.get("adapter_hash"):
                raise ValueError(f"{key}: adapter changed; verify again")
            if any(
                not (root / f).is_file() or sha(root / f) != h
                for f, h in r.get("checkpoint_hashes", {}).items()
            ):
                raise ValueError(f"{key}: checkpoint files changed; verify again")
            if key == "cua-s1":
                import cua_s1.model as module

                if sha(module.__file__) != r.get("loader_hash"):
                    raise ValueError("CUA loader changed; verify again")
    return records
