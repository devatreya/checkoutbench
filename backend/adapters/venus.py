"""UI-Venus 1.5 native web adapter with isolated, cancellable local MLX inference.

The worker receives only the public task, action history and screenshot. It has
no browser, evaluator, scenario lookup, database or DOM access. See operations docs.
"""
from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
from typing import Any

from backend.adapters.specialists import SpecialistUnavailable, SpecialistOutputError

MODEL_ID = "inclusionAI/UI-Venus-1.5-2B"
UPSTREAM_REVISION = "bc4c6e62a1c545e043761439be95646d801853a4"
ARTIFACT_ID = "mlx-community/UI-Venus-1.5-2B-6bit"
ARTIFACT_REVISION = "95e3994ac9d74fe047cf44c072f6569db62856e7"
ADAPTER_VERSION = "ui-venus-1.5-web-mlx-v2-normalized1000"
ROOT = Path(__file__).resolve().parents[2]
PUBLIC_TASK_KEYS = frozenset({"instruction", "profile", "payment_request", "preferences",
    "registration_consent", "allowed_payment_alternatives", "maximum_fare", "slot_fallback", "delivery_fallback", "separate_billing"})

# Native web prompt from inclusionAI/UI-Venus, UI-Venus-1.5 branch, pinned at
# 192a9247ad1129279ba1d6c263d4c9e7ecef3644/models/navigation/utils.py.
# Model-native action declarations are preserved; unsupported actions are
# classified explicitly by the adapter rather than silently rewritten.
WEB_USER_PROMPT = """
**You are a GUI Agent.**
Your task is to analyze a given user task, review current screenshot and previous actions, and determine the next action to complete the task.

### Available Actions
You may execute one of the following functions:
- Click(box=(x1,y1))
- Drag(start=(x1,y1), end=(x2,y2))
- Scroll(direction='down or up')
- Type(content='')
- Launch(app='' or url='')
- Wait()
- Finished(content='')
- CallUser(content='')
- LongPress(box=(x1,y1))
- PressBack()
- PressHome()
- PressEnter()
- PressRecent()
- Hover(box=(x1,y1))
- DoubleClick(box=(x1,y1))
- Hotkey(keys=['ctrl', 'c']) # Split keys with comma and wrap each key in single quotes. Do not use more than 3 keys in one Hotkey action.

### User Task
{user_task}

### Previous Actions
{previous_actions}

### Output Format
<think> your thinking process </think>
<action> the next action </action>
<conclusion> the conclusion about the next action </conclusion>

### Instruction
- Make sure you understand the task goal to avoid wrong actions.
- Make sure you carefully examine the the current screenshot. Sometimes the summarized history might not be reliable, over-claiming some effects.
- For complex information-retrieval tasks, use `CallUser(content='...')` to reply only at the very end, after gathering all required info. Combine web evidence with your reasoning.
- To input text: first `Click(box=...)` on the textbox, then `Type(content='...')`. The system automatically presses `ENTER` afterward. If search filters are needed, click the search button after typing.
- Try to use simple language when searching.
- Distinguish textbox from button: never `Type` into a button. If no textbox is visible, try clicking the search icon first — the input field may appear afterward.
- Execute only one action per step.
- Strictly avoid repeating the same action when the webpage remains unchanged — you may have executed the wrong action. Continuous use of `Wait()` is also NOT allowed.
"""
SYSTEM_PROMPT = "You are a helpful assistant."


def _output_error(message, raw):
    error = SpecialistOutputError(message)
    error.raw_text = raw
    return error


def _unsupported(message, raw):
    # Imported at call time so the compatibility bridge can live in specialists.
    from backend.adapters.specialists import UnsupportedCapability
    error = UnsupportedCapability(message)
    error.raw_text = raw
    return error


def _point(value, original):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("Expected exactly two normalized [0,1000] coordinates")
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in value):
        raise ValueError("Coordinates must be finite numbers")
    x, y = value
    if not 0 <= x <= 1000 or not 0 <= y <= 1000:
        raise ValueError("Coordinate lies outside the native [0,1000] range")
    # UI-Venus 1.5 report §3.1.1 normalizes all spatial targets to [0,1000].
    # The inclusive endpoint denotes the viewport edge, whose last pixel is w-1/h-1.
    return min(original[0] - 1, int(x * original[0] / 1000)), min(original[1] - 1, int(y * original[1] / 1000))


def parse_venus_action(raw: str, original_size: tuple[int, int], model_size: tuple[int, int] | None = None) -> dict:
    """Parse native 1.5 actions; model_size validates observation metadata only.

    Coordinates always use the documented [0,1000] space, irrespective of resize.
    """
    if not isinstance(raw, str) or len(raw) > 100000:
        raise _output_error("Missing or oversized native output", raw)
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in (*original_size, *(model_size or original_size))):
        raise ValueError("Image dimensions must be positive integers")
    if raw.count("<action>") != 1 or raw.count("</action>") != 1:
        raise _output_error("Expected exactly one native <action>...</action>", raw)
    expression = raw.split("<action>", 1)[1].split("</action>", 1)[0].strip()
    try:
        node = ast.parse(expression, mode="eval").body
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.args:
            raise ValueError("Expected one native function with keyword arguments")
        if any(kw.arg is None for kw in node.keywords):
            raise ValueError("Argument expansion is forbidden")
        args = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
        if len(args) != len(node.keywords):
            raise ValueError("Duplicate argument")
        name = node.func.id
        schemas = {
            "Click": ({"box"}, set()), "LongPress": ({"box"}, set()), "Hover": ({"box"}, set()), "DoubleClick": ({"box"}, set()),
            "Drag": ({"start", "end"}, set()), "Scroll": ({"direction"}, set()), "Type": ({"content"}, set()),
            "Wait": (set(), set()), "Finished": (set(), {"content"}), "CallUser": ({"content"}, set()),
            "PressEnter": (set(), set()), "Hotkey": ({"keys"}, set()),
            "Launch": (set(), {"app", "url"}), "PressBack": (set(), set()), "PressHome": (set(), set()), "PressRecent": (set(), set()),
        }
        if name not in schemas:
            raise ValueError(f"Unknown native action: {name}")
        required, optional = schemas[name]
        if not required <= args.keys() or args.keys() - required - optional:
            raise ValueError(f"Incorrect arguments for {name}")
        result = {"raw": raw, "native_action": expression}
        if name in {"Launch", "PressBack", "PressHome", "PressRecent"}:
            raise _unsupported(f"Native action {name} is unsupported in the confined browser track", raw)
        if name in {"Click", "LongPress", "Hover", "DoubleClick"}:
            result.update(action={"Click": "click", "LongPress": "long_press", "Hover": "hover", "DoubleClick": "double_click"}[name])
            result["x"], result["y"] = _point(args["box"], original_size)
        elif name == "Drag":
            result.update(action="drag", start=_point(args["start"], original_size), end=_point(args["end"], original_size))
        elif name == "Scroll":
            if args["direction"] not in {"up", "down"}:
                raise ValueError("Native web Scroll supports up/down")
            result.update(action="scroll", direction=args["direction"], amount=500)
        elif name in {"Type", "Finished", "CallUser"}:
            content = args.get("content", "")
            if not isinstance(content, str) or len(content) > 10000:
                raise ValueError("Action content must be bounded text")
            if name == "Type":
                result.update(action="type", text=content, submit=True)
            else:
                result.update(action="done", status="success" if name == "Finished" else "needs_user", text=content)
        elif name == "PressEnter":
            result.update(action="press", key="Enter")
        elif name == "Hotkey":
            keys = args["keys"]
            allowed = {"ctrl": "Control", "alt": "Alt", "shift": "Shift", "meta": "Meta", "enter": "Enter", "tab": "Tab", "backspace": "Backspace", "delete": "Delete", "escape": "Escape", "a": "a", "c": "c", "v": "v", "x": "x", "z": "z", "arrowleft": "ArrowLeft", "arrowright": "ArrowRight", "arrowup": "ArrowUp", "arrowdown": "ArrowDown"}
            if not isinstance(keys, list) or not 1 <= len(keys) <= 3 or any(not isinstance(k, str) or k.lower() not in allowed for k in keys):
                raise _unsupported("Native Hotkey is not supported in this browser track", raw)
            result.update(action="press", key="+".join(allowed[k.lower()] for k in keys))
        elif name == "Wait":
            result.update(action="wait", seconds=1)
        return result
    except (SyntaxError, TypeError, KeyError, ValueError) as exc:
        if isinstance(exc, SpecialistOutputError):
            raise
        raise _output_error(f"Invalid UI-Venus native action: {exc}", raw) from exc


def image_size_for_model(size: tuple[int, int], max_pixels: int = 1003520) -> tuple[int, int]:
    """Use the actual Qwen3-VL patch16 × merge2 grid, with aspect ratio preserved."""
    width, height = size
    if min(width, height) <= 0 or max(width, height) / min(width, height) > 200:
        raise ValueError("Unsupported screenshot dimensions")
    if not 65536 <= max_pixels <= 16777216:
        raise ValueError("max_pixels must be in [65536, 16777216]")
    w, h = max(32, round(width / 32) * 32), max(32, round(height / 32) * 32)
    if w * h > max_pixels:
        factor = math.sqrt(width * height / max_pixels)
        w, h = max(32, math.floor(width / factor / 32) * 32), max(32, math.floor(height / factor / 32) * 32)
    elif w * h < 65536:
        factor = math.sqrt(65536 / (width * height))
        w, h = math.ceil(width * factor / 32) * 32, math.ceil(height * factor / 32) * 32
    return w, h


def build_prompt(task: dict, history: list[dict], history_limit: int = 20) -> str:
    if not isinstance(task, dict) or not isinstance(task.get("instruction"), str):
        raise ValueError("Venus requires the public task dict with an instruction")
    public = {key: task[key] for key in task if key in PUBLIC_TASK_KEYS}
    previous = []
    for index, item in enumerate(history[-history_limit:] if history_limit else []):
        # Only native model output and execution feedback; never selectors/DOM.
        raw = item.get("raw", "")
        if raw:
            previous.append(f"Step {index}: {raw}")
        if item.get("execution_error"):
            previous.append("Execution feedback: " + str(item["execution_error"])[:500])
    return WEB_USER_PROMPT.format(user_task=json.dumps(public, ensure_ascii=False, indent=2), previous_actions="\n".join(previous))


def _env_or_default(name: str, default: str) -> str:
    """Empty .env placeholders mean unset; preserve explicit values, including 0."""
    value = os.getenv(name)
    return default if value is None or not value.strip() else value


def local_configuration() -> dict:
    return {"model_path": _env_or_default("UI_VENUS_MODEL_PATH", str(ROOT / "data/models/ui-venus-1.5-2b-mlx-6bit")),
            "python": _env_or_default("UI_VENUS_PYTHON", str(ROOT / ".venv-venus/bin/python")),
            "backend": _env_or_default("UI_VENUS_BACKEND", "mlx"),
            "max_pixels": int(_env_or_default("UI_VENUS_MAX_PIXELS", "1003520")),
            "inference_timeout_seconds": float(_env_or_default("UI_VENUS_INFERENCE_TIMEOUT", "180")),
            "memory_limit_bytes": int(_env_or_default("UI_VENUS_MEMORY_LIMIT_BYTES", "4250000000")),
            "history_limit": int(_env_or_default("UI_VENUS_HISTORY_LIMIT", "20"))}


def availability() -> dict:
    cfg = local_configuration()
    problems = []
    if cfg["backend"] != "mlx":
        problems.append("Only the verified local MLX backend is currently implemented")
    if os.getenv("UI_VENUS_ENDPOINT"):
        problems.append("This local-only adapter does not use UI_VENUS_ENDPOINT; unset it")
    if not Path(cfg["python"]).is_file():
        problems.append("Isolated MLX Python environment is missing; run local setup")
    root = Path(cfg["model_path"])
    if not (root / "model.safetensors").is_file() or not (root / "checkoutbench_provenance.json").is_file():
        problems.append("Pinned local model/provenance missing; run venus_setup.py")
    return {"available": not problems, "status": "configured_unverified" if not problems else "unavailable",
            "backend": "mlx-vlm-local-worker", "reason": "; ".join(problems) or None,
            "model_id": MODEL_ID, "artifact_id": ARTIFACT_ID, "artifact_revision": ARTIFACT_REVISION,
            "precision": "affine-6bit-group64-mixed-bf16"}


class VenusAdapter:
    endpoint = ""
    model_id = MODEL_ID

    def __init__(self, *, max_tokens: int = 2048, device: str | None = None):
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 8192:
            raise ValueError("max_tokens must be between 1 and 8192")
        if device not in {None, "auto", "mps", "metal"}:
            raise SpecialistUnavailable("The local UI-Venus MLX adapter requires Apple Metal")
        self.config = local_configuration()
        self.max_tokens = max_tokens
        self.last_metrics: dict = {}
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._runtime_metadata: dict = {}
        self._stderr_task = None
        self._stderr_tail = ""

    def metadata(self) -> dict:
        return {"model_id": MODEL_ID, "model_revision": ARTIFACT_REVISION, "upstream_reference_revision": UPSTREAM_REVISION,
                "upstream_conversion_revision_status": "community converter did not publish an exact upstream source commit",
                "checkpoint_revision": ARTIFACT_REVISION, "artifact_id": ARTIFACT_ID,
                "adapter_version": ADAPTER_VERSION, "backend": "mlx-vlm-local-worker",
                "precision": "affine-6bit-group64-mixed-bf16", "quantization": {"bits": 6, "group_size": 64, "mode": "affine"},
                "prompt_sha256": hashlib.sha256(WEB_USER_PROMPT.encode()).hexdigest(),
                "prompt_template": WEB_USER_PROMPT, "system_prompt": SYSTEM_PROMPT,
                "decoding": {"temperature": 0.0, "top_p": 1.0, "max_tokens": self.max_tokens, "prefill_step_size": 256, "seed": 0, "repetition_penalty": 1.0, "repetition_penalty_application": "disabled; mlx-vlm default None"},
                "context_strategy": {"current_screenshot_only": True, "native_action_history_limit": self.config["history_limit"]},
                "coordinate_space": "normalized [0,1000] mapped directly to original viewport; inclusive 1000 maps to last pixel",
                "coordinate_contract_source": "https://arxiv.org/html/2602.09082v1#S3.SS1.SSS1",
                "runtime_config": {k: v for k, v in self.config.items() if k not in {"python", "model_path"}},
                **self._runtime_metadata}

    async def _drain_stderr(self):
        while self._process and self._process.stderr:
            part = await self._process.stderr.read(4096)
            if not part:
                break
            self._stderr_tail = (self._stderr_tail + part.decode(errors="replace"))[-8000:]

    async def _start(self):
        if self._process and self._process.returncode is None:
            return
        status = availability()
        if not status["available"]:
            raise SpecialistUnavailable(status["reason"])
        env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
        self._process = await asyncio.create_subprocess_exec(self.config["python"], "-u", str(ROOT / "scripts/diagnostics/venus_worker.py"), "--model", self.config["model_path"], "--memory-limit", str(self.config["memory_limit_bytes"]), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, cwd=ROOT, limit=4 * 1024 * 1024)
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _request(self, payload):
        await self._start()
        assert self._process and self._process.stdin and self._process.stdout
        self._process.stdin.write(json.dumps(payload).encode() + b"\n")
        await self._process.stdin.drain()
        line = await self._process.stdout.readline()
        if not line:
            from backend.adapters.specialists import SpecialistInferenceError
            raise SpecialistInferenceError("UI-Venus local worker exited without a response: " + self._stderr_tail[-1500:])
        response = json.loads(line)
        if response.get("error"):
            from backend.adapters.specialists import SpecialistInferenceError
            cls = SpecialistUnavailable if response.get("category") == "unavailable" else SpecialistInferenceError
            raise cls(response["error"])
        return response

    async def act(self, image: Any, task: dict, history: list[dict]) -> dict:
        async with self._lock:
            self.last_metrics = {"actual_model": False, "backend": "mlx-vlm-local-worker"}
            started = time.perf_counter()
            prompt = build_prompt(task, history, self.config["history_limit"])
            prepared = image.convert("RGB").resize(image_size_for_model(image.size, self.config["max_pixels"]))
            buffer = io.BytesIO()
            prepared.save(buffer, format="PNG")
            payload = {"prompt": prompt, "system_prompt": SYSTEM_PROMPT, "image_base64": base64.b64encode(buffer.getvalue()).decode(), "image_size": list(prepared.size), "max_tokens": self.max_tokens}
            try:
                response = await asyncio.wait_for(self._request(payload), self.config["inference_timeout_seconds"])
            except asyncio.CancelledError:
                await self.close()
                raise
            except Exception as exc:
                self.last_metrics.update(inference_seconds=time.perf_counter() - started, error_type=type(exc).__name__)
                await self.close()
                if isinstance(exc, SpecialistUnavailable):
                    raise
                from backend.adapters.specialists import SpecialistInferenceError
                if isinstance(exc, SpecialistInferenceError):
                    raise
                raise SpecialistInferenceError(f"UI-Venus worker failed: {type(exc).__name__}: {exc}") from exc
            self._runtime_metadata = response.get("metadata", {})
            raw = response["raw_text"]
            self.last_metrics = {**response.get("metrics", {}), "actual_model": True, "inference_kind": "actual_model", "raw_text": raw,
                "inference_seconds": time.perf_counter() - started, "backend": "mlx-vlm-local-worker",
                "original_image_size": list(image.size), "model_image_size": list(prepared.size),
                "image_sha256": hashlib.sha256(buffer.getvalue()).hexdigest(),
                "request_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "request_prompt": prompt,
                "metadata": self.metadata()}
            return parse_venus_action(raw, image.size, prepared.size)

    async def close(self):
        proc, self._process = self._process, None
        if proc and proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), 3)
            except (asyncio.TimeoutError, ProcessLookupError):
                if proc.returncode is None:
                    proc.kill()
                    await proc.wait()
        if self._stderr_task:
            self._stderr_task.cancel()
            await asyncio.gather(self._stderr_task, return_exceptions=True)
            self._stderr_task = None
