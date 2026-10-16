"""Preregistered paired CUA experiment; reuse the audited adapter, never a runner DB.

Public condition construction and actual inference have no evaluator truth.
Scenario construction is projected to public inputs; private truth is never
consulted for inference. Separate grading starts after ALL forwards finish.
"""
from __future__ import annotations

import copy
import hashlib
import json
import platform
from collections import defaultdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from backend.adapters.specialists import CuaS1Adapter, cua_inputs
from scripts.research.cua_diagnostics import (
    ROOT,
    control_cases,
    development_cases,
    sha,
    verify_identity,
    write_private,
)

PROTOCOL_PATH = ROOT / "research/cua-generalization-protocol.json"
CONDITIONS = ("A", "B", "C", "D")


def digest(value):
    # Preserve insertion order: candidate ordering is experimentally material.
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load_protocol(path=PROTOCOL_PATH):
    protocol = json.loads(Path(path).read_text())
    if protocol["experiment_id"] != "cua-generalization-factorial-v1":
        raise ValueError("Unknown experiment protocol")
    if tuple(protocol["conditions"]) != CONDITIONS:
        raise ValueError("Conditions must be preregistered A/B/C/D")
    return protocol


def public_snapshots():
    return development_cases() | {"contract-controls": control_cases()["contract-controls"]}


def mapping_for(protocol, case, index, element):
    rows = [r for r in protocol["mappings"] if r["case"] == case and r["field_index"] == index]
    if case == "contract-controls":
        return {"original_label": element["label"], "familiar_label": element["label"], "eligibility": "synthetic_control"}
    if len(rows) != 1 or rows[0]["original_label"] != element["label"]:
        raise ValueError("Snapshot does not match the preregistered mapping")
    row = rows[0]
    if row["eligibility"] == "excluded" and row["original_label"] != row["familiar_label"]:
        raise ValueError("Excluded labels must remain unchanged")
    if row["eligibility"] == "changed" and row["original_label"] == row["familiar_label"]:
        raise ValueError("Changed label intervention must actually change label")
    return row


def condition_case(snapshot, mappings, condition, protocol, supplemental=False):
    if set(snapshot) != {"elements", "profile"}:
        raise ValueError("Public snapshot accepts only elements and profile")
    allowed = {"label", "role", "value", "form_title", "placeholder", "checked"}
    if any(set(e) - allowed for e in snapshot["elements"]):
        raise ValueError("Unexpected field metadata in public snapshot")
    result = copy.deepcopy(snapshot)
    if protocol["conditions"][condition]["labels"] == "familiar":
        for element, mapping in zip(result["elements"], mappings, strict=True):
            element["label"] = mapping["familiar_label"]
    if supplemental:
        extras = protocol["supplemental"]["entities"]
        if set(result["profile"]) & set(extras):
            raise ValueError("Distractors must not overwrite original candidates")
        result["profile"].update(copy.deepcopy(extras))
    return result


def build_design(protocol, cases=None):
    cases = public_snapshots() if cases is None else cases
    if tuple(cases) != (*protocol["development_cases"], "contract-controls"):
        raise ValueError("Case list differs from preregistration")
    design = {}
    audit = []
    for case, snapshot in cases.items():
        mappings = [mapping_for(protocol, case, i, e) for i, e in enumerate(snapshot["elements"])]
        for supplemental in (False, True):
            group = "supplemental" if supplemental else "primary"
            paired = {c: condition_case(snapshot, mappings, c, protocol, supplemental) for c in CONDITIONS}
            for i, original in enumerate(snapshot["elements"]):
                serialized = {}
                for c in CONDITIONS:
                    transformed = paired[c]
                    element = transformed["elements"][i]
                    before = {k: v for k, v in original.items() if k != "label"}
                    after = {k: v for k, v in element.items() if k != "label"}
                    if before != after:
                        raise ValueError("Intervention changed non-label field state")
                    entities, contexts, options = cua_inputs([element], transformed["profile"], protocol["conditions"][c]["serialization"])
                    serialized[c] = (entities, contexts, options)
                    design[(group, case, i, c)] = {
                        "element": copy.deepcopy(element),
                        "profile": copy.deepcopy(transformed["profile"]),
                        "mapping": copy.deepcopy(mappings[i]),
                        "entities": entities,
                        "contexts": contexts,
                        "options": options,
                    }
                if not all(serialized[c][0] == serialized["A"][0] for c in CONDITIONS):
                    raise ValueError("Candidate order/content/count invariant failed")
                if serialized["A"][2] != serialized["B"][2] or serialized["C"][2] != serialized["D"][2]:
                    raise ValueError("Label-only intervention changed options")
                if serialized["A"][1] != serialized["C"][1] or serialized["B"][1] != serialized["D"][1]:
                    raise ValueError("Serialization-only intervention changed context")
                audit.append({"group": group, "case": case, "field_index": i,
                              "field_id": f"{case}:{i}", "snapshot_sha256": digest(original),
                              "ordered_entities_sha256": digest(serialized["A"][0]),
                              "candidate_count": len(serialized["A"][0]),
                              "invariants_valid": True})
            if supplemental:
                for i in range(len(snapshot["elements"])):
                    original_entities = design[("primary", case, i, "A")]["entities"]
                    extra_entities = design[(group, case, i, "A")]["entities"]
                    if extra_entities[:len(original_entities)] != original_entities:
                        raise ValueError("Supplemental candidates changed original prefix")
                    if len(extra_entities) != len(original_entities) + len(protocol["supplemental"]["entities"]):
                        raise ValueError("Supplemental candidate count mismatch")
    return design, audit


def freeze_manifest(protocol_path=PROTOCOL_PATH):
    """Public hashes are fixed before any model is loaded or inference executes."""
    protocol = load_protocol(protocol_path)
    cases = public_snapshots()
    design, audit = build_design(protocol, cases)
    sources = ("scripts/diagnostics/cua_generalization.py", "scripts/research/cua_diagnostics.py",
               "backend/adapters/specialists.py", "backend/evaluator/semantic.py", "scenarios/v21.py")
    return {"experiment_id": protocol["experiment_id"], "protocol_sha256": sha(protocol_path),
            "public_snapshots_sha256": digest(cases), "design_sha256": digest(list(design.items())),
            "source_sha256": {p: sha(ROOT / p) for p in sources}, "invariants": audit,
            "planned_forward_calls": protocol["counts"]["total_forward_calls"]}


async def infer_design(design, adapters, protocol):
    """Forward passes only; caller cannot supply truth and no revisits occur."""
    records = []
    for key, item in design.items():
        group, case, index, condition = key
        adapter = adapters[condition]
        element, profile = copy.deepcopy(item["element"]), copy.deepcopy(item["profile"])
        before = digest((element, profile))
        result = await adapter.score_fields([element], profile)
        if len(result) != 1 or result[0].get("inference_kind") != "actual_model":
            raise ValueError("Every condition requires a genuine local model forward")
        if digest((element, profile)) != before:
            raise ValueError("Inference mutated its public snapshot")
        output = result[0]
        observed = output["model_input"]
        if (observed["context"] != item["contexts"][0]
                or observed["options"] != item["options"]
                or observed["entity_keys"] != [k for k, _ in item["entities"]]
                or output["candidate_count"] != len(item["entities"])):
            raise ValueError("Actual model inputs differ from frozen design")
        records.append({"group": group, "case": case, "field_index": index,
                        "field_id": f"{case}:{index}", "condition": condition,
                        "eligibility": item["mapping"]["eligibility"],
                        "original_label": item["mapping"]["original_label"],
                        "experimental_label": element["label"], "before_value": element.get("value", ""),
                        "role": element["role"], "output": output,
                        "metrics": copy.deepcopy(adapter.last_metrics), "repeat": False})
    # Repeat only after every primary and supplemental field pass, with the
    # identical public input. These never contribute to field denominators.
    repeat_case, repeat_index = protocol["reproduction"]["field"].split(":")
    for condition in CONDITIONS:
        key = ("primary", repeat_case, int(repeat_index), condition)
        repeated = await infer_one_repeat(design[key], adapters[condition], key)
        records.append(repeated)
    if len(records) != protocol["counts"]["total_forward_calls"]:
        raise ValueError("Forward count differs from preregistration")
    return records


async def infer_one_repeat(item, adapter, key):
    group, case, index, condition = key
    output = (await adapter.score_fields([copy.deepcopy(item["element"])], copy.deepcopy(item["profile"])))[0]
    if output.get("inference_kind") != "actual_model":
        raise ValueError("Reproducibility check requires actual inference")
    if output["model_input"]["context"] != item["contexts"][0] or output["model_input"]["options"] != item["options"]:
        raise ValueError("Repeat input mismatch")
    return {"group": group, "case": case, "field_index": index, "field_id": f"{case}:{index}",
            "condition": condition, "original_label": item["mapping"]["original_label"],
            "experimental_label": item["element"]["label"], "eligibility": item["mapping"]["eligibility"],
            "before_value": item["element"].get("value", ""), "role": item["element"]["role"],
            "output": output, "metrics": copy.deepcopy(adapter.last_metrics), "repeat": True}


def grade_records(records, protocol):
    """Private post-inference phase; preserves every failure, no model call."""
    from backend.evaluator.semantic import decision_report
    from scenarios.v21 import scenario_v21

    truths = {sid: scenario_v21(sid, protocol["seed"], protocol["profile_id"]) for sid in protocol["development_cases"]}
    control_values = ["person@example.invalid", "Example Person", "Boston", "person@example.invalid", "true", "true", None]
    control_actions = [{"fill"}, {"fill"}, {"fill"}, {"fill", "skip"}, {"check"}, {"skip", "check"}, {"click"}]
    graded = []
    for record in records:
        r = copy.deepcopy(record)
        output, index = r["output"], r["field_index"]
        action = output["action"]
        effective = output["value"] if action == "fill" else "true" if action == "check" else r["before_value"]
        if r["case"] == "contract-controls":
            r["action_contract_correct"] = action in control_actions[index] and (index == 6 or effective == control_values[index])
            if index == 6:
                r["scoring"] = {"scored": False, "unscored_reason": "button_action_contract_not_field_value"}
                graded.append(r)
                continue
            key = str(index)
            scenario = {"dom_ids": {key: key}, "expected_values": {key: control_values[index]},
                        "fields": [{"key": key, "kind": r["role"]}], "required_fields": [key], "optional_fields": []}
            handle = key
        else:
            scenario = truths[r["case"]]
            key = scenario["fields"][index]["key"]
            handle = scenario["dom_ids"][key]
        decision = {**output, "control_handle": handle, "value": effective,
                    "before_value": r["before_value"], "role": r["role"]}
        r["scoring"] = decision_report(scenario, [decision])["rows"][0]
        r["scoring"]["required_empty"] = r["scoring"]["required"] and r["before_value"] in ("", None, "false")
        graded.append(r)
    return graded


def fraction(n, d):
    return {"numerator": n, "denominator": d, "rate": n / d if d else None}


def metrics(rows):
    scored = [r for r in rows if r["scoring"]["scored"]]
    required = [r for r in scored if r["scoring"]["required_empty"]]
    optional = [r for r in scored if r["scoring"]["optional"]]
    wrong = [r for r in scored if not r["scoring"]["field_value_correct"]]
    wrong_skip = [r for r in required if r["output"]["action"] == "skip" and not r["scoring"]["field_value_correct"]]
    confidence = lambda group: {"count": len(group), "mean": sum(r["output"]["confidence"] for r in group) / len(group) if group else None,
                                "min": min((r["output"]["confidence"] for r in group), default=None),
                                "max": max((r["output"]["confidence"] for r in group), default=None),
                                "above_0_99": sum(r["output"]["confidence"] > .99 for r in group)}
    count = lambda group, key: sum(r["scoring"][key] for r in group)
    contract = [r for r in rows if "action_contract_correct" in r]
    wrong_values = count(scored, "wrong_value")
    return {"observations": len(rows), "unique_snapshot_fields": len({r["field_id"] for r in rows}),
            "field_value_accuracy": fraction(count(scored, "field_value_correct"), len(scored)),
            "strict_assignment_accuracy": fraction(count(scored, "strict_assignment_correct"), len(scored)),
            "required_empty_skip_rate": fraction(sum(r["output"]["action"] == "skip" for r in required), len(required)),
            "wrong_value_rate": fraction(wrong_values, len(scored)),
            "wrong_value_among_fills": fraction(wrong_values, sum(r["output"]["action"] == "fill" for r in scored)),
            "optional_acceptability": fraction(count(optional, "acceptable"), len(optional)),
            "incorrect_confidence": confidence(wrong), "incorrect_required_skip_confidence": confidence(wrong_skip),
            "action_contract_accuracy": fraction(sum(r["action_contract_correct"] for r in contract), len(contract))}


def transition(rows, before, after):
    pairs = defaultdict(dict)
    for r in rows:
        if r["condition"] in (before, after) and r["scoring"]["scored"]:
            if r["condition"] in pairs[r["field_id"]]:
                raise ValueError("Duplicate field/condition in paired denominator")
            pairs[r["field_id"]][r["condition"]] = r["scoring"]["field_value_correct"]
    counts = {"incorrect_to_correct": 0, "correct_to_incorrect": 0, "incorrect_to_incorrect": 0, "correct_to_correct": 0}
    fields = []
    for field, pair in pairs.items():
        if set(pair) != {before, after}:
            raise ValueError("Unpaired field in contrast")
        label = ("correct" if pair[before] else "incorrect") + "_to_" + ("correct" if pair[after] else "incorrect")
        counts[label] += 1
        fields.append({"field_id": field, "transition": label})
    delta = counts["incorrect_to_correct"] - counts["correct_to_incorrect"]
    return {"before": before, "after": after, "counts": counts, "accuracy_difference": fraction(delta, len(pairs)), "fields": fields}


def summarize(records, protocol):
    unique = [r for r in records if not r["repeat"]]
    subsets = {
        "checkout_all": lambda r: r["case"] != "contract-controls",
        "checkout_changed_labels": lambda r: r["eligibility"] == "changed",
        "checkout_familiar_inclusive": lambda r: r["eligibility"] in ("changed", "identity"),
        "checkout_identity_controls": lambda r: r["eligibility"] == "identity",
        "checkout_label_excluded": lambda r: r["eligibility"] == "excluded",
        "synthetic_contract_controls": lambda r: r["case"] == "contract-controls",
    }
    result = {"denominator_unit": "unique (case, field_index) snapshot per condition; repeats excluded", "groups": {}, "reproducibility": []}
    for group in ("primary", "supplemental"):
        result["groups"][group] = {}
        for name, predicate in subsets.items():
            rows = [r for r in unique if r["group"] == group and predicate(r)]
            by_condition = {c: metrics([r for r in rows if r["condition"] == c]) for c in CONDITIONS}
            contrasts = {f"{after}-{before}": transition(rows, before, after) for before, after in (("A", "B"), ("C", "D"), ("A", "C"), ("B", "D"))}
            ab, cd = contrasts["B-A"]["accuracy_difference"], contrasts["D-C"]["accuracy_difference"]
            if ab["denominator"] != cd["denominator"]:
                raise ValueError("Interaction denominators differ")
            result["groups"][group][name] = {"conditions": by_condition, "contrasts": contrasts,
                "interaction_D_minus_C_minus_B_plus_A": fraction(cd["numerator"] - ab["numerator"], ab["denominator"])}
    result["supplemental_effects"] = {}
    for name, predicate in subsets.items():
        result["supplemental_effects"][name] = {}
        for c in CONDITIONS:
            rows = [dict(r, condition=r["group"]) for r in unique if r["condition"] == c and predicate(r)]
            result["supplemental_effects"][name][c] = transition(rows, "primary", "supplemental")
    for repeat in (r for r in records if r["repeat"]):
        original = next(r for r in unique if r["group"] == repeat["group"] and r["field_id"] == repeat["field_id"] and r["condition"] == repeat["condition"])
        difference = max(abs(a-b) for a,b in zip(original["output"]["distribution"], repeat["output"]["distribution"], strict=True))
        identical = original["output"]["model_input"] == repeat["output"]["model_input"]
        same_prediction = all(original["output"][k] == repeat["output"][k] for k in ("action", "entity_key", "selected_index", "value"))
        result["reproducibility"].append({"condition": repeat["condition"], "field_id": repeat["field_id"],
            "inputs_identical": identical, "prediction_identical": same_prediction, "maximum_probability_difference": difference,
            "within_declared_tolerance": identical and same_prediction and difference <= protocol["reproduction"]["distribution_absolute_tolerance"]})
    return result


def sanitized_record(r):
    output = r["output"]
    inputs = output["model_input"]
    keys = inputs["entity_keys"] + ["check", "click", "skip"]
    top = sorted(range(len(keys)), key=output["distribution"].__getitem__, reverse=True)[:3]
    result = {k: r[k] for k in ("group", "case", "field_index", "field_id", "condition", "eligibility", "original_label", "experimental_label", "repeat", "metrics")}
    result.update({k: output[k] for k in ("action", "entity_key", "selected_index", "confidence", "distribution", "candidate_count", "input_protocol", "inference_kind")})
    result["scoring"] = {k: v for k,v in r["scoring"].items() if k not in ("distribution", "control_handle")}
    if "action_contract_correct" in r:
        result["action_contract_correct"] = r["action_contract_correct"]
    result.update(candidate_keys=inputs["entity_keys"], skip_probability=output["distribution"][-1],
                  top_three=[{"index": i, "entity_or_action": keys[i], "probability": output["distribution"][i]} for i in top],
                  context_sha256=digest(inputs["context"]), options_sha256=digest(inputs["options"]),
                  context_truncated=inputs["context_encoding"]["truncated"],
                  context_byte_length=inputs["context_encoding"]["byte_length"],
                  option_byte_lengths=[e["byte_length"] for e in inputs["option_encodings"]],
                  truncated_option_indices=[i for i,e in enumerate(inputs["option_encodings"]) if e["truncated"]])
    return result


async def run(args):
    import torch

    protocol_path = args.generalization_protocol
    protocol = load_protocol(protocol_path)
    manifest = freeze_manifest(protocol_path)
    frozen = json.loads(args.freeze_manifest.read_text())
    if frozen != manifest:
        raise ValueError("Protocol, source, or public input changed after preregistration freeze")
    if not args.output or not args.summary_output or not args.include_sensitive:
        raise ValueError("Generalization requires --include-sensitive, --output and --summary-output")
    raw_path = args.output.resolve()
    if not raw_path.is_relative_to((ROOT / "data").resolve()):
        raise ValueError("Exact predictions must stay under ignored local data/")
    # Refuse output collisions BEFORE spending compute; write_private also uses O_EXCL.
    if args.output.exists() or args.summary_output.exists():
        raise FileExistsError("Experiment evidence is immutable; choose new output paths")
    identity = verify_identity(args.model_path)
    declared_identity = {k: v for k, v in protocol["model_identity"].items() if k != "repository"}
    if identity != declared_identity:
        raise ValueError("Verified checkpoint differs from preregistered identity")
    from cua_s1 import concepts, schema, synth

    upstream = {"concepts.py": concepts, "schema.py": schema, "synth.py": synth}
    if {name: sha(module.__file__) for name, module in upstream.items()} != protocol["upstream_source_sha256"]:
        raise ValueError("Upstream catalogue or input/generator source differs from preregistration")
    inference_config = protocol["inference_configuration"]
    if args.device != inference_config["device"]:
        raise ValueError("Device differs from preregistered primary runtime")
    torch.set_num_threads(inference_config["threads"])
    design, audit = build_design(protocol)
    adapters = {}
    for condition in CONDITIONS:
        adapter = CuaS1Adapter(device=args.device, diagnostics=True,
                               input_protocol=protocol["conditions"][condition]["serialization"])
        adapter.path = str(args.model_path)
        adapter.endpoint = ""
        adapters[condition] = adapter
    # Only public projections enter inference. Separate private grading follows
    # every forward pass, including supplemental controls and repeats.
    records = await infer_design(design, adapters, protocol)
    for adapter in adapters.values():
        if (adapter.model.training or str(next(adapter.model.parameters()).dtype) != inference_config["precision"]
                or sum(p.numel() for p in adapter.model.parameters()) != inference_config["parameters"]):
            raise ValueError("Loaded model configuration differs from preregistration")
    records = grade_records(records, protocol)
    report = {"format": "checkoutbench-cua-generalization-1", "created_at": datetime.now(UTC).isoformat(),
              "experiment_id": protocol["experiment_id"], "scope": protocol["scope"],
              "identity": identity, "freeze": manifest, "freeze_file_sha256": sha(args.freeze_manifest),
              "runtime": {"python": platform.python_version(), "torch": torch.__version__, "safetensors": version("safetensors"),
                          "platform": platform.platform(), "device": args.device, "threads": torch.get_num_threads(),
                          "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
                          "precision": str(next(adapters["A"].model.parameters()).dtype)},
              "parameters": sum(p.numel() for p in adapters["A"].model.parameters()),
              "forward_calls": len(records), "unique_snapshot_count": 30, "unique_conceptual_control_count": 28,
              "control_unit_note": "23 checkout fields plus seven synthetic observations of five conceptual controls; two additional observations are prefilled email/checked checkbox states.",
              "invariants": audit, "analysis": summarize(records, protocol), "records": records}
    write_private(args.output, report)
    summary = {k: v for k,v in report.items() if k != "records"}
    summary["raw_artifact_sha256"] = sha(args.output)
    summary["records"] = [sanitized_record(r) for r in records]
    write_private(args.summary_output, summary)
    print(json.dumps({"experiment_id": protocol["experiment_id"], "forward_calls": len(records),
                      "protocol_sha256": manifest["protocol_sha256"], "raw_artifact_sha256": summary["raw_artifact_sha256"],
                      "summary_sha256": sha(args.summary_output)}))
    return report


def main():
    import argparse
    import asyncio
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", default=os.getenv("CUA_S1_MODEL_PATH"))
    parser.add_argument("--device", default="cpu", choices=("cpu", "mps", "cuda"))
    parser.add_argument("--generalization-protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--freeze-manifest", type=Path)
    parser.add_argument("--write-freeze", type=Path, help="Preregister immutable hashes, with NO inference")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--include-sensitive", action="store_true")
    args = parser.parse_args()
    if args.write_freeze:
        write_private(args.write_freeze, freeze_manifest(args.generalization_protocol))
        print(json.dumps({"freeze_sha256": sha(args.write_freeze), "inference_calls": 0}))
        return
    if not args.freeze_manifest or not args.model_path:
        parser.error("--freeze-manifest and --model-path are required for genuine inference")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
