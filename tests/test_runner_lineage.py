"""Runner identity/error boundaries; synthetic traces are not inference evidence."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.adapters.base import Ledger
from backend.adapters.specialists import (
    SpecialistInferenceError, SpecialistOutputError, SpecialistUnavailable, UnsupportedCapability,
)
from backend.browser.v21 import NoProgress
from backend.runner import engine
from scenarios.identity import identity
from scenarios.catalog import scenario
from scenarios.research import digest


def config(sid="V21-G01"):
    return {"models": ["ui-venus"], "scenarios": [sid], "repeats": 1,
            "seed": 2026, "max_steps": 8, "timeout": 10, "video": False,
            "max_tokens": 100, "reasoning": "none", "infrastructure_retries": 0}


def test_aliases_normalize_before_dispatch_without_mutating_configuration():
    supplied = config(identity("V21-G01")["public_id"])
    original = copy.deepcopy(supplied)
    assert engine.canonical_config(supplied)["scenarios"] == ["V21-G01"]
    assert supplied == original
    supplied["scenarios"].append("V21-G01")
    with pytest.raises(ValueError, match="only once"):
        engine.canonical_config(supplied)


async def test_start_validates_public_alias_as_canonical_research_id(monkeypatch):
    from backend.research import protocol

    checkpoints = []
    monkeypatch.setattr(protocol, "validate_checkpoints", lambda models: checkpoints.append(models))
    runner = engine.Runner()
    dispatched = []
    async def batch_run(c):
        dispatched.append(c)
    monkeypatch.setattr(runner, "batch_run", batch_run)
    supplied = config(identity("V3-G01")["public_id"])
    await runner.start(supplied)
    await runner.worker
    assert checkpoints == [["ui-venus"]]
    assert dispatched[0]["scenarios"] == ["V3-G01"]
    assert supplied["scenarios"] == [identity("V3-G01")["public_id"]]


@pytest.fixture
def isolated_runner(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "DATA", tmp_path)
    saved = []
    monkeypatch.setattr(engine, "save", lambda record: saved.append(copy.deepcopy(record)))
    monkeypatch.setattr(engine, "detect_hardware", lambda: {"device": "test-double"})
    return engine.Runner(), saved, tmp_path


async def test_unavailable_diagnostic_retains_identity_runtime_and_scenario_lineage(isolated_runner, monkeypatch):
    from backend.adapters import specialists

    runner, saved, root = isolated_runner
    monkeypatch.setattr(specialists, "specialist_catalog", lambda: [{"id": "ui-venus", "available": False, "reason": "Test checkpoint unavailable"}])
    supplied = config(identity("V21-G01")["public_id"])
    await runner.one("ui-venus", supplied["scenarios"][0], supplied, 0, Ledger(None))
    row = runner.current
    assert row["scenario"] == row["canonical_id"] == "V21-G01"
    assert row["public_id"] == identity("V21-G01")["public_id"]
    assert row["benchmark_version"] == "2.1"
    assert row["scenario_hash"] == digest(scenario("V21-G01", 2026))
    assert row["release_hash"] and row["runtime_source_hash"]
    ex = row["execution_manifest"]
    assert not ex["standard_run_all"] and row["result_store"] == "validation"
    assert ex["public_task_hash"] and ex["viewport"] == row["viewport"]
    assert ex["device_scale_factor"] == 1 and ex["observation_track"] == "screenshot_gui"
    assert "backend/adapters/venus.py" in ex["adapter_source_hashes"]
    assert row["outcome_category"] == "unavailable" and not row["model_reasoning_failure"]
    assert row["genuine_inference_call_count"] == 0
    assert saved[-1] == json.loads((root / "validation" / row["id"] / "actions.json").read_text())


@pytest.mark.parametrize("exception,reason,category,status", [
    (SpecialistInferenceError("worker error"), "inference_error", "infrastructure_failure", "blocked"),
    (UnsupportedCapability("unsupported native action"), "unsupported_capability", "unsupported_capability", "blocked"),
    (SpecialistOutputError("malformed output"), "invalid_model_action", "invalid_model_action", "failed"),
    (SpecialistUnavailable("dependency missing"), "dependency missing", "unavailable", "unavailable"),
])
async def test_error_classes_are_retained_not_converted_to_reasoning_failure(isolated_runner, monkeypatch, exception, reason, category, status):
    from backend.adapters import specialists

    runner, _, _ = isolated_runner
    def reject():
        raise exception
    monkeypatch.setattr(specialists, "specialist_catalog", reject)
    await runner.one("ui-venus", "V21-G01", config(), 0, Ledger(None))
    row = runner.current
    assert row["failure_reason"] == reason and row["status"] == status
    assert row["outcome_category"] == category and not row["model_reasoning_failure"]
    assert not row["success"]
    if isinstance(exception, SpecialistInferenceError):
        assert row["inference_error_detail"] == "worker error"


class BrowserDouble:
    """Browser lifecycle double used only to exercise runner persistence paths."""
    def __init__(self):
        self.page = SimpleNamespace()
        self.pages = [self.page]
        self.browser = SimpleNamespace(version="test-double-browser")
        self.closed = False
        self.page.context = self
        self.page.url = "http://127.0.0.1/test-double"
        self.page.is_closed = lambda: self.closed
        self.page.set_default_timeout = lambda value: None
        self.page.goto = self.noop
        self.page.locator = lambda selector: SimpleNamespace(wait_for=self.noop)
        self.page.screenshot = self.screenshot

    async def noop(self, *args, **kwargs):
        pass

    async def screenshot(self, **kwargs):
        Path(kwargs["path"]).write_bytes(b"explicit test double screenshot")

    async def close(self):
        self.closed = True

    route = route_web_socket = noop


async def test_visual_stall_has_no_deterministic_navigation_attribution(isolated_runner, monkeypatch):
    from backend.adapters import specialists

    runner, _, _ = isolated_runner
    monkeypatch.setattr(specialists, "specialist_catalog", lambda: [{"id": "ui-venus", "available": True, "backend": "test-double"}])
    context = BrowserDouble()
    class PlaywrightDouble:
        async def __aenter__(self):
            async def launch(*args, **kwargs):
                return context
            return SimpleNamespace(chromium=SimpleNamespace(launch_persistent_context=launch))
        async def __aexit__(self, *args):
            pass
    monkeypatch.setattr(engine, "async_playwright", PlaywrightDouble)
    async def visual(page, public, ctl, model):
        assert not {"expected_values", "dom_ids"} & public.keys()
        ctl.run["inference_configuration"] = {"adapter_version": "test-double", "precision": "test-only"}
        ctl.usage.calls.append({"model": model, "backend": "test-double", "status": "generated", "operation": "act"})
        await ctl.record("visual_action", {"action": "click", "selection_source": "model", "execution_status": "executed"})
        raise NoProgress({"reason": "repeated_visual_action", "count": 3})
    monkeypatch.setattr(engine, "visual_agent", visual)
    await runner.one("ui-venus", "V21-G01", config(), 0, Ledger(None))
    row = runner.current
    assert row["failure_reason"] == "no_progress" and not row["success"]
    assert not row["failure_attribution"]["navigation_controller"]
    assert row["model_decision_count"] == row["model_execution_count"] == 1
    assert row["execution_manifest"]["inference_configuration"]["adapter_version"] == "test-double"
    assert row["execution_manifest"]["browser_version"] == "test-double-browser"
    assert row["genuine_inference_call_count"] == 0


@pytest.mark.parametrize("reason,status,success,expected", [
    (None, "completed", True, "successful_completion"),
    ("incomplete", "failed", False, "model_failure"),
    ("no_progress", "failed", False, "model_failure"),
    ("invalid_model_action", "failed", False, "invalid_model_action"),
    ("unsupported_capability", "blocked", False, "unsupported_capability"),
    ("inference_error", "blocked", False, "infrastructure_failure"),
    ("timeout", "failed", False, "evaluation_timeout"),
    ("user_stopped", "stopped", False, "user_stopped"),
])
def test_outcome_categories_use_execution_evidence_not_self_report(reason, status, success, expected):
    # Serialized provenance fixtures, not a model invocation or performance result.
    row = {"kind": "specialist", "failure_reason": reason, "status": status, "success": success,
           "model_completion": {"status": "success"},
           "calls": [{"backend": "local", "inference_kind": "actual_model"}]}
    result = engine.outcome_evidence(row)
    assert result["outcome_category"] == expected
    assert result["model_reasoning_failure"] == (expected == "model_failure")
    row["calls"][0]["backend"] = "test-double"
    assert engine.outcome_evidence(row)["genuine_inference_call_count"] == 0


def test_invalid_output_rate_uses_completed_genuine_generation_denominator():
    row = {"model": "ui-venus", "status": "failed", "failure_reason": "invalid_model_action",
           "calls": [{"actual_model": True}, {"actual_model": True, "error_type": "SpecialistOutputError"},
                     {"actual_model": False, "error_type": "SpecialistInferenceError"}]}
    result = engine.outcome_evidence(row)
    assert result["invalid_model_output_count"] == 1
    assert result["invalid_model_output_denominator"] == 2
    assert result["invalid_model_output_rate"] == 0.5
    assert result["inference_failure_rate"] == 1 / 3
    assert engine.outcome_evidence({"calls": []})["invalid_model_output_rate"] is None
