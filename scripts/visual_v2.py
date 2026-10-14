"""Capture every distinct fixture variant at both viewports; no inference or external traffic."""

import argparse, asyncio, json
from pathlib import Path
import httpx
from playwright.async_api import async_playwright


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="docs/v2/screenshots")
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30) as c, async_playwright() as pw:
        scenarios = (await c.get(args.url + "/api/scenarios")).json()
        variants = {}
        for s in scenarios:
            variants.setdefault((s["family"], s["variant"]), s["id"])
        browser = await pw.chromium.launch()
        reports = []
        for viewport in [dict(width=1280, height=900), dict(width=390, height=844)]:
            page = await browser.new_page(viewport=viewport)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for (family, variant), sid in variants.items():
                info = (await c.post(args.url + "/api/preview/" + sid)).json()
                before = len(errors)
                await page.goto(info["url"])
                await page.locator("#workflow,#shipping").first.wait_for()
                await page.wait_for_timeout(250)
                name = f"{family}-{variant}-{viewport['width']}.png"
                await page.screenshot(path=str(out / name), full_page=True)
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth > innerWidth + 2"
                )
                reports.append(
                    dict(
                        scenario=sid,
                        family=family,
                        variant=variant,
                        viewport=viewport,
                        screenshot=name,
                        document_overflow=overflow,
                        errors=errors[before:],
                    )
                )
            await page.close()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        await page.goto(args.url)
        await page.get_by_role("button", name="Coverage", exact=True).click()
        await page.get_by_role(
            "heading", name="Scenario coverage", exact=True
        ).wait_for()
        await page.screenshot(path=str(out / "coverage-desktop.png"), full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.locator(".coverage-preview").scroll_into_view_if_needed()
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(out / "coverage-mobile.png"), full_page=True)
        await browser.close()
        (out / "inspection.json").write_text(json.dumps(reports, indent=2))
        print(
            f"{len(reports)} fixture screenshots; {sum(bool(r['errors']) for r in reports)} JS errors; {sum(r['document_overflow'] for r in reports)} document overflow reports"
        )


if __name__ == "__main__":
    asyncio.run(main())
