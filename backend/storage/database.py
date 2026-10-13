import json, sqlite3, os
from pathlib import Path
from statistics import median, mean, pstdev
from collections import defaultdict

DATA = Path(os.getenv("BENCH_DATA_DIR", "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "results.sqlite3"


def connect():
    c = sqlite3.connect(DB)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
    )
    return c


def save(run):
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?)", (run["id"], json.dumps(run))
        )


def runs():
    with connect() as c:
        return [
            json.loads(r[0])
            for r in c.execute("SELECT data FROM runs ORDER BY rowid DESC")
        ]


def get(rid):
    with connect() as c:
        r = c.execute("SELECT data FROM runs WHERE id=?", (rid,)).fetchone()
    return json.loads(r[0]) if r else None


def recover():
    for r in runs():
        if r.get("status") == "running":
            r.update(status="blocked", failure_reason="server_restarted")
            save(r)


def leaderboard(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["status"] not in ("completed", "failed"):
            continue
        # Exact configurations stay separate. Never pool a reference executor with AI results.
        key = (
            r["model"],
            r["config"]["reasoning"],
            r["config"]["max_tokens"],
            r["config"]["max_steps"],
            r["config"]["timeout"],
            r.get("cohort", "legacy"),
        )
        groups[key].append(r)
    result = []
    for key, rs in groups.items():
        successes = [r for r in rs if r.get("success")]
        n = len(rs)
        k = len(successes)
        rate = k / n
        z = 1.96
        center = (rate + z * z / (2 * n)) / (1 + z * z / n)
        half = (
            z * ((rate * (1 - rate) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
        )
        by_scenario = {
            sid: {
                "successes": sum(
                    bool(r.get("success")) for r in rs if r["scenario"] == sid
                ),
                "runs": sum(r["scenario"] == sid for r in rs),
            }
            for sid in sorted({r["scenario"] for r in rs})
        }
        cost = sum(r.get("cost", 0) for r in rs)
        result.append(
            dict(
                model=key[0],
                reasoning=key[1],
                cohort=key[-1],
                holdout_success_rate=mean(
                    bool(r.get("success")) for r in rs if r.get("holdout")
                )
                if any(r.get("holdout") for r in rs)
                else None,
                recovery_success_rate=mean(
                    bool(r.get("success"))
                    for r in rs
                    if r.get("validation_errors") or r.get("retries")
                )
                if any(r.get("validation_errors") or r.get("retries") for r in rs)
                else None,
                config=rs[0]["config"],
                runs=n,
                successes=k,
                success_rate=rate,
                ci95=[max(0, center - half), min(1, center + half)],
                median_seconds=median(r["wall_seconds"] for r in successes)
                if successes
                else None,
                duration_stddev=pstdev([r["wall_seconds"] for r in successes])
                if successes
                else None,
                field_accuracy=mean(r.get("required_field_accuracy", 0) for r in rs),
                actions=mean(r.get("action_count", 0) for r in rs),
                cost=cost,
                cost_per_success=cost / k
                if k and all(r.get("cost_kind") != "not_reported" for r in rs)
                else None,
                scenarios=by_scenario,
                kind=rs[0]["kind"],
                failure_categories={
                    f: sum(r.get("failure_reason") == f for r in rs)
                    for f in {
                        r.get("failure_reason") for r in rs if r.get("failure_reason")
                    }
                },
            )
        )
    return sorted(
        result,
        key=lambda x: (
            -x["success_rate"],
            -x["ci95"][0],
            x["median_seconds"] if x["median_seconds"] is not None else float("inf"),
            x["actions"],
            x["cost_per_success"]
            if x["cost_per_success"] is not None
            else float("inf"),
        ),
    )
