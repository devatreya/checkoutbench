"""Contract tests use explicit test doubles; real weights are gated separately."""

import copy
import json
import math
import os

import pytest

from backend.adapters.specialists import (
    CuaS1Adapter,
    SpecialistOutputError,
    cua_byte_trace,
    cua_inputs,
)
from backend.evaluator.semantic import decision_report, grade_decisions
from scripts.research.cua_diagnostics import public_case, write_private


@pytest.mark.parametrize(
    "role,checked",
    [
        ("textbox", None),
        ("checkbox", True),
        ("checkbox", False),
        ("combobox", None),
        ("button", None),
    ],
)
def test_official_context_and_options(role, checked):
    schema = pytest.importorskip("cua_s1.schema")
    e = {
        "label": "City " + "é" * 80,
        "role": role,
        "checked": checked,
        "value": "x" * 65,
        "form_title": "Title " * 20,
        "placeholder": "hint " * 25,
    }
    entities, contexts, options = cua_inputs(
        [e], {"person": {"city": "Boston"}, "unused": ""}
    )
    native = {
        "textbox": "Edit",
        "checkbox": "CheckBox",
        "combobox": "ComboBox",
        "button": "Button",
    }[role]
    assert contexts == [
        schema.render_context(
            e["form_title"],
            schema.Element(native, e["label"], e["value"], checked=checked),
            e["placeholder"],
        )
    ]
    assert options == schema.render_options(
        [schema.Entity(k.replace(".", " "), v) for k, v in entities]
    )
    for i in range(len(options)):
        action, index = schema.decode(i, entities)
        assert action == ("fill" if i < len(entities) else options[i])
        assert index == (i if i < len(entities) else None)


def test_byte_limits_match_real_collator():
    model = pytest.importorskip("cua_s1.model")
    context, option = "€" * 100, "😀" * 100
    collator = model.ByteCollator(224, 96)
    batch = collator([model.ChoiceExample(context, (option, "skip"), 0)])
    assert batch["context_ids"][0].tolist() == cua_byte_trace(context, 224)["byte_ids"]
    assert batch["option_ids"][0, 0].tolist() == cua_byte_trace(option, 96)["byte_ids"]
    assert cua_byte_trace(context, 224)["truncated"]
    assert len(batch["context_ids"][0]) == 224
    assert len(batch["option_ids"][0, 0]) == 96
    assert not cua_byte_trace("a" * 96, 96)["truncated"]


@pytest.mark.parametrize(
    "state,expected",
    [
        (True, "checked"),
        (False, "unchecked"),
        ("true", "checked"),
        ("false", "unchecked"),
    ],
)
def test_checkbox_public_state(state, expected):
    _, contexts, _ = cua_inputs([{"role": "checkbox", "value": state}], {})
    assert contexts[0].endswith(" " + expected)
    _, contexts, _ = cua_inputs(
        [{"role": "checkbox", "value": "true", "checked": False}], {}
    )
    assert contexts[0].endswith(" unchecked")


def test_document_protocol_preserves_information_and_order():
    profile = {
        "customer": {
            "full_name": "Person",
            "shipping": {"city": "A"},
            "billing": {"city": "B"},
        },
        "missing": None,
        "flag": True,
    }
    e1, _, o1 = cua_inputs([], profile, "path-v1")
    e2, _, o2 = cua_inputs([], profile, "document-v2")
    assert e1 == e2
    assert o1[:3] == [
        "fill customer full name: Person",
        "fill customer shipping city: A",
        "fill customer billing city: B",
    ]
    assert o2 == [
        "fill Full name (customer): Person",
        "fill City (customer / shipping): A",
        "fill City (customer / billing): B",
        "check",
        "click",
        "skip",
    ]
    with pytest.raises(ValueError):
        cua_inputs([], {"x": math.nan})


class ChoiceDouble(CuaS1Adapter):
    """Never claim model inference for deterministic unit predictions."""

    def __init__(self, index, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = ""
        self.index = index
        self.seen = []

    def _score(self, contexts, options):
        self._inference_kind = "test_double"
        self.seen.append((contexts, options))
        return [[float(i == self.index) for i in range(len(options))] for _ in contexts]


@pytest.mark.parametrize(
    "index,action,value,key",
    [
        (0, "fill", "A", "a"),
        (1, "fill", "B", "b"),
        (2, "check", None, None),
        (3, "click", None, None),
        (4, "skip", None, None),
    ],
)
async def test_index_decode_and_model_selected_value(index, action, value, key):
    a = ChoiceDouble(index, diagnostics=True)
    r = (
        await a.score_fields([{"id": "opaque", "label": "Email"}], {"a": "A", "b": "B"})
    )[0]
    assert (r["action"], r["value"], r["entity_key"], r["selected_index"]) == (
        action,
        value,
        key,
        index,
    )
    assert r["element_id"] == "opaque" and r["confidence"] == 1
    assert r["inference_kind"] == "test_double"
    assert len(r["model_input"]["options"]) == len(r["distribution"])
    assert a.last_metrics["model_forward_seconds"] is None


async def test_missing_and_ambiguous_candidates_are_not_repaired():
    a = ChoiceDouble(1)
    result = await a.score_fields([{"label": "Name"}], {"a": "Same", "b": "Same"})
    assert result[0]["entity_key"] == "b"  # Do not collapse equal-valued candidates.
    assert "model_input" not in result[0]
    a.index = 2
    result = await a.score_fields([{"label": "Name"}], {})
    assert result[0]["action"] == "skip"
    assert await a.score_fields([], {}) == [] and a.last_metrics == {}


@pytest.mark.parametrize(
    "scores",
    [
        [1, 0],
        [0, 0, 0, 0],
        [True, 0, 0, 0],
        [math.nan, 0, 0, 1],
        [math.inf, 0, 0, 0],
        [-0.1, 0.1, 0, 1],
        [0.5, 0.499, 0, 0],
        [1.1, 0, 0, 0],
    ],
)
async def test_invalid_probabilities_rejected(scores, monkeypatch):
    a = ChoiceDouble(0)
    monkeypatch.setattr(a, "_score", lambda contexts, options: [scores])
    with pytest.raises(SpecialistOutputError):
        await a.score_fields([{"label": "Name"}], {"name": "Person"})


async def test_no_private_or_dom_hint_leakage():
    from scenarios.v21 import scenario_v21

    s = scenario_v21("V21-G01", 2026, "aditi")
    public = public_case(s)
    poisoned = copy.deepcopy(s)
    poisoned["expected_values"] = {"email": "PRIVATE_ORACLE_SENTINEL"}
    poisoned["dom_ids"] = {"email": "PRIVATE_HANDLE_SENTINEL"}
    poisoned["required_fields"] = ["PRIVATE_ORACLE_SENTINEL"]
    assert public_case(poisoned) == public
    a = ChoiceDouble(0, diagnostics=True)
    first = await a.score_fields(**public)
    second = await a.score_fields(**public_case(poisoned))
    assert first == second
    e = dict(
        public["elements"][0],
        id="PRIVATE_HANDLE_SENTINEL",
        expected_value="PRIVATE_ORACLE_SENTINEL",
    )
    await a.score_fields([e], public["profile"])
    assert "PRIVATE_" not in json.dumps(a.seen)
    # Even the collator's unused training label cannot change genuine logits;
    # the real-model test below checks this independently.


def scenario_truth():
    return {
        "dom_ids": {"email": "a", "landmark": "b", "consent": "c", "missing": "d"},
        "expected_values": {
            "email": "x@example.invalid",
            "landmark": "Park",
            "consent": "true",
            "missing": "X",
        },
        "required_fields": ["email", "consent", "missing"],
        "optional_fields": ["landmark"],
        "fields": [{"key": "consent", "kind": "checkbox"}],
        "expected_entity_keys": {
            "email": "customer.email",
            "landmark": "customer.shipping.landmark",
        },
    }


def test_measurement_denominators_optional_and_metadata():
    decisions = [
        {
            "control_handle": "a",
            "action": "fill",
            "value": "WRONG",
            "entity_key": "customer.phone",
            "confidence": 0.9,
            "distribution": [0.9, 0.1],
            "inference_kind": "actual_model",
        },
        {
            "control_handle": "a",
            "action": "skip",
            "value": "WRONG",
            "execution_status": "stale_observation",
        },
        {"control_handle": "b", "action": "skip", "value": ""},
        {"control_handle": "unknown", "action": "fill", "value": "X"},
        {"control_handle": "c", "action": "click", "value": "true"},
    ]
    report = decision_report(scenario_truth(), decisions)
    assert grade_decisions(scenario_truth(), decisions) == [False] * 4
    assert report["scored_decisions"] == 4 and report["unscored_decisions"] == 1
    assert report["unique_scored_fields"] == 3 and report["repeated_decisions"] == 1
    assert report["required_scored_decisions"] == 3
    assert report["optional_field_acceptability"] == 1
    assert report["acceptable_optional_skips"] == 1
    assert report["skip_predictions"] == 2 and report["wrong_value_selections"] == 1
    assert report["invalid_action_selections"] == 1
    assert (
        report["strict_entity_accuracy"] == 0 and report["entity_scored_decisions"] == 3
    )
    assert report["unobserved_required_fields"] == ["missing"]
    assert report["rows"][0]["distribution"] == [0.9, 0.1]
    assert report["inference_kinds"] == {"actual_model": 1, "unrecorded": 4}


def test_identity_not_inferred_from_matching_values_and_skip_separate():
    d = {"control_handle": "a", "action": "fill", "value": "x@example.invalid"}
    r = decision_report(scenario_truth(), [d])
    assert (
        r["field_classification_accuracy"] == 1 and r["strict_entity_accuracy"] is None
    )
    d["entity_key"] = "other.same_value"
    r = decision_report(scenario_truth(), [d])
    assert r["field_classification_accuracy"] == 1 and r["strict_entity_accuracy"] == 0
    d["action"] = "skip"
    r = decision_report(scenario_truth(), [d])
    assert (
        r["field_classification_accuracy"] == 1 and r["strict_assignment_accuracy"] == 0
    )
    assert (
        decision_report(scenario_truth(), [])["field_classification_accuracy"] is None
    )


def test_optional_skip_of_wrong_existing_value_not_acceptable():
    d = {
        "control_handle": "b",
        "action": "skip",
        "value": "Wrong",
        "before_value": "Wrong",
    }
    assert decision_report(scenario_truth(), [d])["optional_field_acceptability"] == 0


def test_private_artifact_no_overwrite(tmp_path):
    target = tmp_path / "diagnostic.json"
    write_private(target, {"exact": "synthetic"})
    assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private(target, {})


@pytest.mark.skipif(
    os.getenv("RUN_CUA_REAL") != "1",
    reason="explicit opt-in genuine pinned checkpoint inference",
)
async def test_actual_pinned_model_inference(monkeypatch):
    import torch
    from cua_s1.model import ChoiceExample

    from scripts.research.cua_diagnostics import verify_identity

    verify_identity(os.environ["CUA_S1_MODEL_PATH"])
    monkeypatch.delenv("CUA_S1_ENDPOINT", raising=False)
    adapter = CuaS1Adapter(device="cpu", diagnostics=True)
    elements = [
        {
            "label": "Email address",
            "role": "textbox",
            "value": "",
            "form_title": "Registration",
        }
    ]
    profile = {"Email": "person@example.invalid", "Name": "Example Person"}
    first = (await adapter.score_fields(elements, profile))[0]
    assert first["inference_kind"] == "actual_model"
    assert adapter.last_metrics["call_temperature"] == "cold"
    second = (await adapter.score_fields(elements, profile))[0]
    assert second["distribution"] == pytest.approx(first["distribution"], abs=1e-6)
    assert adapter.last_metrics["call_temperature"] == "warm"
    assert first["action"] == "fill" and first["value"] == profile["Email"]
    assert sum(first["distribution"]) == pytest.approx(1, abs=1e-6)
    assert sum(p.numel() for p in adapter.model.parameters()) == 706048
    assert not adapter.model.training
    inp = first["model_input"]
    batches = [
        adapter.processor([ChoiceExample(inp["context"], tuple(inp["options"]), label)])
        for label in (0, 4)
    ]
    with torch.inference_mode():
        assert torch.equal(adapter.model(batches[0]), adapter.model(batches[1]))
    assert len(first["distribution"]) == len(inp["options"])


async def test_probability_ties_keep_first_and_wrong_row_count_rejected(monkeypatch):
    a = ChoiceDouble(0)
    monkeypatch.setattr(a, "_score", lambda contexts, options: [[0.5, 0.5, 0, 0, 0]])
    assert (await a.score_fields([{}], {"a": "A", "b": "B"}))[0]["entity_key"] == "a"
    monkeypatch.setattr(a, "_score", lambda contexts, options: [])
    with pytest.raises(SpecialistOutputError):
        await a.score_fields([{}], {})


def test_unknown_checkbox_state_rejected_and_legacy_replay():
    with pytest.raises(ValueError):
        cua_inputs([{"role": "checkbox", "checked": "mixed"}], {})
    _, c, _ = cua_inputs([{"role": "checkbox", "value": "true"}], {}, "path-v1")
    assert c[0].endswith(" unchecked")
