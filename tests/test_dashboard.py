"""Browser checks for guided setup and separation of reference/model results."""

import pytest
from playwright.async_api import expect


@pytest.mark.asyncio
async def test_software_preset_requires_review_and_resets_only_setup(server, page):
    batch_requests = []
    page.on(
        "request",
        lambda r: (
            batch_requests.append(r.url)
            if r.method == "POST" and r.url.endswith("/api/batches")
            else None
        ),
    )
    await page.goto(server)
    await page.get_by_role("button", name="Set up all v2.1 checks", exact=True).click()
    await expect(
        page.get_by_role("heading", name="Scenarios", exact=True)
    ).to_be_visible()
    await expect(page.get_by_label("Trials per scenario", exact=True)).to_have_value(
        "1"
    )
    submitted = []

    async def estimate(route):
        submitted.append(route.request.post_data_json)
        await route.fulfill(
            json={
                "runs": len(submitted[-1]["scenarios"]),
                "estimated_cost": 0,
                "assumption": "Software check",
                "unknown": [],
            }
        )

    await page.route("**/api/estimate", estimate)
    await page.get_by_role("button", name="Review & run", exact=True).click()
    await expect(
        page.get_by_role("heading", name="74 evaluations, identical conditions.")
    ).to_be_visible()
    assert submitted[-1]["models"] == ["reference"]
    assert len(submitted[-1]["scenarios"]) == 74
    assert all(s.startswith("V21-") for s in submitted[-1]["scenarios"])
    assert submitted[-1]["agent_mode"] == "standard"
    assert not batch_requests
    await page.get_by_role("button", name="Cancel", exact=True).click()
    await page.get_by_role("button", name="Reset setup to one software check").click()
    await page.get_by_role("button", name="Review & run", exact=True).click()
    await expect(
        page.get_by_role("heading", name="1 evaluation, identical conditions.")
    ).to_be_visible()
    assert submitted[-1]["scenarios"] == ["V21-S01"]
    assert not batch_requests


@pytest.mark.asyncio
async def test_result_filters_separate_reference_model_and_version(server, page):
    rows = [
        dict(
            id=rid,
            model=model,
            benchmark_version=version,
            scenario="V21-S01",
            status="completed",
            success=True,
            cost=0,
            events=[],
        )
        for rid, model, version in [
            ("ref-new-000", "reference", "2.1"),
            ("ai-new-000", "test/model", "2.1"),
            ("ref-old-000", "reference", "2.0"),
        ]
    ]
    await page.route(
        "**/api/results",
        lambda route: route.fulfill(
            json={"runs": rows, "leaderboard": [], "link_comparisons": []}
        ),
    )
    await page.goto(server)
    await page.locator("nav").get_by_role("button", name="Results", exact=True).click()
    history = page.locator("section").filter(
        has=page.get_by_role("heading", name="Evaluation history", exact=True)
    )
    await expect(history.get_by_text("ref-new-", exact=True)).to_be_visible()
    await expect(history.get_by_text("ai-new-0", exact=True)).to_be_visible()
    await expect(history.get_by_text("ref-old-", exact=True)).to_have_count(0)
    await page.get_by_label("Result type", exact=True).select_option("models")
    await expect(history.get_by_text("ref-new-", exact=True)).to_have_count(0)
    await expect(history.get_by_text("ai-new-0", exact=True)).to_be_visible()
    await page.get_by_label("Result type", exact=True).select_option("reference")
    await page.get_by_label("Leaderboard version", exact=True).select_option("all")
    await expect(history.get_by_text("ref-new-", exact=True)).to_be_visible()
    await expect(history.get_by_text("ref-old-", exact=True)).to_be_visible()
    await expect(history.get_by_text("ai-new-0", exact=True)).to_have_count(0)
