"""Real local inference on a saved screenshot; diagnostic, never a leaderboard run."""
from __future__ import annotations
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from backend.adapters.venus import VenusAdapter
from PIL import Image


async def run(args):
    args.output.mkdir(parents=True, exist_ok=True)
    task = json.loads(args.task.read_text())
    task = task.get("task", task)
    if args.click_smoke:
        task = {"instruction": "Click the visible Receipt email input. Do not enter any text or submit a payment."}
    (args.output / "public-task.json").write_text(json.dumps(task, indent=2))
    image = Image.open(args.image).convert("RGB")
    image.save(args.output / "input.png")
    adapter = VenusAdapter(max_tokens=args.max_tokens)
    rows = []
    try:
        for i in range(args.calls):
            row = {"experiment": "adapter-smoke-identical-input-cold-warm", "official_leaderboard": False,
                   "timestamp": datetime.now(timezone.utc).isoformat(), "call": i + 1}
            start = time.perf_counter()
            try:
                row["action"] = await adapter.act(image, task, [])
                row["status"] = "parsed_action"
            except Exception as exc:
                row.update(status="error", error_type=type(exc).__name__, error=str(exc))
            row.update(seconds=time.perf_counter()-start, metrics=adapter.last_metrics, metadata=adapter.metadata())
            rows.append(row)
            (args.output / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
            print(json.dumps({key: row[key] for key in ["call","status","seconds"]} | {"error":row.get("error"), "action":row.get("action",{}).get("native_action"), "peak_memory":row["metrics"].get("mlx_peak_memory_bytes")}), flush=True)
            if row["status"] == "error":
                break
    finally:
        await adapter.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--task',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--calls',type=int,default=2)
    p.add_argument('--max-tokens',type=int,default=256)
    p.add_argument('--click-smoke',action='store_true')
    asyncio.run(run(p.parse_args()))

if __name__=='__main__': main()
