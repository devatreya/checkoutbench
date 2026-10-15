"""Explicit research lifecycle operations. Never approves a review automatically."""

import argparse, json
from pathlib import Path
from backend.research.protocol import freeze, release, readiness
from backend.research.export import bundle
from backend.storage.database import runs
from scenarios.research import ROOT, scenario_research


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    sub.add_parser("readiness")
    ex = sub.add_parser("export")
    ex.add_argument("--output", default="data/research/export.zip")
    official = sub.add_parser("configure-official")
    official.add_argument("config", help="Complete Batch JSON; explicit settings and verified models")
    rv = sub.add_parser("review-packet")
    rv.add_argument("--output", default="data/research/review-packet.json")
    im = sub.add_parser("import-review")
    im.add_argument("file")
    seal = sub.add_parser("seal")
    seal.add_argument("bundle")
    seal.add_argument("review")
    final = sub.add_parser("reserve-final")
    final.add_argument("protocol")
    final.add_argument("checkpoints")
    final.add_argument("evaluator")
    a = p.parse_args()
    if a.command == "freeze":
        print(
            json.dumps(
                {
                    k: v
                    for k, v in freeze().items()
                    if k in ("release", "release_hash", "scenario_count")
                },
                indent=2,
            )
        )
    elif a.command == "configure-official":
        from backend.app import Batch
        from backend.research.official import configure
        print(json.dumps(configure(Batch(**json.loads(Path(a.config).read_text())).model_dump()), indent=2))
    elif a.command == "readiness":
        print(json.dumps(readiness(), indent=2))
    elif a.command == "export":
        path = Path(a.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundle(runs()))
        print(path)
    elif a.command == "review-packet":
        from scenarios.catalog import task

        m = release()
        packet = [
            {
                "scenario": s,
                "task": task(scenario_research(s["id"])),
                "private_truth": scenario_research(s["id"])["expected_values"],
                "review": {
                    "scenario_hash": s["scenario_hash"],
                    "reviewer": "",
                    "reviewer_kind": "independent_human",
                    "reviewed_at": "",
                    "decision": "pending",
                    "dispute": "",
                    "checks": {
                        k: False
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
                    },
                },
            }
            for s in m["scenarios"]
        ]
        path = Path(a.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet, indent=2) + "\n")
        print(path)
    elif a.command == "import-review":
        incoming = json.loads(Path(a.file).read_text())
        allowed = {s["scenario_hash"] for s in release()["scenarios"]}
        if not isinstance(incoming, list) or any(
            r.get("scenario_hash") not in allowed
            or not r.get("reviewer")
            or not r.get("reviewed_at")
            or r.get("decision") not in ("approved", "disputed", "rejected")
            or r.get("reviewer_kind") != "independent_human"
            for r in incoming
        ):
            raise ValueError(
                "Signed, dated independent human review rows for exact scenario hashes required"
            )
        path = ROOT / "research/ground-truth-reviews.json"
        previous = json.loads(path.read_text()) if path.exists() else []
        path.write_text(json.dumps(previous + incoming, indent=2) + "\n")
        print("Review records imported; disputes remain publication blockers")
    elif a.command == "seal":
        from backend.research.holdout import seal

        print(json.dumps(seal(Path(a.bundle), Path(a.review)), indent=2))
    elif a.command == "reserve-final":
        from backend.research.holdout import claim_final

        print(
            json.dumps(
                claim_final(
                    a.protocol, json.loads(Path(a.checkpoints).read_text()), a.evaluator
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
