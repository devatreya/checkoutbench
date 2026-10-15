import asyncio, copy, json
import httpx, pytest
from scenarios.catalog import scenario, task
from scenarios.v21 import V21_SPECS
from backend.workflows_v21 import init, public, transition, evaluate
from tests.test_v2 import run_batch


def test_task_is_independent_of_private_answers():
    s = scenario("V21-R01", 2026)
    before = task(s)
    poisoned = copy.deepcopy(s)
    poisoned["expected_values"] = {k: "PRIVATE_SENTINEL" for k in s["expected_values"]}
    poisoned["expected_outcome"] = "PRIVATE_OUTCOME"
    poisoned["dom_ids"] = {k: "PRIVATE_MAPPING" for k in s["dom_ids"]}
    poisoned["fields"] = [{"key": "PRIVATE_FIELD", "label": "PRIVATE_LABEL"}]
    assert task(poisoned) == before
    assert "preferences" not in before
    for forbidden in (
        "expected_values",
        "dom_ids",
        "expected_outcome",
        "fault",
        "required_fields",
    ):
        assert forbidden not in before


def test_website_exposes_opaque_action_handles_only():
    for row in V21_SPECS:
        s = scenario(row["id"])
        st = init(s)
        d = public(st, "token")
        assert (
            not {"expected_values", "dom_ids", "expected_outcome", "fault", "profile"}
            & d.keys()
        )
        assert all(
            f["key"].startswith("f") and len(f["key"]) == 15 for f in d["fields"]
        )
        with pytest.raises(Exception):
            transition(st, "input", {"values": {"name": "SECRET"}}, "token")


def test_payment_platform_rules():
    for row in V21_SPECS:
        s = scenario(row["id"])
        assert s["device_supported"]
        if s["platform"] == "desktop_web":
            assert (
                "upi_app" not in s["supported_payment_methods"]
                and "upi_vpa" not in s["supported_payment_methods"]
            )
        if s["family"] == "link":
            assert (
                s["customer_brief"]["customer"]["shipping"]["country"]
                == "United States"
            )
    assert "upi_vpa" in scenario("V21-CF04")["supported_payment_methods"]


async def test_v21_smoke(server):
    rows = await run_batch(
        server,
        [
            "V21-S01",
            "V21-S02",
            "V21-S06",
            "V21-R01",
            "V21-L01",
            "V21-ST02",
            "V21-RZ01",
            "V21-CF02",
            "V21-G03",
            "V21-E04",
        ],
        timeout=35,
    )
    assert all(r["success"] for r in rows), [
        (
            r["scenario"],
            r["failure_reason"],
            r.get("error"),
            r["completion_stage"],
            r["field_results"],
            r["optional_results"],
        )
        for r in rows
        if not r["success"]
    ]


async def test_v21_all_reference_paths(server):
    rows = await run_batch(server, [s["id"] for s in V21_SPECS], timeout=45)
    assert all(r["success"] for r in rows), [
        (
            r["scenario"],
            r["failure_reason"],
            r.get("error"),
            r["completion_stage"],
            r["field_results"],
            r["optional_results"],
        )
        for r in rows
        if not r["success"]
    ]


class SpyControls:
    def __init__(self, page, limit=1):
        from collections import defaultdict

        self.page = page
        self.max_steps = 10
        self.events = []
        self.groundings = []
        self.limit = limit
        self.timings = defaultdict(float)

    async def check(self):
        from backend.adapters.base import Stopped

        if len(self.events) >= self.limit:
            raise Stopped("test action limit")

    async def record(self, kind, detail):
        self.events.append((kind, detail))

    async def assess_grounding(self, loc, prediction):
        box = await loc.bounding_box()
        self.groundings.append(
            box["x"] <= prediction["x"] <= box["x"] + box["width"]
            and box["y"] <= prediction["y"] <= box["y"] + box["height"]
        )


class WrongCua:
    key = "cua-s1"
    last_metrics = {"backend": "test-double"}

    def __init__(self):
        self.inputs = []

    async def score_fields(self, elements, profile):
        self.inputs.append((elements, profile))
        return [{"action": "fill", "value": profile["customer"]["shipping"]["city"]}]


class WrongTiny:
    key = "tinyclick"
    last_metrics = {"backend": "test-double"}

    def __init__(self):
        self.inputs = []

    async def ground(self, image, prompt):
        self.inputs.append((image.size, prompt))
        return {
            "x": 400,
            "y": 110,
        }  # visibly wrong second field, not the recipient input


@pytest.mark.parametrize("mode", ["cua-s1", "tinyclick", "hybrid"])
async def test_wrong_model_output_controls_real_execution(page, mode):
    from backend.browser.v21 import reference_v21
    from backend.adapters.base import Stopped

    await page.set_content(
        '<style>input{position:absolute;left:20px;top:20px;width:480px;height:35px}#other{top:90px}</style><input id="opaque_random_7" aria-label="Recipient"><input id="other" aria-label="Delivery instructions">'
    )
    s = scenario("V21-G01")
    cua = WrongCua() if mode != "tinyclick" else None
    tiny = WrongTiny() if mode != "cua-s1" else None
    ctl = SpyControls(page)
    with pytest.raises(Stopped):
        await reference_v21(page, task(s), ctl, mode, cua, tiny)
    if cua:
        assert len(cua.inputs) == 1
        assert set(cua.inputs[0][0][0]) == {"label", "role", "value", "form_title"}
        assert "expected_values" not in json.dumps(cua.inputs)
        assert "opaque_random_7" not in json.dumps(cua.inputs)
        assert ctl.usage.calls[0]["model"] == "cua-s1"
    if tiny:
        assert len(tiny.inputs) == 1 and not ctl.groundings[0]
        assert await page.locator("#opaque_random_7").input_value() == ""
        assert await page.locator("#other").input_value() == (
            s["customer_brief"]["customer"]["shipping"]["city"]
            if cua
            else s["customer_brief"]["customer"]["full_name"]
        )
        assert any(c["model"] == "tinyclick" for c in ctl.usage.calls)
        assert not any(e[0] == "scroll" for e in ctl.events)
    else:
        assert (
            await page.locator("#opaque_random_7").input_value()
            == s["customer_brief"]["customer"]["shipping"]["city"]
        )
    # A controller may not repair the incorrect value from an internal answer map.
    assert (
        ctl.events[0][1]["value"] != s["customer_brief"]["customer"]["full_name"]
        if cua
        else True
    )


def test_false_completion_stale_payment_and_wrong_fields_fail():
    s = scenario("V21-L03")
    st = init(s)
    st["values"] = copy.deepcopy(s["expected_values"])
    st["stage"] = "checkout_ready"
    st["link_authenticated"] = True
    st["values"]["billing_address1"] = "stale address"
    assert not evaluate(s, st)["success"]
    s = scenario("V21-ST02")
    st = init(s)
    st["values"] = copy.deepcopy(s["expected_values"])
    st["stage"] = "payment_successful_simulation"
    assert evaluate(s, st)["failure_reason"] == "unverified_transaction"
    st["return_verified"] = True
    st["values"]["cardNumber"] = "4000000000000000"
    assert not evaluate(s, st)["success"]
    st["values"] = copy.deepcopy(s["expected_values"])
    st["values"]["name"] = "Bengaluru"
    assert not evaluate(s, st)["success"]


def test_private_routes_are_not_reachable_from_agent():
    from backend.browser.security import allowed_url

    origin = "http://127.0.0.1:8766"
    token = "123"
    for path in (
        "/api/scenarios",
        "/api/results",
        "/api/test-user/123",
        "/v21/other/state",
        "/scenarios/v21.py",
        "/api/sandboxes/stripe",
    ):
        assert not allowed_url(origin + path, origin, token)
    assert allowed_url(origin + "/v21/123/provider", origin, token)


def test_official_sandbox_gate_rejects_live_or_missing_config(monkeypatch):
    from backend.sandboxes import config
    from fastapi import HTTPException

    for provider in ("stripe", "razorpay", "cashfree", "shopify"):
        prefix = "BENCH_SANDBOX_" + provider.upper() + "_"
        monkeypatch.delenv(prefix + "ENABLED", raising=False)
        with pytest.raises(HTTPException):
            config(provider)
    monkeypatch.setenv("BENCH_SANDBOX_STRIPE_ENABLED", "1")
    monkeypatch.setenv("BENCH_SANDBOX_STRIPE_KEY", "sk_live_NOT_A_REAL_KEY")
    with pytest.raises(HTTPException):
        config("stripe")
    monkeypatch.setenv("BENCH_SANDBOX_RAZORPAY_ENABLED", "1")
    monkeypatch.setenv("BENCH_SANDBOX_RAZORPAY_KEY", "rzp_live_NOT_A_REAL_KEY")
    with pytest.raises(HTTPException):
        config("razorpay")


async def preview_page(server, page, sid):
    async with httpx.AsyncClient() as client:
        preview = (await client.post(server + "/api/preview/" + sid)).json()
    await page.goto(preview["url"])
    await page.locator("#workflow").wait_for()
    return preview


async def prepared_page(server, page, sid):
    from backend.browser.v21 import semantic_value

    preview = await preview_page(server, page, sid)
    base = "http://127.0.0.1:8766/v21/" + preview["token"]
    async with httpx.AsyncClient() as client:
        d = (await client.get(base + "/state")).json()
        vals = {
            f["key"]: semantic_value(
                f["label"], preview["task"]["profile"], f.get("options") or []
            )
            for f in d["fields"]
        }
        vals = {k: v for k, v in vals.items() if v is not None}
        await client.post(base + "/action", json={"action": "continue", "values": vals})
        await client.post(base + "/action", json={"action": "review", "values": {}})
    await page.reload()
    await page.get_by_role(
        "button", name="Launch payment gateway", exact=True
    ).wait_for()
    return preview, base


async def test_provider_boundaries_and_device_ui(server, page):
    await preview_page(server, page, "V21-ST01")
    assert await page.locator("iframe").count() == 0
    await preview_page(server, page, "V21-ST02")
    assert await page.get_by_title("Stripe-style embedded checkout").count() == 1
    await preview_page(server, page, "V21-R01")
    assert await page.locator("table.passenger-table").count() == 1
    assert await page.get_by_label("Passenger 1 gender", exact=True).count() == 1
    assert (
        await page.get_by_role("button", name="Use saved first passenger").count() == 1
    )
    for sid, kind in [
        ("V21-RZ01", "modal"),
        ("V21-CF01", "hosted"),
        ("V21-CF02", "popup"),
        ("V21-CF03", "inline"),
    ]:
        await prepared_page(server, page, sid)
        if kind == "popup":
            async with page.expect_popup() as pop:
                await page.get_by_role("button", name="Launch payment gateway").click()
            child = await pop.value
            await child.wait_for_load_state()
            assert "/provider" in child.url
            await child.close()
        else:
            await page.get_by_role("button", name="Launch payment gateway").click()
            if kind == "modal":
                await page.get_by_role("dialog", name="Standard checkout").wait_for()
                await page.get_by_role("button", name="Dismiss payment gateway").click()
                await page.get_by_role(
                    "button", name="Launch payment gateway"
                ).wait_for()
            elif kind == "hosted":
                await page.wait_for_url("**/provider")
            else:
                await page.get_by_title("Cashfree inline checkout").wait_for()


async def test_shopify_progression_and_extension_isolation(server, page):
    preview = await preview_page(server, page, "V21-S03")
    assert await page.get_by_label("Email", exact=True).count() == 1
    assert await page.get_by_label("Payment method", exact=True).count() == 1
    assert (
        await page.get_by_role("button", name="Review details", exact=True).count() == 0
    )
    extension = page.get_by_title("Merchant options sandbox")
    assert await extension.get_attribute("sandbox") == "allow-scripts"
    frame = await (await extension.element_handle()).content_frame()
    await frame.get_by_text("Merchant options", exact=False).wait_for()
    assert (
        await frame.evaluate(
            "()=>{try{return !!parent.document.body}catch(e){return false}}"
        )
        is False
    )
    await preview_page(server, page, "V21-S01")
    assert await page.get_by_label("Email", exact=True).count() == 1
    assert await page.get_by_label("Payment method", exact=True).count() == 0
    assert await page.get_by_role("button", name="Continue to shipping").count() == 1


async def test_payment_element_and_refreshed_passport_are_distinct(server, page):
    from backend.browser.v21 import semantic_value

    preview = await preview_page(server, page, "V21-ST03")
    base = "http://127.0.0.1:8766/v21/" + preview["token"]
    async with httpx.AsyncClient() as client:
        d = (await client.get(base + "/state")).json()
        vals = {
            f["key"]: semantic_value(f["label"], preview["task"]["profile"])
            for f in d["fields"]
        }
        await client.post(base + "/action", json={"action": "continue", "values": vals})
        await client.post(base + "/action", json={"action": "review", "values": {}})
    await page.reload()
    component = page.get_by_title("Isolated Payment Element")
    await component.wait_for()
    frame = await (await component.element_handle()).content_frame()
    await frame.get_by_role("radiogroup", name="Payment method").wait_for()
    assert await page.get_by_role("radiogroup", name="Payment method").count() == 0
    assert await frame.get_by_role("radio", name="Card", exact=True).count() == 1
    await preview_page(server, page, "V21-P05")
    assert await page.get_by_label("Application reference").count() == 1
    assert await page.get_by_label("Appointment centre").count() == 0
    assert await page.get_by_role("button", name="Choose appointment").count() == 1
    await preview_page(server, page, "V21-P01")
    assert await page.get_by_label("Appointment centre").count() == 1


async def test_legacy_data_routes_reject_new_sessions(server, page):
    preview = await preview_page(server, page, "V21-S01")
    origin = "http://127.0.0.1:8766"
    token = preview["token"]
    async with httpx.AsyncClient() as client:
        for path in ("/session/" + token, "/v2/" + token + "/state"):
            assert (await client.get(origin + path)).status_code == 404
        assert (
            await client.post(
                origin + "/v21/" + token + "/action",
                json={"action": "input", "values": {"postal": "560038"}},
            )
        ).status_code == 400
        for provider in ("stripe", "shopify", "razorpay", "cashfree"):
            assert (
                await client.post(
                    server + "/api/sandboxes/" + provider + "/validate", json={}
                )
            ).status_code == 409


async def test_invalid_cua_selection_stays_in_accuracy_denominator(page):
    from backend.browser.v21 import reference_v21
    from backend.evaluator.semantic import grade_decisions
    from backend.adapters.base import Stopped

    s = scenario("V21-G01")
    handle = s["dom_ids"]["payment_method"]
    await page.set_content(
        f'<label>Payment method<select id="{handle}"><option value="">Select</option><option value="card">Card</option><option value="cod">Cash on delivery</option></select></label>'
    )
    ctl = SpyControls(page)
    cua = WrongCua()
    with pytest.raises(Stopped):
        await reference_v21(page, task(s), ctl, "cua-s1", cua=cua)
    assert ctl.events[0][0] == "invalid_model_selection"
    assert grade_decisions(s, ctl.semantic_decisions) == [False]


async def test_v21_link_comparison_preserves_native_attribution(server):
    for arm in ("native_link", "agent_without_link", "agent_with_link"):
        rows = await run_batch(server, ["V21-L01", "V21-L03"], mode=arm, timeout=45)
        for row in rows:
            assert row["success"] == (
                not (arm == "native_link" and row["scenario"] == "V21-L03")
            )
            assert row["model_call_count"] == 0
            if arm == "agent_without_link":
                assert row["native_autofill_fields"] == 0
            if arm == "native_link":
                assert row["agent_actions"] == 0


async def test_tiny_scrolls_fixed_steps_without_revisiting_completed_fields(page):
    from backend.browser.v21 import reference_v21
    from backend.adapters.base import Stopped

    s = scenario("V21-G01")
    profile = task(s)
    await page.set_content(
        f'<style>body{{height:1700px}}input{{position:absolute;left:20px;width:300px;height:40px}}#a{{top:20px}}#b{{top:1100px;background:rgb(0,0,255)}}</style><input id="a" aria-label="Recipient" value="{profile["profile"]["customer"]["full_name"]}"><input id="b" aria-label="City">'
    )

    class PixelGrounder:
        key = "tinyclick"
        last_metrics = {"backend": "test-double"}

        async def ground(self, image, prompt):
            rgb = image.convert("RGB")
            points = [
                (x, y)
                for y in range(0, rgb.height, 5)
                for x in range(0, rgb.width, 5)
                if rgb.getpixel((x, y)) == (0, 0, 255)
            ]
            assert points, (
                "Controller requested grounding before target appeared in the screenshot"
            )
            x, y = points[len(points) // 2]
            return {"x": x, "y": y}

    ctl = SpyControls(page, limit=2)
    with pytest.raises(Stopped):
        await reference_v21(page, profile, ctl, "tinyclick", tiny=PixelGrounder())
    assert [kind for kind, _ in ctl.events] == ["scroll", "fill"]
    assert ctl.events[0][1]["amount"] == 500
    assert (
        await page.locator("#b").input_value()
        == profile["profile"]["customer"]["shipping"]["city"]
    )
    assert len(ctl.usage.calls) == 1


async def test_iframe_visibility_is_clipped_to_browser_screenshot(page):
    from backend.browser.v21 import observe

    await page.set_content(
        '<style>body{height:2000px}iframe{position:absolute;top:1200px;left:20px;height:200px}</style><iframe srcdoc="<input id=opaque aria-label=Recipient>"></iframe>'
    )
    frame = page.frames[-1]
    await frame.locator("input").wait_for()
    assert not (await observe(frame))[0]["onscreen"]
    await page.mouse.wheel(0, 700)
    await page.wait_for_timeout(150)
    assert (await observe(frame))[0]["onscreen"]


async def test_controller_reobserves_new_fields_before_advancing(page, monkeypatch):
    """A Link-like asynchronous return must not advance using an older field snapshot."""
    from backend.browser import v21

    original = v21.observe
    changed = False

    async def changing_screen(frame):
        nonlocal changed
        rows = await original(frame)
        if not changed:
            changed = True
            await page.set_content(
                """<details><summary>Billing · Review saved details</summary><label>Billing address<input id="opaque_billing" value="Old address"></label></details><button onclick="document.body.innerHTML='<h1>Checkout ready</h1>'">Review details</button>"""
            )
        return rows

    monkeypatch.setattr(v21, "observe", changing_screen)
    await page.set_content("<button>Review details</button>")
    ctl = SpyControls(page, limit=30)
    await v21.reference_v21(page, task(scenario("V21-L03")), ctl)
    fills = [d for k, d in ctl.events if k == "fill"]
    assert (
        fills
        and fills[0]["value"]
        == scenario("V21-L03")["customer_brief"]["customer"]["billing"]["full_address"]
    )
    assert ctl.events[-1][1]["field"] == "Review details"
