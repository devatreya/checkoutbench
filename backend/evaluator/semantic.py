"""Private, post-execution semantic grading. Invalid and skipped choices remain in the denominator."""

from backend.evaluator.scoring import norm


def grade_decisions(s, decisions):
    inverse = {v: k for k, v in s["dom_ids"].items()}
    return [
        norm(inverse[d["control_handle"]], d.get("value"))
        == norm(
            inverse[d["control_handle"]],
            s["expected_values"][inverse[d["control_handle"]]],
        )
        for d in decisions
        if inverse.get(d["control_handle"]) in s["expected_values"]
    ]
