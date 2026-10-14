"""Capture the six dashboard sections without starting benchmark/model runs."""

import argparse, asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--output", default="docs/ui/screenshots")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for width, height in [(1440, 1000), (390, 844)]:
            page = await browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto(args.url)
            await page.get_by_role(
                "button", name="Set up all v2.1 checks", exact=True
            ).wait_for()
            for section in [
                "Overview",
                "Models",
                "Scenarios",
                "Coverage",
                "Live session",
                "Results",
            ]:
                await (
                    page.locator("nav")
                    .get_by_role("button", name=section, exact=False)
                    .click()
                )
                await page.wait_for_timeout(350)
                for element in await page.locator("iframe").all():
                    await element.scroll_into_view_if_needed()
                    frame = await (await element.element_handle()).content_frame()
                    await frame.locator("#workflow").wait_for()
                    await page.wait_for_timeout(150)
                overflow = await page.evaluate(
                    "document.documentElement.scrollWidth>innerWidth+2"
                )
                name = f"{section.lower().replace(' ', '-')}-{width}.png"
                await page.screenshot(path=str(out / name), full_page=True)
                reports.append(
                    {
                        "section": section,
                        "viewport": {"width": width, "height": height},
                        "document_overflow": overflow,
                        "javascript_errors": list(errors),
                        "screenshot": name,
                    }
                )
            await page.close()
        await browser.close()
    (out / "inspection.json").write_text(json.dumps(reports, indent=2) + "\n")
    summary = {
        "screenshots": len(reports),
        "document_overflows": sum(r["document_overflow"] for r in reports),
        "javascript_errors": sum(len(r["javascript_errors"]) for r in reports),
    }
    print(json.dumps(summary))
    if summary["document_overflows"] or summary["javascript_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
