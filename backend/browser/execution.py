import asyncio, io, re, time
from PIL import Image
from backend.adapters.base import Usage, Stopped

VIEWPORT = {"width": 1280, "height": 900}


async def extract(page):
    elements = []
    for frame_no, frame in enumerate(page.frames):
        rows = await frame.locator("input,select,textarea").evaluate_all(
            """els=>els.filter(e=>e.getBoundingClientRect().width>0&&!e.disabled).map((e,i)=>({id:e.id,label:e.labels?.[0]?.innerText||e.getAttribute('aria-label')||e.placeholder||'',name:e.name,type:e.type,tag:e.tagName.toLowerCase(),value:e.value,required:e.required,options:e.tagName==='SELECT'?[...e.options].map(o=>o.value):[]}))"""
        )
        for row in rows:
            row["frame"] = frame_no
            row["element_id"] = f"{frame_no}:{row['id']}"
            elements.append(row)
    return elements


def profile_values(profile):
    result = {k: v for k, v in profile.items() if isinstance(v, str)}
    result.update(profile.get("card", {}))
    result.update({"billing_" + k: v for k, v in profile.get("billing", {}).items()})
    return result


async def reference(page, task, ctl, mode="reference"):
    """Generic DOM controller. Receives only the public task, never a scenario/evaluator."""
    from backend.adapters.specialists import CuaS1Adapter, TinyClickAdapter

    use_cua = mode in ("cua-s1", "hybrid")
    use_tiny = mode in ("tinyclick", "hybrid")
    cua = CuaS1Adapter() if use_cua else None
    tiny = TinyClickAdapter() if use_tiny else None
    p = task["profile"]
    desired = task["payment_request"]
    pv = profile_values(p)
    usage = Usage()
    if (cua and cua.endpoint) or (tiny and tiny.endpoint):
        usage.cost_kind = "not_reported"
    ctl.usage = usage

    async def click(locator, description):
        await ctl.check()
        await locator.scroll_into_view_if_needed()
        if tiny:
            image = Image.open(io.BytesIO(await page.screenshot()))
            start = time.perf_counter()
            prediction = await tiny.ground(image, description)
            usage.inference_seconds += time.perf_counter() - start
            box = await locator.bounding_box()
            correct = bool(
                box
                and box["x"] <= prediction["x"] <= box["x"] + box["width"]
                and box["y"] <= prediction["y"] <= box["y"] + box["height"]
            )
            ctl.groundings.append(correct)
            await page.mouse.click(prediction["x"], prediction["y"])
            await ctl.record(
                "grounded_click",
                {
                    "target": description,
                    "prediction": prediction,
                    "grounding_correct": correct,
                },
            )
        else:
            await locator.click()
            await ctl.record("click", {"target": description})
        await page.locator("button:disabled").first.wait_for(state="hidden")

    for step in range(ctl.max_steps):
        await ctl.check()
        if await page.get_by_role(
            "heading", name="Ready for payment authorisation"
        ).count():
            return usage
        if await page.locator("#shipping").count():
            same = page.get_by_label("Billing address is the same as shipping")
            if (
                task.get("separate_billing")
                and await same.count()
                and await same.is_checked()
            ):
                await click(same, "Billing address is the same as shipping checkbox")
            elements = await extract(page)
            mappings = {}
            if cua:
                start = time.perf_counter()
                predictions = await cua.score_fields(elements, p)
                usage.inference_seconds += time.perf_counter() - start
                mappings = {x["element_id"]: x for x in predictions}
            acted = False
            for el in elements:
                await ctl.check()
                if el["type"] in ("checkbox", "radio"):
                    continue
                key = el["name"] or el["id"]
                value = pv.get(key)
                pred = mappings.get(el["element_id"])
                if cua:
                    if not pred or pred["action"] != "fill":
                        continue
                    value = pred.get("value")
                    expected = pv.get(key)
                    if expected is not None:
                        ctl.classifications.append(str(value) == str(expected))
                if value is None or el["value"] == str(value):
                    continue
                locator = page.frames[el["frame"]].locator('[id="' + el["id"] + '"]')
                try:
                    if el["tag"] == "select":
                        if value not in el["options"]:
                            continue
                        await locator.select_option(label=str(value))
                    else:
                        await locator.fill(str(value))
                    await ctl.record(
                        "fill",
                        {
                            "field": el["label"],
                            "confidence": pred.get("confidence") if pred else None,
                            "entity_key": pred.get("entity_key") if pred else key,
                            "value": str(value),
                        },
                    )
                    acted = True
                except Exception as e:
                    await ctl.record(
                        "invalid_action",
                        {"field": el["label"], "reason": type(e).__name__},
                    )
            # Re-extract after state changes so a newly enabled city can be selected.
            if acted:
                continue
            await click(
                page.get_by_role("button", name="Continue to payment →"),
                "Continue to payment",
            )
        elif (
            await page.get_by_role("button", name="Open secure checkout").count()
            and not await page.get_by_role("dialog").count()
        ):
            await click(
                page.get_by_role("button", name="Open secure checkout"),
                "Open secure checkout",
            )
        elif await page.get_by_role("button", name="Retry payment", exact=True).count():
            await click(
                page.get_by_role("button", name="Retry payment", exact=True),
                "Retry payment",
            )
        elif await page.get_by_role(
            "button", name="Continue to authorisation preview"
        ).count():
            await click(
                page.get_by_role("button", name="Continue to authorisation preview"),
                "Continue to authorisation preview",
            )
        elif await page.get_by_role("radiogroup", name="Payment method").count():
            label = {
                "upi_app": "UPI apps",
                "upi_qr": "Scan and pay",
                "card": "Credit/Debit/ATM card",
                "upi_vpa": "UPI ID (legacy)",
            }[desired["method"]]
            choice = page.get_by_role("radio", name=label, exact=True)
            if await choice.get_attribute("aria-checked") != "true":
                await click(choice, label)
                continue
            if desired["method"] == "upi_app":
                choice = page.get_by_role("radio", name=desired["app"], exact=True)
                if await choice.get_attribute("aria-checked") != "true":
                    await click(choice, desired["app"])
                    continue
            elif desired["method"] == "upi_vpa":
                await page.get_by_label("Synthetic UPI ID").fill(p["upiVpa"])
                await ctl.record("fill", {"field": "Synthetic UPI ID"})
            elif desired["method"] == "card":
                for key, label in [
                    ("cardName", "Name on card"),
                    ("cardNumber", "Test card number"),
                    ("expiry", "Expiry (MM/YY)"),
                    ("cvv", "Test CVV"),
                ]:
                    await ctl.check()
                    await (
                        page.frame_locator("iframe")
                        .get_by_label(label, exact=True)
                        .fill(p["card"][key])
                    )
                    await ctl.record("fill", {"field": label})
            await click(page.locator("#pay"), "Prepare or retry simulated payment")
        else:
            await asyncio.sleep(0.15)
    return usage


async def visual_agent(page, task, ctl, model):
    from backend.adapters.specialists import MaiUIAdapter, VenusAdapter
    from backend.browser.visual import run_visual

    adapter = (MaiUIAdapter if model == "mai-ui" else VenusAdapter)(
        max_tokens=ctl.run["config"]["max_tokens"]
    )
    return await run_visual(page, task, ctl, adapter, model)
