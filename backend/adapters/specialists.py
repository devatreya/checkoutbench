"""Genuine, lazy specialist inference. No weights are downloaded by this module.

Heavy dependencies are optional. Local paths must contain audited safetensors;
remote endpoints must serve the exact configured model, never a substitute.
See docs/SPECIALISTS.md for the wire contracts and upstream references.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import re
import threading
import time
from pathlib import Path
from typing import Any


class SpecialistUnavailable(RuntimeError):
    """Missing dependency, checkpoint, hardware support or inference service."""


class SpecialistOutputError(ValueError):
    """Invalid model output; this is a genuine failed model decision."""


SPECS = {
    "cua-s1": ("CUA_S1", "cua-ai/cua-s1-forms", 706048, "field_classification"),
    "tinyclick": ("TINYCLICK", "kzawistowsk/TinyClick", 270000000, "visual_grounding"),
    "mai-ui": ("MAI_UI", "Tongyi-MAI/MAI-UI-2B", 2000000000, "gui_agent"),
    "ui-venus": ("UI_VENUS", "inclusionAI/UI-Venus-1.5-2B", 2000000000, "gui_agent"),
}


def detect_hardware() -> dict:
    result = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "cpu": True,
        "cuda": False,
        "mps": False,
        "device": "cpu",
        "torch": None,
    }
    try:
        import torch

        result.update(
            torch=torch.__version__,
            cuda=torch.cuda.is_available(),
            mps=bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            ),
        )
        result["device"] = (
            "cuda" if result["cuda"] else "mps" if result["mps"] else "cpu"
        )
        if result["cuda"]:
            result["gpu"] = torch.cuda.get_device_name(0)
            result["gpu_memory_bytes"] = torch.cuda.get_device_properties(
                0
            ).total_memory
    except ImportError:
        pass
    return result


def specialist_catalog() -> list[dict]:
    hardware = detect_hardware()
    rows = []
    for key, (prefix, model_id, count, capability) in SPECS.items():
        path, endpoint = (
            os.getenv(prefix + "_MODEL_PATH", ""),
            os.getenv(prefix + "_ENDPOINT", ""),
        )
        issues = []
        if not endpoint:
            if not path or not Path(path).exists():
                issues.append(
                    f"Set {prefix}_MODEL_PATH to local weights or {prefix}_ENDPOINT"
                )
            if path and Path(path).exists():
                root = Path(path)
                tensors = (
                    [root]
                    if root.suffix == ".safetensors"
                    else list(root.glob("*.safetensors"))
                )
                if not tensors:
                    issues.append("No safetensors checkpoint present")
                if (
                    key == "cua-s1"
                    and not (
                        root.with_suffix(".json")
                        if root.is_file()
                        else root / "cua-s1-forms.json"
                    ).is_file()
                ):
                    issues.append("Required CUA-S1 signed JSON sidecar is missing")
            for module in (
                ["torch", "cua_s1", "safetensors"]
                if key == "cua-s1"
                else ["torch", "transformers", "PIL"]
            ):
                if importlib.util.find_spec(module) is None:
                    issues.append(f"Missing Python dependency: {module}")
            selected = os.getenv(prefix + "_DEVICE", "auto")
            if selected.startswith("cuda") and not hardware["cuda"]:
                issues.append("CUDA requested but unavailable")
            if selected == "mps" and not hardware["mps"]:
                issues.append("MPS requested but unavailable")
        rows.append(
            {
                "id": key,
                "model_id": model_id,
                "name": model_id.split("/")[-1],
                "parameters": count,
                "capability": capability,
                "kind": "specialist",
                "reasoning_levels": ["default"],
                "available": not issues,
                "backend": "remote" if endpoint else "local",
                "status": "configured_unverified" if not issues else "unavailable",
                "reason": "; ".join(issues)
                or "Configured; first inference validates runtime compatibility",
                "hardware": hardware,
            }
        )
    components = [row for row in rows if row["id"] in {"cua-s1", "tinyclick"}]
    available = all(row["available"] for row in components)
    rows.append(
        {
            "id": "hybrid",
            "model_id": "cua-ai/cua-s1-forms+kzawistowsk/TinyClick",
            "name": "CUA-S1 + TinyClick hybrid",
            "parameters": 270706048,
            "kind": "specialist",
            "capability": "field_classification+visual_grounding",
            "reasoning_levels": ["default"],
            "available": available,
            "backend": "+".join(row["backend"] for row in components),
            "status": "configured_unverified" if available else "unavailable",
            "reason": "; ".join(
                row["reason"] for row in components if not row["available"]
            )
            or "Both components configured; inference unverified",
            "hardware": hardware,
        }
    )
    return rows


def _image_url(image: Any) -> str:
    stream = io.BytesIO()
    image.convert("RGB").save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode(
        "ascii"
    )


def _point(
    coords: Any, size: tuple[int, int], scale: tuple[float, float]
) -> tuple[int, int]:
    if not isinstance(coords, (list, tuple)) or len(coords) not in (2, 4):
        raise SpecialistOutputError("Expected a point or bounding box")
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in coords
    ):
        raise SpecialistOutputError("Coordinates must be finite numbers")
    if len(coords) == 4:
        if coords[2] < coords[0] or coords[3] < coords[1]:
            raise SpecialistOutputError("Inverted bounding box")
        coords = [(coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2]
    x, y = coords
    if not 0 <= x <= scale[0] or not 0 <= y <= scale[1]:
        raise SpecialistOutputError("Coordinate outside screenshot")
    return min(size[0] - 1, int(x * size[0] / scale[0])), min(
        size[1] - 1, int(y * size[1] / scale[1])
    )


def parse_tinyclick(raw: str, size: tuple[int, int]) -> dict:
    """Florence location tokens: a point or a bounding box, in 1000 bins."""
    coords = [int(x) for x in re.findall(r"<loc_(\d+)>", raw)]
    if len(coords) not in (2, 4) or any(v > 999 for v in coords):
        raise SpecialistOutputError(
            "TinyClick must return two or four Florence <loc_N> tokens"
        )
    x, y = _point([v + 0.5 for v in coords], size, (1000, 1000))
    return {"action": "click", "x": x, "y": y, "raw": raw, "confidence": None}


def parse_mai(raw: str, size: tuple[int, int]) -> dict:
    matches = re.findall(r"<tool_call>(.*?)</tool_call>", raw, re.S)
    if len(matches) != 1:
        raise SpecialistOutputError("MAI-UI must return exactly one tool_call")
    try:
        call = json.loads(matches[0])
        if call.get("name") != "mobile_use" or not isinstance(
            call.get("arguments"), dict
        ):
            raise ValueError("Expected mobile_use arguments")
        args = call["arguments"]
        name = args["action"]
        result = {"action": name, "raw": raw}
        if name in {"click", "long_press", "double_click"}:
            result["x"], result["y"] = _point(args["coordinate"], size, (999, 999))
        elif name == "type":
            if not isinstance(args.get("text"), str):
                raise ValueError("Missing text")
            result["text"] = args["text"]
        elif name == "swipe":
            direction = args["direction"]
            if direction not in {"up", "down", "left", "right"}:
                raise ValueError("Invalid swipe direction")
            result.update(action="scroll", direction=direction, amount=500)
            if "coordinate" in args:
                result["x"], result["y"] = _point(args["coordinate"], size, (999, 999))
        elif name == "drag":
            result["start"] = _point(args["start_coordinate"], size, (999, 999))
            result["end"] = _point(args["end_coordinate"], size, (999, 999))
        elif name == "system_button" and args.get("button") == "enter":
            result.update(action="press", key="Enter")
        elif name == "wait":
            result["seconds"] = 1
        elif name == "terminate":
            if args.get("status") not in {"success", "fail"}:
                raise ValueError("Invalid termination status")
            result.update(action="done", status=args["status"])
        elif name == "answer":
            result.update(action="done", status="answer", text=args.get("text", ""))
        else:
            raise ValueError(f"Unsupported browser action: {name}")
        return result
    except (KeyError, TypeError, ValueError) as exc:
        raise SpecialistOutputError(f"Invalid MAI-UI action: {exc}") from exc


def parse_venus(
    raw: str, size: tuple[int, int], resized_size: tuple[int, int] | None = None
) -> dict:
    """Parse the official 1.5 function grammar without eval or code execution."""
    matches = re.findall(r"<action>(.*?)</action>", raw, re.S)
    if len(matches) != 1:
        raise SpecialistOutputError("UI-Venus must return exactly one action")
    try:
        node = ast.parse(matches[0].strip(), mode="eval").body
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.args
        ):
            raise ValueError("Expected one named function with keyword arguments")
        if any(kw.arg is None for kw in node.keywords):
            raise ValueError("Argument expansion is forbidden")
        args = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
        if len(args) != len(node.keywords):
            raise ValueError("Duplicate keywords")
        name = node.func.id
        result = {"action": name.lower(), "raw": raw}
        if name in {"Click", "LongPress", "DoubleClick", "Hover"}:
            result["action"] = {
                "Click": "click",
                "LongPress": "long_press",
                "DoubleClick": "double_click",
                "Hover": "hover",
            }[name]
            result["x"], result["y"] = _point(args["box"], size, resized_size or size)
        elif name == "Type":
            if not isinstance(args.get("content"), str):
                raise ValueError("Missing text")
            result.update(action="type", text=args["content"], submit=True)
        elif name == "Scroll":
            if args.get("direction") not in {"down", "up", "left", "right"}:
                raise ValueError("Only direction-based browser scrolling is supported")
            result.update(direction=args["direction"], amount=500)
        elif name == "Drag":
            result["start"] = _point(args["start"], size, resized_size or size)
            result["end"] = _point(args["end"], size, resized_size or size)
        elif name == "PressEnter":
            result.update(action="press", key="Enter")
        elif name == "Hotkey":
            keys = args.get("keys")
            allowed = {
                "ctrl": "Control",
                "alt": "Alt",
                "shift": "Shift",
                "meta": "Meta",
                "enter": "Enter",
                "tab": "Tab",
                "backspace": "Backspace",
                "a": "a",
                "c": "c",
                "v": "v",
            }
            if (
                not isinstance(keys, list)
                or not 1 <= len(keys) <= 3
                or any(k not in allowed for k in keys)
            ):
                raise ValueError("Unsupported hotkey")
            result.update(action="press", key="+".join(allowed[k] for k in keys))
        elif name == "Wait":
            result["seconds"] = 1
        elif name in {"Finished", "CallUser"}:
            result.update(
                action="done",
                status="success" if name == "Finished" else "needs_user",
                text=args.get("content", ""),
            )
        else:
            raise ValueError(f"Unsupported browser action: {name}")
        return result
    except (SyntaxError, TypeError, KeyError, ValueError) as exc:
        raise SpecialistOutputError(f"Invalid UI-Venus action: {exc}") from exc


class _Adapter:
    key: str

    def __init__(self, *, max_tokens: int = 2048, device: str | None = None):
        self.prefix, self.model_id, _, _ = SPECS[self.key]
        self.path = os.getenv(self.prefix + "_MODEL_PATH", "")
        self.endpoint = os.getenv(self.prefix + "_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv(self.prefix + "_API_KEY", "")
        self.device = device or os.getenv(self.prefix + "_DEVICE", "auto")
        self.served_model = os.getenv(self.prefix + "_SERVED_MODEL", self.model_id)
        self.max_tokens = max_tokens
        self.model = self.processor = None
        self.last_metrics: dict = {}
        self._load_seconds = 0.0
        self._lock = threading.Lock()

    async def _post(self, suffix: str, payload: dict) -> dict:
        import httpx

        headers = {"Authorization": "Bearer " + self.api_key} if self.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                response = await client.post(
                    self.endpoint + suffix, json=payload, headers=headers
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Do not stringify response bodies or URLs that could disclose credentials.
            raise SpecialistUnavailable(
                f"{self.model_id} endpoint request failed ({type(exc).__name__})"
            ) from exc

    def _device(self):
        import torch

        name = detect_hardware()["device"] if self.device == "auto" else self.device
        if name.startswith("cuda") and not torch.cuda.is_available():
            raise SpecialistUnavailable("CUDA requested but unavailable")
        if name == "mps" and not torch.backends.mps.is_available():
            raise SpecialistUnavailable("MPS requested but unavailable")
        return torch.device(name)

    def _require_path(self):
        if not self.path or not Path(self.path).exists():
            raise SpecialistUnavailable(
                f"Configure {self.prefix}_MODEL_PATH or {self.prefix}_ENDPOINT"
            )

    async def _local(self, fn, *args):
        def locked():
            with self._lock:
                return fn(*args)

        try:
            return await asyncio.to_thread(locked)
        except SpecialistOutputError:
            raise
        except SpecialistUnavailable:
            raise
        except Exception as exc:
            raise SpecialistUnavailable(
                f"{self.model_id} local inference failed: {type(exc).__name__}: {exc}"
            ) from exc


CUA_INPUT_PROTOCOLS = ("path-v1", "path-v2", "document-v2")


def cua_inputs(elements: list[dict], profile: dict, protocol: str = "path-v2"):
    """Serialize public observations and document candidates only.

    path-v1 reproduces the historical adapter. path-v2 fixes state/hints while
    keeping candidate labels unchanged. document-v2 is an opt-in experiment:
    sentence-case leaf labels followed by all parent qualifiers. No candidates
    are filtered, deduplicated, reordered, or chosen using a target field.
    """
    if protocol not in CUA_INPUT_PROTOCOLS:
        raise ValueError(f"Unknown CUA input protocol: {protocol}")
    entities: list[tuple[str, str]] = []

    def flatten(value, prefix=""):
        for key, item in value.items():
            label = f"{prefix}.{key}" if prefix else key
            if isinstance(item, dict):
                flatten(item, label)
            elif isinstance(item, (str, int, float)) and not isinstance(item, bool):
                if isinstance(item, float) and not math.isfinite(item):
                    raise ValueError("CUA candidate numbers must be finite")
                entities.append((label, str(item)))

    flatten(profile)
    options = []
    for key, value in entities:
        parts = key.replace("_", " ").split(".")
        label = " ".join(parts)
        if protocol == "document-v2":
            leaf = parts[-1]
            label = leaf[:1].upper() + leaf[1:]
            if len(parts) > 1:
                label += " (" + " / ".join(parts[:-1]) + ")"
        options.append(f"fill {label}: {value}")
    options += ["check", "click", "skip"]
    roles = {
        "textbox": "Edit",
        "input": "Edit",
        "edit": "Edit",
        "textfield": "Edit",
        "axtextfield": "Edit",
        "textarea": "Edit",
        "select": "ComboBox",
        "combobox": "ComboBox",
        "axcombobox": "ComboBox",
        "checkbox": "CheckBox",
        "axcheckbox": "CheckBox",
        "button": "Button",
        "axbutton": "Button",
        "radio": "RadioButton",
    }
    if protocol == "path-v1":
        roles = {
            k: v
            for k, v in roles.items()
            if k
            in {"textbox", "input", "select", "combobox", "checkbox", "button", "radio"}
        }
    contexts = []
    for element in elements:
        raw_role = element.get("role", "textbox")
        role = roles.get(str(raw_role).lower(), raw_role)
        if role == "CheckBox":
            checked = element.get("checked")
            if protocol != "path-v1":
                if checked is None:
                    checked = element.get("value", False)
                if isinstance(checked, str):
                    state_text = checked.strip().lower()
                    if state_text not in {"true", "false", ""}:
                        raise ValueError("Checkbox state must be true/false text")
                    checked = state_text == "true"
                elif checked is not None and not isinstance(checked, bool):
                    raise ValueError(
                        "Checkbox state must be boolean or true/false text"
                    )
            state = "checked" if checked else "unchecked"
        else:
            state = f'value="{str(element.get("value", ""))[:48]}"'
        hint = ""
        if protocol != "path-v1" and element.get("placeholder"):
            hint = f' hint="{str(element["placeholder"])[:72]}"'
        contexts.append(
            "TASK fill the form from the document, then submit\n"
            f"FORM {str(element.get('form_title', 'Checkout'))[:64]}\n"
            f'ELEMENT {role} "{str(element.get("label", ""))[:72]}" {state}{hint}'
        )
    return entities, contexts, options


def cua_byte_trace(text: str, limit: int) -> dict:
    """Exact UTF-8 truncation, including partial codepoints, as upstream sees it."""
    raw = text.encode("utf-8", errors="replace")
    return {
        "byte_length": len(raw),
        "limit": limit,
        "truncated": len(raw) > limit,
        "byte_ids": [byte + 1 for byte in raw[:limit]],
    }


class CuaS1Adapter(_Adapter):
    key = "cua-s1"

    def __init__(self, *, input_protocol="path-v2", diagnostics=False, **kwargs):
        super().__init__(**kwargs)
        if input_protocol not in CUA_INPUT_PROTOCOLS:
            raise ValueError(f"Unknown CUA input protocol: {input_protocol}")
        self.input_protocol = input_protocol
        self.diagnostics = diagnostics
        self.model_config: dict = {}
        self.checkpoint_identity: dict = {}
        self._inference_kind = "unverified"

    async def score_fields(self, elements: list[dict], profile: dict) -> list[dict]:
        if not elements:
            self.last_metrics = {}
            return []
        entities, contexts, options = cua_inputs(elements, profile, self.input_protocol)
        self._inference_kind = "unverified"
        started = time.perf_counter()
        was_warm = self.model is not None
        self._load_seconds = 0.0
        if self.endpoint:
            data = await self._post(
                "/score",
                {"model": self.served_model, "contexts": contexts, "options": options},
            )
            probabilities = data.get("probabilities")
        else:
            probabilities = await self._local(self._score, contexts, options)
        elapsed = time.perf_counter() - started
        self.last_metrics = {
            "inference_seconds": elapsed,
            "cold_model_loading_seconds": None if self.endpoint else self._load_seconds,
            "call_temperature": "remote_unobserved"
            if self.endpoint
            else "warm"
            if was_warm
            else "cold",
            "warm_inference_seconds": None
            if self.endpoint or not was_warm
            else max(0, elapsed - self._load_seconds),
            "model_id": self.model_id,
            "backend": "remote" if self.endpoint else "local",
            "input_protocol": self.input_protocol,
            "inference_kind": "remote_unverified"
            if self.endpoint
            else self._inference_kind,
            "model_forward_seconds": getattr(self, "_forward_seconds", None)
            if not self.endpoint and self._inference_kind == "actual_model"
            else None,
        }
        if not isinstance(probabilities, list) or len(probabilities) != len(elements):
            raise SpecialistOutputError(
                "CUA-S1 output must contain one distribution per element"
            )
        result = []
        for element, context, scores in zip(elements, contexts, probabilities):
            if (
                not isinstance(scores, list)
                or len(scores) != len(options)
                or any(
                    isinstance(v, bool)
                    or not isinstance(v, (int, float))
                    or not math.isfinite(v)
                    or not 0 <= v <= 1
                    for v in scores
                )
                or abs(sum(scores) - 1) > 1e-5
            ):
                raise SpecialistOutputError("Invalid CUA-S1 probability distribution")
            best = max(range(len(scores)), key=scores.__getitem__)
            is_fill = best < len(entities)
            result.append(
                {
                    "element_id": element.get("element_id", element.get("id")),
                    "action": "fill" if is_fill else options[best],
                    "value": entities[best][1] if is_fill else None,
                    "entity_key": entities[best][0] if is_fill else None,
                    "confidence": scores[best],
                    "distribution": scores,
                    "selected_index": best,
                    "candidate_count": len(entities),
                    "input_protocol": self.input_protocol,
                    "inference_kind": self.last_metrics["inference_kind"],
                }
            )
            if self.diagnostics:
                # Exact inputs can contain personal data; never enabled implicitly.
                limits = self.model_config
                result[-1]["model_input"] = {
                    "context": context,
                    "options": list(options),
                    "entity_keys": [key for key, _ in entities],
                    "context_encoding": cua_byte_trace(
                        context, limits["context_tokens"]
                    )
                    if "context_tokens" in limits
                    else None,
                    "option_encodings": [
                        cua_byte_trace(o, limits["option_tokens"]) for o in options
                    ]
                    if "option_tokens" in limits
                    else None,
                }
        return result

    def _score(self, contexts, options):
        import torch
        from cua_s1.model import ChoiceExample, load_checkpoint

        self._require_path()
        if self.model is None:
            load_start = time.perf_counter()
            path = Path(self.path)
            path = path / "cua-s1-forms.safetensors" if path.is_dir() else path
            if path.suffix != ".safetensors" or not path.with_suffix(".json").is_file():
                raise SpecialistUnavailable(
                    "CUA-S1 requires its safetensors checkpoint and signed JSON sidecar; pickle is forbidden"
                )
            self.model, self.processor, self.model_config = load_checkpoint(
                path, self._device()
            )
            self.checkpoint_identity = {
                "weights_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sidecar_sha256": hashlib.sha256(
                    path.with_suffix(".json").read_bytes()
                ).hexdigest(),
                "config": self.model_config,
            }
            self._load_seconds = time.perf_counter() - load_start
        batch = self.processor([ChoiceExample(c, tuple(options), 0) for c in contexts])
        batch = {
            key: value.to(next(self.model.parameters()).device)
            for key, value in batch.items()
        }
        forward_start = time.perf_counter()
        with torch.inference_mode():
            probabilities = self.model(batch).softmax(-1).cpu().tolist()
        self._forward_seconds = time.perf_counter() - forward_start
        self._inference_kind = "actual_model"
        return probabilities


class TinyClickAdapter(_Adapter):
    key = "tinyclick"

    async def ground(self, image: Any, instruction: str) -> dict:
        started = time.perf_counter()
        was_warm = self.model is not None
        self._load_seconds = 0.0
        if self.endpoint:
            data = await self._post(
                "/ground",
                {
                    "model": self.served_model,
                    "image": _image_url(image),
                    "instruction": instruction,
                },
            )
            raw = data.get("generated_text")
            if not isinstance(raw, str):
                raise SpecialistOutputError(
                    "TinyClick endpoint must return generated_text with location tokens"
                )
        else:
            raw = await self._local(self._generate, image, instruction)
        self.last_metrics = {
            "inference_seconds": time.perf_counter() - started,
            "cold_model_loading_seconds": None if self.endpoint else self._load_seconds,
            "call_temperature": "remote_unobserved"
            if self.endpoint
            else "warm"
            if was_warm
            else "cold",
            "warm_inference_seconds": None
            if self.endpoint or not was_warm
            else max(0, time.perf_counter() - started - self._load_seconds),
            "model_id": self.model_id,
            "backend": "remote" if self.endpoint else "local",
        }
        return parse_tinyclick(raw, image.size)

    def _generate(self, image, instruction):
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        self._require_path()
        if self.model is None:
            load_start = time.perf_counter()
            trusted = os.getenv("TINYCLICK_TRUST_LOCAL_CODE", "0") == "1"
            self.processor = AutoProcessor.from_pretrained(
                self.path, local_files_only=True, trust_remote_code=trusted
            )
            self.model = (
                AutoModelForCausalLM.from_pretrained(
                    self.path,
                    local_files_only=True,
                    use_safetensors=True,
                    trust_remote_code=trusted,
                )
                .to(self._device())
                .eval()
            )
            self._load_seconds = time.perf_counter() - load_start
        text = ("What to do to execute the command? " + instruction.strip()).lower()
        inputs = self.processor(
            images=image.convert("RGB"), text=text, return_tensors="pt", do_resize=True
        ).to(self.model.device)
        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs, max_new_tokens=min(self.max_tokens, 128), do_sample=False
            )
        return self.processor.batch_decode(outputs, skip_special_tokens=False)[0]


MAI_PROMPT = """You control the visible simulated checkout through mobile_use actions. Return exactly one JSON call inside <tool_call> tags: {"name":"mobile_use","arguments":{...}}.
Actions: {"action":"click","coordinate":[x,y]}, {"action":"type","text":"..."}, {"action":"swipe","direction":"up|down|left|right"}, {"action":"system_button","button":"enter"}, {"action":"wait"}, {"action":"terminate","status":"success|fail"}.
Coordinates use the model's 0..999 space. Work only inside this checkout. Stop at simulated authorisation; never enter a real OTP or UPI PIN."""
VENUS_PROMPT = """Analyze the task, screenshot and previous actions; choose one next action.
Available functions: Click(box=(x,y)), Drag(start=(x,y),end=(x,y)), Scroll(direction='up|down|left|right'), Type(content=''), Wait(), Finished(content=''), CallUser(content=''), LongPress(box=(x,y)), PressEnter(), Hover(box=(x,y)), DoubleClick(box=(x,y)), Hotkey(keys=['ctrl','a']).
Return <action>Function(keyword=value)</action>. Coordinates are pixels in the provided resized screenshot. Click the input before Type; Type presses ENTER afterwards. Stay in the simulated checkout and stop at simulated authorisation. Never enter a real OTP or UPI PIN."""


class _VisualAdapter(_Adapter):
    async def act(self, image: Any, task: str, history: list[dict]) -> dict:
        started = time.perf_counter()
        was_warm = self.model is not None
        self._load_seconds = 0.0
        prepared = image.convert("RGB")
        if self.key == "ui-venus":
            # The actual 1.5 Qwen3 checkpoint uses patch_size=16, merge_size=2.
            # Prepare on that 32-pixel grid and preserve exact model-image size.
            # Upstream navigation code still says factor=28 (Qwen2 convention).
            from math import ceil, floor, sqrt

            w, h = image.size
            rw, rh = max(32, round(w / 32) * 32), max(32, round(h / 32) * 32)
            max_pixels = int(os.getenv("UI_VENUS_MAX_PIXELS", "1003520"))
            if rw * rh > max_pixels:
                factor = sqrt(w * h / max_pixels)
                rw, rh = (
                    max(32, floor(w / factor / 32) * 32),
                    max(32, floor(h / factor / 32) * 32),
                )
            if rw * rh < 65536:
                factor = sqrt(65536 / (w * h))
                rw, rh = ceil(w * factor / 32) * 32, ceil(h * factor / 32) * 32
            prepared = prepared.resize((rw, rh))
        prompt = MAI_PROMPT if self.key == "mai-ui" else VENUS_PROMPT
        if isinstance(task, dict) and (
            "preferences" in task or task.get("benchmark_version") == "2.1"
        ):
            prompt = prompt.replace(
                "Stop at simulated authorisation; never enter a real OTP or UPI PIN.",
                "Never enter a real OTP or UPI PIN.",
            ).replace(
                "stop at simulated authorisation.", "follow the task's evaluation mode."
            )
            prompt += " This is a local synthetic v2 checkout. Request authorisation through the visible handoff button. In simulated_completion mode, a separate test user approves; wait and return to checkout. Do not guess codes. Stop at the visible Checkout ready, Authentication required (reported handoff), Payment successful in simulation, or justified Stopped safely outcome. Verify saved autofill against the supplied preferences."
        prior = "\n".join(str(h.get("raw", json.dumps(h))) for h in history[-20:])
        query = f"Task: {task}\nPrevious actions:\n{prior}\nChoose the next action."
        if self.endpoint:
            response = await self._post(
                "/chat/completions",
                {
                    "model": self.served_model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": query},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": _image_url(prepared)},
                                },
                            ],
                        },
                    ],
                    "max_tokens": self.max_tokens,
                    "temperature": 0,
                },
            )
            try:
                raw = response["choices"][0]["message"]["content"]
                if not isinstance(raw, str):
                    raise ValueError("Response content is not text")
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise SpecialistOutputError(
                    "Malformed vision endpoint response"
                ) from exc
            usage = response.get("usage", {})
        else:
            raw, usage = await self._local(self._generate, prepared, prompt, query)
        self.last_metrics = {
            "inference_seconds": time.perf_counter() - started,
            "cold_model_loading_seconds": None if self.endpoint else self._load_seconds,
            "call_temperature": "remote_unobserved"
            if self.endpoint
            else "warm"
            if was_warm
            else "cold",
            "warm_inference_seconds": None
            if self.endpoint or not was_warm
            else max(0, time.perf_counter() - started - self._load_seconds),
            "model_id": self.model_id,
            "backend": "remote" if self.endpoint else "local",
            "usage": usage,
            "input_image_size": prepared.size,
        }
        return (
            parse_mai(raw, image.size)
            if self.key == "mai-ui"
            else parse_venus(raw, image.size, prepared.size)
        )

    def _generate(self, image, prompt, query):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        self._require_path()
        if self.model is None:
            load_start = time.perf_counter()
            device = self._device()
            dtype = (
                torch.float32
                if device.type == "cpu"
                else torch.bfloat16
                if device.type == "cuda" and torch.cuda.is_bf16_supported()
                else torch.float16
            )
            self.processor = AutoProcessor.from_pretrained(
                self.path, local_files_only=True, trust_remote_code=False
            )
            self.model = (
                Qwen3VLForConditionalGeneration.from_pretrained(
                    self.path,
                    local_files_only=True,
                    use_safetensors=True,
                    torch_dtype=dtype,
                    attn_implementation="eager",
                )
                .to(device)
                .eval()
            )
            self._load_seconds = time.perf_counter() - load_start
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": query},
                ],
            },
        ]
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            do_resize=self.key != "ui-venus",
        ).to(self.model.device)
        with torch.inference_mode():
            output = self.model.generate(
                **inputs, max_new_tokens=self.max_tokens, do_sample=False
            )
        n = inputs["input_ids"].shape[1]
        return self.processor.batch_decode(output[:, n:], skip_special_tokens=True)[
            0
        ], {"prompt_tokens": n, "completion_tokens": output.shape[1] - n}


class MaiUIAdapter(_VisualAdapter):
    key = "mai-ui"


class VenusAdapter(_VisualAdapter):
    key = "ui-venus"
