"""Real Chromium regression checks for evaluator-only coordinate replay.

Synthetic target points and DOM setup are test oracles, never model input.
These tests do not construct adapters or load/invoke any local model.
"""
from html import escape

from playwright.async_api import async_playwright
import pytest

from scripts.diagnostics import venus_coordinate_audit as audit


VIEWPORT = {"width": 320, "height": 200}


def document(button_action):
    return f'''<!doctype html><style>
      * {{box-sizing:border-box}} body {{margin:0;background:white}}
      #target {{position:absolute;left:20px;top:20px;width:120px;height:40px}}
      #wrong {{position:absolute;left:190px;top:20px;width:110px;height:40px}}
      </style><input id="target" value="before">
      <button id="wrong" onmousedown="event.preventDefault()"
        onclick="{button_action}">Other action</button>'''


async def configure_fixture(monkeypatch, tmp_path, pw, html):
    """Patch only fixture acquisition; exercise the real replay/execute path."""
    contexts = []

    async def fresh_page(browser, client, base_url, group):
        context = await browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
        contexts.append(context)
        page = await context.new_page()
        await page.set_content(html)
        # Deliberately preexisting target focus tests whether an unrelated click
        # can be misclassified merely because focus survived on the input.
        for frame in page.frames:
            if await frame.locator("#target").count() == 1:
                await frame.locator("#target").focus()
        return context, page

    reference_browser = await pw.chromium.launch(headless=True)
    try:
        context, page = await fresh_page(reference_browser, None, None, None)
        original = tmp_path / "original.png"
        await page.screenshot(path=str(original))
        await context.close()
    finally:
        await reference_browser.close()
    contexts.clear()
    monkeypatch.setattr(audit, "fixture_page", fresh_page)
    return {"original_image": str(original)}, contexts


def candidate(point):
    return {"point": list(point), "valid": True, "source_size": [320, 200]}


@pytest.mark.parametrize("button_action,connected,focused", [
    ("document.querySelector('#target').focus()", True, True),
    ("document.querySelector('#target').remove()", False, False),
    ("document.querySelector('#target').value='changed';document.querySelector('#target').focus()", True, True),
])
async def test_wrong_browser_point_cannot_succeed_from_focus_removal_or_unrelated_state_change(
    monkeypatch, tmp_path, button_action, connected, focused
):
    async with async_playwright() as pw:
        group, contexts = await configure_fixture(monkeypatch, tmp_path, pw, document(button_action))
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"wrong": candidate((240, 40))}, tmp_path)
    row = rows["wrong"]
    assert row["status"] == "executed"
    assert row["frame_pixels_equal"] is True
    assert row["physical_pointer_verified"] is True
    assert row["target_hit"] is False
    assert row["target_received_click"] is False
    assert row["after"]["target_still_connected"] is connected
    assert row["after"]["focus_correct"] is focused
    assert row["interaction_success"] is False
    assert len(contexts) == 1
    assert not contexts[0].pages


async def test_correct_browser_point_is_hit_and_success_in_independent_contexts(monkeypatch, tmp_path):
    async with async_playwright() as pw:
        group, contexts = await configure_fixture(monkeypatch, tmp_path, pw, document(""))
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"first": candidate((80, 40)), "second": candidate((80, 40))}, tmp_path)
    assert len(contexts) == 2
    assert contexts[0] is not contexts[1]
    assert all(not context.pages for context in contexts)
    for row in rows.values():
        assert row["status"] == "executed"
        assert row["frame_pixels_equal"] is True
        assert row["target_hit"] is True
        assert row["physical_pointer_verified"] is True
        assert row["target_received_click"] is True
        assert row["after"]["focus_correct"] is True
        assert row["interaction_success"] is True


async def test_real_document_navigation_failure_is_retained_and_next_candidate_runs(monkeypatch, tmp_path):
    # A real navigation discards window.__coordinateAudit, making the post-click
    # assessment fail. Its row must survive and the next fresh context must run.
    html = document("location.href='about:blank?coordinate-audit-navigation=1'")
    async with async_playwright() as pw:
        group, contexts = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"navigation": candidate((240, 40)), "following": candidate((80, 40))}, tmp_path)
    assert list(rows) == ["navigation", "following"]
    failed = rows["navigation"]
    assert failed["status"] == "browser_execution_failure"
    assert failed["interaction_success"] is False
    assert failed["target_hit"] is False
    assert failed["error_type"]
    assert failed["error"]
    assert rows["following"]["status"] == "executed"
    assert rows["following"]["target_hit"] is True
    assert rows["following"]["interaction_success"] is True
    assert len(contexts) == 2
    assert all(not context.pages for context in contexts)


async def test_iframe_target_uses_main_viewport_box_and_maps_owner_events(monkeypatch, tmp_path):
    child = document("")
    html = f"<style>body{{margin:0}}</style><iframe style='position:absolute;left:60px;top:50px;width:200px;height:140px;border:3px solid black' srcdoc='{escape(child, quote=True)}'></iframe>"
    async with async_playwright() as pw:
        group, contexts = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"inside": candidate((120, 90)),
                                   "outside_frame": candidate((30, 20)),
                                   "wrong_inside_frame": candidate((230, 90))}, tmp_path)
    correct = rows["inside"]
    assert correct["status"] == "executed"
    annotation = correct["annotation"]
    assert annotation["frame"]["is_main"] is False
    assert annotation["bbox_local"] == {"x": 20, "y": 20, "width": 120, "height": 40}
    assert annotation["bbox"] == {"x": 83, "y": 73, "width": 120, "height": 40}
    assert annotation["frame_offset"] == {"x": 63, "y": 53}
    assert correct["target_hit"] is True
    assert correct["interaction_success"] is True
    assert correct["physical_pointer_verified"] is True
    assert correct["pointer_verification_source"] == "owner_frame"
    down = next(e for e in correct["after"]["events"] if e["type"] == "mousedown")
    assert [down["clientX"], down["clientY"]] == [57, 37]
    assert [down["main_clientX"], down["main_clientY"]] == [120, 90]
    for name, source in [("outside_frame", "main_document"), ("wrong_inside_frame", "owner_frame")]:
        row = rows[name]
        assert row["status"] == "executed"
        assert row["target_hit"] is False
        assert row["physical_pointer_verified"] is True
        assert row["pointer_verification_source"] == source
        assert row["interaction_success"] is False
    assert len(contexts) == 3
    assert all(not context.pages for context in contexts)


async def test_open_shadow_target_composed_events_and_deep_focus(monkeypatch, tmp_path):
    html = """<style>body{margin:0}#wrong{position:absolute;left:190px;top:20px;width:110px;height:40px}</style>
      <div id="host"></div><button id="wrong">Other</button><script>
      document.querySelector('#host').attachShadow({mode:'open'}).innerHTML=
      '<input id="target" style="position:fixed;box-sizing:border-box;left:20px;top:20px;width:120px;height:40px" value="before">';
      </script>"""
    async with async_playwright() as pw:
        group, contexts = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"correct": candidate((80, 40)), "wrong": candidate((240, 40))}, tmp_path)
    correct = rows["correct"]
    assert correct["status"] == "executed"
    assert correct["annotation"]["match_count"] == 1
    assert correct["annotation"]["frame"]["is_main"] is True
    assert correct["target_hit"] is True
    assert correct["physical_pointer_verified"] is True
    assert correct["target_received_click"] is True
    assert correct["after"]["focus_correct"] is True
    assert correct["after"]["focused_id"] == "target"
    assert correct["interaction_success"] is True
    assert rows["wrong"]["status"] == "executed"
    assert rows["wrong"]["physical_pointer_verified"] is True
    assert rows["wrong"]["target_hit"] is False
    assert rows["wrong"]["interaction_success"] is False
    assert len(contexts) == 2


async def test_ambiguous_target_is_retained_as_error_instead_of_chosen(monkeypatch, tmp_path):
    child = document("")
    html = child + f"<iframe srcdoc='{escape(child, quote=True)}'></iframe>"
    async with async_playwright() as pw:
        group, _ = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"ambiguous": candidate((80, 40))}, tmp_path)
    row = rows["ambiguous"]
    assert row["status"] == "browser_execution_failure"
    assert row["interaction_success"] is False
    assert row["target_hit"] is False
    assert "unique" in row["error"]
    assert "found 2" in row["error"]


async def test_wrong_physical_button_programmatic_target_click_is_not_success(monkeypatch, tmp_path):
    html = document("document.querySelector('#target').click()")
    async with async_playwright() as pw:
        group, _ = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"wrong": candidate((240, 40))}, tmp_path)
    row = rows["wrong"]
    assert row["status"] == "executed"
    assert row["physical_pointer_verified"] is True
    assert row["target_hit"] is False
    assert row["after"]["focus_correct"] is True
    assert any(e["type"] == "click" and e["target_match"] and not e["isTrusted"]
               for e in row["after"]["events"])
    assert row["associated_physical_delivery"] is False
    assert row["target_received_click"] is False
    assert row["interaction_success"] is False


async def test_trusted_checkbox_label_delivery_remains_success(monkeypatch, tmp_path):
    html = """<style>body{margin:0}#target{position:absolute;left:20px;top:20px;width:40px;height:40px}
      label{position:absolute;left:190px;top:20px;width:110px;height:40px}</style>
      <input type="checkbox" id="target"><label for="target">Target label</label>"""
    async with async_playwright() as pw:
        group, _ = await configure_fixture(monkeypatch, tmp_path, pw, html)
        rows = await audit.replay(pw, None, "unused", group,
                                  {"evaluation_selector": "#target"},
                                  {"label": candidate((240, 40))}, tmp_path)
    row = rows["label"]
    assert row["status"] == "executed"
    assert row["target_hit"] is False
    assert row["physical_pointer_verified"] is True
    assert row["associated_physical_delivery"] is True
    assert row["after"]["checked"] is True
    assert row["interaction_success"] is True
