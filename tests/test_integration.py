import asyncio, json, csv, io
import httpx, pytest
from playwright.async_api import expect
from scenarios.catalog import SPECS, scenario
from backend.browser.execution import reference
from backend.adapters.base import Usage
from pathlib import Path


async def preview(server, page, sid):
    async with httpx.AsyncClient() as c:
        r = await c.post(server + "/api/preview/" + sid)
        r.raise_for_status()
        p = r.json()
    await page.goto(p["url"])
    await page.locator("#shipping").wait_for()
    return p


async def fill_shipping(page, p):
    for key in (
        "name",
        "email",
        "phone",
        "address1",
        "address2",
        "state",
        "city",
        "postal",
    ):
        loc = page.locator('[name="' + key + '"]')
        if key in ("state", "city"):
            await loc.select_option(p[key])
        else:
            await loc.fill(p[key])


async def test_all_scenarios_reference_and_exports(server):
    async with httpx.AsyncClient(timeout=20) as c:
        cfg = {
            "models": ["reference"],
            "scenarios": [s[0] for s in SPECS],
            "repeats": 1,
            "seed": 731,
            "max_steps": 100,
            "timeout": 45,
            "video": True,
        }
        r = await c.post(server + "/api/batches", json=cfg)
        assert r.status_code == 200, r.text
        batch = r.json()["id"]
        for _ in range(600):
            state = (await c.get(server + "/api/state")).json()
            if not state["running"]:
                break
            await asyncio.sleep(0.25)
        else:
            pytest.fail("Reference suite timed out")
        all_results = (await c.get(server + "/api/results")).json()
        rows = [r for r in all_results["runs"] if r["batch_id"] == batch]
        assert len(rows) == 18
        assert all(r["success"] for r in rows), [
            (
                r["scenario"],
                r["status"],
                r.get("failure_reason"),
                r.get("error"),
                r.get("field_results"),
            )
            for r in rows
            if not r["success"]
        ]
        assert all(r["events"] and r["videos"] for r in rows)
        assert all(not r.get("blocked_requests") for r in rows)
        assert next(r for r in rows if r["scenario"] == "T14")["retries"] == 1
        assert next(r for r in rows if r["scenario"] == "T13")["validation_errors"] == 1
        j = await c.get(server + "/api/export/json")
        assert len(j.json()["runs"]) >= 18
        j2 = await c.get(server + "/api/export/json")
        assert j.content == j2.content
        exported = list(
            csv.DictReader(io.StringIO((await c.get(server + "/api/export/csv")).text))
        )
        assert {r["id"] for r in rows} <= {r["id"] for r in exported}
        assert json.loads(exported[0]["config"])["seed"] == 731
        shot = await c.get(server + rows[0]["events"][-1]["screenshot"])
        assert shot.status_code == 200 and shot.headers["content-type"] == "image/jpeg"


async def test_required_dependencies_and_network_isolation(server, page):
    info = await preview(server, page, "T04")
    assert await page.locator("[name=city]").is_disabled()
    await page.get_by_role("button", name="Continue to payment →").click()
    await expect(page.locator("#shippingError")).to_have_text(
        "Please check the highlighted delivery details."
    )
    await page.locator("[name=state]").select_option("Maharashtra")
    assert "Pune" in await page.locator("[name=city]").inner_text()
    assert "Bengaluru" not in await page.locator("[name=city]").inner_text()
    async with httpx.AsyncClient() as c:
        fixture_origin = info["url"].split("/checkout/")[0]
        for path in [
            "/api/scenarios",
            "/api/results",
            "/fixtures.json",
            "/docs",
            "/openapi.json",
        ]:
            assert (await c.get(fixture_origin + path)).status_code == 404
        config = (await c.get(info["url"].replace("/checkout/", "/session/"))).json()
        assert not any(
            k in config
            for k in ("profile", "expected", "success_conditions", "required_fields")
        )
        assert (
            await c.post(
                server + "/api/control/pause",
                headers={"origin": "https://evil.example"},
            )
        ).status_code == 403


async def test_optional_address_empty_ui(server, page):
    info = await preview(server, page, "T03")
    p = info["task"]["profile"]
    p["address2"] = ""
    assert not await page.locator("[name=address2]").get_attribute("required")
    await fill_shipping(page, p)
    await page.get_by_role("button", name="Continue to payment →").click()
    await page.get_by_role("heading", name="Choose how to pay").wait_for()


async def test_original_optional_regression(page):
    from tests.conftest import ROOT

    await page.goto((ROOT / "index.html").as_uri())
    values = {
        "fullName": "Aditi Rao",
        "email": "aditi.rao@example.test",
        "phone": "9000000001",
        "address1": "14B Maple Residency",
        "postal": "560038",
    }
    for k, v in values.items():
        await page.locator("#" + k).fill(v)
    await page.locator("#state").select_option("Karnataka")
    await page.locator("#city").select_option("Bengaluru")
    await page.get_by_role("button", name="Continue to payment →").click()
    assert await page.locator("#payment-page").is_visible()


async def test_unavailable_not_failure(server):
    async with httpx.AsyncClient() as c:
        r = await c.post(
            server + "/api/batches",
            json={"models": ["openai/gpt-6-astra"], "scenarios": ["T01"], "repeats": 1},
        )
        assert r.status_code == 200
        for _ in range(50):
            st = (await c.get(server + "/api/state")).json()
            if not st["running"]:
                break
            await asyncio.sleep(0.1)
        assert st["current"]["status"] == "unavailable"
        assert not st["current"]["success"]
        board = (await c.get(server + "/api/results")).json()["leaderboard"]
        assert all(b["model"] != "openai/gpt-6-astra" for b in board)


async def test_pause_resume_stop(server):
    async with httpx.AsyncClient() as c:
        r = await c.post(
            server + "/api/batches",
            json={"models": ["reference"], "scenarios": ["T15"], "repeats": 10},
        )
        assert r.status_code == 200
        await c.post(server + "/api/control/pause")
        await asyncio.sleep(0.5)
        first = (await c.get(server + "/api/state")).json()
        await asyncio.sleep(0.5)
        second = (await c.get(server + "/api/state")).json()
        assert (
            second["paused"]
            and second["batch"]["finished"] == first["batch"]["finished"]
        )
        await c.post(server + "/api/control/resume")
        for _ in range(40):
            st = (await c.get(server + "/api/state")).json()
            if st.get("current"):
                break
            await asyncio.sleep(0.1)
        await c.post(server + "/api/control/stop")
        for _ in range(60):
            st = (await c.get(server + "/api/state")).json()
            if not st["running"]:
                break
            await asyncio.sleep(0.1)
        assert st["batch"]["status"] == "stopped" and st["batch"]["finished"] < 10
