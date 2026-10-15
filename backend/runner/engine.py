import asyncio, json, time, os, tempfile, socket, platform, hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
from dataclasses import asdict
from playwright.async_api import (
    async_playwright,
    TimeoutError as BrowserTimeout,
    Error as BrowserError,
)
from scenarios.catalog import scenario, task
from backend.fixtures import new_session, SESSIONS
from backend.evaluator.scoring import evaluate
from backend.storage.database import DATA, save
from backend.adapters.base import Usage, Ledger, Unavailable, Stopped, BudgetExceeded
from backend.adapters.specialists import (
    SpecialistUnavailable,
    SpecialistOutputError,
    detect_hardware,
)
from backend.browser.execution import reference, visual_agent, VIEWPORT
from backend.browser.security import allowed_url
from backend.adapters.openrouter import run_openrouter


class Controls:
    def __init__(self, runner, page, run, directory):
        self.runner = runner
        self.page = page
        self.run = run
        self.directory = directory
        self.origin = runner.origin
        self.max_steps = run["config"]["max_steps"]
        self.usage = Usage()
        self.classifications = []
        self.groundings = []
        self.timings = dict(
            model_screenshot_seconds=0.0,
            artifact_capture_seconds=0.0,
            artifact_storage_seconds=0.0,
            browser_execution_seconds=0.0,
            controller_compute_seconds=0.0,
        )
        self.started = time.perf_counter()

    @property
    def stopped(self):
        return self.runner.stop_requested

    async def check(self):
        if self.stopped:
            raise Stopped("Stopped by user")
        await self.runner.resume.wait()
        if self.stopped:
            raise Stopped("Stopped by user")
        if (
            sum(e["action"] not in ("start", "finish") for e in self.run["events"])
            >= self.max_steps
        ):
            raise Stopped("Maximum action budget reached")

    async def assess_grounding(self, locator, prediction):
        # Private measurement after prediction. Never returned to the action planner.
        try:
            box = await locator.bounding_box(timeout=250)
        except BrowserError:
            box = None
        self.groundings.append(
            bool(
                box
                and box["x"] <= prediction["x"] <= box["x"] + box["width"]
                and box["y"] <= prediction["y"] <= box["y"] + box["height"]
            )
        )

    async def record(self, kind, detail):
        if self.page.is_closed():
            remaining = [p for p in self.page.context.pages if not p.is_closed()]
            if remaining:
                self.page = remaining[-1]
        path = self.directory / f"step-{len(self.run['events']):04d}.jpg"
        capture_started = time.perf_counter()
        await self.page.screenshot(path=str(path), type="jpeg", quality=65)
        self.timings["artifact_capture_seconds"] += (
            time.perf_counter() - capture_started
        )
        event = {
            "index": len(self.run["events"]),
            "elapsed": time.perf_counter() - self.started,
            "action": kind,
            "detail": detail,
            "screenshot": f"/artifacts/{self.run['id']}/{path.name}",
        }
        self.run["events"].append(event)
        self.run["screenshot"] = event["screenshot"]
        state = getattr(self, "session_state", None)
        if state and state["scenario"].get("benchmark_version") == "2.1":
            from backend.research.measurement import observe

            source = detail.get("selection_source") or detail.get("grounding_source")
            actor = (
                "model"
                if source in ("model", "cua-s1", "tinyclick")
                else "controller"
                if source
                else "browser"
            )
            observe(
                state["scenario"],
                state,
                kind,
                actor,
                detail.get("prediction"),
                event["screenshot"],
                event["index"],
            )
            self.run["stage_events"] = state.get("research_events", [])
        storage_started = time.perf_counter()
        save(self.run)
        self.timings["artifact_storage_seconds"] += (
            time.perf_counter() - storage_started
        )
        self.runner.current = self.run


class Runner:
    def __init__(self):
        self.origin = "http://127.0.0.1:" + os.getenv("CHECKOUT_PORT", "8001")
        self.resume = asyncio.Event()
        self.resume.set()
        self.stop_requested = False
        self.current = None
        self.batch = None
        self.worker = None
        self.active_task = None

    def snapshot(self):
        return {
            "batch": self.batch,
            "current": self.current,
            "paused": not self.resume.is_set(),
            "running": bool(self.worker and not self.worker.done()),
        }

    async def start(self, config):
        if any(s.startswith("V3-") for s in config.get("scenarios", [])):
            from backend.research.protocol import validate_checkpoints

            validate_checkpoints(config["models"])
        if self.worker and not self.worker.done():
            raise ValueError("A batch is already running")
        if config.get("agent_mode") in (
            "native_link",
            "agent_with_link",
            "agent_without_link",
            "paired_link",
        ) and any(scenario(sid).get("family") != "link" for sid in config["scenarios"]):
            raise ValueError("Select only Link scenarios for Link comparison arms")
        if config.get("research_release"):
            from backend.research.protocol import validate_standard

            validate_standard(config)
        if any(
            not sid.startswith(("V21-", "V3-")) for sid in config["scenarios"]
        ) and any(m != "reference" for m in config["models"]):
            raise ValueError(
                "Historical v1/v2 controllers are archived for reference replay. Use v2.1 for model evaluation."
            )
        self.stop_requested = False
        self.resume.set()
        self.current = None
        self.batch = {
            "id": uuid4().hex,
            "config": config,
            "total": len(config["models"])
            * len(config["scenarios"])
            * config["repeats"],
            "finished": 0,
            "status": "running",
            "spent": 0,
        }
        if config.get("agent_mode") == "paired_link":
            self.batch["total"] = (
                (1 + 2 * len(config["models"]))
                * len(config["scenarios"])
                * config["repeats"]
            )
        self.worker = asyncio.create_task(self.batch_run(config))
        return self.batch

    async def batch_run(self, c):
        ledger = Ledger(c.get("spending_cap"))
        try:
            for repeat in range(c["repeats"]):
                for sid in c["scenarios"]:
                    plan = [(m, c) for m in c["models"]]
                    if c.get("agent_mode") == "paired_link":
                        plan = [("reference", {**c, "agent_mode": "native_link"})] + [
                            (m, {**c, "agent_mode": arm})
                            for m in c["models"]
                            for arm in ("agent_without_link", "agent_with_link")
                        ]
                    for model, run_config in plan:
                        await self.resume.wait()
                        if self.stop_requested:
                            return
                        self.active_task = asyncio.create_task(
                            self.one(model, sid, run_config, repeat, ledger)
                        )
                        try:
                            await self.active_task
                        except asyncio.CancelledError:
                            if not self.stop_requested:
                                raise
                        for attempt in range(c.get("infrastructure_retries", 1)):
                            if (
                                self.stop_requested
                                or not self.current
                                or self.current.get("failure_reason")
                                != "infrastructure_error"
                                or self.current.get("action_count", 0) > 0
                                or self.current.get("cost", 0) > 0
                            ):
                                break
                            await asyncio.sleep(0.5)
                            self.active_task = asyncio.create_task(
                                self.one(
                                    model, sid, run_config, repeat, ledger, attempt + 1
                                )
                            )
                            try:
                                await self.active_task
                            except asyncio.CancelledError:
                                if not self.stop_requested:
                                    raise
                        self.batch["finished"] += 1
                        self.batch["spent"] = ledger.spent
                        self.batch["reserved"] = ledger.reserved
        finally:
            self.batch["status"] = "stopped" if self.stop_requested else "completed"
            self.active_task = None

    async def one(self, model, sid, c, repeat, ledger, infra_attempt=0):
        s = scenario(sid, c["seed"], c.get("profile"))
        is_v21 = s.get("benchmark_version") == "2.1"
        is_v2 = s.get("benchmark_version") in ("2.0", "2.1")
        agent_mode = c.get("agent_mode", "standard")
        public = task(s, agent_mode)
        public.setdefault("payment_request", {"method": s["method"], "app": s["app"]})
        public["separate_billing"] = "billing" in s["features"]
        rid = uuid4().hex
        directory = DATA / rid
        directory.mkdir()
        started = time.perf_counter()
        kind = (
            "reference"
            if model == "reference"
            else "direct"
            if model.startswith("direct/")
            else "openrouter"
            if "/" in model
            else "specialist"
        )
        run = dict(
            id=rid,
            batch_id=self.batch["id"] if self.batch else None,
            model=model,
            kind=kind,
            scenario=sid,
            scenario_title=s["title"],
            holdout="holdout" in s["features"],
            seed=s["seed"],
            profile_id=s["profile"]["id"],
            repeat=repeat,
            config={k: v for k, v in c.items() if k not in ("models", "scenarios")},
            timestamp=datetime.now(timezone.utc).isoformat(),
            status="running",
            infrastructure_attempt=infra_attempt,
            events=[],
            hardware=detect_hardware(),
            viewport=s.get("viewport", VIEWPORT),
            benchmark_version=s.get("benchmark_version", "1.0"),
            environment=s.get("family", s["theme"]),
            variant=s.get("variant", s["theme"]),
            merchant=s.get("merchant"),
            difficulty_config=s.get("difficulty_config", {"features": s["features"]}),
            agent_mode=agent_mode,
            evaluation_mode=s.get("evaluation_mode", "handoff"),
            platform=s.get("platform", "legacy_unspecified"),
            provenance=s.get("provenance"),
            integrity_class=s.get(
                "integrity_class", "historical-controller-not-comparable"
            ),
            evaluation_claim="fixture verification only"
            if model == "reference"
            else "model-assisted controller"
            if model in ("cua-s1", "tinyclick", "hybrid")
            else "model browser agent",
            success=False,
            cost=0,
        )
        run["cohort"] = hashlib.sha256(
            json.dumps(
                {k: v for k, v in c.items() if k not in ("models", "spending_cap")},
                sort_keys=True,
            ).encode()
        ).hexdigest()[:12]
        if s.get("research_release"):
            from backend.research.protocol import execution_manifest

            run.update(execution_manifest(c, s, model))
        self.current = run
        save(run)
        token = new_session(s, agent_mode)
        # Token is held only in memory and removed before persistence/export.
        SESSIONS[token].update(research_run_id=rid, research_model=model)
        user_task = None
        ctl = None
        context = None
        usage = Usage()
        try:
            if agent_mode == "native_link" and (
                s.get("family") != "link" or model != "reference"
            ):
                raise Unavailable(
                    "Native Link is a scripted test-user baseline for Link scenarios only"
                )
            if is_v2:
                if is_v21:
                    from backend.workflows_v21 import tick_test_user
                else:
                    from backend.workflows import tick_test_user

                async def test_user():
                    while True:
                        if not self.stop_requested and self.resume.is_set():
                            tick_test_user(SESSIONS[token])
                        await asyncio.sleep(0.15)

                user_task = asyncio.create_task(test_user())
            # Validate availability before launching a browser; blocked is not a model failure.
            if kind in ("openrouter", "direct"):
                from backend.adapters.catalog import require

                meta = require(model)
                run["model_metadata"] = {
                    k: meta.get(k)
                    for k in ("id", "pricing", "supported_parameters", "architecture")
                }
            elif kind == "specialist":
                from backend.adapters.specialists import specialist_catalog

                items = {m["id"]: m for m in specialist_catalog()}
                row = items.get(model)
                if not row or not row["available"]:
                    raise Unavailable(
                        (row or {}).get("reason")
                        or "Specialist weights or endpoint unavailable"
                    )
                run["model_metadata"] = row
                if c.get("spending_cap") is not None and "remote" in row["backend"]:
                    raise BudgetExceeded(
                        "Remote specialist billing cannot be bounded by this runner; configure an endpoint-side quota or use local inference."
                    )
            launch_started = time.perf_counter()
            async with async_playwright() as pw:
                with tempfile.TemporaryDirectory(prefix="checkoutbench-") as tmp:
                    with socket.socket() as sock:
                        sock.bind(("127.0.0.1", 0))
                        port = sock.getsockname()[1]
                    context = await pw.chromium.launch_persistent_context(
                        tmp,
                        headless=True,
                        viewport=s.get("viewport", VIEWPORT),
                        device_scale_factor=1,
                        service_workers="block",
                        args=[
                            f"--remote-debugging-port={port}",
                            "--disable-background-networking",
                        ],
                        record_video_dir=str(directory / "video")
                        if c["video"]
                        else None,
                    )

                    async def guard(route):
                        u = urlsplit(route.request.url)
                        ok = allowed_url(route.request.url, self.origin, token)
                        if ok:
                            await route.continue_()
                        else:
                            run.setdefault("blocked_requests", []).append(
                                u.scheme + "://" + str(u.hostname) + u.path
                            )
                            await route.abort()

                    await context.route("**/*", guard)
                    await context.route_web_socket("**/*", lambda ws: ws.close())
                    page = context.pages[0]
                    page.set_default_timeout(7000)
                    ctl = Controls(self, page, run, directory)
                    ctl.session_state = SESSIONS[token]
                    if run.get("execution_manifest"):
                        run["execution_manifest"]["browser_version"] = (
                            context.browser.version
                            if context.browser
                            else "persistent-context: see Playwright runtime"
                        )
                    ctl.timings["browser_setup_seconds"] = (
                        time.perf_counter() - launch_started
                    )
                    try:
                        await page.goto(self.origin + "/checkout/" + token)
                        await page.locator(
                            "#workflow" if is_v2 else "#shipping"
                        ).wait_for()
                        await ctl.record("start", {"url": page.url})
                        if kind in ("openrouter", "direct"):
                            coro = run_openrouter(
                                page,
                                public,
                                ctl,
                                model,
                                c,
                                ledger,
                                f"http://127.0.0.1:{port}",
                            )
                        elif model in ("mai-ui", "ui-venus"):
                            coro = visual_agent(page, public, ctl, model)
                        elif is_v21:
                            from backend.browser.v21 import reference_v21

                            coro = reference_v21(page, public, ctl, model)
                        elif is_v2:
                            from backend.browser.v2 import reference_v2

                            coro = reference_v2(page, public, ctl, model)
                        else:
                            coro = reference(page, public, ctl, model)
                        usage = await asyncio.wait_for(coro, timeout=c["timeout"])
                        await ctl.record("finish", {})
                    finally:
                        if ctl:
                            usage = ctl.usage
                        if context:
                            await context.close()
            run["status"] = "completed"
        except (Unavailable, SpecialistUnavailable) as e:
            run.update(status="unavailable", failure_reason=str(e))
        except BudgetExceeded as e:
            run.update(status="blocked", failure_reason="spending_cap", error=str(e))
        except (Stopped, asyncio.CancelledError) as e:
            run.update(
                status="stopped" if self.stop_requested else "failed",
                failure_reason="user_stopped" if self.stop_requested else "max_steps",
            )
        except asyncio.TimeoutError:
            run.update(status="failed", failure_reason="timeout")
        except BrowserTimeout:
            run.update(
                status="failed" if ctl else "blocked",
                failure_reason="browser_action_timeout"
                if ctl
                else "infrastructure_error",
            )
        except BrowserError:
            run.update(
                status="failed" if ctl and len(run["events"]) > 1 else "blocked",
                failure_reason="invalid_browser_action"
                if ctl and len(run["events"]) > 1
                else "infrastructure_error",
            )
        except SpecialistOutputError as e:
            run.update(
                status="failed", failure_reason="invalid_model_action", error=str(e)
            )
        except Exception as e:
            # Do not log exception text from provider libraries: it can contain request headers.
            run.update(
                status="blocked",
                failure_reason="infrastructure_error",
                error=type(e).__name__,
            )
        finally:
            if user_task:
                user_task.cancel()
                try:
                    await user_task
                except asyncio.CancelledError:
                    pass
            if ctl:
                usage = ctl.usage
            score = evaluate(s, SESSIONS[token])
            previous = run.get("failure_reason")
            run.update(score)
            if previous:
                run["failure_reason"] = previous
            if run["status"] == "completed" and not run["success"]:
                run["status"] = "failed"
            if run["status"] not in ("completed", "failed"):
                run["success"] = False
            run.update(asdict(usage))
            run["model_call_count"] = len(usage.calls)
            run["action_attribution"] = {
                label: sum(
                    e["detail"].get("selection_source") == label for e in run["events"]
                )
                for label in (
                    "deterministic_reference",
                    "deterministic_semantic_assistance",
                    "deterministic_controller",
                    "cua-s1",
                    "model",
                )
            }
            run["fallback_policy"] = (
                "No semantic or coordinate correction after inference; unsupported selections/errors affect execution. Lifecycle navigation is deterministic for specialists."
            )
            run["wall_seconds"] = time.perf_counter() - started
            if is_v21 and ctl:
                from backend.evaluator.scoring import norm

                from backend.evaluator.semantic import grade_decisions

                decisions = getattr(ctl, "semantic_decisions", [])
                ctl.classifications = grade_decisions(s, decisions)
                run["semantic_decisions"] = decisions
                run["field_classification_samples"] = len(ctl.classifications)
                run["latency_breakdown"] = {
                    **ctl.timings,
                    "cua_inference_seconds": sum(
                        x.get("seconds", 0)
                        for x in usage.calls
                        if x.get("model") == "cua-s1"
                    ),
                    "tinyclick_inference_seconds": sum(
                        x.get("seconds", 0)
                        for x in usage.calls
                        if x.get("model") == "tinyclick"
                    ),
                    "total_inference_seconds": usage.inference_seconds,
                }
                accounted = sum(ctl.timings.values()) + usage.inference_seconds
                run["latency_breakdown"]["other_wait_observation_teardown_seconds"] = (
                    max(0, run["wall_seconds"] - accounted)
                )
                run["latency_breakdown"]["end_to_end_seconds"] = run["wall_seconds"]
                if kind in ("openrouter", "direct"):
                    for key in (
                        "browser_execution_seconds",
                        "controller_compute_seconds",
                        "model_screenshot_seconds",
                    ):
                        run["latency_breakdown"][key] = None
                run["latency_measurement"] = (
                    "Disjoint measured intervals; residual includes DOM observation, deliberate waits, network responses and teardown. Model load is included in inference. Null component intervals mean the browser-use library does not expose a separate measurement."
                )

            run["browser_interaction_seconds"] = max(
                0, run["wall_seconds"] - usage.inference_seconds
            )
            run["browser_time_kind"] = (
                "wall_minus_inference_includes_controller_and_setup"
            )
            run["action_count"] = len(
                [e for e in run["events"] if e["action"] not in ("start", "finish")]
            )
            if agent_mode == "native_link":
                run["user_interactions"] = (
                    run.get("user_interactions", 0) + run["action_count"]
                )
                run["agent_actions"] = 0
            else:
                run["agent_actions"] = (
                    0 if model == "reference" else run["action_count"]
                )
            run["invalid_actions"] = sum(
                (e["action"] == "invalid_action") + len(e["detail"].get("errors", []))
                for e in run["events"]
            )
            run["retries"] = SESSIONS[token]["retries"]
            run["validation_errors"] = SESSIONS[token]["validation_errors"]
            run["field_classification_accuracy"] = (
                sum(ctl.classifications) / len(ctl.classifications)
                if ctl and ctl.classifications
                else None
            )
            run["grounding_accuracy"] = (
                sum(ctl.groundings) / len(ctl.groundings)
                if ctl and ctl.groundings
                else None
            )
            run["videos"] = (
                [
                    f"/artifacts/{rid}/video/{p.name}"
                    for p in (directory / "video").glob("*.webm")
                ]
                if c["video"]
                else []
            )
            if is_v21:
                from backend.research.measurement import finish as research_finish

                run.update(research_finish(run, s, SESSIONS[token]))
            (directory / "actions.json").write_text(json.dumps(run, indent=2))
            save(run)
            self.current = run
            SESSIONS.pop(token, None)

    def control(self, action):
        if action == "pause":
            self.resume.clear()
        if action == "resume":
            self.resume.set()
        if action == "stop":
            self.stop_requested = True
            self.resume.set()
            if self.active_task:
                self.active_task.cancel()
