"""Explicit runtime audits linked to an immutable scenario release.

This is an integrity binding, not a publisher signature or automatic approval.
Creating a candidate never approves it. Runtime changes require a reviewed
artifact, while canonical tasks, fixture markup and objective scoring stay fixed.
"""

import hashlib
import json
from pathlib import Path

from scenarios.research import digest

ROOT = Path(__file__).resolve().parents[2]
BINDING_FILE = "research/runtime-binding.json"
BASELINE_FILE = "research/scenario-integrity-baseline.json"
SCHEMA = "checkoutbench-runtime-binding-1"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_canonical_hashes():
    """Hash every original scenario object, without display metadata or filtering."""
    from scenarios.catalog import SPECS, scenario
    from scenarios.v2 import V2_SPECS
    from scenarios.v21 import V21_SPECS
    from scenarios.research import SPECS as RESEARCH_SPECS

    ids = [row[0] for row in SPECS]
    ids += [row["id"] for row in (*V2_SPECS, *V21_SPECS, *RESEARCH_SPECS)]
    if len(ids) != len(set(ids)):
        raise ValueError("Canonical scenario IDs are not unique")
    return {sid: digest(scenario(sid)) for sid in sorted(ids)}


def _changes(frozen, current):
    return {
        path: {"before": frozen.get(path), "after": current.get(path)}
        for path in sorted(set(frozen) | set(current))
        if frozen.get(path) != current.get(path)
    }


def _protected(path):
    return (
        path.startswith("checkout_fixtures/")
        or (path.startswith("scenarios/") and path not in {
            "scenarios/catalog.py", "scenarios/identity.py", "scenarios/identities.json"
        })
        or path in {
            "backend/fixtures.py", "backend/evaluator/scoring.py",
            "backend/evaluator/v2.py",
        }
    )


def _scenario_proof(manifest, current_sources):
    baseline_path = ROOT / BASELINE_FILE
    try:
        baseline = json.loads(baseline_path.read_text())
        expected = baseline["canonical_scenario_hashes"]
        files = baseline["file_hashes"]
        frozen_file_hash = files["research/release.json"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("An explicit canonical scenario integrity baseline is required") from exc
    if not isinstance(expected, dict) or not expected:
        raise ValueError("Canonical scenario baseline is empty or invalid")
    if _sha(ROOT / "research/release.json") != frozen_file_hash:
        raise ValueError("Frozen release file changed; a runtime binding cannot replace it")
    # This catalog wrapper may resolve aliases, but its canonical output must
    # remain exactly equal for every inventoried scenario, including old IDs.
    actual = current_canonical_hashes()
    if actual != expected:
        raise ValueError("Canonical scenario objects differ from the audited baseline")
    for path, expected_hash in files.items():
        if path == "scenarios/catalog.py":
            continue
        target = ROOT / path
        if not target.is_file() or _sha(target) != expected_hash:
            raise ValueError(f"Protected canonical file changed: {path}")
    changes = _changes(manifest["source_hashes"], current_sources)
    forbidden = [path for path in changes if _protected(path)]
    if forbidden:
        raise ValueError("Runtime binding cannot modify canonical fixture/scoring sources: " + ", ".join(forbidden))
    return {
        "baseline_sha256": _sha(baseline_path),
        "frozen_release_file_sha256": frozen_file_hash,
        "canonical_scenario_count": len(actual),
        "canonical_scenario_hashes_sha256": digest(actual),
    }


def create_binding(manifest, current_sources, *, review=None):
    """Build a candidate; only an explicit final review can mark it approved.

    The caller owns persistence. No runtime execution path should call this
    function to manufacture approval for its own changed sources.
    """
    proof = _scenario_proof(manifest, current_sources)
    binding = {
        "schema": SCHEMA,
        "frozen_release_hash": manifest["release_hash"],
        "scenario_manifest_hash": manifest["manifest_hash"],
        "frozen_source_hash": manifest["source_hash"],
        "source_hash": digest(current_sources),
        "source_hashes": dict(current_sources),
        "changes": _changes(manifest["source_hashes"], current_sources),
        "scenario_integrity": proof,
        "review": review or {"status": "pending"},
    }
    binding["binding_hash"] = digest(binding)
    return binding


def audited_runtime(manifest, current_sources):
    """Return None for original sources, otherwise require an exact reviewed audit.

    Callers must independently verify the frozen scenario manifest. A returned
    binding is a distinct execution protocol and must not pool with old runs.
    """
    if current_sources == manifest["source_hashes"]:
        return None
    try:
        binding = json.loads((ROOT / BINDING_FILE).read_text())
    except (OSError, ValueError) as exc:
        raise ValueError("Runtime sources changed; an explicit reviewed runtime binding is required") from exc
    if not isinstance(binding, dict):
        raise ValueError("Runtime binding must be an object")
    unsigned = {k: v for k, v in binding.items() if k != "binding_hash"}
    if binding.get("binding_hash") != digest(unsigned):
        raise ValueError("Runtime binding hash failed integrity verification")
    review = binding.get("review")
    if not isinstance(review, dict) or not (
        review.get("status") == "approved"
        and isinstance(review.get("reviewer"), str) and review["reviewer"].strip()
        and isinstance(review.get("summary"), str) and review["summary"].strip()
    ):
        raise ValueError("Runtime binding has not received explicit final review")
    expected = create_binding(manifest, current_sources, review=review)
    if binding != expected:
        raise ValueError("Runtime binding differs from current sources, release or canonical scenario proof")
    return binding
