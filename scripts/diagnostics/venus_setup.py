"""Download the explicitly pinned UI-Venus 1.5 MLX conversion; never run inference."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

MODEL_ID = "inclusionAI/UI-Venus-1.5-2B"
MODEL_REVISION = "bc4c6e62a1c545e043761439be95646d801853a4"
ARTIFACT_ID = "mlx-community/UI-Venus-1.5-2B-6bit"
ARTIFACT_REVISION = "95e3994ac9d74fe047cf44c072f6569db62856e7"
UPSTREAM_CODE_REVISION = "192a9247ad1129279ba1d6c263d4c9e7ecef3644"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destination", type=Path, default=Path("data/models/ui-venus-1.5-2b-mlx-6bit"))
    args = p.parse_args()
    from huggingface_hub import snapshot_download
    root = args.destination.resolve()
    snapshot_download(ARTIFACT_ID, revision=ARTIFACT_REVISION, local_dir=root,
                      allow_patterns=["*.json", "*.jinja", "*.txt", "*.safetensors", "README.md"], max_workers=2)
    with urlopen(f"https://huggingface.co/api/models/{ARTIFACT_ID}/revision/{ARTIFACT_REVISION}?blobs=true") as response:
        remote = json.load(response)
    files = {}
    for item in remote["siblings"]:
        file = root / item["rfilename"]
        if not file.is_file():
            continue
        digest = sha256(file)
        if item.get("lfs", {}).get("sha256") and digest != item["lfs"]["sha256"]:
            raise RuntimeError(f"SHA256 mismatch: {file.name}")
        files[item["rfilename"]] = {"sha256": digest, "bytes": file.stat().st_size}
    config = json.loads((root / "config.json").read_text())
    if config["model_type"] != "qwen3_vl" or config.get("quantization") != {"group_size": 64, "bits": 6, "mode": "affine"}:
        raise RuntimeError("Unexpected model architecture or quantization")
    provenance = {"model_id": MODEL_ID, "upstream_revision": MODEL_REVISION,
                  "artifact_id": ARTIFACT_ID, "artifact_revision": ARTIFACT_REVISION,
                  "upstream_code_revision": UPSTREAM_CODE_REVISION,
                  "backend": "mlx-vlm", "precision": "affine-6bit-group64-mixed-bf16",
                  "quantization": config["quantization"], "files": files,
                  "provenance_note": "Community card identifies original model but not its exact upstream commit; current official revision independently pinned. This is a community conversion, not original precision. Config intentionally unties separately stored lm_head and embeddings."}
    (root / "checkoutbench_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"path": str(root), "artifact_id": ARTIFACT_ID, "revision": ARTIFACT_REVISION, "files_verified": len(files)}))


if __name__ == "__main__":
    main()
