"""Screenshot-only model decisions with shared browser execution and verification.

Public DOM state is used only by the bounded stall monitor, never to select an
action, complete the task, or construct model observations. Outcome scoring is
owned by Runner's independent verifier after this loop exits.
"""
import asyncio
import copy
import hashlib
import io
import json
import math
import time

from PIL import Image

from backend.adapters.base import Stopped, Usage
from backend.adapters.specialists import SpecialistOutputError, UnsupportedCapability
from backend.browser.v21 import NoProgress, ProgressGuard, page_state


def validate_action(action, size):
    """Validate the entire standardized action before touching the browser."""
    if not isinstance(action, dict) or not isinstance(action.get("action"), str):
        raise SpecialistOutputError("Visual adapter did not return an action object")
    kind = action["action"]
    supported = {"click", "double_click", "hover", "long_press", "drag", "type",
                 "press", "scroll", "wait", "done"}
    if kind not in supported:
        raise UnsupportedCapability("Unsupported visual action: " + kind)

    def point(p):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise SpecialistOutputError("A coordinate pair is required")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in p):
            raise SpecialistOutputError("Coordinates must be finite numbers")
        if not (0 <= p[0] < size[0] and 0 <= p[1] < size[1]):
            raise SpecialistOutputError("Coordinates are outside the screenshot")
    if kind in {"click", "double_click", "hover", "long_press"}:
        point((action.get("x"), action.get("y")))
    elif kind == "drag":
        point(action.get("start")); point(action.get("end"))
    elif kind == "type":
        if not isinstance(action.get("text"), str):
            raise SpecialistOutputError("Type requires text")
        if "submit" in action and not isinstance(action["submit"], bool):
            raise SpecialistOutputError("Type submit must be a boolean")
    elif kind == "scroll":
        if action.get("direction", "down") not in {"up", "down", "left", "right"}:
            raise SpecialistOutputError("Invalid scroll direction")
        amount = action.get("amount", 500)
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or not 0 < amount <= 3000:
            raise SpecialistOutputError("Invalid scroll amount")
    elif kind == "wait":
        seconds = action.get("seconds", 1)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 3:
            raise SpecialistOutputError("Wait duration must be between zero and three seconds")
    elif kind == "press":
        keys = str(action.get("key", "")).split("+")
        allowed = {"Control", "Meta", "Alt", "Shift", "Enter", "Tab", "Escape", "Backspace", "Delete",
                   "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown", "a", "c", "v", "x", "z"}
        if not 1 <= len(keys) <= 3 or any(k not in allowed for k in keys):
            raise UnsupportedCapability("Unsupported browser hotkey")
    return action


async def execute_action(page, action):
    kind = action["action"]
    if kind == "click":
        await page.mouse.click(action["x"], action["y"])
    elif kind == "double_click":
        await page.mouse.dblclick(action["x"], action["y"])
    elif kind == "hover":
        await page.mouse.move(action["x"], action["y"])
    elif kind in {"long_press", "drag"}:
        start = action["start"] if kind == "drag" else (action["x"], action["y"])
        await page.mouse.move(*start)
        await page.mouse.down()
        try:
            if kind == "drag":
                await page.mouse.move(*action["end"], steps=10)
            else:
                await asyncio.sleep(0.6)
        finally:
            await page.mouse.up()
    elif kind == "type":
        await page.keyboard.insert_text(action["text"])
        if action.get("submit"):
            await page.keyboard.press("Enter")
    elif kind == "press":
        await page.keyboard.press(action["key"])
    elif kind == "scroll":
        direction, amount = action.get("direction", "down"), action.get("amount", 500)
        await page.mouse.wheel((-amount if direction == "left" else amount if direction == "right" else 0),
                               (-amount if direction == "up" else amount if direction == "down" else 0))
    elif kind == "wait":
        await asyncio.sleep(action.get("seconds", 1))


async def run_visual(page, task, ctl, adapter, model):
    usage, history, guard = Usage(), [], ProgressGuard(limit=3)
    ctl.usage = usage
    ctl.run["observation_track"] = "screenshot_gui"
    ctl.run["visual_protocol"] = {
        "model_observations": "screenshot, public customer task, previous model actions",
        "dom_access_to_model": False, "semantic_repair": False,
        "completion": "model declaration followed by independent outcome verification",
        "stall_monitor": "three equivalent actions without visible public state change; DOM telemetry is not provided to model",
        "viewport": ctl.run["viewport"], "device_scale_factor": 1,
    }
    try:
        if any(k in task for k in ("expected_values", "expected_entity_keys", "dom_ids", "fields")):
            raise ValueError("Private scenario data cannot enter visual inference")
        observations = ctl.directory / "observations"
        observations.mkdir(exist_ok=True)
        for step in range(ctl.max_steps):
            await ctl.check()
            pages = [p for p in page.context.pages if not p.is_closed()]
            if not pages:
                raise RuntimeError("No checkout browser page remains")
            page = pages[-1]
            ctl.page = page
            before = await page_state(page)
            before_scroll = await page_state(page, include_viewport=True)
            capture = time.perf_counter()
            png = await page.screenshot()
            image = Image.open(io.BytesIO(png)).convert("RGB")
            ctl.timings["model_screenshot_seconds"] += time.perf_counter() - capture
            observation = observations / f"{step:04d}.png"
            observation.write_bytes(png)
            call = {"model": model, "operation": "act", "input": {
                "screenshot": str(observation.relative_to(ctl.directory)),
                "screenshot_sha256": hashlib.sha256(png).hexdigest(),
                "image_size": list(image.size), "task": copy.deepcopy(task),
                "history": copy.deepcopy(history)}, "status": "started"}
            usage.calls.append(call)
            start = time.perf_counter()
            try:
                action = await adapter.act(image, copy.deepcopy(task), copy.deepcopy(history))
                call["output"] = copy.deepcopy(action)
                validate_action(action, image.size)
                call["status"] = "generated"
            except BaseException as exc:
                call.update(status="failed", error_type=type(exc).__name__)
                raise
            finally:
                elapsed = time.perf_counter() - start
                usage.inference_seconds += elapsed
                metadata = copy.deepcopy(getattr(adapter, "last_metrics", {}))
                # Adapter transport details must not replace the exception class
                # caught by the shared runner (used by failure-rate accounting).
                cause = metadata.pop("error_type", None)
                if cause is not None:
                    metadata["adapter_error_type"] = cause
                call.update(metadata, seconds=elapsed)
                if callable(getattr(adapter, "metadata", None)):
                    ctl.run["inference_configuration"] = copy.deepcopy(adapter.metadata())
                tokens = metadata.get("usage", {})
                usage.prompt_tokens += tokens.get("prompt_tokens", 0)
                usage.completion_tokens += tokens.get("completion_tokens", 0)
                if getattr(adapter, "endpoint", ""):
                    usage.cost_kind = "not_reported"
                if tokens.get("cost") is not None:
                    usage.cost += tokens["cost"]
            if action["action"] == "done":
                ctl.run["model_completion"] = copy.deepcopy(action)
                # No success is inferred from the model's self-report.
                return usage
            browser_started = time.perf_counter()
            try:
                await execute_action(page, action)
                await page.wait_for_timeout(150)
            except Exception as exc:
                await ctl.record("invalid_action", {"prediction": action, "error_type": type(exc).__name__,
                    "execution_status": "failed", "selection_source": "model"})
                raise
            finally:
                ctl.timings["browser_execution_seconds"] += time.perf_counter() - browser_started
            history.append(action)
            await ctl.record("visual_action", {**action, "selection_source": "model",
                "grounding_source": model, "execution_status": "executed", "call_index": len(usage.calls)-1})
            # Reuse the shared bounded public-state policy without leaking it.
            scroll = action["action"] == "scroll"
            after = await page_state(page, include_viewport=scroll)
            semantic_keys = {"action", "x", "y", "start", "end", "text", "submit", "key", "direction", "amount", "seconds"}
            signature = json.dumps({k: v for k, v in action.items() if k in semantic_keys}, sort_keys=True)
            count = guard.observe(signature, before_scroll if scroll else before, after)
            if count >= guard.limit:
                diagnostics = {"reason": "repeated_visual_action", "count": count, "limit": guard.limit,
                               "state_fingerprint": after, "action": action["action"]}
                await ctl.record("no_progress", diagnostics)
                raise NoProgress(diagnostics)
        raise Stopped("Maximum action budget reached")
    finally:
        close = getattr(adapter, "close", None)
        if close:
            await close()
