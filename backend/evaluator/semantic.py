"""Private post-inference grading; never imported by the model adapter.

Historical field accuracy is an effective-value metric, not proof of a selected
entity's identity. Identity accuracy requires private expected_entity_keys and
recorded entity_key. Missing evidence is reported as unscored, never inferred.
"""

from collections import Counter

from backend.evaluator.scoring import norm

SEMANTIC_SCORING_VERSION = "semantic-2"


def decision_report(s, decisions):
    """Grade decision attempts (including repeats), with explicit coverage.

    `value` is the controller's measured/effective value (including select value
    translation). `before_value` is optional state before the action. Additional
    prediction metadata is retained if supplied. expected_entity_keys is a
    private field-key -> entity-key (or list of acceptable keys) mapping.
    This function has no model calls and does not mutate either input.
    """
    inverse = {v: k for k, v in s["dom_ids"].items()}
    expected = s["expected_values"]
    fields = {f["key"]: f for f in s.get("fields", [])}
    required = set(s.get("required_fields", []))
    optional = set(s.get("optional_fields", []))
    entity_truth = s.get("expected_entity_keys", {})
    rows = []
    for d in decisions:
        key = inverse.get(d.get("control_handle"))
        row = {
            k: d[k]
            for k in (
                "control_handle",
                "action",
                "entity_key",
                "confidence",
                "distribution",
                "selected_index",
                "input_protocol",
                "inference_kind",
                "execution_status",
            )
            if k in d
        }
        row.update(
            field=key,
            scored=key in expected,
            required=key in required,
            optional=key in optional,
        )
        if key not in expected:
            row["unscored_reason"] = "unknown_handle_or_missing_truth"
            rows.append(row)
            continue
        action = d.get("action")
        role = str(d.get("role", fields.get(key, {}).get("kind", "text"))).lower()
        checkbox = role in {"checkbox", "axcheckbox"}
        valid = action in ({"check", "skip"} if checkbox else {"fill", "skip"})
        # Check may not target an ordinary value field, and click never supplies
        # a field value. Keep invalid actions in the scoring denominator.
        matches = norm(key, d.get("value")) == norm(key, expected[key])
        field_correct = valid and matches
        assignment_correct = field_correct and action in {"fill", "check"}
        effective = d.get("before_value", d.get("value"))
        optional_skip = (
            key in optional and action == "skip" and not norm(key, effective)
        )
        identity = None
        if key in entity_truth:
            acceptable = entity_truth[key]
            acceptable = (
                acceptable if isinstance(acceptable, (list, tuple)) else [acceptable]
            )
            # A skip has no entity pointer; it is a wrong assignment even if
            # leaving the field alone is acceptable to checkout completion.
            if action != "fill":
                identity = False
            elif "entity_key" in d:
                identity = valid and d["entity_key"] in acceptable
        row.update(
            valid_action=valid,
            skip=action == "skip",
            field_value_correct=field_correct,
            strict_assignment_correct=assignment_correct,
            strict_entity_correct=identity,
            acceptable_optional_skip=optional_skip,
            acceptable=field_correct or optional_skip,
            wrong_value=action == "fill" and not matches,
        )
        rows.append(row)

    scored = [r for r in rows if r["scored"]]
    req = [r for r in scored if r["required"]]
    opt = [r for r in scored if r["optional"]]
    identities = [r for r in scored if r["strict_entity_correct"] is not None]
    known_fields = set(inverse.values()) & set(expected)
    observed = {r["field"] for r in scored}

    def accuracy(group, key):
        return sum(r[key] for r in group) / len(group) if group else None

    return {
        "scoring_version": SEMANTIC_SCORING_VERSION,
        "denominator_unit": "decision_attempt; repeated controls count repeatedly",
        "decisions_total": len(rows),
        "scored_decisions": len(scored),
        "unscored_decisions": len(rows) - len(scored),
        "unique_scored_fields": len(observed),
        "repeated_decisions": len(scored) - len(observed),
        "expected_fields_with_handles": len(known_fields),
        "unobserved_fields": sorted(known_fields - observed),
        "unobserved_required_fields": sorted(required - observed),
        "field_classification_accuracy": accuracy(scored, "field_value_correct"),
        "strict_assignment_accuracy": accuracy(scored, "strict_assignment_correct"),
        "strict_entity_accuracy": accuracy(identities, "strict_entity_correct"),
        "entity_scored_decisions": len(identities),
        "entity_unscored_decisions": len(scored) - len(identities),
        "required_field_accuracy": accuracy(req, "field_value_correct"),
        "required_scored_decisions": len(req),
        "optional_scored_decisions": len(opt),
        "optional_field_acceptability": accuracy(opt, "acceptable"),
        "acceptable_optional_skips": sum(r["acceptable_optional_skip"] for r in scored),
        "wrong_value_selections": sum(r["wrong_value"] for r in scored),
        "skip_predictions": sum(r["skip"] for r in scored),
        "invalid_action_selections": sum(not r["valid_action"] for r in scored),
        "execution_statuses": dict(
            Counter(d.get("execution_status", "unrecorded") for d in decisions)
        ),
        "inference_kinds": dict(
            Counter(d.get("inference_kind", "unrecorded") for d in decisions)
        ),
        "rows": rows,
    }


def grade_decisions(s, decisions):
    """Backward-compatible list of field-value grades, now action-aware.

    A successful no-op on an already-correct value remains correct here. Use
    decision_report's separate strict assignment/entity metrics for pointer
    accuracy; an optional empty skip is only acceptable, not a correct value
    match when the document specifies a nonempty value.
    """
    return [
        r["field_value_correct"]
        for r in decision_report(s, decisions)["rows"]
        if r["scored"]
    ]
