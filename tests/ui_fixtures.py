"""Synthetic API responses for UI tests only. Never inserted in the results DB."""

import copy
import json
from pathlib import Path
import httpx

IDS = ["cua-s1", "tinyclick", "hybrid", "mai-ui", "ui-venus"]


def sample_runs():
    config = dict(
        reasoning="default",
        max_tokens=8192,
        max_steps=100,
        timeout=180,
        seed=2026,
        profile=None,
        repeats=3,
    )
    rows = []
    for model in ["cua-s1", "tinyclick"]:
        for i in range(6):
            success = model == "cua-s1" or i < 2
            rows.append(
                dict(
                    id=f"ui-{model}-{i}",
                    model=model,
                    kind="specialist",
                    scenario="V21-S01" if i % 2 == 0 else "V21-G02",
                    scenario_title="Synthetic UI fixture task",
                    environment="shopify" if i % 2 == 0 else "generic",
                    benchmark_version="2.1",
                    cohort="matched-ui-cohort",
                    config=copy.deepcopy(config),
                    profile_id="aditi",
                    seed=2026,
                    repeat=i // 2,
                    platform="desktop_web",
                    integrity_class="isolated-user-intent-v21",
                    agent_mode="standard",
                    evaluation_mode="handoff",
                    status="completed" if success else "failed",
                    success=success,
                    timestamp=f"2026-10-15T08:00:{i:02d}+00:00",
                    wall_seconds=10 + i if model == "cua-s1" else 20 + i,
                    inference_seconds=2.5,
                    required_field_accuracy=1 if success else 0.5,
                    payment_accuracy=1,
                    field_results={"name": True, "postal": success},
                    optional_results={"address2": success},
                    failure_reason=None if success else "field_mismatch",
                    completion_stage="checkout_ready" if success else "details",
                    stage_completion={
                        "payment_prepared": success,
                        "authentication_simulated": False,
                    },
                    cost=0.001,
                    cost_kind="actual",
                    recovery_success_rate=None,
                    model_call_count=1,
                    action_count=2,
                    calls=[dict(model=model, backend="local", seconds=2.5)],
                    validation_errors=0,
                    action_attribution={"model": 1, "deterministic_controller": 1},
                    latency_breakdown={
                        "browser_execution_seconds": 1,
                        "model_screenshot_seconds": 0.2,
                        "controller_compute_seconds": 0.1,
                    },
                    events=[
                        dict(
                            index=0,
                            elapsed=0.2,
                            action="fill",
                            detail={
                                "selection_source": "model",
                                "field": "Recipient",
                                "result": "typed",
                            },
                            screenshot="/artifacts/ui/action-0.png",
                        ),
                        dict(
                            index=1,
                            elapsed=0.8,
                            action="click",
                            detail={
                                "selection_source": "deterministic_controller",
                                "target": "Continue",
                            },
                            screenshot="/artifacts/ui/action-1.png",
                        ),
                    ],
                    screenshot="/artifacts/ui/action-1.png",
                    videos=[],
                )
            )
    other = copy.deepcopy(rows[0])
    other.update(
        id="other-condition",
        cohort="different-ui-cohort",
        success=False,
        status="failed",
        required_field_accuracy=0,
    )
    rows.append(other)
    historical = copy.deepcopy(rows[0])
    historical.update(
        id="historical-specialist", benchmark_version="2.0", cohort="historical-cohort"
    )
    rows.append(historical)
    for id, model, kind in [
        ("hidden-reference", "reference", "reference"),
        ("hidden-frontier", "openai/gpt-6-astra", "openrouter"),
        ("hidden-direct", "direct/example", "direct"),
    ]:
        hidden = copy.deepcopy(rows[0])
        hidden.update(id=id, model=model, kind=kind)
        rows.append(hidden)
    double = copy.deepcopy(rows[0])
    double.update(id="hidden-test-double", calls=[dict(backend="test-double")])
    rows.append(double)
    reference_assisted = copy.deepcopy(rows[0])
    reference_assisted.update(
        id="hidden-reference-attribution",
        action_attribution={"deterministic_reference": 1},
    )
    rows.append(reference_assisted)
    return rows


async def install_ui_data(page, server, populated=True):
    metadata = httpx.get(server + "/api/models").json()
    for m in metadata["models"]:
        if m["id"] in IDS:
            m.update(
                available=m["id"] != "ui-venus",
                status="configured_unverified"
                if m["id"] != "ui-venus"
                else "unavailable",
                backend="local",
                reason=None
                if m["id"] != "ui-venus"
                else "Checkpoint weights are not configured.",
            )
    metadata["models"].append(
        dict(
            id="direct/example",
            name="Hidden Direct Frontier",
            kind="direct",
            available=True,
        )
    )
    state = {"running": False, "paused": False}
    posted = []
    runs = sample_runs() if populated else []
    await page.route("**/api/models", lambda r: r.fulfill(json=metadata))
    await page.route(
        "**/api/results",
        lambda r: r.fulfill(
            json={"runs": runs, "leaderboard": [], "link_comparisons": []}
        ),
    )
    await page.route("**/api/state", lambda r: r.fulfill(json=state))

    async def events(route):
        await route.fulfill(
            content_type="text/event-stream", body="data: " + json.dumps(state) + "\n\n"
        )

    await page.route("**/api/events", events)
    await page.route(
        "**/api/estimate",
        lambda r: r.fulfill(
            json={
                "runs": len(r.request.post_data_json["models"])
                * len(r.request.post_data_json["scenarios"])
                * r.request.post_data_json["repeats"],
                "estimated_cost": 0,
                "unknown": [],
                "assumption": "Synthetic UI estimate",
            }
        ),
    )

    async def start(route):
        posted.append(route.request.post_data_json)
        current = copy.deepcopy(sample_runs()[0])
        current.update(
            status="running", success=False, timestamp="2026-10-15T08:00:00+00:00"
        )
        state.update(
            running=True,
            current=current,
            batch={
                "id": "ui-only-batch",
                "finished": 0,
                "total": len(posted[-1]["models"])
                * len(posted[-1]["scenarios"])
                * posted[-1]["repeats"],
                "status": "running",
                "config": posted[-1],
            },
        )
        await route.fulfill(json={"id": "ui-only-batch"})

    await page.route("**/api/batches", start)

    async def control(route):
        action = route.request.url.rsplit("/", 1)[-1]
        if action == "stop":
            state["running"] = False
            state["current"]["status"] = "stopped"
        else:
            state["paused"] = action == "pause"
        await route.fulfill(json=state)

    await page.route("**/api/control/*", control)
    image = (
        Path(__file__).resolve().parents[1]
        / "docs/v2.1/screenshots/shopify-fashion-1-1280.png"
    ).read_bytes()
    await page.route(
        "**/artifacts/ui/*.png",
        lambda r: r.fulfill(content_type="image/png", body=image),
    )
    return {"posted": posted, "state": state, "runs": runs}
