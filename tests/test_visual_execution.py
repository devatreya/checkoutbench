"""Screenshot-track execution contracts; all adapters here are explicit doubles."""

from collections import defaultdict
from copy import deepcopy
import io
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from backend.adapters.base import Stopped
from backend.adapters.specialists import SpecialistOutputError, UnsupportedCapability
from backend.browser import visual
from backend.browser.v21 import NoProgress


class Browser:
    """Only coordinate/keyboard execution, screenshots, and lifecycle are exposed."""

    def __init__(self):
        self.mouse = SimpleNamespace(**{
            name: AsyncMock() for name in ("click", "dblclick", "move", "down", "up", "wheel")
        })
        self.keyboard = SimpleNamespace(insert_text=AsyncMock(), press=AsyncMock())
        self.context = SimpleNamespace(pages=[self])
        self.wait_for_timeout = AsyncMock()
        output = io.BytesIO()
        Image.new("RGB", (100, 80), "white").save(output, format="PNG")
        self.screenshot = AsyncMock(return_value=output.getvalue())

    def is_closed(self):
        return False

    def locator(self, *args, **kwargs):
        raise AssertionError("Visual actions may not target DOM selectors")

    def get_by_role(self, *args, **kwargs):
        raise AssertionError("Visual actions may not target semantic roles")

    def evaluate(self, *args, **kwargs):
        raise AssertionError("Model execution must not inspect private page state")

    def mutations(self):
        return sum(
            value.await_count
            for obj in (self.mouse, self.keyboard)
            for value in vars(obj).values()
        )


class Controls:
    def __init__(self, directory, max_steps=8):
        self.directory, self.max_steps = directory, max_steps
        self.run = {"viewport": {"width": 100, "height": 80}, "success": False}
        self.timings = defaultdict(float)
        self.check = AsyncMock()
        self.events = []

    async def record(self, action, detail):
        self.events.append({"action": action, "detail": deepcopy(detail)})


class AdapterDouble:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.inputs = []
        self.last_metrics = {"backend": "test-double", "inference_kind": "test_double"}
        self.close = AsyncMock()
        self.endpoint = ""

    def metadata(self):
        return {"inference_kind": "test_double", "precision": "fixture-only"}

    async def act(self, image, task, history):
        self.inputs.append((image.copy(), deepcopy(task), deepcopy(history)))
        result = next(self.actions)
        if isinstance(result, BaseException):
            raise result
        return deepcopy(result)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    page, controls = Browser(), Controls(tmp_path)
    state = AsyncMock(return_value="same-visible-state")
    monkeypatch.setattr(visual, "page_state", state)
    return page, controls, state


@pytest.mark.parametrize("action", [
    {"action": "click", "x": 100, "y": 5},
    {"action": "click", "x": True, "y": 5},
    {"action": "hover", "x": float("nan"), "y": 5},
    {"action": "drag", "start": [1, 2], "end": [4, 80]},
    {"action": "type", "text": 12},
    {"action": "type", "text": "hello", "submit": "false"},
    {"action": "scroll", "direction": "diagonal"},
    {"action": "scroll", "amount": float("inf")},
    {"action": "wait", "seconds": 4},
    {"action": "press", "key": "Meta+q"},
    {"action": "navigate", "url": "https://example.invalid"},
])
async def test_malformed_action_rejected_before_any_browser_mutation(harness, action):
    page, ctl, _ = harness
    adapter = AdapterDouble([action])
    with pytest.raises((SpecialistOutputError, UnsupportedCapability)):
        await visual.run_visual(page, {"instruction": "Synthetic checkout"}, ctl, adapter, "ui-venus")
    assert page.mutations() == 0
    assert not ctl.events
    assert ctl.usage.calls[0]["status"] == "failed"
    assert ctl.usage.calls[0]["output"] == action
    adapter.close.assert_awaited_once()


async def test_native_actions_execute_with_pixels_and_public_history_only(harness):
    page, ctl, _ = harness
    actions = [
        {"action": "click", "x": 11, "y": 12},
        {"action": "type", "text": "Synthetic person", "submit": True},
        {"action": "scroll", "direction": "left", "amount": 70},
        {"action": "press", "key": "Control+a"},
        {"action": "drag", "start": [1, 2], "end": [30, 40]},
        {"action": "done", "status": "success", "text": "I finished"},
    ]
    task = {"instruction": "Use synthetic customer data", "profile": {"name": "Synthetic person"}}
    adapter = AdapterDouble(actions)
    usage = await visual.run_visual(page, task, ctl, adapter, "ui-venus")
    page.mouse.click.assert_awaited_once_with(11, 12)
    page.keyboard.insert_text.assert_awaited_once_with("Synthetic person")
    assert [call.args for call in page.keyboard.press.await_args_list] == [("Enter",), ("Control+a",)]
    page.mouse.wheel.assert_awaited_once_with(-70, 0)
    assert [call.args for call in page.mouse.move.await_args_list] == [(1, 2), (30, 40)]
    assert page.mouse.move.await_args_list[-1].kwargs == {"steps": 10}
    page.mouse.down.assert_awaited_once()
    page.mouse.up.assert_awaited_once()
    assert len(usage.calls) == 6
    assert len(ctl.events) == 5
    assert ctl.run["success"] is False  # Native completion is not verifier success.
    assert ctl.run["model_completion"] == actions[-1]
    assert ctl.run["visual_protocol"]["dom_access_to_model"] is False
    for index, (image, observed_task, history) in enumerate(adapter.inputs):
        assert image.size == (100, 80)
        assert observed_task == task
        assert history == actions[:index]
        assert "same-visible-state" not in json.dumps((observed_task, history))
    assert len(list((ctl.directory / "observations").glob("*.png"))) == 6
    assert all(call["backend"] == "test-double" for call in usage.calls)
    adapter.close.assert_awaited_once()


async def test_native_text_changes_do_not_reset_equivalent_action_stall(harness):
    page, ctl, _ = harness
    adapter = AdapterDouble([
        {"action": "click", "x": 20, "y": 20, "raw": f"reason {i}", "native_action": f"native {i}"}
        for i in range(3)
    ])
    with pytest.raises(NoProgress) as failure:
        await visual.run_visual(page, {"instruction": "Continue"}, ctl, adapter, "ui-venus")
    assert failure.value.diagnostics["count"] == 3
    assert page.mouse.click.await_count == 3
    assert [e["action"] for e in ctl.events] == ["visual_action"] * 3 + ["no_progress"]
    assert len(ctl.usage.calls) == 3
    adapter.close.assert_awaited_once()


async def test_terminal_looking_state_does_not_automatically_complete(harness):
    page, ctl, state = harness
    state.return_value = "checkout_ready / Payment successful"
    ctl.max_steps = 1
    adapter = AdapterDouble([{"action": "click", "x": 10, "y": 10}])
    with pytest.raises(Stopped, match="Maximum action budget"):
        await visual.run_visual(page, {"instruction": "Checkout"}, ctl, adapter, "ui-venus")
    page.mouse.click.assert_awaited_once()
    assert "model_completion" not in ctl.run
    assert ctl.run["success"] is False
    adapter.close.assert_awaited_once()


async def test_scroll_movement_counts_as_progress_but_never_enters_model_input(harness):
    page, ctl, state = harness
    # Each loop observes semantic state, viewport state, then post-scroll viewport.
    state.side_effect = ["same", "viewport-0", "viewport-1", "same", "viewport-1", "viewport-2", "same", "viewport-2", "viewport-3", "same", "viewport-3"]
    adapter = AdapterDouble([{"action": "scroll", "amount": 20}] * 3 + [{"action": "done"}])
    await visual.run_visual(page, {"instruction": "Read checkout"}, ctl, adapter, "ui-venus")
    assert page.mouse.wheel.await_count == 3
    assert all(e["action"] != "no_progress" for e in ctl.events)
    assert all("viewport-" not in json.dumps((task, history)) for _, task, history in adapter.inputs)


async def test_parse_failure_retains_raw_native_output_and_closes_adapter(harness):
    page, ctl, _ = harness
    raw = "<action>malformed()</action>"
    adapter = AdapterDouble([SpecialistOutputError("Malformed output")])
    adapter.last_metrics.update(raw_text=raw, usage={"prompt_tokens": 5, "completion_tokens": 2})
    with pytest.raises(SpecialistOutputError):
        await visual.run_visual(page, {"instruction": "Checkout"}, ctl, adapter, "ui-venus")
    call = ctl.usage.calls[0]
    assert call["raw_text"] == raw
    assert call["status"] == "failed"
    assert call["error_type"] == "SpecialistOutputError"
    assert ctl.usage.prompt_tokens == 5
    assert ctl.usage.completion_tokens == 2
    assert page.mutations() == 0
    adapter.close.assert_awaited_once()


@pytest.mark.parametrize("cause", ["TimeoutError", "JSONDecodeError"])
async def test_transport_cause_cannot_overwrite_inference_failure_classification(harness, cause):
    from backend.adapters.specialists import SpecialistInferenceError
    from backend.runner.engine import outcome_evidence
    page, ctl, _ = harness
    adapter = AdapterDouble([SpecialistInferenceError("Worker transport failed")])
    adapter.last_metrics.update(error_type=cause, actual_model=False)
    with pytest.raises(SpecialistInferenceError):
        await visual.run_visual(page, {"instruction": "Checkout"}, ctl, adapter, "ui-venus")
    call = ctl.usage.calls[0]
    assert call["error_type"] == "SpecialistInferenceError"
    assert call["adapter_error_type"] == cause
    evidence = outcome_evidence({"status": "blocked", "failure_reason": "inference_error", "calls": ctl.usage.calls})
    assert evidence["inference_failure_count"] == 1
    assert evidence["inference_failure_rate"] == 1
    assert evidence["outcome_category"] == "infrastructure_failure"
    assert page.mutations() == 0
    adapter.close.assert_awaited_once()


async def test_failed_drag_releases_pointer_and_records_single_failed_action(harness):
    page, ctl, _ = harness
    page.mouse.move.side_effect = [None, RuntimeError("Pointer interrupted")]
    adapter = AdapterDouble([{"action": "drag", "start": [1, 2], "end": [3, 4]}])
    with pytest.raises(RuntimeError, match="Pointer interrupted"):
        await visual.run_visual(page, {"instruction": "Drag"}, ctl, adapter, "ui-venus")
    page.mouse.up.assert_awaited_once()
    assert len(ctl.events) == 1
    assert ctl.events[0]["action"] == "invalid_action"
    assert ctl.events[0]["detail"]["execution_status"] == "failed"
    adapter.close.assert_awaited_once()


@pytest.mark.parametrize("mode", ["budget", "stop", "closed_pages", "private_task"])
async def test_adapter_cleanup_on_early_termination(harness, mode):
    page, ctl, _ = harness
    task = {"instruction": "Synthetic checkout"}
    adapter = AdapterDouble([])
    if mode == "budget":
        ctl.max_steps = 0
        expected = Stopped
    elif mode == "stop":
        ctl.check.side_effect = Stopped("Stopped")
        expected = Stopped
    elif mode == "closed_pages":
        page.context.pages = []
        expected = RuntimeError
    else:
        task["expected_values"] = {"email": "oracle@example.invalid"}
        expected = ValueError
    with pytest.raises(expected):
        await visual.run_visual(page, task, ctl, adapter, "ui-venus")
    assert not adapter.inputs
    assert page.mutations() == 0
    adapter.close.assert_awaited_once()


def test_protocol_hash_preserves_legacy_but_separates_runtime_versions():
    from backend.research.protocol import protocol_hash
    from scenarios.research import digest

    settings = {"seed": 2026, "max_steps": 100}
    old = digest({"settings": settings, "release_hash": "immutable"})
    runtime = {"runtime_source_hash": "source-a", "runtime_binding_hash": "review-a", "runtime_audited": True}
    assert protocol_hash(settings, "immutable") == old
    assert protocol_hash(settings, "immutable", None) == old
    assert protocol_hash(settings, "immutable", runtime) != old
    assert protocol_hash(settings, "immutable", runtime) != protocol_hash(settings, "immutable", {**runtime, "runtime_source_hash": "source-b"})


def test_official_population_separates_runtime_records_and_preserves_legacy(tmp_path, monkeypatch):
    from backend.research import official
    from backend.research.protocol import protocol_hash
    from tests.test_official_results import sample

    manifest, legacy_config, legacy_record = sample()
    runtime = {"runtime_source_hash": "source-a", "runtime_binding_hash": "review-a", "runtime_audited": True}
    config, record = deepcopy(legacy_config), deepcopy(legacy_record)
    config["runtime"] = runtime
    config["research_protocol_hash"] = protocol_hash(config["settings"], manifest["release_hash"], runtime)
    record.update(id="new-runtime", research_protocol_hash=config["research_protocol_hash"])
    record["execution_manifest"].update(runtime)
    assert official.select([legacy_record, record], manifest, legacy_config)[0] == [legacy_record]
    assert official.select([legacy_record, record], manifest, config)[0] == [record]
    mismatched = deepcopy(record)
    mismatched["execution_manifest"]["runtime_source_hash"] = "other"
    assert official.select([mismatched], manifest, config)[0] == []
    monkeypatch.setattr(official, "DATA", tmp_path)
    path = tmp_path / "research/official-protocol.json"
    path.parent.mkdir()
    for current in (legacy_config, config):
        path.write_text(json.dumps(current))
        assert official.configuration(manifest) == (current, None)


def test_readiness_checks_runtime_audit_without_obsolete_source_key(tmp_path, monkeypatch):
    from backend.research import protocol

    monkeypatch.setattr(protocol, "ROOT", tmp_path)
    monkeypatch.setattr(protocol, "release", lambda: {"release": "fixture-only", "release_hash": "release", "scenarios": []})
    monkeypatch.setattr(protocol, "review_status", lambda _: {"independent_human_review_complete": False})
    monkeypatch.setattr(protocol, "checkpoint_records", lambda: {})
    monkeypatch.setattr(protocol, "runtime_identity", lambda _: {"runtime_audited": False})
    report = protocol.readiness()
    assert report["checks"]["execution_sources_verified"] is False
    assert "frozen_sources_match" not in report["checks"]
    assert report["status"] == "NOT READY"
