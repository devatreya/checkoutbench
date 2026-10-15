"""Verify exact local checkpoints and execute real cold/warm adapter inference.

No download, substitute, remote attestation, or benchmark comparison is implicit.
Run from repo: .venv/bin/python -m scripts.research.verify_models --model cua-s1
"""

import argparse, asyncio, hashlib, json, os, platform, time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from backend.adapters.specialists import (
    CuaS1Adapter,
    TinyClickAdapter,
    MaiUIAdapter,
    VenusAdapter,
    SPECS,
)
from backend.storage.database import DATA
from scenarios.research import ROOT, digest
from scenarios.catalog import scenario, task

CLASSES = {
    "cua-s1": CuaS1Adapter,
    "tinyclick": TinyClickAdapter,
    "mai-ui": MaiUIAdapter,
    "ui-venus": VenusAdapter,
}


def sha(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def runtime_versions():
    from importlib.metadata import version, PackageNotFoundError

    result = {}
    for name in ("torch", "transformers", "safetensors", "numpy"):
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


async def verify(model):
    provenance = json.loads((ROOT / "research/model-provenance.json").read_text())
    record = {
        "model": model,
        "verified": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if model == "hybrid":
            from backend.research.protocol import checkpoint_records

            previous = checkpoint_records()
            if not all(
                previous.get(k, {}).get("verified") for k in ("cua-s1", "tinyclick")
            ):
                raise ValueError(
                    "Both exact component checkpoints must be verified first"
                )
            # Execute both genuine inference paths, not just read two availability flags.
            parts = [await verify(k) for k in ("cua-s1", "tinyclick")]
            if not all(x["verified"] for x in parts):
                raise ValueError("A component failed genuine inference")
            record.update(
                verified=True,
                components=parts,
                backend="local",
                smoke="Both component adapters invoked; full hybrid browser benchmark remains separate",
            )
        else:
            p = provenance[model]
            record.update(
                repository=p["repository"], revision=p["revision"], license=p["license"]
            )
            if not p["weight_files"]:
                raise ValueError(
                    "Exact upstream safetensors weights unavailable; no substitute accepted"
                )
            a = CLASSES[model](max_tokens=128)
            if a.endpoint:
                raise ValueError(
                    "Remote identity cannot be verified from endpoint responses alone; use pinned local weights or independently audited deployment attestation"
                )
            root = Path(a.path)
            if not a.path or not root.exists():
                raise ValueError("Exact local checkpoint is not configured")
            if root.is_file():
                root = root.parent
            hashes = {}
            for w in p["weight_files"]:
                f = root / w["path"]
                if not f.is_file() or not w["sha256"] or sha(f) != w["sha256"]:
                    raise ValueError(
                        "Checkpoint hash mismatch or incomplete local weights"
                    )
                hashes[w["path"]] = w["sha256"]
            # Verify config/tokenizer/processor files against the SAME pinned repository.
            import httpx

            with httpx.Client(
                follow_redirects=True,
                verify=os.getenv("SSL_CERT_FILE", "/etc/ssl/cert.pem"),
                timeout=30,
            ) as client:
                for f in root.rglob("*"):
                    if (
                        f.is_file()
                        and f.suffix in (".json", ".txt", ".model", ".jinja")
                        and ".cache" not in f.parts
                    ):
                        rel = str(f.relative_to(root))
                        response = client.get(
                            f"https://huggingface.co/{p['repository']}/resolve/{p['revision']}/{rel}"
                        )
                        response.raise_for_status()
                        if hashlib.sha256(response.content).hexdigest() != sha(f):
                            raise ValueError("Pinned configuration/tokenizer mismatch")
                        hashes[rel] = sha(f)
            from PIL import Image, ImageDraw

            image = Image.new("RGB", (640, 480), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((30, 30, 300, 80), outline="black")
            draw.text((45, 48), "Email address", fill="black")
            profile = scenario("V21-G01")["customer_brief"]
            metrics = []
            outputs = []
            for _ in range(2):
                if model == "cua-s1":
                    output = await a.score_fields(
                        [
                            {
                                "element_id": "smoke-email",
                                "label": "Email address",
                                "role": "textbox",
                                "value": "",
                                "form_title": "Synthetic checkout",
                            }
                        ],
                        profile,
                    )
                elif model == "tinyclick":
                    output = await a.ground(image, "Click the Email address field")
                else:
                    output = await a.act(image, task(scenario("V21-G01")), [])
                outputs.append(output)
                metrics.append(dict(a.last_metrics))
            import torch

            count = sum(p.numel() for p in a.model.parameters())
            if model == "cua-s1" and count != 706048:
                raise ValueError("Unexpected CUA architecture parameter count")
            record.update(
                verified=True,
                checkpoint_hashes=hashes,
                parameters=count,
                architecture=type(a.model).__name__,
                backend="local",
                torch=torch.__version__,
                runtime_versions=runtime_versions(),
                precision=str(next(a.model.parameters()).dtype),
                quantisation="none",
                device=str(next(a.model.parameters()).device),
                hardware={
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "os": platform.platform(),
                },
                adapter_hash=sha(ROOT / "backend/adapters/specialists.py"),
                binding_hash=digest(str(root.resolve())),
                calls=metrics,
                outputs=outputs,
                smoke="Real cold then warm inference; format validation only, not benchmark accuracy",
            )
            if model == "cua-s1":
                import cua_s1.model as module

                record["loader_hash"] = sha(module.__file__)
                revision = DATA / "research/cua-loader/revision.txt"
                record["loader_revision"] = (
                    revision.read_text().strip() if revision.exists() else None
                )
    except Exception as e:
        # Do not save endpoint URLs, credentials, or arbitrary upstream response bodies.
        record.update(
            verified=False,
            blocker=str(e)
            if isinstance(e, ValueError)
            else type(e).__name__ + " during verification",
        )
    path = DATA / "research/checkpoint-verification.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(path.read_text()) if path.exists() else {}
    saved[model] = record
    path.write_text(json.dumps(saved, indent=2) + "\n")
    return record


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=[*CLASSES, "hybrid"], required=True)
    args = p.parse_args()
    r = asyncio.run(verify(args.model))
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["verified"] else 2)
