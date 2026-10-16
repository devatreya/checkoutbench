"""Local UI-Venus checkpoint attestation; smoke plumbing is not model accuracy."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "backend/adapters/venus.py", "backend/adapters/venus_verification.py",
    "scripts/diagnostics/venus_worker.py", "scripts/diagnostics/venus_requirements.txt",
    "scripts/diagnostics/venus_requirements.lock.txt", "scripts/diagnostics/venus_artifact_manifest.json",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_bindings():
    return {name: sha(ROOT / name) for name in SOURCES}


def runtime_binding(python):
    # Metadata/device query only: no model imported or loaded in the worker.
    code = '''import importlib.metadata,json,platform,sys
import mlx.core as mx
print(json.dumps({"python":platform.python_version(),"platform":platform.platform(),"hardware":mx.device_info(),"software":{p:importlib.metadata.version(p) for p in ["mlx","mlx-vlm","mlx-lm","transformers","huggingface-hub","Pillow","torch","torchvision"]}}))'''
    try:
        result = subprocess.run([str(python), "-c", code], capture_output=True, text=True, timeout=30, check=True)
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        raise ValueError("UI-Venus isolated runtime metadata could not be verified") from exc


def checkpoint_binding(root):
    from backend.adapters.venus import ARTIFACT_ID, ARTIFACT_REVISION
    pinned = json.loads((ROOT / "scripts/diagnostics/venus_artifact_manifest.json").read_text())
    local = json.loads((root / "checkoutbench_provenance.json").read_text())
    if local != pinned or pinned["artifact_id"] != ARTIFACT_ID or pinned["artifact_revision"] != ARTIFACT_REVISION:
        raise ValueError("UI-Venus local provenance does not match the reviewed exact artifact")
    hashes = {}
    for name, spec in pinned["files"].items():
        path = root / name
        if path.resolve().parent != root.resolve() or not path.is_file() or path.stat().st_size != spec["bytes"] or sha(path) != spec["sha256"]:
            raise ValueError("UI-Venus checkpoint integrity mismatch: " + name)
        hashes[name] = spec["sha256"]
    return hashes


def _smoke_binding(path):
    from backend.adapters.venus import WEB_USER_PROMPT, ARTIFACT_REVISION, image_size_for_model, build_prompt, parse_venus_action
    from PIL import Image
    import io
    rows = json.loads(path.read_text())
    valid = []
    for row in rows:
        metrics = row.get("metrics", {})
        metadata = metrics.get("metadata", {})
        if row.get("experiment") != "adapter-smoke-identical-input-cold-warm" or row.get("official_leaderboard") is not False:
            raise ValueError("Not an explicitly separated adapter-smoke record")
        if row.get("status") != "parsed_action" or metrics.get("inference_kind") != "actual_model" or not metrics.get("actual_model"):
            continue
        if not metrics.get("raw_text") or row.get("action", {}).get("raw") != metrics["raw_text"] or not metrics.get("usage", {}).get("prompt_tokens", 0):
            raise ValueError("Smoke lacks genuine generation/raw-action evidence")
        if metadata.get("checkpoint_revision") != ARTIFACT_REVISION or metadata.get("code_source_hashes") != source_bindings():
            raise ValueError("Smoke code or model revision differs from current runtime")
        if metadata.get("prompt_sha256") != hashlib.sha256(WEB_USER_PROMPT.encode()).hexdigest():
            raise ValueError("Smoke prompt format changed")
        public = json.loads((path.parent / "public-task.json").read_text())
        if build_prompt(public, [], metadata["context_strategy"]["native_action_history_limit"]) != metrics.get("request_prompt"):
            raise ValueError("Smoke public task does not reproduce the recorded request")
        image = Image.open(path.parent / "input.png").convert("RGB")
        prepared = image.resize(image_size_for_model(image.size, metadata["runtime_config"]["max_pixels"]))
        data = io.BytesIO(); prepared.save(data, format="PNG")
        if hashlib.sha256(data.getvalue()).hexdigest() != metrics.get("image_sha256"):
            raise ValueError("Smoke screenshot does not match the actual model input")
        if metrics.get("model_image_size") != list(prepared.size) or metrics.get("image_grid_thw") != [[1, prepared.height // 16, prepared.width // 16]]:
            raise ValueError("Smoke coordinate/processor grid mismatch")
        if json.loads(json.dumps(parse_venus_action(metrics["raw_text"], image.size, prepared.size))) != row["action"]:
            raise ValueError("Smoke action does not match the current native coordinate contract")
        valid.append(row)
    if not valid:
        raise ValueError("At least one persisted actual-model generation and parsed native action is required")
    files = {str(file.resolve()): sha(file) for file in [path, path.parent / "input.png", path.parent / "public-task.json"]}
    return valid[-1], files


def create_record(smoke_results_path):
    from backend.adapters.venus import local_configuration, availability, ARTIFACT_ID, ARTIFACT_REVISION, MODEL_ID
    cfg = local_configuration()
    state = availability()
    if not state["available"]:
        raise ValueError(state["reason"])
    path = Path(smoke_results_path).resolve()
    row, evidence = _smoke_binding(path)
    if row["metrics"]["metadata"].get("runtime_config") != {k: v for k, v in cfg.items() if k not in {"python", "model_path"}}:
        raise ValueError("UI-Venus runtime configuration changed since the smoke")
    root = Path(cfg["model_path"]).resolve()
    runtime = runtime_binding(cfg["python"])
    for key in ["python", "platform", "hardware", "software"]:
        if row["metrics"]["metadata"].get(key) != runtime[key]:
            raise ValueError("Smoke runtime metadata differs from the configured runtime: " + key)
    record = {"verified": True, "verification_scope": "local adapter loading, genuine screenshot inference, native parsing and coordinate-grid contract; not grounding correctness or checkout success",
              "model_id": MODEL_ID, "artifact_id": ARTIFACT_ID, "checkpoint_revision": ARTIFACT_REVISION,
              "backend": "mlx-vlm-local-worker", "device": "metal", "precision": "affine-6bit-group64-mixed-bf16",
              "repository": ARTIFACT_ID, "revision": ARTIFACT_REVISION, "adapter_hash": sha(ROOT / "backend/adapters/venus.py"),
              "quantisation": {"bits": 6, "group_size": 64, "mode": "affine", "unquantized_dtype": "bfloat16"},
              "checkpoint_hashes": checkpoint_binding(root),
              "binding_hash": hashlib.sha256(str(root).encode()).hexdigest(),
              "python_binding": {"path": str(Path(cfg["python"]).absolute()), "binary_sha256": sha(cfg["python"])},
              "runtime_versions": runtime, "code_source_hashes": source_bindings(),
              "prompt_sha256": row["metrics"]["metadata"]["prompt_sha256"],
              "runtime_config": row["metrics"]["metadata"]["runtime_config"],
              "smoke_results_path": str(path), "smoke_evidence_hashes": evidence,
              "verified_at": datetime.now(timezone.utc).isoformat(), "actual_model": True}
    return record


def verify_record(record):
    """Raise on any stale evidence, artifact, source, runtime or local binding."""
    if record.get("verified") is not True or record.get("actual_model") is not True:
        raise ValueError("UI-Venus needs an actual local inference verification record")
    if record.get("code_source_hashes") != source_bindings():
        raise ValueError("UI-Venus adapter/worker/prompt/runtime lock changed; verify again")
    for name, digest in record.get("smoke_evidence_hashes", {}).items():
        if not Path(name).is_file() or sha(name) != digest:
            raise ValueError("UI-Venus persisted smoke evidence changed")
    current = create_record(record["smoke_results_path"])
    for key in current.keys() - {"verified_at"}:
        if current[key] != record.get(key):
            raise ValueError("UI-Venus verification binding changed: " + key)
    return record
