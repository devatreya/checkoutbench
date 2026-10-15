"""Submit and verify the complete deterministic reference suite against a running app."""

import argparse, asyncio, json
from pathlib import Path
import httpx


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--family", default=None)
    parser.add_argument("--suite", choices=["all", "1.0", "2.0", "2.1", "3.0"], default="all")
    parser.add_argument("--output", default="data/reference-verification.json")
    args = parser.parse_args()
    async with httpx.AsyncClient(timeout=30) as c:
        specs = (await c.get(args.url + "/api/scenarios")).json()
        specs = [
            s
            for s in specs
            if (not args.family or s.get("family") == args.family)
            and (args.suite == "all" or s.get("benchmark_version", "1.0") == args.suite)
        ]
        if not specs:
            raise SystemExit("No matching scenarios")
        config = dict(
            models=["reference"],
            scenarios=[s["id"] for s in specs],
            repeats=args.repeats,
            seed=2026,
            max_steps=100,
            timeout=180,
        )
        r = await c.post(args.url + "/api/batches", json=config)
        r.raise_for_status()
        batch = r.json()["id"]
        while True:
            state = (await c.get(args.url + "/api/state")).json()
            if not state["running"]:
                break
            await asyncio.sleep(1)
        rows = [
            r
            for r in (await c.get(args.url + "/api/results")).json()["runs"]
            if r["batch_id"] == batch
        ]
        summary = {
            "batch": batch,
            "conditions": config,
            "runs": len(rows),
            "successes": sum(r["success"] for r in rows),
            "results": [
                {
                    k: r.get(k)
                    for k in (
                        "id",
                        "model",
                        "scenario",
                        "seed",
                        "repeat",
                        "status",
                        "success",
                        "wall_seconds",
                        "required_field_accuracy",
                        "payment_accuracy",
                        "optional_correct",
                        "action_count",
                        "retries",
                        "validation_errors",
                        "failure_reason",
                    )
                }
                for r in rows
            ],
        }
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2))
        print(
            f"{summary['successes']}/{summary['runs']} reference trials passed. Saved {out}"
        )
        if (
            summary["runs"] != len(specs) * args.repeats
            or summary["successes"] != summary["runs"]
        ):
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
