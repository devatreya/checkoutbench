"""Capture v2.2 pages and labelled synthetic analysis states, without inference."""

import argparse
import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.async_api import async_playwright
from tests.ui_fixtures import install_ui_data, sample_runs


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--output", default="docs/v2.2/screenshots")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for width, height in [(1440, 900), (1280, 800), (390, 844)]:
            for synthetic in [False, True]:
                page = await browser.new_page(
                    viewport={"width": width, "height": height}
                )
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                if synthetic:
                    fixture = await install_ui_data(page, args.url)
                    run = copy.deepcopy(sample_runs()[0])
                    run.update(
                        status="running",
                        timestamp=(
                            datetime.now(timezone.utc) - timedelta(seconds=12)
                        ).isoformat(),
                    )
                    fixture["state"].update(
                        running=True,
                        current=run,
                        batch={
                            "finished": 1,
                            "total": 6,
                            "config": {"models": ["cua-s1", "tinyclick"]},
                        },
                    )
                await page.add_init_script(
                    "localStorage.setItem('checkoutbench.setup.v2.2',JSON.stringify({models:['cua-s1','tinyclick'],scenarios:['V21-S01','V21-G02'],repeats:3}))"
                )
                await page.goto(args.url)
                await page.get_by_role(
                    "button", name="Start Benchmark →", exact=True
                ).wait_for()
                if synthetic:
                    await page.evaluate(
                        """() => { const banner=document.createElement('div'); banner.textContent='UI TEST DATA · no model evaluation'; Object.assign(banner.style,{position:'fixed',right:'8px',top:'3px',zIndex:'1000',fontSize:'10px',padding:'3px 6px',background:'#ffe7a8',color:'#42310b',borderRadius:'4px'});document.body.append(banner); }"""
                    )

                async def capture(name):
                    await page.wait_for_timeout(200)
                    await page.evaluate("document.fonts.ready")
                    dimensions = await page.evaluate(
                        "({horizontal:document.documentElement.scrollWidth>innerWidth+2,vertical:document.documentElement.scrollHeight>innerHeight+2})"
                    )
                    filename = f"{'fixture-' if synthetic else ''}{name}-{width}.png"
                    await page.screenshot(path=str(out / filename), full_page=True)
                    reports.append(
                        dict(
                            page=name,
                            synthetic_ui_data=synthetic,
                            viewport={"width": width, "height": height},
                            document_horizontal_overflow=dimensions["horizontal"],
                            desktop_document_scroll=width > 760
                            and dimensions["vertical"],
                            javascript_errors=list(errors),
                            screenshot=filename,
                        )
                    )

                async def nav(slug):
                    await page.evaluate('(s)=>{location.hash="/"+s}', slug)
                    await page.wait_for_timeout(100)

                if not synthetic:
                    for slug in [
                        "overview",
                        "models",
                        "scenarios",
                        "review",
                        "live",
                        "results",
                        "coverage",
                    ]:
                        await nav(slug)
                        await capture(slug)
                else:
                    for slug in ["review", "live"]:
                        await nav(slug)
                        await capture(slug)
                    await nav("results")
                    for title in [
                        "Summary",
                        "Model Comparison",
                        "Scenario Analysis",
                        "Run Explorer",
                    ]:
                        await page.get_by_role("tab", name=title, exact=True).click()
                        await capture("results-" + title.lower().replace(" ", "-"))
                    await nav("results/ui-cua-s1-0")
                    for title in [
                        "Outcome",
                        "Action timeline",
                        "Visual replay",
                        "Fields",
                        "Payment & authentication",
                        "Performance",
                    ]:
                        await page.get_by_role("tab", name=title, exact=True).click()
                        await capture(
                            "detail-"
                            + title.lower().replace(" & ", "-").replace(" ", "-")
                        )
                await page.close()
        await browser.close()
    (out / "inspection.json").write_text(json.dumps(reports, indent=2) + "\n")
    summary = dict(
        screenshots=len(reports),
        horizontal_overflows=sum(r["document_horizontal_overflow"] for r in reports),
        desktop_scrolls=sum(r["desktop_document_scroll"] for r in reports),
        javascript_errors=sum(len(r["javascript_errors"]) for r in reports),
    )
    print(json.dumps(summary))
    if any(
        summary[k]
        for k in ["horizontal_overflows", "desktop_scrolls", "javascript_errors"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
