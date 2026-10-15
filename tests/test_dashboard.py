"""AI-first UI journey and analysis checks. Model starts are intercepted, never inferred."""

import json
import re
import httpx
import pytest
from playwright.async_api import expect
from tests.ui_fixtures import install_ui_data, IDS


async def nav(page, slug):
    await page.evaluate('(slug)=>{location.hash="/"+slug}', slug)


async def test_overview_and_central_visibility_policy(server, page):
    mock = await install_ui_data(page, server)
    await page.goto(server)
    await expect(
        page.get_by_role("button", name="Start Benchmark →", exact=True)
    ).to_have_count(1)
    await expect(
        page.get_by_role(
            "button",
            name=re.compile(
                "software check|Run reference|Validate this scenario", re.I
            ),
        )
    ).to_have_count(0)
    await expect(page.get_by_text("hidden-frontier", exact=True)).to_have_count(0)
    await page.get_by_role("button", name="Start Benchmark →", exact=True).click()
    await expect(page.get_by_role("heading", name="Models", exact=True)).to_be_visible()
    await expect(page.locator(".model-card")).to_have_count(5)
    await expect(
        page.get_by_text("Configured · inference unverified", exact=True)
    ).to_have_count(4)
    await expect(page.get_by_text("Inference verified", exact=True)).to_have_count(0)
    for name in [
        "GPT-6",
        "Claude",
        "Hidden Direct Frontier",
        "Deterministic reference",
    ]:
        await expect(page.get_by_text(name, exact=False)).to_have_count(0)
    await page.get_by_label("Search specialist configurations").fill("GPT")
    await expect(page.locator(".model-card")).to_have_count(0)
    assert not mock["posted"]


async def test_setup_persists_and_start_requires_explicit_confirmation(server, page):
    mock = await install_ui_data(page, server)
    await page.goto(server + "/#/models")
    await page.get_by_role(
        "checkbox", name="CUA-S1-Forms + Playwright", exact=True
    ).check()
    await page.get_by_role("button", name="Continue to Scenarios →").click()
    await expect(
        page.get_by_role("heading", name="Scenarios", exact=True)
    ).to_be_visible()
    await expect(page.locator(".model-card")).to_have_count(0)
    await page.get_by_role("button", name="Quick benchmark · 5").click()
    await page.get_by_role("button", name="Continue to Review →").click()
    await expect(
        page.get_by_role("heading", name="Review & Run", exact=True)
    ).to_be_visible()
    await page.get_by_label("Repetitions per scenario", exact=True).fill("1")
    await page.reload()
    await expect(
        page.get_by_label("Repetitions per scenario", exact=True)
    ).to_have_value("1")
    await expect(page.get_by_text("5 planned evaluations", exact=False)).to_be_visible()
    assert not mock["posted"]
    await page.get_by_role("button", name="Start Benchmark →", exact=True).click()
    await expect(
        page.get_by_role("dialog", name="Confirm benchmark start")
    ).to_be_visible()
    assert not mock["posted"]
    await page.get_by_role("button", name="Cancel", exact=True).click()
    await page.get_by_role("button", name="Start Benchmark →", exact=True).click()
    await page.get_by_role("button", name="Confirm and start", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Live Benchmark", exact=True)
    ).to_be_visible()
    await expect(page.get_by_role("progressbar", name="Batch progress")).to_be_visible()
    assert len(mock["posted"]) == 1
    assert mock["posted"][0]["models"] == ["cua-s1"]
    assert len(mock["posted"][0]["scenarios"]) == 5
    await page.reload()
    await expect(
        page.get_by_role("heading", name="Live Benchmark", exact=True)
    ).to_be_visible()
    assert len(mock["posted"]) == 1
    await page.get_by_role("button", name="Pause", exact=True).click()
    await expect(page.get_by_role("button", name="Resume", exact=True)).to_be_visible(
        timeout=10000
    )
    await page.get_by_role("button", name="Resume", exact=True).click()
    await expect(page.get_by_role("button", name="Pause", exact=True)).to_be_visible(
        timeout=10000
    )
    await page.get_by_role("button", name="Stop benchmark", exact=True).click()
    await expect(
        page.get_by_role("button", name="View Results →", exact=True)
    ).to_be_visible(timeout=10000)
    assert len(mock["posted"]) == 1


async def test_unavailable_and_historical_review_safeguards(server, page):
    mock = await install_ui_data(page, server)
    await page.goto(server + "/#/models")
    await page.get_by_role("checkbox", name="UI-Venus-1.5-2B", exact=True).check()
    await page.get_by_role("button", name="Continue to Scenarios →").click()
    await page.get_by_role("button", name="Quick benchmark · 5").click()
    await page.get_by_role("button", name="Continue to Review →").click()
    await expect(
        page.get_by_role("button", name="Start Benchmark →", exact=True)
    ).to_be_disabled()
    await expect(
        page.get_by_text("Checkpoint weights are not configured.", exact=False)
    ).to_be_visible()
    await nav(page, "models")
    await page.get_by_role("checkbox", name="UI-Venus-1.5-2B", exact=True).uncheck()
    await page.get_by_role(
        "checkbox", name="CUA-S1-Forms + Playwright", exact=True
    ).check()
    await nav(page, "scenarios")
    await page.get_by_role("button", name="Filters & versions").click()
    await page.get_by_label("Advanced: benchmark version").select_option("2.0")
    await page.get_by_role("button", name="Full suite · 56", exact=True).click()
    await page.get_by_role("button", name="Continue to Review →").click()
    await expect(
        page.get_by_role("button", name="Start Benchmark →", exact=True)
    ).to_be_disabled()
    await expect(
        page.get_by_text("Historical suites are preview-only", exact=False)
    ).to_be_visible()
    assert not mock["posted"]


async def test_scenario_filters_and_independent_preview(server, page):
    mock = await install_ui_data(page, server)
    await page.goto(server + "/#/scenarios")
    await page.get_by_role("button", name="Filters & versions").click()
    await page.get_by_label("Environment", exact=True).select_option("razor")
    await page.get_by_label("Device", exact=True).select_option("mobile_web")
    await page.get_by_label("Payment method", exact=True).select_option("upi_app")
    rows = page.locator(".scenario-list article")
    await expect(rows).not_to_have_count(0)
    await rows.first.get_by_role("button", name="Preview", exact=True).click()
    await expect(page.get_by_role("dialog")).to_be_visible()
    await expect(page.get_by_title("Checkout preview")).to_be_visible()
    await page.get_by_role("tab", name="Customer profile", exact=True).click()
    await expect(page.locator(".modal pre")).to_contain_text("customer")
    await page.get_by_role("tab", name="Task & challenges", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Success condition", exact=True)
    ).to_be_visible()
    assert not mock["posted"]


async def test_results_scoping_comparison_and_scenario_analysis(server, page):
    fixture = await install_ui_data(page, server)
    await page.goto(server + "/#/results")
    summary = page.locator(".summary-workspace")
    await expect(summary.get_by_text("66.7%", exact=True).first).to_be_visible()
    await expect(
        summary.get_by_text("8 successful / 12 scored runs", exact=True)
    ).to_be_visible()
    await page.get_by_role("button", name="Metrics Explained").click()
    await expect(
        page.get_by_role("heading", name="Confidence interval", exact=True)
    ).to_be_visible()
    await page.get_by_role("button", name="Close dialog").click()
    await page.get_by_role("tab", name="Model Comparison", exact=True).click()
    await expect(
        page.get_by_text("CUA-S1 has the highest observed success rate", exact=False)
    ).to_be_visible()
    await page.get_by_role("button", name="Filter runs", exact=True).click()
    await page.get_by_label("Results environment", exact=True).select_option("generic")
    await expect(
        page.get_by_text("No overall winner is inferred.", exact=False)
    ).to_be_visible()
    await page.get_by_role("tab", name="Scenario Analysis", exact=True).click()
    await expect(page.get_by_role("cell", name=re.compile("V21-G02"))).to_be_visible()
    await expect(page.get_by_role("cell", name=re.compile("V21-S01"))).to_have_count(0)
    await page.get_by_role("button", name="Analyse", exact=True).click()
    await expect(
        page.get_by_role("heading", name="V21-G02 · performance across systems")
    ).to_be_visible()
    # Infrastructure attempts can incur costs without entering scored denominators.
    blocked = {
        **fixture["runs"][0],
        "id": "ui-blocked-cost",
        "status": "blocked",
        "success": False,
        "cost": 0.005,
    }
    fixture["runs"].append(blocked)
    await page.reload()
    await expect(
        summary.get_by_text("8 successful / 12 scored runs", exact=True)
    ).to_be_visible()
    expenditure = summary.locator(".stat").filter(
        has=page.get_by_text("Inference expenditure", exact=True)
    )
    await expect(expenditure).to_contain_text("$0.0170")
    blocked["cost_kind"] = "not_reported"
    await page.reload()
    await expect(expenditure).to_contain_text("Not reported")
    await page.get_by_role("tab", name="Summary", exact=True).focus()
    await page.keyboard.press("ArrowRight")
    await expect(
        page.get_by_role("tab", name="Model Comparison", exact=True)
    ).to_have_attribute("aria-selected", "true")


async def test_run_explorer_evidence_missing_metrics_and_exports(
    server, page, tmp_path
):
    fixture = await install_ui_data(page, server)
    await page.goto(server + "/#/results")
    await page.get_by_role("tab", name="Run Explorer", exact=True).click()
    await page.get_by_label("Scenario cohort / conditions").select_option("all")
    await page.get_by_label("Results version").select_option("all")
    async with page.expect_download() as got:
        await page.get_by_role("button", name="Export all specialist runs JSON").click()
    downloaded = await got.value
    target = tmp_path / "all.json"
    await downloaded.save_as(target)
    data = json.loads(target.read_text())
    assert len(data["runs"]) == 14
    assert all(
        r["model"] in IDS and not r["id"].startswith("hidden") for r in data["runs"]
    )
    await page.get_by_label("Search run records").fill("ui-cua-s1-0")
    async with page.expect_download() as got:
        await page.get_by_role("button", name="Export filtered summaries CSV").click()
    downloaded = await got.value
    target = tmp_path / "filtered.csv"
    await downloaded.save_as(target)
    assert len(target.read_text().splitlines()) == 2
    await page.get_by_role("button", name="Open run ui-cua-s1-0", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Run Details", exact=True)
    ).to_be_visible()
    await page.get_by_role("tab", name="Action timeline", exact=True).click()
    await expect(page.get_by_text("Result: typed", exact=True)).to_be_visible()
    await page.get_by_role("tab", name="Visual replay", exact=True).click()
    await expect(
        page.get_by_role("img", name=re.compile("Browser evidence"))
    ).to_have_attribute("src", re.compile("action-0.png"))
    await page.get_by_role("button", name="Next action", exact=True).click()
    await expect(
        page.get_by_role("img", name=re.compile("Browser evidence"))
    ).to_have_attribute("src", re.compile("action-1.png"))
    await page.get_by_role("tab", name="Fields", exact=True).click()
    await expect(page.get_by_role("cell", name="Required", exact=True)).to_have_count(2)
    await page.get_by_role("tab", name="Payment & authentication", exact=True).click()
    await expect(
        page.locator(".facts > div").filter(
            has=page.get_by_text("Actual selected method", exact=True)
        )
    ).to_contain_text("Not reported")
    await page.get_by_role("tab", name="Performance", exact=True).click()
    await expect(
        page.locator(".facts > div").filter(
            has=page.get_by_text("Model calls", exact=True)
        )
    ).to_contain_text("1")
    await expect(
        page.locator(".facts > div").filter(
            has=page.get_by_text("Artifact storage", exact=True)
        )
    ).to_contain_text("Not reported")
    async with page.expect_download() as got:
        await page.get_by_role("button", name="Individual run JSON").click()
    downloaded = await got.value
    target = tmp_path / "run.json"
    await downloaded.save_as(target)
    assert json.loads(target.read_text()) == fixture["runs"][0]


async def test_hidden_run_deep_link_and_saved_model_ids_are_sanitised(server, page):
    await install_ui_data(page, server)
    await page.add_init_script(
        "localStorage.setItem('checkoutbench.setup.v2.2',JSON.stringify({models:['reference','openai/gpt-6-astra','cua-s1'],scenarios:['V21-S01']}))"
    )
    await page.goto(server + "/#/models")
    await expect(page.get_by_role("checkbox", checked=True)).to_have_count(1)
    await nav(page, "results/hidden-frontier")
    await expect(
        page.get_by_role("heading", name="Run unavailable in this workspace")
    ).to_be_visible()
    await expect(page.get_by_text("GPT-6", exact=False)).to_have_count(0)


@pytest.mark.parametrize("width,height", [(1440, 900), (1280, 800), (390, 844)])
async def test_pages_have_purpose_and_fit_responsive_viewports(
    server, page, width, height
):
    fixture = await install_ui_data(page, server)
    live = {**fixture["runs"][0], "status": "running", "action_count": 100}
    live["events"] = [{**live["events"][0], "index": i} for i in range(100)]
    fixture["state"].update(
        running=True,
        current=live,
        batch={"finished": 0, "total": 1, "config": {"models": ["cua-s1"]}},
    )
    await page.set_viewport_size({"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(server)
    for slug in [
        "overview",
        "models",
        "scenarios",
        "review",
        "live",
        "results",
        "coverage",
    ]:
        await nav(page, slug)
        await expect(page.locator("h1")).to_be_visible()
        assert await page.locator(".page-title p").inner_text()
        assert not await page.evaluate(
            "document.documentElement.scrollWidth>innerWidth+2"
        ), slug
        if slug == "live":
            history = page.locator(".action-history")
            assert await history.evaluate("el => el.scrollHeight > el.clientHeight"), (
                "Long action histories must scroll internally"
            )
        if slug == "models":
            for card in await page.locator(".model-card").all():
                assert await card.evaluate(
                    "(el)=>el.scrollHeight<=el.clientHeight+2"
                ), "Model card content must remain within its own card"
        if slug == "scenarios" and width <= 760:
            assert await page.evaluate("document.documentElement.scrollHeight<2500"), (
                "Scenario collection must be contained on mobile"
            )
        if width > 760:
            assert not await page.evaluate(
                "document.documentElement.scrollHeight>innerHeight+2"
            ), slug
            if slug in ["models", "scenarios", "review"]:
                box = await page.locator(".step-footer").bounding_box()
                assert box["y"] + box["height"] <= height + 2
    assert not errors


def test_hidden_frontier_and_reference_backend_catalogue_still_available(server):
    rows = httpx.get(server + "/api/models").json()["models"]
    assert any(r["id"] == "reference" for r in rows)
    assert sum(r["kind"] == "openrouter" for r in rows) >= 6
    assert {r["id"] for r in rows if r["kind"] == "specialist"} == set(IDS)
