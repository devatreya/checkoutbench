"""Private local MLX worker. NDJSON over pipes; no HTTP service or browser access."""
from __future__ import annotations
import argparse
import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(root):
    provenance = json.loads((root / "checkoutbench_provenance.json").read_text())
    if provenance.get("artifact_id") != "mlx-community/UI-Venus-1.5-2B-6bit" or provenance.get("artifact_revision") != "95e3994ac9d74fe047cf44c072f6569db62856e7":
        raise ValueError("The configured artifact is not the pinned UI-Venus 1.5 6bit conversion")
    pinned = json.loads(Path(__file__).with_name("venus_artifact_manifest.json").read_text())
    if provenance["files"] != pinned["files"]:
        raise ValueError("Local provenance differs from the reviewed pinned artifact manifest")
    for name, record in pinned["files"].items():
        path = root / name
        if path.resolve().parent != root.resolve() or not path.is_file():
            raise ValueError("Missing or invalid pinned artifact file")
        if path.stat().st_size != record["bytes"] or file_hash(path) != record["sha256"]:
            raise ValueError(f"Pinned artifact integrity check failed: {name}")
    return provenance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--memory-limit", type=int, default=4250000000)
    args = parser.parse_args()
    wire = sys.stdout
    # Every library log goes to stderr; stdout contains protocol messages only.
    with contextlib.redirect_stdout(sys.stderr):
        model = processor = mx = None
        metadata = {}
        for line in sys.stdin:
            try:
                request = json.loads(line)
                cold = model is None
                load_started = time.perf_counter()
                if cold:
                    provenance = verify(args.model)
                    import mlx.core as mx
                    from mlx_vlm import load
                    from mlx_vlm.generate import generate
                    from mlx_vlm.utils import prepare_inputs
                    from PIL import Image
                    mx.set_memory_limit(args.memory_limit)
                    mx.set_cache_limit(256 * 1024 * 1024)
                    model, processor = load(str(args.model), trust_remote_code=False, local_files_only=True)
                    processor.image_processor.do_resize = False
                    metadata = {"artifact_provenance": provenance,
                        "code_source_hashes": {name: file_hash(Path(__file__).resolve().parents[2] / name) for name in ["backend/adapters/venus.py", "backend/adapters/venus_verification.py", "scripts/diagnostics/venus_worker.py", "scripts/diagnostics/venus_requirements.txt", "scripts/diagnostics/venus_requirements.lock.txt", "scripts/diagnostics/venus_artifact_manifest.json"]},
                        "software": {name: importlib.metadata.version(name) for name in ["mlx", "mlx-vlm", "mlx-lm", "transformers", "huggingface-hub", "Pillow", "torch", "torchvision"]},
                        "python": platform.python_version(), "platform": platform.platform(),
                        "hardware": mx.device_info(), "checkpoint_sha256": provenance["files"]["model.safetensors"]["sha256"]}
                loading_seconds = time.perf_counter() - load_started if cold else 0.0
                image = Image.open(io.BytesIO(base64.b64decode(request["image_base64"], validate=True))).convert("RGB")
                if list(image.size) != request["image_size"]:
                    raise ValueError("Screenshot dimensions do not match the request")
                messages = [{"role": "system", "content": request["system_prompt"]},
                            {"role": "user", "content": [{"type": "text", "text": request["prompt"]}, {"type": "image", "image": image}]}]
                template = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                prep_started = time.perf_counter()
                inputs = prepare_inputs(processor, images=[image], prompts=template, add_special_tokens=True)
                grid = inputs["image_grid_thw"].tolist()
                if len(grid) != 1 or [grid[0][2] * 16, grid[0][1] * 16] != list(image.size):
                    raise ValueError(f"Processor image coordinate mismatch: grid={grid}, image={image.size}")
                preparation_seconds = time.perf_counter() - prep_started
                mx.reset_peak_memory()
                mx.random.seed(0)
                generated_started = time.perf_counter()
                result = generate(model, processor, prompt=template, max_tokens=request["max_tokens"], temperature=0.0, top_p=1.0, prefill_step_size=256, verbose=False, **inputs)
                elapsed = time.perf_counter() - generated_started
                metrics = {"call_temperature": "cold" if cold else "warm", "cold_model_loading_seconds": loading_seconds,
                           "warm_inference_seconds": None if cold else elapsed, "image_preprocessing_seconds": preparation_seconds,
                           "model_forward_seconds": elapsed, "usage": {"prompt_tokens": result.prompt_tokens, "completion_tokens": result.generation_tokens},
                           "prompt_tokens_per_second": result.prompt_tps, "generation_tokens_per_second": result.generation_tps,
                           "mlx_peak_memory_bytes": mx.get_peak_memory(), "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           "image_grid_thw": grid, "chat_template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                           "generated_token_limit_reached": result.generation_tokens >= request["max_tokens"]}
                response = {"raw_text": result.text, "metadata": metadata, "metrics": metrics}
                del inputs
                mx.clear_cache()
            except Exception as exc:
                category = "unavailable" if isinstance(exc, (ImportError, FileNotFoundError)) else "inference_error"
                response = {"error": f"{type(exc).__name__}: {exc}", "category": category}
            wire.write(json.dumps(response) + "\n")
            wire.flush()
            if response.get("error"):
                break


if __name__ == "__main__":
    main()
