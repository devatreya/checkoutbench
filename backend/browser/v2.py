"""Public-task reference controller. Native arm is scripted test-user interaction, not AI."""

import asyncio
import io
import time
from PIL import Image
from playwright.async_api import TimeoutError as BrowserTimeout, Error as BrowserError
from backend.adapters.base import Usage, Unavailable
from backend.adapters.specialists import CuaS1Adapter, TinyClickAdapter

TERMINAL_TITLES = [
    "Checkout ready",
    "Authentication required",
    "Payment successful in simulation",
    "Stopped safely",
    "Payment failed",
]


async def terminal(page):
    return any(
        [
            await page.get_by_role("heading", name=t, exact=True).count() > 0
            for t in TERMINAL_TITLES
        ]
    )


async def reference_v2(page, task, ctl, mode="reference"):
    usage = Usage()
    ctl.usage = usage
    prefs = task["preferences"]
    native = task.get("agent_mode") == "native_link"
    cua = CuaS1Adapter() if mode in ("cua-s1", "hybrid") else None
    tiny = TinyClickAdapter() if mode in ("tinyclick", "hybrid") else None
    if (cua and cua.endpoint) or (tiny and tiny.endpoint):
        usage.cost_kind = "not_reported"

    async def click(loc, label):
        await ctl.check()
        try:
            await loc.scroll_into_view_if_needed(timeout=1200)
        except (BrowserTimeout, BrowserError):
            return
        if tiny:
            image = Image.open(io.BytesIO(await ctl.page.screenshot()))
            start = time.perf_counter()
            a = await tiny.ground(image, label)
            usage.inference_seconds += time.perf_counter() - start
            box = await loc.bounding_box()
            ctl.groundings.append(
                bool(
                    box
                    and box["x"] <= a["x"] <= box["x"] + box["width"]
                    and box["y"] <= a["y"] <= box["y"] + box["height"]
                )
            )
            await ctl.page.mouse.click(a["x"], a["y"])
        else:
            try:
                await loc.click(timeout=1200)
            except (BrowserTimeout, BrowserError):
                return
        await ctl.record("click", {"target": label})
        await asyncio.sleep(0.18)

    for _ in range(ctl.max_steps * 3):
        await ctl.check()
        pages = [p for p in page.context.pages if not p.is_closed()]
        active = pages[-1]
        ctl.page = active
        if await terminal(active):
            return usage
        # Frames are visible browser surfaces, not private state APIs.
        frames = active.frames
        surfaces = list(reversed(frames))
        acted = False
        for frame in surfaces:
            text = await frame.locator("body").inner_text()
            if (
                "Maximum attempts reached" in text
                or "mock CAPTCHA needs" in text
                or "application has expired" in text
                or "QR service unavailable" in text
                or "This challan is settled" in text
            ):
                for name in [
                    "Request user intervention",
                    "Report settled — stop safely",
                ]:
                    loc = frame.get_by_role("button", name=name, exact=True)
                    if await loc.count():
                        await click(loc, name)
                        acted = True
                        break
                if acted:
                    break
            # Authenticate returning Link users before filling delivery fields so native
            # autofill is actually exercised, rather than credited after manual entry.
            login = frame.get_by_role("button", name="Continue with Link", exact=True)
            if (
                task["payment_request"]["method"] == "link"
                and await login.count()
                and await login.is_visible()
            ):
                email = frame.locator('input[name="email"]').first
                if await email.input_value() != prefs["email"]:
                    await email.fill(prefs["email"])
                    await email.dispatch_event("change")
                    await ctl.record(
                        "fill", {"field": "email", "value": prefs["email"]}
                    )
                await click(login, "Continue with Link")
                acted = True
                break
            # Native Link only never corrects the native saved values; these failures are intentional controls.
            for summary in await frame.locator("details:not([open]) > summary").all():
                await click(summary, "Edit saved details")
                acted = True
                break
            if acted:
                break
            inputs = await frame.locator(
                "input[name],select[name],textarea[name]"
            ).all()
            elements = []
            for loc in inputs:
                if not await loc.is_visible() or not await loc.is_enabled():
                    continue
                key = await loc.get_attribute("name")
                typ = await loc.get_attribute("type")
                if key not in prefs or typ == "radio":
                    continue
                if native and await loc.input_value() and key not in ("email",):
                    continue
                value = prefs[key]
                if cua and key not in (
                    "payment_method",
                    "upi_app",
                    "saved_card",
                    "cardNumber",
                    "cardName",
                    "expiry",
                    "cvv",
                ):
                    label = await loc.evaluate(
                        '(e)=>e.labels?.[0]?.innerText || e.getAttribute("aria-label") || e.name'
                    )
                    start = time.perf_counter()
                    pred = (
                        await cua.score_fields(
                            [
                                {
                                    "id": key,
                                    "label": label,
                                    "role": "textbox",
                                    "value": await loc.input_value(),
                                }
                            ],
                            task["profile"],
                        )
                    )[0]
                    usage.inference_seconds += time.perf_counter() - start
                    if pred["action"] != "fill":
                        continue
                    value = str(pred["value"])
                    ctl.classifications.append(value == prefs[key])
                if typ == "checkbox":
                    desired = value == "true"
                    if await loc.is_checked() != desired:
                        await loc.set_checked(desired)
                        await ctl.record("check", {"field": key})
                        await asyncio.sleep(0.1)
                        acted = True
                        break
                elif await loc.input_value() != value:
                    if await loc.evaluate("(e)=>e.tagName") == "SELECT":
                        await loc.select_option(label=value)
                    else:
                        await loc.fill(value)
                        await loc.dispatch_event("change")
                    await ctl.record("fill", {"field": key, "value": value})
                    acted = True
                    break
            if acted:
                break
            # Customer instruction supplies the preference; no scenario answer is consulted.
            for key in ("payment_method", "saved_card"):
                if key not in prefs:
                    continue
                loc = frame.locator(f'input[name="{key}"][value="{prefs[key]}"]')
                if (
                    await loc.count()
                    and await loc.is_visible()
                    and await loc.is_enabled()
                    and not await loc.is_checked()
                ):
                    await click(loc, prefs[key])
                    acted = True
                    break
            if acted:
                break
            if "Your synthetic notices" in text:
                if "A transaction is pending" in text:
                    loc = frame.get_by_role(
                        "button", name="Check transaction status", exact=True
                    )
                else:
                    loc = frame.get_by_role(
                        "button", name="Inspect " + prefs.get("challan", ""), exact=True
                    )
                if await loc.count():
                    await click(loc, "Inspect requested challan")
                    acted = True
                    break
            if "This QR is unusable or expired" in text:
                loc = frame.get_by_role("button", name="Regenerate QR", exact=True)
                if await loc.count():
                    await click(loc, "Regenerate QR")
                    acted = True
                    break
            if (
                "Code rejected" in text
                or "Code expired" in text
                or "Authentication expired" in text
                or "Authentication invalid" in text
                or "· expired" in text
                or "· invalid" in text
            ):
                loc = frame.get_by_role("button", name="Resend code", exact=True)
                if await loc.count():
                    await click(loc, "Resend code")
                    acted = True
                    break
            names = []
            if task["payment_request"]["method"] == "link":
                names += ["Continue with Link"] + (
                    ["Create synthetic account"]
                    if task.get("registration_consent")
                    else ["Continue without Link"]
                )
            else:
                names += ["Continue without Link", "Use ordinary card checkout"]
            names += [
                "Return to checkout",
                "Resume saved session",
                "Continue to shipping",
                "Find challans",
                "Review details",
                "Confirm review and continue",
                "Show QR code",
                "Prepare selected payment",
                "Continue to simulated bank",
                "Start authentication",
                "Continue to authentication page",
                "Open authentication window",
                "Check transaction status",
                "Return and verify transaction",
            ]
            # Do not repeatedly request while the independent test user is approving.
            if (
                "Approval received" not in text
                and "· invalid" not in text
                and "· expired" not in text
                and "· locked" not in text
            ):
                names += ["Request user authorisation"]
            for name in names:
                loc = frame.get_by_role("button", name=name, exact=True)
                if not await loc.count():
                    loc = frame.get_by_role("link", name=name, exact=True)
                if (
                    await loc.count()
                    and await loc.first.is_visible()
                    and await loc.first.is_enabled()
                ):
                    await click(loc.first, name)
                    acted = True
                    break
            if acted:
                break
        if not acted:
            await asyncio.sleep(0.3)
    return usage
