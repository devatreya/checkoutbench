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
        page.get_by_role("heading", name="Benchmark Coverage", exact=True)
    ).to_be_visible()
    await expect(page.locator(".model-card")).to_have_count(0)
    await page.get_by_role("button", name="Continue to Review →").click()
    await expect(
        page.get_by_role("heading", name="Review & Run", exact=True)
    ).to_be_visible()
    await page.get_by_label("Repetitions per scenario", exact=True).fill("1")
    await page.reload()
    await expect(
        page.get_by_label("Repetitions per scenario", exact=True)
    ).to_have_value("1")
    await expect(page.get_by_text("174 planned evaluations", exact=False)).to_be_visible()
    assert not mock["posted"]
    await page.get_by_role("button", name="Run All →", exact=True).click()
    await expect(
        page.get_by_role("dialog", name="Confirm benchmark start")
    ).to_be_visible()
    assert not mock["posted"]
    await page.get_by_role("button", name="Cancel", exact=True).click()
    await page.get_by_role("button", name="Run All →", exact=True).click()
    await page.get_by_role("button", name="Confirm and start", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Live Benchmark", exact=True)
    ).to_be_visible()
    await expect(page.get_by_role("progressbar", name="Batch progress")).to_be_visible()
    assert len(mock["posted"]) == 1
    assert mock["posted"][0]["models"] == ["cua-s1"]
    assert len(mock["posted"][0]["scenarios"]) == 174
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
    await page.get_by_role("button", name="Continue to Review →").click()
    await expect(
        page.get_by_role("button", name="Run All →", exact=True)
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
    await expect(page.get_by_role("checkbox")).to_have_count(0)
    assert not mock["posted"]


async def test_coverage_is_frozen_and_no_scenario_selection(server,page):
    mock=await install_ui_data(page,server)
    await page.goto(server+'/#/scenarios')
    await expect(page.get_by_role('heading',name='Benchmark Coverage',exact=True)).to_be_visible()
    await expect(page.get_by_role('checkbox')).to_have_count(0)
    await expect(page.get_by_role('button',name=re.compile('Quick benchmark|Full suite|Select all'))).to_have_count(0)
    await expect(page.get_by_text('Frozen active tasks',exact=True)).to_be_visible()
    await expect(page.get_by_text('174',exact=True)).to_be_visible()
    assert not mock['posted']


async def test_scenario_identity_is_public_across_coverage_and_results(server, page):
    await install_ui_data(page, server)
    await page.goto(server + "/#/scenarios")
    await page.get_by_text("Browse scenario IDs and tasks", exact=True).click()
    await expect(page.get_by_role("cell", name="GENERIC-01", exact=True)).to_be_visible()
    await expect(page.get_by_role("cell", name="STRIPE-03", exact=True)).to_be_visible()
    await expect(page.locator("body")).not_to_contain_text("V3-G01")
    await expect(page.get_by_text("No real transaction occurs.", exact=False).first).to_be_visible()
    await nav(page, "results")
    await page.get_by_role("tab", name="Run Explorer", exact=True).click()
    await page.get_by_label("Search run records").fill("GENERIC-02")
    await expect(page.get_by_role("button", name="Open run ui-cua-s1-1", exact=True)).to_be_visible()
    await expect(page.get_by_role("button", name="Open run ui-cua-s1-0", exact=True)).to_have_count(0)
    await expect(page.locator("body")).not_to_contain_text("V3-G02")
    await page.get_by_role("button", name="Open run ui-cua-s1-1", exact=True).click()
    await expect(page.locator(".facts").first).to_contain_text("GENERIC-02")
    await expect(page.locator(".facts").first).not_to_contain_text("V3-G02")


async def test_real_scenario_api_and_browser_preview_use_public_identity(server, page):
    # No API route mocks: verify the actual registry overlay reaches the app.
    response = httpx.get(server + "/api/scenarios")
    response.raise_for_status()
    rows = response.json()
    stripe = next(row for row in rows if row["id"] == "V3-ST03")
    assert stripe["canonical_id"] == "V3-ST03"
    assert stripe["public_id"] == "STRIPE-03"
    assert "inspired" in stripe["display_name"]
    await page.goto(server + "/#/coverage")
    await expect(page.get_by_text("SHOPIFY-01", exact=True)).to_be_visible()
    await expect(page.locator("body")).not_to_contain_text("V3-S01")
    await page.get_by_role("button", name="Preview checkout", exact=True).click()
    await expect(page.get_by_role("dialog", name="SHOPIFY-01 · Preview")).to_be_visible()
    await expect(page.locator(".checkout-frame")).to_be_visible()


async def test_run_details_distinguish_track_quantization_and_failure_type(server, page):
    fixture = await install_ui_data(page, server)
    fixture["runs"][0].update(
        model="ui-venus", observation_track="screenshot_gui",
        outcome_category="infrastructure_failure",
        inference_configuration={
            "backend": "mlx-vlm-local-worker", "precision": "affine-6bit-group64-mixed-bf16",
            "quantization": {"bits": 6, "mode": "affine", "group_size": 64},
            "artifact_id": "synthetic-ui-fixture", "checkpoint_revision": "test-revision",
        },
    )
    await page.goto(server + "/#/results/ui-cua-s1-0")
    await expect(page.locator(".facts").first).to_contain_text("Screenshot-only GUI actions")
    await expect(page.locator(".facts").first).to_contain_text("infrastructure failure")
    await page.get_by_role("tab", name="Performance", exact=True).click()
    await expect(page.get_by_text("6-bit quantized weights", exact=False)).to_be_visible()
    await expect(page.get_by_text("mlx-vlm-local-worker", exact=True)).to_be_visible()
    await expect(page.get_by_text("affine-6bit-group64-mixed-bf16", exact=True)).to_be_visible()


async def test_results_scoping_comparison_and_scenario_analysis(server, page):
    fixture = await install_ui_data(page, server)
    await page.goto(server + "/#/results")
    for label in ("Results version", "Research protocol", "Scenario cohort / conditions"):
        await expect(page.get_by_label(label, exact=True)).to_have_count(0)
    await expect(page.get_by_text("66.7%", exact=False).first).to_be_visible()
    await page.get_by_label("Research model", exact=True).select_option("cua-s1")
    resolution = page.locator(".coverage-tracks").first.locator("section").filter(has=page.get_by_role("heading", name="Task resolution", exact=True))
    await expect(resolution).to_contain_text("100.0%")
    await expect(resolution).to_contain_text("6 / 6 trials")
    await expect(resolution).not_to_contain_text("66.7%")
    await page.get_by_label("Research model", exact=True).select_option("all")
    await page.get_by_text("Metrics Explained", exact=True).click()
    await expect(page.get_by_text("Confidence intervals resample", exact=False)).to_be_visible()
    await page.get_by_role("tab", name="Model Comparison", exact=True).click()
    await expect(page.get_by_text("deterministic semantic/controller assistance", exact=False)).to_be_visible()
    await page.get_by_role("tab", name="Providers", exact=True).click()
    await expect(page.get_by_role("cell", name="Shopify", exact=False).first).to_be_visible()
    await page.get_by_role("tab", name="Scenario Analysis", exact=True).click()
    await expect(page.get_by_role("cell", name="GENERIC-02", exact=False).first).to_be_visible()
    fixture["runs"].append({**fixture["runs"][0],"id":"ui-blocked-cost","status":"blocked","success":False,"calls":[],"cost":0.005})
    await page.reload()
    await page.get_by_role("tab", name="Run Explorer", exact=True).click()
    await expect(page.get_by_role("button", name="Open run ui-blocked-cost", exact=True)).to_be_visible()
    await page.get_by_role("tab", name="Summary", exact=True).focus()
    await page.keyboard.press("ArrowRight")
    await expect(page.get_by_role("tab", name="Model Comparison", exact=True)).to_have_attribute("aria-selected", "true")


async def test_run_explorer_evidence_missing_metrics_and_exports(
    server, page, tmp_path
):
    fixture = await install_ui_data(page, server)
    await page.goto(server + "/#/results")
    await page.get_by_role("tab", name="Run Explorer", exact=True).click()
    async with page.expect_download() as got:
        await page.get_by_role("button", name="Export run JSON").click()
    downloaded = await got.value
    target = tmp_path / "all.json"
    await downloaded.save_as(target)
    data = json.loads(target.read_text())
    assert len(data["runs"]) == 12
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
    from tests.ui_fixtures import official_ui_data
    assert json.loads(target.read_text()) == official_ui_data(fixture["runs"])["runs"][0]


async def test_hidden_run_deep_link_and_saved_model_ids_are_sanitised(server, page):
    await install_ui_data(page, server)
    await page.add_init_script(
        "localStorage.setItem('checkoutbench.setup.v2.2',JSON.stringify({models:['reference','openai/gpt-6-astra','cua-s1'],scenarios:['V21-S01']}))"
    )
    await page.goto(server + "/#/models")
    await expect(page.get_by_role("checkbox", checked=True)).to_have_count(1)
    await nav(page, "results/hidden-frontier")
    await expect(
        page.get_by_role("heading", name="Run is not in the official evaluation dataset")
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


async def test_research_payment_stage_views_show_honest_empty_state(server,page):
    await install_ui_data(page,server,populated=False)
    await page.goto(server+'/#/results')
    await expect(page.get_by_role('tab',name='Payment & Stage Analysis',exact=True)).to_be_visible()
    await page.get_by_role('tab',name='Payment & Stage Analysis',exact=True).click()
    for name in ['Payment Method Ranking','Checkout Funnel','Failure Breakdown','Vendor × Payment Method']:
        await page.get_by_role('tab',name=name,exact=True).click()
        await expect(page.get_by_role('heading',name='No benchmark results yet',exact=True)).to_be_visible()
    await expect(page.get_by_role('link',name='Research bundle ↓')).to_be_visible()


async def test_official_empty_state_start_navigation(server,page):
    await install_ui_data(page,server,populated=False)
    await page.goto(server+'/#/results')
    for name in ['Summary','Model Comparison','Scenario Analysis','Payment & Stage Analysis','Run Explorer']:
        await page.get_by_role('tab',name=name,exact=True).click()
        await expect(page.get_by_role('heading',name='No benchmark results yet',exact=True)).to_be_visible()
        await expect(page.locator('.page-body')).not_to_contain_text('100.0%')
    await page.get_by_role('button',name='Start Benchmark →',exact=True).click()
    await expect(page).to_have_url(re.compile('/#/models$'))
