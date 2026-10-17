"""Independent coordinate/executor audit. All native outputs are scripted.

Real Chromium tests prove coordinate delivery and focus, not model grounding or
benchmark success. Oracle DOM reads occur only in test assertions/setup, never in
adapter inputs. No local model is loaded by this module.
"""
from collections import defaultdict
from fractions import Fraction
import base64
import io

import httpx
from PIL import Image
import pytest

from backend.adapters.specialists import SpecialistOutputError
from backend.adapters.venus import VenusAdapter, image_size_for_model, parse_venus_action
from backend.browser.visual import run_visual, validate_action


def native(expression):
    return f"<think>Scripted executor audit only</think><action>{expression}</action>"


def rational_pixel(value, dimension):
    """Independent exact arithmetic oracle; do not copy float/int conversion."""
    return min(dimension - 1, Fraction(str(value)) * dimension // 1000)


@pytest.mark.parametrize("size", [(1280, 900), (1920, 480), (480, 1920), (390, 844), (101, 99), (1, 1)])
@pytest.mark.parametrize("point", [(0, 0), (1000, 1000), (291, 951), (499.9, 500.1), (0.999, 999.999)])
def test_native_normalized_coordinates_match_exact_arithmetic_across_aspect_ratios(size, point):
    expected = tuple(rational_pixel(v, d) for v, d in zip(point, size))
    # Deliberately different processor shapes must never change normalized space.
    for model_size in [None, (32, 32), image_size_for_model(size)]:
        for name in ["Click", "DoubleClick", "Hover", "LongPress"]:
            action = parse_venus_action(native(f"{name}(box={point!r})"), size, model_size)
            assert (action["x"], action["y"]) == expected
            validate_action(action, size)
        drag = parse_venus_action(native(f"Drag(start={point!r}, end=(1000, 0))"), size, model_size)
        assert drag["start"] == expected
        assert drag["end"] == (size[0] - 1, 0)
        validate_action(drag, size)


@pytest.mark.parametrize("point", ["(-0.0001, 500)", "(1000.0001, 500)", "(500, -0.0001)",
                                    "(500, 1000.0001)", "(True, 1)", "(1, False)",
                                    "(1e999, 1)", "(1, -1e999)", "('500', 2)", "(1,)", "(1, 2, 3, 4)"])
def test_bounds_and_shape_rejected_for_every_native_spatial_argument(point):
    expressions = [f"{name}(box={point})" for name in ["Click", "DoubleClick", "Hover", "LongPress"]]
    expressions += [f"Drag(start={point}, end=(1, 2))", f"Drag(start=(1, 2), end={point})"]
    for expression in expressions:
        raw = native(expression)
        with pytest.raises(SpecialistOutputError) as caught:
            parse_venus_action(raw, (390, 844), (384, 832))
        assert caught.value.raw_text == raw


def test_native_list_pairs_and_fractional_rounding_use_original_screenshot():
    # The floor differs from round-to-nearest, and from resized-image mapping.
    action = parse_venus_action(native("Click(box=[499.9, 500.1])"), (101, 99), (256, 256))
    assert (action["x"], action["y"]) == (50, 49)
    assert parse_venus_action(native("Click(box=(999.999,1000))"), (101, 99))["x"] == 100


class ScriptedNativeExecutor(VenusAdapter):
    """Actual adapter preparation/parsing with a literal transport test double."""
    def __init__(self, expressions):
        super().__init__(max_tokens=16)
        self.expressions = iter(expressions)
        self.payloads = []
        self.inputs = []

    def metadata(self):
        return {"inference_kind": "scripted_native_executor_test", "actual_model": False}

    async def _request(self, payload):
        self.payloads.append(payload)
        return {"raw_text": native(next(self.expressions))}

    async def act(self, image, task, history):
        self.inputs.append((image.size, task, history))
        action = await super().act(image, task, history)
        # The production transport marks a completed response as actual inference;
        # this explicit replacement must never be mistaken for inference evidence.
        self.last_metrics.update(actual_model=False, inference_kind="scripted_native_executor_test")
        return action


class AuditControls:
    def __init__(self, directory, size, max_steps):
        self.directory = directory
        self.max_steps = max_steps
        self.run = {"viewport": {"width": size[0], "height": size[1]}, "success": False}
        self.timings = defaultdict(float)
        self.events = []

    async def check(self):
        pass

    async def record(self, kind, detail):
        self.events.append((kind, detail))


@pytest.mark.parametrize("size", [(1280, 900), (1920, 480), (480, 1920), (390, 844), (101, 99)])
async def test_chromium_native_click_delivers_original_pixels_and_focuses_target(page, tmp_path, size):
    await page.set_viewport_size({"width": size[0], "height": size[1]})
    # Percentage positions deliberately differ between axes and survive resize.
    await page.set_content('''<style>*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}
      input{position:absolute;left:25%;top:62%;width:14%;height:10%;padding:0;border:0}
      #edge{position:fixed;right:0;bottom:0;width:2px;height:2px}</style>
      <input id="target" aria-label="Audit target"><button id="edge"></button>
      <script>window.audit=[]; document.addEventListener('mousedown', e =>
      audit.push({x:e.clientX,y:e.clientY,id:e.target.id}));</script>''')
    assert await page.evaluate("devicePixelRatio") == 1
    adapter = ScriptedNativeExecutor(["Click(box=(291,651))", "Type(content='executor proof')",
                                      "Click(box=(1000,1000))", "Finished(content='executor test')"])
    ctl = AuditControls(tmp_path, size, 4)
    usage = await run_visual(page, {"instruction": "Scripted executor test only"}, ctl, adapter, "ui-venus")
    expected = [rational_pixel(291, size[0]), rational_pixel(651, size[1])]
    assert await page.evaluate("audit") == [
        {"x": expected[0], "y": expected[1], "id": "target"},
        {"x": size[0] - 1, "y": size[1] - 1, "id": "edge"},
    ]
    # insert_text can succeed only if the physical first click focused this input.
    assert await page.locator("#target").input_value() == "executor proof"
    assert await page.evaluate("document.activeElement.id") == "edge"
    assert all(observed == size for observed, _, _ in adapter.inputs)
    for payload in adapter.payloads:
        prepared = Image.open(io.BytesIO(base64.b64decode(payload["image_base64"])))
        assert prepared.size == tuple(payload["image_size"]) == image_size_for_model(size)
    assert all(call["actual_model"] is False for call in usage.calls)
    assert ctl.run["success"] is False
    assert [row[1]["action"] for row in ctl.events] == ["click", "type", "click"]


async def test_unmodified_checkout_native_coordinate_click_focuses_public_email_field(server, page, tmp_path):
    """Public DOM chooses a scripted test point: executor proof, never grounding."""
    async with httpx.AsyncClient() as client:
        result = await client.post(server + "/api/preview/T01")
        result.raise_for_status()
        preview = result.json()
    await page.goto(preview["url"])
    email = page.locator('input[type="email"]').first
    await email.wait_for(state="visible")
    box = await email.bounding_box()
    size = Image.open(io.BytesIO(await page.screenshot())).size
    # A DOM oracle supplies the point in this test only. It is never model input.
    x = (box["x"] + box["width"] / 2) * 1000 / size[0]
    y = (box["y"] + box["height"] / 2) * 1000 / size[1]
    adapter = ScriptedNativeExecutor([f"Click(box=({x!r},{y!r}))", "Type(content='coordinate-audit@example.test')", "Finished()"])
    ctl = AuditControls(tmp_path, size, 3)
    await run_visual(page, {"instruction": "Enter the scripted test email, then stop."}, ctl, adapter, "ui-venus")
    assert await email.input_value() == "coordinate-audit@example.test"
    assert all("box" not in task and "dom_ids" not in task for _, task, _ in adapter.inputs)
    assert ctl.run["success"] is False


async def test_popup_native_coordinates_follow_active_screenshot_dimensions(page, tmp_path):
    await page.set_content("<button>Parent</button>")
    async with page.expect_popup() as opened:
        await page.evaluate("window.open('about:blank', 'audit-popup', 'width=730,height=510')")
    popup = await opened.value
    await popup.set_content('<style>body{margin:0}input{position:fixed;left:40%;top:40%;width:20%;height:20%}</style><input id="popup-target">')
    actual_size = Image.open(io.BytesIO(await popup.screenshot())).size
    assert await popup.evaluate("devicePixelRatio") == 1
    adapter = ScriptedNativeExecutor(["Click(box=(500,500))", "Type(content='popup proof')", "Finished()"])
    ctl = AuditControls(tmp_path, (1280, 900), 3)
    await run_visual(page, {"instruction": "Scripted popup executor test."}, ctl, adapter, "ui-venus")
    assert await popup.locator("#popup-target").input_value() == "popup proof"
    assert ctl.page == popup
    assert actual_size == (730, 510)
    assert popup.viewport_size == {"width": 730, "height": 510}
    assert await popup.evaluate("[innerWidth, innerHeight, devicePixelRatio]") == [730, 510, 1]
    assert ctl.run["visual_protocol"]["viewport"] == {"width": 730, "height": 510}
    assert ctl.run["visual_protocol"]["initial_viewport"] == {"width": 1280, "height": 900}
    assert all(size == actual_size for size, _, _ in adapter.inputs)
    assert ctl.events[0][1]["x"] == rational_pixel(500, actual_size[0])
    assert ctl.events[0][1]["y"] == rational_pixel(500, actual_size[1])


@pytest.mark.parametrize("size", [(20000, 100), (100, 20000)])
def test_extreme_ratio_rejects_unrepresentable_pixel_cap_instead_of_overshooting(size):
    # Accepted ratio 200 plus a 32px minimum short side previously produced
    # 115712 pixels despite the explicit 65536 cap.
    with pytest.raises(ValueError):
        image_size_for_model(size, max_pixels=65536)


async def test_chromium_dpr_two_uses_css_screenshot_coordinates_and_focuses_target(page, tmp_path):
    """Executor-only: real DPR 2 browser, scripted native output, no inference."""
    viewport = {"width": 390, "height": 844}
    context = await page.context.browser.new_context(viewport=viewport, device_scale_factor=2)
    try:
        high_dpr_page = await context.new_page()
        await high_dpr_page.set_content('''<style>html,body{margin:0;width:100%;height:100%;overflow:hidden}
          input{position:absolute;left:25%;top:62%;width:14%;height:10%;padding:0;border:0}</style>
          <input id="target" aria-label="DPR audit target">
          <script>window.audit=[]; document.addEventListener('mousedown', e =>
          audit.push({x:e.clientX,y:e.clientY,id:e.target.id}));</script>''')
        assert high_dpr_page.viewport_size == viewport
        assert await high_dpr_page.evaluate("[innerWidth, innerHeight, devicePixelRatio]") == [390, 844, 2]
        # Establish that unscaled capture really has a physical-pixel mismatch.
        assert Image.open(io.BytesIO(await high_dpr_page.screenshot())).size == (780, 1688)
        adapter = ScriptedNativeExecutor(["Click(box=(291,651))", "Type(content='DPR two proof')", "Finished()"])
        ctl = AuditControls(tmp_path, (390, 844), 3)
        usage = await run_visual(high_dpr_page, {"instruction": "Scripted DPR executor test only."}, ctl, adapter, "ui-venus")
        assert await high_dpr_page.evaluate("audit") == [{"x": 113, "y": 549, "id": "target"}]
        assert await high_dpr_page.locator("#target").input_value() == "DPR two proof"
        assert await high_dpr_page.evaluate("document.activeElement.id") == "target"
        assert all(size == (390, 844) for size, _, _ in adapter.inputs)
        assert all(Image.open(path).size == (390, 844) for path in (tmp_path / "observations").glob("*.png"))
        assert all(call["input"]["image_size"] == [390, 844] for call in usage.calls)
        assert ctl.run["visual_protocol"]["viewport"] == viewport
        assert ctl.run["visual_protocol"]["screenshot_scale"] == "css"
        assert all(call["actual_model"] is False for call in usage.calls)
        assert ctl.run["success"] is False
    finally:
        await context.close()
