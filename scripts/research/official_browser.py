"""Read-only official Stripe test-session browser inspection, separate from AI scores.

Requires BENCH_SANDBOX_STRIPE_ENABLED=1, BENCH_SANDBOX_STRIPE_KEY=sk_test_...
and an existing cs_test_ session. Full payment/3DS validation remains pending until
an authorised operator supplies and reviews its browser trace and final status.
"""

import argparse, asyncio, hashlib, json
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from backend.sandboxes import config
from backend.storage.database import DATA


async def main(sid):
    get, key, _ = config("stripe")
    if not sid.startswith("cs_test_"):
        raise ValueError("Test session required")
    async with httpx.AsyncClient(
        timeout=20, follow_redirects=False, trust_env=False
    ) as c:
        response = await c.get(
            "https://api.stripe.com/v1/checkout/sessions/" + sid, auth=(key, "")
        )
        response.raise_for_status()
        obj = response.json()
    if (
        obj.get("livemode") is not False
        or urlsplit(obj.get("url") or "").hostname != "checkout.stripe.com"
    ):
        raise ValueError("Verified hosted test session URL required")
    from playwright.async_api import async_playwright

    path = DATA / "research/official-stripe"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context()
        await ctx.tracing.start(screenshots=True, snapshots=True)
        page = await ctx.new_page()
        await page.goto(obj["url"], wait_until="domcontentloaded")
        await page.screenshot(path=str(path / "hosted.png"), full_page=True)
        record = {
            "provider": "stripe",
            "source_class": "official provider sandbox",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "browser": browser.version,
            "sdk_version": "provider-hosted, unreported",
            "configuration": {
                "ui_mode": obj.get("ui_mode"),
                "payment_method_types": obj.get("payment_method_types"),
            },
            "test_payment_method": "not submitted",
            "actions": [
                "navigate to API-verified hosted test checkout",
                "capture screenshot",
            ],
            "final_test_status": {
                k: obj.get(k) for k in ("status", "payment_status", "livemode")
            },
            "completed_browser_workflow": False,
            "scope": "Hosted UI inspection only; not payment completion or broad fidelity evidence",
        }
        await ctx.tracing.stop(path=str(path / "trace.zip"))
        await browser.close()
    record["screenshot_sha256"] = hashlib.sha256(
        (path / "hosted.png").read_bytes()
    ).hexdigest()
    record["trace_sha256"] = hashlib.sha256(
        (path / "trace.zip").read_bytes()
    ).hexdigest()
    (path / "evidence.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--stripe-session", required=True)
    a = p.parse_args()
    asyncio.run(main(a.stripe_session))
