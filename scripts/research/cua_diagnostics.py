"""Pinned local CUA diagnostics, without browser/server or result-store writes.

Default stdout is a value-free summary. --include-sensitive writes exact inputs
and byte IDs to a NEW mode-0600 file; never overwrite evidence. No downloads.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import platform
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.adapters.specialists import CUA_INPUT_PROTOCOLS, CuaS1Adapter

ROOT = Path(__file__).resolve().parents[2]
MODEL_REVISION = "4a7a9f42a3d42e6dfbd111c0c843e37ac50f1332"
LOADER_REVISION = "6d82b3b1b21813ad047f966ab1384a1258c16170"
PINNED_HASHES = {
    "cua-s1-forms.safetensors": "05954c1caf51c2fb6c13ea4acbfc88a2e7653dea192252bb51dc89e76a356ddc",
    "cua-s1-forms.json": "62d31e2f9a001a8e9b6f8534c5194d07ebdd3f9d62ef1ac281906622992650ca",
    "model.py": "7538cb4c9730d70a0b325050f370f981a9e109a1b182b8c66be3ba0fa2474344",
    "checkpoint.py": "724c42cf2955cf7d8991c08b14369afc9be3b408835ceec52bdc10cfd41ab61b",
}
DEVELOPMENT_CASES = ("V21-G01", "V21-S01", "V21-ST03")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_identity(model_path):
    from cua_s1 import checkpoint, model

    path = Path(model_path)
    weight = path / "cua-s1-forms.safetensors" if path.is_dir() else path
    files = {
        "cua-s1-forms.safetensors": weight,
        "cua-s1-forms.json": weight.with_suffix(".json"),
        "model.py": Path(model.__file__),
        "checkpoint.py": Path(checkpoint.__file__),
    }
    hashes = {name: sha(path) for name, path in files.items()}
    if hashes != PINNED_HASHES:
        raise ValueError(
            "Checkpoint/config/loader does not match the audited pinned artifacts"
        )
    return {
        "model_revision": MODEL_REVISION,
        "loader_revision": LOADER_REVISION,
        "sha256": hashes,
    }


def public_case(s):
    """One-way public projection; field keys/DOM IDs/truth never enter inference."""
    return {
        "profile": copy.deepcopy(s["customer_brief"]),
        "elements": [
            {
                "label": f["label"],
                "role": "checkbox"
                if f["kind"] == "checkbox"
                else "combobox"
                if f.get("options")
                else "textbox",
                "value": "",
                "form_title": f.get("section", "Checkout"),
            }
            for f in s["fields"]
        ],
    }


def development_cases():
    from scenarios.v21 import scenario_v21

    return {
        sid: public_case(scenario_v21(sid, 2026, "aditi")) for sid in DEVELOPMENT_CASES
    }


def control_cases():
    # Separate synthetic contract controls, never benchmark accuracy examples.
    profile = {
        "Email": "person@example.invalid",
        "Full name": "Example Person",
        "City": "Boston",
    }
    elements = [
        {"label": label, "role": "textbox", "value": "", "form_title": "Registration"}
        for label in ("Email address", "Full name", "City")
    ]
    elements += [
        dict(elements[0], value=profile["Email"]),
        {
            "label": "I agree to the terms and conditions",
            "role": "checkbox",
            "value": "false",
            "form_title": "Registration",
        },
        {
            "label": "I agree to the terms and conditions",
            "role": "checkbox",
            "value": "true",
            "form_title": "Registration",
        },
        {
            "label": "Submit",
            "role": "button",
            "value": "",
            "form_title": "Registration",
        },
    ]
    crowded = dict(profile)
    # Increasing irrelevant candidate count tests interference without pruning
    # any actual customer brief or selecting candidates by the target label.
    crowded.update({f"Reference {i}": f"SYNTHETIC-{i:04d}" for i in range(72)})
    return {
        "contract-controls": {"profile": profile, "elements": elements},
        "candidate-count-control": {"profile": crowded, "elements": elements},
        "candidate-order-control": {
            "profile": dict(reversed(list(crowded.items()))),
            "elements": elements,
        },
    }


async def infer_cases(adapter, cases):
    """Actual adapter path; this function has no scenario/evaluator access."""
    records = []
    for case_name, case in cases.items():
        if set(case) != {"elements", "profile"}:
            raise ValueError("Each public case must contain only elements and profile")
        # One field per call matches the original controller's batching policy.
        for i, element in enumerate(case["elements"]):
            output = (await adapter.score_fields([element], case["profile"]))[0]
            if output["inference_kind"] != "actual_model":
                raise ValueError("Diagnostics require actual local model inference")
            scores = output["distribution"]
            top = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:5]
            records.append(
                {
                    "case": case_name,
                    "field_index": i,
                    "label": element["label"],
                    "output": output,
                    "top_indices": top,
                    "metrics": copy.deepcopy(adapter.last_metrics),
                }
            )
        # Re-observe the first field with the model-selected value, without a
        # browser or a semantic repair. This reproduces the nonempty-state
        # mechanism behind the original second email decision.
        if case_name in DEVELOPMENT_CASES:
            first = records[-len(case["elements"])]["output"]
            if first["action"] == "fill":
                revisited = dict(case["elements"][0], value=first["value"])
                records += await infer_cases(
                    adapter,
                    {
                        case_name + "-selected-value-revisit": {
                            "profile": case["profile"],
                            "elements": [revisited],
                        }
                    },
                )
    return records


def original_run_audit(database, run_id):
    from backend.evaluator.semantic import decision_report
    from scenarios.v21 import scenario_v21

    with sqlite3.connect(
        Path(database).resolve().as_uri() + "?mode=ro", uri=True
    ) as conn:
        row = conn.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("Original run not found")
    record = json.loads(row[0])
    scenario = scenario_v21(record["scenario"], record["seed"], record["profile_id"])
    report = decision_report(scenario, record["semantic_decisions"])
    # These legacy records lack entity pointers/distributions and cannot supply
    # exact historical probabilities. A replay must not be passed off as one.
    return {
        "run_id": run_id,
        "record_sha256": hashlib.sha256(row[0].encode()).hexdigest(),
        "recorded_accuracy": record.get("field_classification_accuracy"),
        "recorded_samples": record.get("field_classification_samples"),
        "recorded_calls": [
            {
                k: c[k]
                for k in (
                    "model",
                    "operation",
                    "seconds",
                    "call_temperature",
                    "backend",
                    "cold_model_loading_seconds",
                    "warm_inference_seconds",
                )
                if k in c
            }
            for c in record.get("calls", [])
        ],
        "measurement": report,
        "limitation": "Original record lacks serialized contexts/options, entity pointers and probabilities",
    }


def public_summary(report):
    """Exclude values and reversible byte encodings, retain probability evidence."""
    result = {k: v for k, v in report.items() if k != "records"}
    result["records"] = []
    for r in report["records"]:
        out = r["output"]
        inputs = out["model_input"]
        keys = inputs["entity_keys"] + ["check", "click", "skip"]
        result["records"].append(
            {
                "case": r["case"],
                "field_index": r["field_index"],
                "label": r["label"],
                "input_protocol": out["input_protocol"],
                "action": out["action"],
                "entity_key": out["entity_key"],
                "selected_index": out["selected_index"],
                "confidence": out["confidence"],
                "distribution": out["distribution"],
                "candidate_keys": keys,
                "metrics": r["metrics"],
                "context_sha256": hashlib.sha256(
                    inputs["context"].encode()
                ).hexdigest(),
                "options_sha256": hashlib.sha256(
                    json.dumps(inputs["options"]).encode()
                ).hexdigest(),
                "context_truncated": inputs["context_encoding"]["truncated"],
                "truncated_option_indices": [
                    i
                    for i, t in enumerate(inputs["option_encodings"])
                    if t["truncated"]
                ],
                "top_alternatives": [
                    {
                        "index": i,
                        "entity_or_action": keys[i],
                        "probability": out["distribution"][i],
                    }
                    for i in r["top_indices"]
                ],
            }
        )
    return result


def write_private(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


async def run(args):
    from importlib.metadata import version

    import torch

    if not args.model_path:
        raise ValueError("--model-path or CUA_S1_MODEL_PATH is required")
    identity = verify_identity(args.model_path)
    cases = (
        json.loads(args.input.read_text())
        if args.input
        else development_cases() | control_cases()
    )
    report = {
        "format": "checkoutbench-cua-diagnostics-1",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "development and synthetic contract diagnostics; not end-to-end/holdout results",
        "identity": identity,
        "runtime": {
            "torch": torch.__version__,
            "safetensors": version("safetensors"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "device": args.device,
            "threads": torch.get_num_threads(),
        },
        "adapter_sha256": sha(ROOT / "backend/adapters/specialists.py"),
        "diagnostic_sha256": sha(__file__),
        "records": [],
    }
    for protocol in args.protocols:
        adapter = CuaS1Adapter(
            device=args.device, diagnostics=True, input_protocol=protocol
        )
        adapter.path = str(args.model_path)
        adapter.endpoint = ""  # This tool only verifies local checkpoints.
        report["records"] += await infer_cases(adapter, cases)
        report["configuration"] = adapter.checkpoint_identity
        report["parameters"] = sum(p.numel() for p in adapter.model.parameters())
        report["precision"] = str(next(adapter.model.parameters()).dtype)
        # Explicit cold/warm repeat on exactly the same input.
        first = next(iter(cases.values()))
        repeat = await infer_cases(
            adapter,
            {
                "warm-repeat": {
                    "profile": first["profile"],
                    "elements": first["elements"][:1],
                }
            },
        )
        report["records"] += repeat
    if args.original_db:
        report["original_run"] = original_run_audit(args.original_db, args.run_id)
    summary = public_summary(report)
    if args.output:
        write_private(args.output, report if args.include_sensitive else summary)
    if args.summary_output:
        write_private(args.summary_output, summary)
    # No customer/payment values in console output.
    for r in summary["records"]:
        print(
            json.dumps(
                {
                    k: r[k]
                    for k in (
                        "case",
                        "field_index",
                        "input_protocol",
                        "action",
                        "entity_key",
                        "confidence",
                        "top_alternatives",
                    )
                }
            )
        )
    if "original_run" in summary:
        print(
            json.dumps(
                {
                    "original_accuracy": summary["original_run"]["measurement"][
                        "field_classification_accuracy"
                    ],
                    "original_samples": summary["original_run"]["measurement"][
                        "scored_decisions"
                    ],
                }
            )
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", default=os.getenv("CUA_S1_MODEL_PATH"))
    parser.add_argument("--device", default="cpu", choices=("cpu", "mps", "cuda"))
    parser.add_argument(
        "--protocols",
        nargs="+",
        default=list(CUA_INPUT_PROTOCOLS),
        choices=CUA_INPUT_PROTOCOLS,
    )
    parser.add_argument(
        "--input", type=Path, help="JSON mapping case names to public elements/profile"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--include-sensitive", action="store_true")
    parser.add_argument("--original-db", type=Path)
    parser.add_argument("--run-id", default="6c30aaa4aebf45b0b57c84ea4f1756f1")
    args = parser.parse_args()
    if args.include_sensitive and not args.output:
        parser.error("--include-sensitive requires --output (never raw stdout)")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
