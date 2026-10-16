import asyncio, csv, io, json, os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("SSL_CERT_FILE") and Path("/etc/ssl/cert.pem").exists():
    os.environ["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_CLOUD_SYNC", "false")
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from scenarios.catalog import SPECS, PROFILES, scenario, task
from scenarios.identity import resolve_id, identity
from backend.presentation import present
from scenarios.v2 import V2_SPECS
from scenarios.v21 import V21_SPECS

ALL_IDS = [s[0] for s in SPECS] + [s["id"] for s in V2_SPECS + V21_SPECS]
from scenarios.research import SPECS as RESEARCH_SPECS

ALL_IDS += [s["id"] for s in RESEARCH_SPECS]
from backend.fixtures import new_session
from backend.adapters import catalog
from backend.storage.database import (
    DATA,
    runs,
    get,
    leaderboard,
    recover,
    link_comparisons,
)
from backend.runner.engine import Runner

ROOT = Path(__file__).resolve().parent.parent
runner = Runner()


@asynccontextmanager
async def lifespan(app):
    recover()
    refresh = asyncio.create_task(catalog.refresh())
    yield
    runner.control("stop")
    if runner.worker:
        await runner.worker
    refresh.cancel()


app = FastAPI(title="CheckoutBench", version="3.0.0", lifespan=lifespan)


@app.middleware("http")
async def local_only(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in (
        "http://127.0.0.1:" + os.getenv("BENCH_PORT", "8000"),
        "http://localhost:" + os.getenv("BENCH_PORT", "8000"),
    ):
        return Response(status_code=403)
    if request.headers.get("host", "").split(":")[0] not in (
        "127.0.0.1",
        "localhost",
        "testserver",
    ):
        return Response(status_code=403)
    return await call_next(request)


class Batch(BaseModel):
    models: list[str] = Field(min_length=1, max_length=30)
    scenarios: list[str] = Field(min_length=1, max_length=500)
    research_release: str | None = None
    release_hash: str | None = None
    agent_mode: str = "standard"
    profile: str | None = None
    repeats: int = Field(default=3, ge=1, le=100)
    seed: int = Field(default=2026, ge=0, le=2**31 - 1)
    max_steps: int = Field(default=80, ge=5, le=500)
    timeout: int = Field(default=180, ge=10, le=1800)
    max_tokens: int = Field(default=8192, ge=256, le=131072)
    reasoning: str = "default"
    spending_cap: float | None = Field(default=None, gt=0)
    video: bool = False
    infrastructure_retries: int = Field(default=1, ge=0, le=3)

    @field_validator("agent_mode")
    @classmethod
    def mode_known(cls, v):
        if v not in (
            "standard",
            "native_link",
            "agent_with_link",
            "agent_without_link",
            "paired_link",
        ):
            raise ValueError("Unknown experimental arm")
        return v

    @field_validator("scenarios")
    @classmethod
    def scenarios_known(cls, v):
        return list(dict.fromkeys(resolve_id(x) for x in v))

    @field_validator("models")
    @classmethod
    def models_known(cls, v):
        known = {m["id"] for m in catalog.models()["models"]} | set(catalog.CATALOG)
        if any(x not in known for x in v):
            raise ValueError("Unknown model; refresh the exact catalogue")
        return list(dict.fromkeys(v))

    @field_validator("reasoning")
    @classmethod
    def valid_reasoning(cls, v):
        if v not in (
            "default",
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ):
            raise ValueError("Unknown effort")
        return v

    @field_validator("profile")
    @classmethod
    def profile_known(cls, v):
        if v is not None and v not in {p["id"] for p in PROFILES}:
            raise ValueError("Unknown synthetic profile")
        return v


@app.get("/api/health")
def health():
    return {"ok": True, "version": "3.0.0"}


@app.get("/api/models")
def models(q: str = ""):
    data = catalog.models()
    from backend.research.protocol import checkpoint_records, validate_checkpoints

    proof = checkpoint_records()
    for row in data["models"]:
        if proof.get(row["id"], {}).get("verified"):
            try:
                validate_checkpoints([row["id"]])
                row["status"] = "verified"
            except (ValueError, ImportError, OSError):
                pass
    if q:
        data["search"] = [
            catalog.entry(mid)
            for mid in catalog.CATALOG
            if q.casefold() in mid.casefold()
        ][:80]
    return data


@app.post("/api/models/refresh")
async def refresh():
    return await catalog.refresh()


@app.get("/api/scenarios")
def scenarios():
    result = []
    for sid in ALL_IDS:
        row = {
            k: v
            for k, v in scenario(sid).items()
            if k not in ("profile", "customer_brief", "dom_ids", "expected_values")
        }
        row.setdefault("benchmark_version", "1.0")
        if row.get("research_release"):
            row["fixture_engine_version"] = row["benchmark_version"]
            row["benchmark_version"] = "3.0"
        row.setdefault("family", row["theme"])
        row.setdefault("variant", row["theme"])
        if "provenance" not in row:
            from scenarios.provenance import SOURCES

            row["provenance"] = {
                **SOURCES.get(row["family"], SOURCES["generic"]),
                "reviewed_at": "2026-10-14",
                "fidelity_classification": "historical fixture; not corrected",
                "live_authenticated_ui_verified": False,
            }
            if row["family"] == "railway":
                legacy_web = row["variant"] == "legacy"
                row["provenance"].update(
                    source_url=(
                        "https://contents.irctc.co.in/en/bookEticket.html"
                        if legacy_web
                        else "https://contents.irctc.co.in/en/UserGuideIRCTC.pdf"
                    ),
                    source_type="historical documentation"
                    if legacy_web
                    else "native mobile",
                    confidence=(
                        "historical browser reference; current layout unverified"
                        if legacy_web
                        else "historical app reference; not desktop fidelity evidence"
                    ),
                )
        row.setdefault("platform", "legacy_unspecified")
        row.setdefault("integrity_class", "historical-controller-not-comparable")
        result.append(row)
    return present(result)


@app.get("/api/profiles")
def profiles():
    return PROFILES


@app.post("/api/preview/{sid}")
def preview(
    sid: str, seed: int = 2026, profile: str | None = None, agent_mode: str = "standard"
):
    if agent_mode not in (
        "standard",
        "native_link",
        "agent_with_link",
        "agent_without_link",
    ):
        raise HTTPException(400)
    try:
        sid = resolve_id(sid)
    except ValueError:
        raise HTTPException(404)
    s = scenario(sid, seed, profile)
    token = new_session(s, agent_mode)
    return {
        "url": runner.origin + "/checkout/" + token,
        "task": task(s, agent_mode),
        "token": token,
        **identity(sid),
    }


@app.post("/api/estimate")
def estimate(c: Batch):
    count = len(c.scenarios) * c.repeats
    amount = 0
    unknown = []
    for mid in c.models:
        if "/" not in mid:
            continue
        meta = catalog.CATALOG.get(mid) or catalog.direct_models().get(mid)
        if not meta:
            unknown.append(mid)
            continue
        p = meta.get("pricing", {})
        amount += (
            count
            * c.max_steps
            * (
                6000 * float(p.get("prompt", 0))
                + c.max_tokens * float(p.get("completion", 0))
                + float(p.get("request", 0))
            )
        )
    return {
        "runs": count
        * (1 + 2 * len(c.models) if c.agent_mode == "paired_link" else len(c.models)),
        "estimated_cost": amount * (2 if c.agent_mode == "paired_link" else 1),
        "unknown": unknown,
        "assumption": "Planning estimate: 6,000 input tokens and full output budget per step. Actual usage varies. Caps reserve the context-window price ceiling before each request.",
    }


@app.post("/api/batches")
async def start(c: Batch):
    try:
        return await runner.start(c.model_dump())
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/control/{action}")
def control(action: str):
    if action not in ("pause", "resume", "stop"):
        raise HTTPException(400)
    runner.control(action)
    return present(runner.snapshot())


@app.get("/api/state")
def state():
    return present(runner.snapshot())


@app.get("/api/results")
def results():
    from backend.research.official import dataset
    return present(dataset(runs()))


@app.get("/api/diagnostics/experiments")
def experiment_history():
    # Operator diagnostics only; never used by the ordinary dashboard or exports.
    return present({"runs": runs()})


@app.get("/api/diagnostics/results")
def diagnostic_results(version: str = "all"):
    rows = [r for r in runs(diagnostic=True) if version == "all" or r.get("benchmark_version", "1.0") == version]
    return present({"runs": rows, "leaderboard": leaderboard(rows), "link_comparisons": link_comparisons(rows)})


@app.get("/api/results/{rid}")
def result(rid: str):
    r = next((r for r in results()["runs"] if r["id"] == rid), None)
    if not r:
        raise HTTPException(404)
    return r


@app.get("/api/diagnostics/export/{fmt}")
def diagnostic_export(fmt: str):
    return export_rows(fmt, runs(diagnostic=True))


@app.get("/api/export/{fmt}")
def export(fmt: str):
    return export_rows(fmt, results()["runs"])


def export_rows(fmt, rows):
    rows = present(rows)
    if fmt == "json":
        return Response(
            json.dumps({"version": "3.0.0", "runs": rows}, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=checkoutbench.json"},
        )
    if fmt != "csv":
        raise HTTPException(404)
    keys = [
        "id",
        "benchmark_version",
        "environment",
        "variant",
        "merchant",
        "agent_mode",
        "evaluation_mode",
        "difficulty_config",
        "model",
        "kind",
        "scenario",
        "canonical_id",
        "public_id",
        "display_name",
        "description",
        "seed",
        "profile_id",
        "repeat",
        "status",
        "task_resolved_correctly",
        "checkout_prepared",
        "authorisation_handoff_correct",
        "safe_abort_correct",
        "simulated_payment_completed",
        "payment_method_correct",
        "scoring_version",
        "research_protocol_hash",
        "release_hash",
        "success",
        "required_field_accuracy",
        "optional_correct",
        "payment_accuracy",
        "action_count",
        "invalid_actions",
        "retries",
        "wall_seconds",
        "inference_seconds",
        "browser_interaction_seconds",
        "prompt_tokens",
        "completion_tokens",
        "cost",
        "cost_kind",
        "failure_reason",
        "outcome_category",
        "genuine_inference_call_count",
        "invalid_model_output_count",
        "invalid_model_output_rate",
        "invalid_model_output_denominator",
        "inference_failure_rate",
        "unsupported_action_count",
        "inference_failure_count",
        "observation_track",
        "inference_configuration",
        "runtime_source_hash",
        "runtime_binding_hash",
        "completion_stage",
        "timestamp",
        "config",
        "hardware",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                for k, v in row.items()
            }
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=checkoutbench.csv"},
    )


@app.get("/api/events")
async def events(request: Request):
    async def stream():
        previous = ""
        while not await request.is_disconnected():
            data = json.dumps(present(runner.snapshot()))
            if data != previous:
                yield f"data: {data}\n\n"
                previous = data
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.75)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/coverage")
def coverage():
    rows = scenarios()
    results = runs(diagnostic=True)
    for s in rows:
        refs = [
            r
            for r in results
            if r["model"] == "reference"
            and r["scenario"] == s["id"]
            and r.get("agent_mode", "standard") == "standard"
            and r["status"] in ("completed", "failed")
        ]
        s["reference_status"] = (
            ("passed" if refs[0].get("success") else "failed") if refs else "unverified"
        )
    families = sorted({s["family"] for s in rows})
    return {
        "scenarios": rows,
        "families": families,
        "variants": len({(s["family"], s["variant"]) for s in rows}),
        "matrix": [
            {
                "family": f,
                "core": sum(
                    s["family"] == f and "holdout" not in s["features"] for s in rows
                ),
                "holdouts": sum(
                    s["family"] == f and "holdout" in s["features"] for s in rows
                ),
                "variants": sorted({s["variant"] for s in rows if s["family"] == f}),
                "payments": sorted({s["method"] for s in rows if s["family"] == f}),
                "unverified": sum(
                    s["family"] == f and s["reference_status"] != "passed" for s in rows
                ),
            }
            for f in families
        ],
    }


@app.post("/api/test-user/{token}")
def approve_test_user(token: str):
    from backend.fixtures import session
    from backend.workflows import tick_test_user, public

    st = session(token)
    if st["scenario"].get("benchmark_version") == "2.1":
        from backend.workflows_v21 import tick_test_user, public
    elif st["scenario"].get("benchmark_version") != "2.0":
        raise HTTPException(400)
    tick_test_user(st)
    return public(st, token)


# Admin-only routes: the fixture origin and runner allowlist never expose them.
from backend.sandboxes import router as sandbox_router

app.include_router(sandbox_router)
from backend.research.api import router as research_router

app.include_router(research_router)

app.mount("/artifacts", StaticFiles(directory=DATA), name="artifacts")
if (ROOT / "frontend/dist").exists():
    app.mount(
        "/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="dashboard"
    )
