"""Public-observation controller. No scenario, fixture state or evaluator imports."""

import asyncio, io, re, time, json, hashlib
from PIL import Image
from playwright.async_api import Error as BrowserError, TimeoutError as BrowserTimeout
from backend.adapters.base import Usage
from backend.adapters.specialists import CuaS1Adapter, TinyClickAdapter, SpecialistOutputError
from backend.browser.v2 import terminal



class NoProgress(RuntimeError):
    """Bounded controller stop; never a replacement for field evaluation."""

    def __init__(self, diagnostics):
        super().__init__("Browser made no meaningful progress")
        self.diagnostics = diagnostics


async def page_state(page):
    """Public UI state, excluding timestamps, validation counters and toast text.

    Field values, visibility, checked state, options, headings and enabled actions
    count as progress. Repeated validation messages do not reset the retry budget.
    """
    state = []
    for active in page.context.pages:
        if active.is_closed():
            continue
        for frame in active.frames:
            state.append([frame.url, await frame.evaluate("""() => {
              const visible = e => e.checkVisibility({visibilityProperty:true,opacityProperty:true});
              return {
                viewport: [scrollX,scrollY,innerWidth,innerHeight],
                headings: [...document.querySelectorAll('h1,h2,h3,legend')].filter(visible).map(e=>e.textContent.trim()),
                controls: [...document.querySelectorAll('input,select,textarea,[role=radio]')].filter(e=>e.type!=='hidden'&&visible(e)).map(e=>[
                  e.id,e.getAttribute('aria-label')||e.labels?.[0]?.textContent,e.type,e.value,
                  e.checked??e.getAttribute('aria-checked'),e.disabled,e.readOnly,e.required,
                  e.tagName==='SELECT'?[...e.options].map(o=>[o.value,o.textContent,o.disabled]):null]),
                actions: [...document.querySelectorAll('button,a,summary')].filter(visible).map(e=>[
                  e.textContent.trim(),e.disabled,e.getAttribute('aria-expanded'),e.tagName==='SUMMARY'?e.parentElement.open:null])
              };
            }""")])
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


async def validation_state(page):
    result = []
    for frame in page.frames:
        result.extend(await frame.locator('input,select,textarea').evaluate_all("""es => es.filter(e=>e.checkVisibility() && !e.disabled && (e.validity && !e.validity.valid || e.getAttribute('aria-invalid')==='true')).map(e=>({control_handle:e.id,message:e.validationMessage||'aria-invalid'}))"""))
        result.extend({"message": text} for text in await frame.locator('[role=alert],.error,.field-error').all_text_contents() if text.strip())
    return result


class ProgressGuard:
    def __init__(self, limit=3):
        self.limit = limit
        self.counts = {}

    def observe(self, action, before, after):
        if before != after:
            self.counts.clear()
            return 0
        key = (action, after)
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


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
        """(es,c)=>es.filter(e=>e.checkVisibility({visibilityProperty:true,opacityProperty:true})&&!e.disabled&&!['radio','hidden'].includes(e.type)).map(e=>{let r=e.getBoundingClientRect();return {handle:e.id,label:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.parentElement.innerText,role:e.tagName==='SELECT'?'combobox':e.type==='checkbox'?'checkbox':'textbox',type:e.type,value:e.type==='checkbox'?String(e.checked):e.value,checked:e.type==='checkbox'?e.checked:null,readonly:e.readOnly,required:e.required,options:e.tagName==='SELECT'?[...e.options].filter(o=>!o.disabled&&o.value).map(o=>o.textContent):[],option_values:e.tagName==='SELECT'?[...e.options].filter(o=>!o.disabled&&o.value).map(o=>o.value):[],onscreen:r.top>=c.top&&r.bottom<=c.bottom&&r.left>=c.left&&r.right<=c.right,form_title:e.closest('fieldset')?.querySelector('legend')?.textContent||e.closest('section')?.querySelector('h2')?.textContent||'Checkout'}})""",
        clip,
    )
    groups = await frame.locator('[role="radiogroup"]').evaluate_all(
        """(es,c)=>es.filter(e=>e.checkVisibility({visibilityProperty:true,opacityProperty:true})).map(e=>{let r=e.getBoundingClientRect(),bs=[...e.querySelectorAll('[role=radio]')];return {handle:e.id,label:e.getAttribute('aria-label'),role:'combobox',type:'choicegroup',checked:null,value:bs.find(b=>b.getAttribute('aria-checked')==='true')?.getAttribute('data-value')||'',options:bs.map(b=>b.textContent),option_values:bs.map(b=>b.getAttribute('data-value')),onscreen:r.top>=c.top&&r.bottom<=c.bottom&&r.left>=c.left&&r.right<=c.right,form_title:'Payment'}})""",
        clip,
    )
    rows += groups
    for row in rows:
        if row["handle"]:
            row["locator"] = frame.locator("[id=" + json.dumps(row["handle"]) + "]")
    return [row for row in rows if row["handle"]]


def field_identity(row):
    return tuple(json.dumps(row.get(k), sort_keys=True) for k in (
        "handle", "label", "role", "type", "value", "checked", "options",
        "option_values", "form_title", "required", "readonly",
    ))


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
    guard = ProgressGuard()
    ctl.harness_diagnostics = []

    async def scroll_fixed():
        nonlocal scrolls
        before_state = await page_state(ctl.page)
        amount = 500 if scrolls % 8 < 7 else -4000
        scrolls += 1
        start = time.perf_counter()
        await ctl.page.mouse.wheel(0, amount)
        ctl.timings["browser_execution_seconds"] += time.perf_counter() - start
        await ctl.record(
            "scroll", {"amount": amount, "selection_source": "deterministic_controller"}
        )
        await asyncio.sleep(0.15)
        after_state = await page_state(ctl.page)
        count = guard.observe(("scroll", amount), before_state, after_state)
        if count >= guard.limit:
            diagnostics = {"reason": "equivalent_action_without_state_change", "action": "scroll", "attempts": count, "limit": guard.limit, "selection_source": "deterministic_controller", "state_fingerprint": after_state}
            ctl.harness_diagnostics.append(diagnostics)
            await ctl.record("no_progress", diagnostics)
            raise NoProgress(diagnostics)

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
                call_temperature=getattr(adapter, "last_metrics", {}).get(
                    "call_temperature"
                ),
                cold_model_loading_seconds=getattr(adapter, "last_metrics", {}).get(
                    "cold_model_loading_seconds"
                ),
                warm_inference_seconds=getattr(adapter, "last_metrics", {}).get(
                    "warm_inference_seconds"
                ),
                backend=getattr(adapter, "last_metrics", {}).get(
                    "backend", "test-double"
                ),
            )
        )
        if operation == "score_fields":
            usage.calls[-1].update(inputs={"elements": args[0], "profile": args[1]}, outputs=result)
        return result

    async def perform(
        loc,
        label,
        value=None,
        kind="click",
        selected_by="deterministic_controller",
        action_handle=None,
        observed_field=None,
    ):
        await ctl.check()
        before_state = await page_state(ctl.page)
        prediction = None
        handle = action_handle or await loc.get_attribute("id")
        if tiny:
            frame = await (await loc.element_handle()).owner_frame()
            if not await in_view(frame, loc):
                if selected_by == "cua-s1":
                    ctl.semantic_decisions[-1]["execution_status"] = "deferred_offscreen"
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
            if observed_field is not None:
                current = next((r for r in await observe(frame) if r["handle"] == observed_field["handle"]), None)
                if current is None or field_identity(current) != field_identity(observed_field):
                    if selected_by == "cua-s1":
                        ctl.semantic_decisions[-1]["execution_status"] = "stale_observation"
                    return None
            # The private recorder scores the prediction only AFTER inference; it cannot alter action choice.
            await ctl.assess_grounding(loc, prediction)
        start = time.perf_counter()
        error = None
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
                await loc.fill(str(value), timeout=1200)
                await loc.dispatch_event("change")
            elif kind == "select":
                await loc.select_option(label=str(value), timeout=1200)
            elif kind == "check":
                await loc.set_checked(value is True or str(value).lower() == "true", timeout=1200)
            else:
                await loc.click(timeout=1200)
        except BrowserError as exc:
            error = type(exc).__name__
        ctl.timings["browser_execution_seconds"] += time.perf_counter() - start
        if selected_by == "cua-s1" and ctl.semantic_decisions:
            ctl.semantic_decisions[-1]["execution_status"] = "failed" if error else "executed"
        try:
            observed_after = await loc.evaluate("e=>({value:e.value??null,checked:e.type==='checkbox'?e.checked:null,visible:e.checkVisibility()})", timeout=250)
        except BrowserError:
            observed_after = None  # navigation or replacement removed the old target
        await ctl.record(
            "invalid_action" if error else kind,
            {
                "requested_action": kind,
                "observed_after": observed_after,
                "execution_status": "failed" if error else "executed",
                "error": error,
                "field": label,
                "value": value,
                "control_handle": handle,
                "prediction": prediction,
                "selection_source": selected_by,
                "grounding_source": "tinyclick" if tiny else "DOM",
            },
        )
        await asyncio.sleep(0.15)
        after_state = await page_state(ctl.page)
        count = guard.observe((kind, handle or label, str(value), selected_by), before_state, after_state)
        if count >= guard.limit:
            diagnostics = {
                "reason": "equivalent_action_without_state_change",
                "attempts": count, "limit": guard.limit,
                "action": kind, "target": label, "control_handle": handle,
                "selection_source": selected_by, "state_fingerprint": after_state,
                "validation": await validation_state(ctl.page),
                "execution_error": error,
            }
            ctl.harness_diagnostics.append(diagnostics)
            await ctl.record("no_progress", diagnostics)
            raise NoProgress(diagnostics)
        return error is None

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
                observed_state = await page_state(active)
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
                    if await loc.count() and await loc.is_visible() and await loc.is_enabled():
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
                    and await login.is_visible()
                    and await login.is_enabled()
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
                if await accelerated.count() and await accelerated.is_visible() and await accelerated.is_enabled():
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
                    key = (frame, field_identity(row))
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
                                            "checked",
                                        )
                                    }
                                ],
                                profile,
                            )
                        )[0]
                        selected_by = "cua-s1"
                        value = prediction.get("value")
                        if prediction["action"] == "check":
                            value = "false" if value is False or str(value).lower() == "false" else "true"
                        elif prediction["action"] == "uncheck":
                            value = "false"
                        measured = (
                            value
                            if prediction["action"] in ("fill", "check", "uncheck")
                            else row["value"]
                        )
                        if str(measured) in row["options"]:
                            measured = row["option_values"][
                                row["options"].index(str(measured))
                            ]
                        ctl.semantic_decisions.append(
                            {
                                **prediction,
                                "raw_prediction": prediction,
                                "execution_status": "pending",
                                "before_value": row["value"],
                                "role": row["role"],
                                "call_index": len(usage.calls) - 1,
                                "control_handle": row["handle"],
                                "action": prediction["action"],
                                "value": measured,
                                "visible_label": row["label"],
                            }
                        )
                        current = next((r for r in await observe(frame) if r["handle"] == row["handle"]), None)
                        if current is None or field_identity(current) != field_identity(row):
                            ctl.semantic_decisions[-1]["execution_status"] = "stale_observation"
                            acted = True
                            break
                        if prediction["action"] not in ("fill", "check", "uncheck", "click", "skip"):
                            raise SpecialistOutputError("Unsupported field action")
                        if prediction["action"] == "skip":
                            ctl.semantic_decisions[-1]["execution_status"] = "skipped"
                            seen[key] = True
                            continue
                        if prediction["action"] == "fill" and row["type"] == "checkbox":
                            ctl.semantic_decisions[-1]["execution_status"] = "invalid_selection"
                            raise SpecialistOutputError("Fill action cannot toggle a checkbox")
                        if prediction["action"] in ("check", "uncheck") and row["type"] != "checkbox":
                            ctl.semantic_decisions[-1]["execution_status"] = "invalid_selection"
                            raise SpecialistOutputError("Check action requires a checkbox")
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
                    if not (cua and prediction["action"] == "click") and (value is None or str(value) in (row["value"], current_label)):
                        if cua:
                            ctl.semantic_decisions[-1]["execution_status"] = "unchanged"
                        seen[key] = True
                        continue
                    if tiny and not row["onscreen"]:
                        overflow = True
                        continue
                    kind = (
                        "click" if cua and prediction["action"] == "click" else
                        "check"
                        if row["type"] == "checkbox"
                        else "select"
                        if row["role"] == "combobox"
                        else "fill"
                    )
                    if kind == "select" and str(value) in row["option_values"]:
                        value = row["options"][row["option_values"].index(str(value))]
                    if kind == "select" and str(value) not in row["options"]:
                        if cua:
                            ctl.semantic_decisions[-1]["execution_status"] = "invalid_selection"
                        await ctl.record(
                            "invalid_model_selection",
                            {
                                "field": row["label"],
                                "value": value,
                                "selection_source": selected_by,
                            },
                        )
                        seen[key] = True
                        continue
                    if cua and prediction["action"] == "click":
                        kind = "click"
                    if row["type"] == "choicegroup" and kind == "select":
                        executed = await perform(
                            row["locator"].get_by_role(
                                "radio", name=str(value), exact=True
                            ),
                            str(value),
                            str(value),
                            "click",
                            selected_by,
                            row["handle"],
                            observed_field=row,
                        )
                    else:
                        executed = await perform(
                            row["locator"], row["label"], str(value), kind, selected_by, observed_field=row
                        )
                    if cua and executed is not None:
                        ctl.semantic_decisions[-1]["execution_status"] = "executed" if executed else "failed"
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
                # Re-observe asynchronous screen transitions before navigation. A button
                # can appear after the field snapshot (for example a Link return),
                # otherwise newly revealed saved fields can be skipped entirely.
                if await page_state(active) != observed_state:
                    acted = True
                    break
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
                        if await page_state(active) != observed_state:
                            acted = True
                            break
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
    diagnostics = {"reason": "observation_budget_exhausted", "selection_source": "deterministic_controller", "validation": await validation_state(ctl.page)}
    ctl.harness_diagnostics.append(diagnostics)
    await ctl.record("no_progress", diagnostics)
    raise NoProgress(diagnostics)
