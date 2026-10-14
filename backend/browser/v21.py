"""Public-observation controller. No scenario, fixture state or evaluator imports."""

import asyncio, io, re, time
from PIL import Image
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout
from backend.adapters.base import Usage
from backend.adapters.specialists import CuaS1Adapter, TinyClickAdapter
from backend.browser.v2 import terminal


def semantic_value(label, profile, options=()):
    """Deterministic reference/TinyClick planning assistance, never used to override CUA output."""
    l = label.lower().strip()
    c = profile["customer"]
    d = profile["delivery"]
    a = c["shipping"]
    b = c["billing"]
    p = profile["payment"]
    card = profile["test_card"]
    passenger = re.search(r"passenger (\d+) (.*)", l)
    if passenger:
        who = profile["travellers"].get(passenger[1], {})
        field = passenger[2]
        return who.get("full_name" if field == "name" else field)
    if "saved payment" in l:
        return next(
            (o for o in options if "4242" in o),
            next((o for o in options if "4444" in o), None),
        )
    if "payment method" in l:
        return {
            "card": "Card",
            "link": "Link · saved payment",
            "upi_qr": "UPI QR",
            "upi_app": "UPI intent",
            "netbanking": "Netbanking",
            "cod": "Cash on delivery",
            "upi_vpa": "Legacy UPI ID (iOS exception)",
        }[p["method"]]
    if "upi application" in l:
        return p["upi_app"]
    if "legacy upi id" in l:
        return p["vpa"]
    if l == "bank":
        return p["bank"]
    if "create a link account" in l:
        return p["registration_authorised"]
    if "cardholder" in l:
        return card["cardholder"]
    if l == "card number":
        return card["number"]
    if "expiry" in l:
        return card["expiry"]
    if "security code" in l:
        return card["security_code"]
    if "email" in l and "news" not in l:
        return c["email"]
    if "phone" in l:
        return c["phone"]
    if "first name" in l or "given name" in l:
        return c["given_name"]
    if "last name" in l or "family name" in l:
        return c["family_name"]
    if l in ("full name", "recipient", "receiver name", "name"):
        return c["full_name"]
    address = b if "billing" in l else a
    if any(t in l for t in ("postal", "pin code", "delivery pin", "zip")):
        return address["postal_code"]
    if "billing address" in l:
        return b["full_address"]
    if l in ("address", "street address", "house / flat / building"):
        return a["full_address"]
    if l == "house / flat number":
        return a["building"]
    if l == "street / road":
        return a["street"]
    if l == "area / locality":
        return a["locality"]
    if "apartment / floor" in l:
        return d["floor"]
    if any(t in l for t in ("landmark", "apartment, suite")):
        return a["landmark"]
    if l in ("city", "town / city"):
        return address["city"]
    if l == "state":
        return address["state"]
    for terms, key in [
        (["delivery method", "delivery speed"], "service"),
        (["delivery window", "delivery appointment"], "time_window"),
        (["gift message"], "gift_message"),
        (["discount", "coupon"], "coupon"),
        (["loyalty"], "loyalty"),
        (["gift wrapping"], "gift_wrap"),
        (["news and offers"], "marketing"),
        (["delivery instructions"], "instructions"),
        (["warranty"], "warranty"),
        (["shipping insurance"], "insurance"),
        (["allow substitutions"], "allow_substitutions"),
        (["substitution preference"], "substitution_limit"),
        (["access instructions"], "access"),
        (["purchase option"], "purchase"),
        (["monthly subscription"], "subscription_authorised"),
    ]:
        if any(t in l for t in terms):
            return d[key]
    j = profile["journey"]
    for term, key in [
        ("boarding station", "boarding"),
        ("preferred coach", "coach"),
        ("reservation choice", "reservation"),
        ("travel insurance", "insurance"),
    ]:
        if term in l:
            return j[key]
    ap = profile["appointment"]
    for terms, key in [
        (["application reference"], "reference"),
        (["service scheme"], "service"),
        (["appointment centre"], "centre"),
        (["appointment slot"], "preferred_time"),
        (["declaration", "confirm these synthetic"], "declaration_authorised"),
        (["justification"], "reason"),
    ]:
        if any(t in l for t in terms):
            return ap[key]
    if "search by" in l:
        return profile["notice"]["search_by"]
    if "lookup identifier" in l:
        return profile["notice"]["identifier"]
    return None


async def visible_clip(frame):
    # Frame geometry supplies visibility only, never an action coordinate or target correction.
    size = frame.page.viewport_size or {"width": 1280, "height": 900}
    box = {"x": 0, "y": 0}
    if frame.parent_frame:
        element = await frame.frame_element()
        box = await element.bounding_box() or {"x": size["width"], "y": size["height"]}
    return {
        "top": max(0, -box["y"]),
        "left": max(0, -box["x"]),
        "bottom": size["height"] - box["y"],
        "right": size["width"] - box["x"],
    }


async def in_view(frame, loc):
    return await loc.evaluate(
        "(e,c)=>{let r=e.getBoundingClientRect();return r.top>=c.top&&r.bottom<=c.bottom&&r.left>=c.left&&r.right<=c.right}",
        await visible_clip(frame),
    )


async def observe(frame):
    # Snapshot visible semantics atomically so a provider rerender cannot pair old labels with new controls.
    clip = await visible_clip(frame)
    rows = await frame.locator("input,select,textarea").evaluate_all(
        """(es,c)=>es.filter(e=>e.checkVisibility()&&!e.disabled&&!['radio','hidden'].includes(e.type)).map(e=>{let r=e.getBoundingClientRect();return {handle:e.id,label:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.parentElement.innerText,role:e.tagName==='SELECT'?'combobox':e.type==='checkbox'?'checkbox':'textbox',type:e.type,value:e.type==='checkbox'?String(e.checked):e.value,options:e.tagName==='SELECT'?[...e.options].filter(o=>!o.disabled&&o.value).map(o=>o.textContent):[],option_values:e.tagName==='SELECT'?[...e.options].filter(o=>!o.disabled&&o.value).map(o=>o.value):[],onscreen:r.top>=c.top&&r.bottom<=c.bottom&&r.left>=c.left&&r.right<=c.right,form_title:e.closest('fieldset')?.querySelector('legend')?.textContent||e.closest('section')?.querySelector('h2')?.textContent||'Checkout'}})""",
        clip,
    )
    groups = await frame.locator('[role="radiogroup"]').evaluate_all(
        """(es,c)=>es.filter(e=>e.getClientRects().length).map(e=>{let r=e.getBoundingClientRect(),bs=[...e.querySelectorAll('[role=radio]')];return {handle:e.id,label:e.getAttribute('aria-label'),role:'combobox',type:'choicegroup',value:bs.find(b=>b.getAttribute('aria-checked')==='true')?.getAttribute('data-value')||'',options:bs.map(b=>b.textContent),option_values:bs.map(b=>b.getAttribute('data-value')),onscreen:r.top>=c.top&&r.bottom<=c.bottom&&r.left>=c.left&&r.right<=c.right,form_title:'Payment'}})""",
        clip,
    )
    rows += groups
    for row in rows:
        if row["handle"]:
            row["locator"] = frame.locator('[id="' + row["handle"] + '"]')
    return [row for row in rows if row["handle"]]


async def reference_v21(page, task, ctl, mode="reference", cua=None, tiny=None):
    usage = Usage()
    ctl.usage = usage
    ctl.semantic_decisions = []
    cua = cua or (CuaS1Adapter() if mode in ("cua-s1", "hybrid") else None)
    tiny = tiny or (TinyClickAdapter() if mode in ("tinyclick", "hybrid") else None)
    if (cua and getattr(cua, "endpoint", None)) or (
        tiny and getattr(tiny, "endpoint", None)
    ):
        usage.cost_kind = "not_reported"
    native = task.get("agent_mode") == "native_link"
    profile = task["profile"]
    seen = {}
    scrolls = 0

    async def scroll_fixed():
        nonlocal scrolls
        amount = 500 if scrolls % 8 < 7 else -4000
        scrolls += 1
        start = time.perf_counter()
        await ctl.page.mouse.wheel(0, amount)
        ctl.timings["browser_execution_seconds"] += time.perf_counter() - start
        await ctl.record(
            "scroll", {"amount": amount, "selection_source": "deterministic_controller"}
        )

    async def model_call(adapter, operation, *args):
        start = time.perf_counter()
        result = await getattr(adapter, operation)(*args)
        elapsed = time.perf_counter() - start
        usage.inference_seconds += elapsed
        usage.calls.append(
            dict(
                model=adapter.key,
                operation=operation,
                seconds=elapsed,
                backend=getattr(adapter, "last_metrics", {}).get(
                    "backend", "test-double"
                ),
            )
        )
        return result

    async def perform(
        loc,
        label,
        value=None,
        kind="click",
        selected_by="deterministic_controller",
        action_handle=None,
    ):
        await ctl.check()
        prediction = None
        handle = action_handle or await loc.get_attribute("id")
        if tiny:
            frame = await (await loc.element_handle()).owner_frame()
            if not await in_view(frame, loc):
                await scroll_fixed()
                return
        if tiny:
            t = time.perf_counter()
            shot = await ctl.page.screenshot()
            ctl.timings["model_screenshot_seconds"] += time.perf_counter() - t
            prediction = await model_call(
                tiny,
                "ground",
                Image.open(io.BytesIO(shot)),
                f"{label}" + (" input" if kind == "fill" else ""),
            )
            # The private recorder scores the prediction only AFTER inference; it cannot alter action choice.
            await ctl.assess_grounding(loc, prediction)
        start = time.perf_counter()
        try:
            if tiny:
                await ctl.page.mouse.click(prediction["x"], prediction["y"])
                if kind == "fill":
                    await ctl.page.keyboard.press("ControlOrMeta+A")
                    await ctl.page.keyboard.insert_text(str(value))
                    await ctl.page.keyboard.press("Tab")
                elif kind == "select":
                    await ctl.page.keyboard.press("Home")
                    await ctl.page.keyboard.type(str(value))
                    await ctl.page.keyboard.press("Enter")
                    await ctl.page.keyboard.press("Tab")
            elif kind == "fill":
                await loc.fill(str(value))
                await loc.dispatch_event("change")
            elif kind == "select":
                await loc.select_option(label=str(value))
            elif kind == "check":
                await loc.set_checked(value == "true")
            else:
                await loc.click(timeout=1200)
        except Exception as exc:
            await ctl.record(
                "invalid_action",
                {
                    "target": label,
                    "reason": type(exc).__name__,
                    "selection_source": selected_by,
                },
            )
        ctl.timings["browser_execution_seconds"] += time.perf_counter() - start
        await ctl.record(
            kind,
            {
                "field": label,
                "value": value,
                "control_handle": handle,
                "prediction": prediction,
                "selection_source": selected_by,
                "grounding_source": "tinyclick" if tiny else "DOM",
            },
        )
        await asyncio.sleep(0.09)

    for _ in range(ctl.max_steps * 4):
        try:
            await ctl.check()
            pages = [p for p in page.context.pages if not p.is_closed()]
            active = pages[-1]
            ctl.page = active
            if any([await terminal(f) for f in active.frames]):
                return usage
            acted = False
            overflow = False
            for frame in reversed(active.frames):
                text = await frame.locator("body").inner_text()
                # Explicit blockers and challenge recovery take precedence over form filling.
                names = []
                if any(
                    t in text
                    for t in [
                        "Maximum attempts",
                        "mock CAPTCHA",
                        "application has expired",
                        "QR service unavailable",
                    ]
                ):
                    names = ["Request user intervention"]
                elif "This challan is settled" in text:
                    names = ["Report settled — stop safely"]
                elif any(
                    t in text
                    for t in ["Code rejected", "Code expired", "· invalid", "· expired"]
                ):
                    names = ["Resend code"]
                elif "This QR is unusable or expired" in text:
                    names = ["Regenerate QR"]
                for name in names:
                    loc = frame.get_by_role("button", name=name, exact=True)
                    if await loc.count() and await loc.is_visible():
                        await perform(loc, name)
                        acted = True
                        break
                if acted:
                    break
                rows = await observe(frame)
                login = frame.get_by_role(
                    "button", name="Continue with Link", exact=True
                )
                if (
                    task["payment_request"]["method"] == "link"
                    and await login.count()
                    and any(
                        "email" in r["label"].lower()
                        and r["value"] == profile["customer"]["email"]
                        for r in rows
                    )
                ):
                    await perform(login, "Continue with Link")
                    acted = True
                    break
                accelerated = frame.get_by_role(
                    "button", name="Authenticate accelerated checkout", exact=True
                )
                if await accelerated.count():
                    await perform(accelerated, "Authenticate accelerated checkout")
                    acted = True
                    break
                for row in rows:
                    if row["type"] == "password" and "code" not in row["label"].lower():
                        continue
                    if "otp" in row["label"].lower() or "digit" in row["label"].lower():
                        continue
                    if native and row["value"] and "email" not in row["label"].lower():
                        continue
                    key = (
                        frame.url,
                        row["handle"],
                        row["value"],
                        tuple(row["options"]),
                    )
                    if key in seen:
                        continue
                    # A model receives visible semantics and the independent customer document only.
                    if cua:
                        prediction = (
                            await model_call(
                                cua,
                                "score_fields",
                                [
                                    {
                                        k: row[k]
                                        for k in (
                                            "label",
                                            "role",
                                            "value",
                                            "form_title",
                                        )
                                    }
                                ],
                                profile,
                            )
                        )[0]
                        selected_by = "cua-s1"
                        value = prediction.get("value")
                        if prediction["action"] == "check":
                            value = "true"
                        measured = (
                            value
                            if prediction["action"] in ("fill", "check")
                            else row["value"]
                        )
                        if str(measured) in row["options"]:
                            measured = row["option_values"][
                                row["options"].index(str(measured))
                            ]
                        ctl.semantic_decisions.append(
                            {
                                "control_handle": row["handle"],
                                "action": prediction["action"],
                                "value": measured,
                                "visible_label": row["label"],
                            }
                        )
                        if prediction["action"] not in ("fill", "check"):
                            seen[key] = True
                            continue
                    else:
                        computation = time.perf_counter()
                        value = semantic_value(row["label"], profile, row["options"])
                        selected_by = (
                            "deterministic_reference"
                            if mode == "reference"
                            else "deterministic_semantic_assistance"
                        )
                        ctl.timings["controller_compute_seconds"] += (
                            time.perf_counter() - computation
                        )
                    current_label = (
                        row["options"][row["option_values"].index(row["value"])]
                        if row["value"] in row["option_values"]
                        else row["value"]
                    )
                    if value is None or str(value) in (row["value"], current_label):
                        seen[key] = True
                        continue
                    if tiny and not row["onscreen"]:
                        overflow = True
                        continue
                    kind = (
                        "check"
                        if row["type"] == "checkbox"
                        else "select"
                        if row["role"] == "combobox"
                        else "fill"
                    )
                    if kind == "select" and str(value) in row["option_values"]:
                        value = row["options"][row["option_values"].index(str(value))]
                    if kind == "select" and str(value) not in row["options"]:
                        await ctl.record(
                            "invalid_model_selection",
                            {
                                "field": row["label"],
                                "value": value,
                                "selection_source": selected_by,
                            },
                        )
                        continue
                    if row["type"] == "choicegroup":
                        await perform(
                            row["locator"].get_by_role(
                                "radio", name=str(value), exact=True
                            ),
                            str(value),
                            str(value),
                            "click",
                            selected_by,
                            row["handle"],
                        )
                    else:
                        await perform(
                            row["locator"], row["label"], str(value), kind, selected_by
                        )
                    acted = True
                    break
                if acted:
                    break
                if tiny and overflow:
                    continue
                if "Your synthetic notices" in text:
                    names = (
                        ["Open transaction verification"]
                        if "pending" in text.lower()
                        else ["Inspect " + profile["notice"]["target"]]
                    )
                else:
                    names = []
                if "Approval received" not in text:
                    names += ["Request user authorisation"]
                if task["payment_request"]["method"] == "link":
                    names += ["Continue with Link"] + (
                        ["Create synthetic account"]
                        if task["registration_consent"]
                        else ["Continue without Link"]
                    )
                else:
                    names += ["Continue without Link", "Use ordinary card checkout"]
                names += [
                    "Return to checkout",
                    "Authenticate accelerated checkout",
                    "Resume saved session",
                    "Continue to shipping",
                    "Continue to payment",
                    "Choose appointment",
                    "Find challans",
                    "Review details",
                    "Confirm review and continue",
                    "Launch payment gateway",
                    "Show QR code",
                    "Prepare selected payment",
                    "Continue to simulated bank",
                    "Start authentication",
                    "Continue to authentication page",
                    "Open authentication window",
                    "Check transaction status",
                    "Return and verify transaction",
                    "Continue with this address",
                ]
                # Expand user-visible saved summaries; no selector encodes a profile attribute.
                for summary in await frame.locator(
                    "details:not([open]) > summary"
                ).all():
                    if await summary.is_visible():
                        await perform(summary, await summary.inner_text())
                        acted = True
                        break
                if acted:
                    break
                for name in names:
                    loc = frame.get_by_role("button", name=name, exact=True)
                    if not await loc.count():
                        loc = frame.get_by_role("link", name=name, exact=True)
                    if (
                        await loc.count()
                        and await loc.first.is_visible()
                        and await loc.first.is_enabled()
                    ):
                        if tiny:
                            # Never scroll a correct target into view for the visual grounder.
                            visible = await loc.first.evaluate(
                                "(e)=>{let r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight}"
                            )
                            if not visible:
                                overflow = True
                                continue
                        await perform(loc.first, name)
                        acted = True
                        break
                if acted:
                    break
            if not acted:
                if overflow:
                    await scroll_fixed()
                await asyncio.sleep(0.15)
        except BrowserTimeout:
            await asyncio.sleep(0.1)
            continue
        except BrowserError as exc:
            if any(
                word in str(exc).lower()
                for word in ("detached", "destroyed", "closed", "navigation")
            ):
                await asyncio.sleep(0.12)
                continue
            raise
    return usage
