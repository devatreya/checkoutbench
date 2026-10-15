"""Seal an externally authored fixture bundle; no ordinary preview or task registration.

This is access control for the benchmark workflow, not secrecy from the machine owner.
A custodian must author and independently validate the final corpus outside development.
"""

import hashlib, json, os
from pathlib import Path
from datetime import datetime, timezone
from backend.storage.database import DATA
from scenarios.research import ROOT, digest

VAULT = DATA / "research/sealed"
PUBLIC = ROOT / "research/sealed-commitments.json"


def seal(bundle: Path, review: Path):
    evidence = json.loads(review.read_text())
    required = (
        "author",
        "independent_reviewer",
        "reviewed_at",
        "implementation_ids",
        "no_development_overlap",
        "solvable",
        "negative_controls_passed",
    )
    if (
        any(not evidence.get(k) for k in required)
        or evidence["author"] == evidence["independent_reviewer"]
    ):
        raise ValueError(
            "Independent author/reviewer and completed solvability/negative controls are required"
        )
    from scenarios.research import build_manifest

    if set(evidence["implementation_ids"]) & {
        s["implementation_family"] for s in build_manifest()["scenarios"]
    }:
        raise ValueError("Holdout implementations overlap development/validation")
    if PUBLIC.exists():
        raise ValueError(
            "A sealed commitment already exists; create a new benchmark release instead of replacing it"
        )
    content = bundle.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    VAULT.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = VAULT / (sha + ".zip")
    path.write_bytes(content)
    path.chmod(0o600)
    (VAULT / (sha + ".review.json")).write_text(json.dumps(evidence, indent=2))
    record = {
        "sha256": sha,
        "bytes": len(content),
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "review_hash": digest(evidence),
        "implementation_count": len(evidence["implementation_ids"]),
        "status": "sealed; never used in development",
    }
    PUBLIC.write_text(json.dumps(record, indent=2) + "\n")
    return record


def claim_final(protocol_hash: str, checkpoint_hashes: dict, evaluator: str):
    """One-use reservation before the custodian releases the evaluation bundle."""
    if not PUBLIC.exists():
        raise ValueError("No independently reviewed sealed bundle supplied")
    if not protocol_hash or not checkpoint_hashes or not evaluator:
        raise ValueError("Frozen protocol, checkpoint hashes and evaluator required")
    commit = json.loads(PUBLIC.read_text())
    path = VAULT / (commit["sha256"] + ".zip")
    if hashlib.sha256(path.read_bytes()).hexdigest() != commit["sha256"]:
        raise ValueError("Sealed bundle was modified")
    reservation = {
        "protocol_hash": protocol_hash,
        "checkpoint_hashes": checkpoint_hashes,
        "evaluator": evaluator,
        "claimed_at": datetime.now(timezone.utc).isoformat(),
        "commitment": commit["sha256"],
    }
    # Exclusive creation prevents rerunning the final corpus under a new tuned configuration.
    with (VAULT / "final-reservation.json").open("x") as f:
        json.dump(reservation, f, indent=2)
    return reservation
