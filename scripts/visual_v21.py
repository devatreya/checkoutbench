"""Versioned source-fidelity screenshots. Synthetic previews only; no model inference."""

import argparse, asyncio, json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright
from backend.browser.v21 import semantic_value


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--output", default="docs/v2.1/screenshots")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30) as client, async_playwright() as pw:
        catalog = (await client.get(args.url + "/api/scenarios")).json()
        variants = {}
        for s in catalog:
            if s["benchmark_version"] == "2.1":
                variants.setdefault((s["family"], s["variant"]), s["id"])
        browser = await pw.chromium.launch()
        reports = []
        for viewport in ({"width": 1280, "height": 900}, {"width": 390, "height": 844}):
            page = await browser.new_page(viewport=viewport)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for (family, variant), sid in variants.items():
                preview = (await client.post(args.url + "/api/preview/" + sid)).json()
                before = len(errors)
                await page.goto(preview["url"])
                await page.locator("#workflow").wait_for()
                for element in await page.locator("iframe").all():
                    frame = await (await element.element_handle()).content_frame()
                    await frame.locator("#workflow,#extension .field").first.wait_for()
                for element in await page.locator("iframe").all():
                    await element.scroll_into_view_if_needed()
                    await page.wait_for_timeout(100)
                await page.wait_for_timeout(250)
                name = f"{family}-{variant}-{viewport['width']}.png"
                await page.screenshot(path=str(out / name), full_page=True)
                reports.append(
                    dict(
                        scenario=sid,
                        viewport=viewport,
                        screenshot=name,
                        stage="initial",
                        errors=errors[before:],
                        document_overflow=await page.evaluate(
                            "document.documentElement.scrollWidth>innerWidth+2"
                        ),
                    )
                )
                if sid in ("V21-RZ01", "V21-CF01", "V21-CF02", "V21-CF03", "V21-ST03"):
                    base = (
                        preview["url"].split("/checkout/")[0]
                        + "/v21/"
                        + preview["token"]
                    )
                    d = (await client.get(base + "/state")).json()
                    vals = {
                        f["key"]: semantic_value(f["label"], preview["task"]["profile"])
                        for f in d["fields"]
                    }
                    await client.post(
                        base + "/action",
                        json={
                            "action": "continue",
                            "values": {k: v for k, v in vals.items() if v is not None},
                        },
                    )
                    await client.post(
                        base + "/action", json={"action": "review", "values": {}}
                    )
                    await page.reload()
                    active = page
                    if sid == "V21-CF02":
                        async with page.expect_popup() as pop:
                            await page.get_by_role(
                                "button", name="Launch payment gateway"
                            ).click()
                        active = await pop.value
                        await active.wait_for_load_state()
                        await active.set_viewport_size(viewport)
                    elif sid != "V21-ST03":
                        await page.get_by_role(
                            "button", name="Launch payment gateway"
                        ).click()
                    await active.wait_for_timeout(400)
                    for frame in active.frames:
                        radio = frame.get_by_role("radio", name="Card", exact=True)
                        if await radio.count():
                            await radio.click()
                            break
                    await active.wait_for_timeout(250)
                    name = f"{family}-{variant}-payment-{viewport['width']}.png"
                    await active.screenshot(path=str(out / name), full_page=True)
                    reports.append(
                        dict(
                            scenario=sid,
                            viewport=viewport,
                            screenshot=name,
                            stage="payment",
                            errors=errors[before:],
                            document_overflow=await active.evaluate(
                                "document.documentElement.scrollWidth>innerWidth+2"
                            ),
                        )
                    )
                    if active != page:
                        await active.close()
            await page.close()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        await page.goto(args.url + "/#/coverage")
        await page.get_by_role(
            "heading", name="Coverage & Sources", exact=True
        ).wait_for()
        await page.screenshot(path=str(out / "coverage-desktop.png"), full_page=True)
        await browser.close()
        (out / "inspection.json").write_text(json.dumps(reports, indent=2))
        print(
            json.dumps(
                dict(
                    screenshots=len(reports),
                    javascript_errors=sum(bool(r["errors"]) for r in reports),
                    document_overflows=sum(r["document_overflow"] for r in reports),
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
