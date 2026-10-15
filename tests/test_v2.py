import asyncio
import httpx
import pytest
from scenarios.v2 import V2_SPECS, scenario_v2
from backend.workflows import init, transition, make_qr, tick_test_user
from backend.evaluator.v2 import evaluate_v2
from backend.qr import generate, LEVELS, QRConfig
from backend.authentication import new_auth, verify


def test_v2_coverage_and_qr():
    core = [s for s in V2_SPECS if not s.get("holdout")]
    assert len(core) >= 38 and sum(bool(s.get("holdout")) for s in V2_SPECS) >= 8
    for prefix, n in [
        ("S", 12),
        ("R", 6),
        ("P", 4),
        ("E", 4),
        ("L", 8),
        ("Q", 6),
        ("A", 5),
    ]:
        assert sum(s["id"].startswith(prefix) for s in core) >= n
    for level in LEVELS:
        _, report = generate(
            "https://wallet.checkoutbench.invalid/s/test/0", LEVELS[level]
        )
        if level in ("Q0", "Q1", "Q5"):
            assert report["decoder_success"], level
        if level in ("Q2", "Q4"):
            assert not report["decoder_success"], level
    for size in (64, 96, 128, 256):
        raw, report = generate("https://example.invalid/t", QRConfig(size=size))
        assert raw
        if size >= 96:
            assert report["decoder_success"]


def test_auth_negative_scoring_and_consent():
    a = new_auth(2026, "link", fault="otp_expired")
    assert verify(a, a["code"]) == "expired"
    a = new_auth(2026, "link", generation=1)
    assert verify(a, "wrong") == "invalid"
    assert verify(a, a["code"]) == "approved"
    s = scenario_v2("L03")
    st = init(s)
    st["stage"] = "checkout_ready"
    st["values"] = dict(s["expected_values"])
    st["values"]["billing_address1"] = "wrong"
    st["link_authenticated"] = True
    assert not evaluate_v2(s, st)["success"]
    st["values"]["billing_address1"] = s["expected_values"]["billing_address1"]
    assert evaluate_v2(s, st)["success"]
    st["link_registered"] = True
    assert evaluate_v2(s, st)["failure_reason"] == "unauthorised_registration"
    s = scenario_v2("A05")
    st = init(s)
    st["stage"] = "safe_abort"
    st["reported_handoff"] = True
    st["values"] = dict(s["expected_values"])
    assert not evaluate_v2(s, st)[
        "success"
    ]  # cannot abort early without actual challenge


async def run_batch(server, ids, mode="standard", timeout=120):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            server + "/api/batches",
            json=dict(
                models=["reference"],
                scenarios=ids,
                repeats=1,
                seed=2026,
                max_steps=150,
                timeout=timeout,
                agent_mode=mode,
                infrastructure_retries=0,
            ),
        )
        assert r.status_code == 200, r.text
        batch = r.json()["id"]
        for _ in range(len(ids) * timeout * 4 + 100):
            state = (await c.get(server + "/api/state")).json()
            if not state["running"]:
                break
            await asyncio.sleep(0.25)
        rows = [
            r
            for r in (await c.get(server + "/api/diagnostics/results")).json()["runs"]
            if r["batch_id"] == batch
        ]
        assert len(rows) == len(ids)
        return rows


async def test_v2_smoke(server):
    rows = await run_batch(server, ["S01", "L01", "R01", "P01", "E04", "Q02", "A02"])
    assert all(r["success"] for r in rows), [
        (
            r["scenario"],
            r["status"],
            r.get("failure_reason"),
            r.get("error"),
            r.get("completion_stage"),
            r.get("field_results"),
        )
        for r in rows
        if not r["success"]
    ]


async def test_v2_complete_reference_suite(server):
    rows = await run_batch(server, [s["id"] for s in V2_SPECS])
    assert all(r["success"] for r in rows), [
        (
            r["scenario"],
            r["status"],
            r.get("failure_reason"),
            r.get("error"),
            r.get("completion_stage"),
            r.get("field_results"),
        )
        for r in rows
        if not r["success"]
    ]
    assert all(not r.get("blocked_requests") for r in rows)


async def test_v2_private_state_and_iframe(server, page):
    async with httpx.AsyncClient() as c:
        p = (await c.post(server + "/api/preview/L06")).json()
        origin = p["url"].split("/checkout/")[0]
        data = (await c.get(origin + "/v2/" + p["token"] + "/state")).json()
        serialized = str(data)
        for k in (
            "expected_values",
            "success_conditions",
            "faults_seen",
            "expected_outcome",
            "profile",
            "seed",
        ):
            assert k not in data
        for path in [
            "/api/coverage",
            "/api/test-user/" + p["token"],
            "/docs",
            "/session/" + p["token"],
        ]:
            assert (await c.get(origin + path)).status_code == 404
        await page.goto(p["url"])
        await page.locator("#workflow").wait_for()
        assert (
            "FICTIONAL BENCHMARK SIMULATION" in await page.locator("body").inner_text()
        )


async def test_link_arms(server):
    for mode in ("native_link", "agent_with_link", "agent_without_link"):
        rows = await run_batch(server, ["L01", "L03"], mode)
        assert all(
            r["success"] or (mode == "native_link" and r["scenario"] == "L03")
            for r in rows
        )
        if mode == "native_link":
            assert not next(r for r in rows if r["scenario"] == "L03")["success"]
    async with httpx.AsyncClient() as c:
        d = (await c.get(server + "/api/diagnostics/results")).json()
        assert any(p["paired"] for p in d["link_comparisons"])
        assert all(
            b["benchmark_version"] == "2.0"
            for b in (await c.get(server + "/api/diagnostics/results?version=2.0")).json()[
                "leaderboard"
            ]
        )


def test_qr_scaling_is_not_recovery_and_payload_is_seeded():
    from PIL import Image
    from io import BytesIO
    import zxingcpp

    s = scenario_v2("Q02")
    a = init(s)
    b = init(s)
    make_qr(a, "session-a")
    make_qr(b, "session-b")
    assert a["qr"]["image"] == b["qr"]["image"]
    scaled = Image.open(BytesIO(a["qr"]["image"])).resize((1024, 1024))
    assert not zxingcpp.read_barcode(scaled)
    a["stage"] = "payment"
    a["values"] = dict(s["expected_values"])
    transition(a, "pay", {}, "session-a")
    assert a["stage"] == "payment"
    transition(a, "qr_refresh", {}, "session-a")
    transition(a, "pay", {}, "session-a")
    assert evaluate_v2(s, a)["success"]


def test_idempotent_transaction_and_authentication_boundaries():
    from backend.workflows import complete_auth

    s = scenario_v2("P01")
    st = init(s)
    st["values"] = dict(s["expected_values"])
    st["stage"] = "payment"
    transition(st, "pay", {}, "x")
    tx = st["transaction"]
    assert st["transaction_count"] == 1
    with pytest.raises(Exception):
        transition(st, "pay", {}, "x")
    assert st["transaction"] == tx and st["transaction_count"] == 1
    transition(st, "gateway", {}, "x")
    with pytest.raises(Exception):
        transition(st, "return_auth", {}, "x")
    assert not evaluate_v2(s, st)["success"]
    transition(st, "request_auth", {}, "x")
    tick_test_user(st)
    transition(st, "return_auth", {}, "x")
    transition(st, "finish", {}, "x")
    assert evaluate_v2(s, st)["success"]
    transition(st, "pay", {}, "x")
    assert st["transaction_count"] == 1


async def test_collapsed_and_conditional_controls(server, page):
    async with httpx.AsyncClient() as c:
        p = (await c.post(server + "/api/preview/S02")).json()
        await page.goto(p["url"])
        await page.locator("#workflow").wait_for()
        assert await page.locator("details.rollup:not([open])").count() > 0
        summary = page.locator("details.rollup").first
        await summary.locator("summary").click()
        assert await summary.get_attribute("open") is not None
        await summary.locator("summary").click()
        assert await summary.get_attribute("open") is None
        p = (await c.post(server + "/api/preview/S07")).json()
        await page.goto(p["url"])
        await page.locator("#workflow").wait_for()
        assert not await page.get_by_label("Delivery window", exact=True).count()
        await page.get_by_label("Delivery method", exact=True).select_option(
            "Scheduled delivery"
        )
        assert await page.get_by_label("Delivery window", exact=True).is_visible()
        assert not await page.get_by_label(
            "Substitution preference", exact=True
        ).count()
        await page.get_by_label("Allow substitutions", exact=True).check()
        assert await page.get_by_label(
            "Substitution preference", exact=True
        ).is_visible()
        p = (await c.post(server + "/api/preview/S04")).json()
        await page.goto(p["url"])
        await page.locator("merchant-extension").wait_for()
        assert await page.get_by_label("Gift wrapping", exact=True).is_visible()


def test_safe_abort_cannot_override_payment_preference():
    s = scenario_v2("A05")
    st = init(s)
    st["values"] = dict(s["expected_values"])
    st["values"]["payment_method"] = "upi_app"
    st["values"]["upi_app"] = "PhonePe"
    st["stage"] = "safe_abort"
    st["reported_handoff"] = True
    st["attempts"] = 1
    st["faults_seen"] = ["auth_locked"]
    assert not evaluate_v2(s, st)["success"]


async def test_registration_requires_explicit_consent(server):
    rows = await run_batch(server, ["L09"])
    assert rows[0]["success"], rows[0].get("failure_reason")
    async with httpx.AsyncClient() as c:
        info = (await c.post(server + "/api/preview/L02")).json()
        origin = info["url"].split("/checkout/")[0]
        base = origin + "/v2/" + info["token"]
        await c.post(
            base + "/action",
            json={"action": "recognize", "values": {"email": "aditi.rao@example.test"}},
        )
        r = await c.post(
            base + "/action",
            json={"action": "register", "values": {"registration_consent": "false"}},
        )
        assert (
            not r.json()["link_registered"] and "explicit consent" in r.json()["error"]
        )


def test_passengers_optional_fields_and_restricted_slots():
    from backend.workflows import validate_details

    s = scenario_v2("R01")
    st = init(s)
    st["values"] = dict(s["expected_values"])
    st["values"].pop("p2_name")
    assert not validate_details(st) and "Passenger 2 name" in st["error"]
    st["values"]["p2_name"] = s["expected_values"]["p2_name"]
    st["values"].pop("coach", None)
    assert validate_details(st)
    s = scenario_v2("S07")
    st = init(s)
    st["values"] = dict(s["expected_values"])
    st["faults_seen"] = ["slot_changed"]
    st["values"]["delivery_slot"] = "Tomorrow 10:00–12:00"
    assert not validate_details(st)


def test_seeded_reset_and_public_projection():
    from backend.workflows import public

    s = scenario_v2("L07", 88)
    a = init(s)
    b = init(s)
    assert public(a, "a")["values"] == public(b, "b")["values"]
    transition(a, "recognize", {"values": {"email": s["profile"]["email"]}}, "a")
    visible = public(a, "a")
    assert "code" not in visible["auth"]
    assert not (
        {"expected_values", "expected_outcome", "profile", "faults_seen", "history"}
        & set(visible)
    )
    assert b["stage"] == "details" and not b["auth"]


async def test_electronics_auth_and_lookup_alternatives(server):
    rows = await run_batch(server, ["S06", "E02", "E04", "V2H05"])
    assert all(r["success"] for r in rows), [
        (r["scenario"], r["failure_reason"]) for r in rows
    ]
    assert (
        next(r for r in rows if r["scenario"] == "S06")["completion_stage"]
        == "payment_successful_simulation"
    )


def test_qr_permitted_intent_alternative():
    s = scenario_v2("Q04")
    st = init(s)
    st["values"] = dict(s["expected_values"])
    st["selected_challan"] = "DEMO-CH-1002"
    st["values"].update(payment_method="upi_app", upi_app="PhonePe")
    st["stage"] = "payment"
    make_qr(st, "x")
    transition(st, "pay", {}, "x")
    assert (
        evaluate_v2(s, st)["success"]
        and evaluate_v2(s, st)["qr_recovery_accuracy"] == 1
    )


def test_version_and_difficulty_aggregation():
    from backend.storage.database import leaderboard

    base = dict(
        model="reference",
        kind="reference",
        status="completed",
        scenario="S01",
        wall_seconds=1.0,
        cohort="same-conditions",
        agent_mode="standard",
        evaluation_mode="handoff",
        config=dict(reasoning="default", max_tokens=8192, max_steps=100, timeout=180),
    )
    rows = [
        dict(base, benchmark_version="1.0", success=True),
        dict(
            base,
            benchmark_version="2.0",
            success=True,
            difficulty_config=dict(
                semantic="standard", visual="responsive", payment="card"
            ),
        ),
        dict(
            base,
            benchmark_version="2.0",
            success=False,
            difficulty_config=dict(
                semantic="unfamiliar", visual="responsive", payment="card"
            ),
        ),
    ]
    summaries = {r["benchmark_version"]: r for r in leaderboard(rows)}
    assert summaries["1.0"]["runs"] == 1
    assert summaries["2.0"]["success_rate"] == 0.5
    dims = summaries["2.0"]["by_difficulty_dimension"]
    assert dims["semantic"]["standard"]["success_rate"] == 1
    assert dims["semantic"]["unfamiliar"]["success_rate"] == 0
    assert dims["visual"]["responsive"] == {"runs": 2, "success_rate": 0.5}
    assert dims["interaction"] == {}


@pytest.mark.parametrize(
    "message,recover",
    [
        ("Locator.inner_text: Frame was detached", True),
        ("Execution context was destroyed, most likely because of a navigation", True),
        ("Locator.click: strict mode violation", False),
    ],
)
async def test_reference_navigation_interrupts_do_not_hide_action_errors(
    monkeypatch, message, recover
):
    """Force a read interrupted by navigation; permanent action errors must still escape."""
    from types import SimpleNamespace
    from playwright.async_api import Error as BrowserError
    import backend.browser.v2 as controller

    observed = 0

    async def terminal(_page):
        nonlocal observed
        observed += 1
        if observed == 1:
            raise BrowserError(message)
        return True

    async def check():
        pass

    page = SimpleNamespace(is_closed=lambda: False)
    page.context = SimpleNamespace(pages=[page])
    ctl = SimpleNamespace(check=check, max_steps=2)
    monkeypatch.setattr(controller, "terminal", terminal)
    if recover:
        await controller.reference_v2(page, {"preferences": {}}, ctl)
        assert observed == 2
    else:
        with pytest.raises(BrowserError, match="strict mode"):
            await controller.reference_v2(page, {"preferences": {}}, ctl)
        assert observed == 1
