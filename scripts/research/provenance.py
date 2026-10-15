"""Fetch immutable upstream metadata only; never downloads or substitutes weights."""

import json, datetime
from pathlib import Path
import httpx

REPOS = {
    "cua-s1": "cua-ai/cua-s1-forms",
    "tinyclick": "kzawistowsk/TinyClick",
    "mai-ui": "Tongyi-MAI/MAI-UI-2B",
    "ui-venus": "inclusionAI/UI-Venus-1.5-2B",
}


def main():
    rows = {}
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for key, repo in REPOS.items():
            try:
                response = c.get(
                    "https://huggingface.co/api/models/" + repo,
                    params={"blobs": "true"},
                )
                response.raise_for_status()
                d = response.json()
                files = [
                    {
                        "path": f["rfilename"],
                        "sha256": f.get("lfs", {}).get("sha256"),
                        "size": f.get("size"),
                    }
                    for f in d.get("siblings", [])
                ]
                weights = [f for f in files if f["path"].endswith(".safetensors")]
                config = {}
                if any(f["path"] == "config.json" for f in files):
                    cr = c.get(
                        f"https://huggingface.co/{repo}/resolve/{d['sha']}/config.json"
                    )
                    cr.raise_for_status()
                    config = cr.json()
                rows[key] = {
                    "repository": repo,
                    "revision": d["sha"],
                    "source_url": "https://huggingface.co/" + repo,
                    "license": d.get("cardData", {}).get("license"),
                    "architectures": config.get("architectures"),
                    "model_type": config.get("model_type"),
                    "safetensors_metadata": d.get("safetensors"),
                    "weight_files": weights,
                    "files": files,
                    "status": "metadata_identified; local verification and real inference pending"
                    if weights
                    else "BLOCKED: requested distribution has no safetensors weights",
                    "checked_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                }
            except Exception as e:
                rows[key] = {
                    "repository": repo,
                    "status": "BLOCKED: upstream metadata unavailable",
                    "error_type": type(e).__name__,
                }
    Path("research/model-provenance.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(
        {
            k: {
                "status": v["status"],
                "license": v.get("license"),
                "weight_files": len(v.get("weight_files", [])),
            }
            for k, v in rows.items()
        }
    )


if __name__ == "__main__":
    main()
