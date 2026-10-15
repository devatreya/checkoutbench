"""Capture actual v3 UI; no injected performance data or inference."""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    out = Path("docs/research/screenshots")
    out.mkdir(exist_ok=True)
    reports = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for width, height in [(1440, 900), (1280, 800), (390, 844)]:
            page = await browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto("http://127.0.0.1:8000")
            await page.get_by_role(
                "button", name="Start Benchmark →", exact=True
            ).wait_for()

            async def shot(name):
                await page.wait_for_timeout(250)
                filename = f"{name}-{width}.png"
                await page.screenshot(path=str(out / filename), full_page=True)
                dimensions = await page.evaluate(
                    "({horizontal:document.documentElement.scrollWidth>innerWidth+2,vertical:document.documentElement.scrollHeight>innerHeight+2})"
                )
                reports.append(
                    {
                        "page": name,
                        "width": width,
                        "height": height,
                        "horizontal_overflow": dimensions["horizontal"],
                        "desktop_document_scroll": width > 760
                        and dimensions["vertical"],
                        "javascript_errors": list(errors),
                        "screenshot": filename,
                    }
                )

            for slug in ("overview", "models", "scenarios", "review", "results"):
                await page.evaluate('(s)=>location.hash="/"+s', slug)
                await shot(slug)
            await page.get_by_role(
                "tab", name="Payment & Stage Analysis", exact=True
            ).click()
            for name in (
                "Payment Method Ranking",
                "Checkout Funnel",
                "Failure Breakdown",
                "Vendor × Payment Method",
            ):
                await page.get_by_role("tab", name=name, exact=True).click()
                await shot(name.lower().replace(" ", "-").replace("×", "by"))
            await page.close()
        await browser.close()
    (out / "report.json").write_text(json.dumps(reports, indent=2) + "\n")
    assert not any(
        r["horizontal_overflow"]
        or r["desktop_document_scroll"]
        or r["javascript_errors"]
        for r in reports
    ), reports
    print(f"{len(reports)} real UI captures passed layout and JavaScript checks")


if __name__ == "__main__":
    asyncio.run(main())
