"""Fixture solvability checks: reference execution, never AI ranking evidence."""

from scenarios.research import IMPLEMENTATIONS
from tests.test_v2 import run_batch


async def test_independent_clients_have_working_card_and_qr_paths(server):
    ids = [
        f"V3-I-{impl}-{method}"
        for impl, _, _ in IMPLEMENTATIONS
        for method in ("card", "upi_qr", "netbanking", "cod")
    ]
    rows = await run_batch(server, ids, timeout=35)
    assert len(rows) == len(ids)
    assert all(r["success"] for r in rows), [
        (
            r["scenario"],
            r.get("error"),
            r.get("failure_reason"),
            r.get("completion_stage"),
        )
        for r in rows
        if not r["success"]
    ]
    assert all(r["checkout_prepared"] and len(r["checkout_stages"]) == 13 for r in rows)
    assert all(r["scoring_version"] == "3.0" for r in rows)


async def test_controlled_qr_and_auth_matrices_browser_paths(server):
    from scenarios.research import SPECS

    ids = [s["id"] for s in SPECS if s["design"] in ("qr", "auth")]
    rows = await run_batch(server, ids, timeout=35)
    assert all(r["task_resolved_correctly"] for r in rows), [
        (
            r["scenario"],
            r.get("error"),
            r.get("failure_reason"),
            r.get("completion_stage"),
        )
        for r in rows
        if not r["task_resolved_correctly"]
    ]
    for r in rows:
        if r["scenario"].startswith("V3-QR") and r["qr_research"]["initially_usable"]:
            assert r["qr_recovery_accuracy"] is None


async def test_layout_pairs_are_solvable_with_private_test_oracle(server, page):
    """Fixture validation, not a model/controller performance measurement."""
    import httpx, asyncio
    from scenarios.research import SPECS, scenario_research

    for spec in (x for x in SPECS if x["design"] == "layout"):
        s = scenario_research(spec["id"])
        async with httpx.AsyncClient() as client:
            preview = (await client.post(server + "/api/preview/" + s["id"])).json()
        await page.set_viewport_size(s["viewport"])
        await page.goto(preview["url"])
        await page.wait_for_timeout(100)
        for _ in range(14):
            for frame in list(page.frames):
                for key, value in s["expected_values"].items():
                    if frame.is_detached():
                        break
                    handle = s["dom_ids"].get(key)
                    if not handle:
                        continue
                    loc = frame.locator("#" + handle)
                    if not await loc.count() or not await loc.first.is_visible():
                        continue
                    loc = loc.first
                    tag = await loc.evaluate("(e)=>e.tagName")
                    kind = await loc.get_attribute("type")
                    if tag == "SELECT":
                        if await loc.input_value() != str(value):
                            await loc.select_option(value=str(value))
                    elif kind == "checkbox":
                        await loc.set_checked(
                            str(value).lower() in ("true", "yes", "1")
                        )
                    elif tag in (
                        "INPUT",
                        "TEXTAREA",
                    ) and await loc.input_value() != str(value):
                        await loc.fill(str(value))
                        await loc.blur()
            for text in (
                "Continue to shipping",
                "Continue to payment",
                "Review details",
                "Confirm review and continue",
                "Prepare selected payment",
            ):
                button = page.get_by_role("button", name=text, exact=True)
                if await button.count() and await button.first.is_visible():
                    await button.first.click()
                    break
            await page.wait_for_timeout(100)
            if "Checkout ready" in await page.locator("body").inner_text():
                break
        assert "Checkout ready" in await page.locator("body").inner_text(), s["id"]
