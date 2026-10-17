"""Predeclared, isolated grounding diagnostics; never a checkout policy or score.

Each native prediction is saved before evaluator-only DOM annotation. All fixed
counterfactual transforms replay that same prediction in fresh fixture contexts.
No target selector, box, expected coordinate, or replay result enters inference.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import httpx
from PIL import Image, ImageChops
from playwright.async_api import async_playwright

from backend.adapters.venus import VenusAdapter
from backend.browser.security import allowed_url
from backend.browser.visual import execute_action, validate_action
from scripts.diagnostics.venus_coordinate_math import native_point, candidate_points


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


async def fixture_page(browser, client, base_url, group):
    response = await client.post(base_url + "/api/preview/" + group["scenario"], params={"seed": 2026})
    preview = response.raise_for_status().json()
    origin = preview["url"].split("/checkout/")[0]
    context = await browser.new_context(viewport=group["viewport"], device_scale_factor=1, service_workers="block")

    async def route(request):
        if allowed_url(request.request.url, origin, preview["token"]):
            await request.continue_()
        else:
            await request.abort()

    await context.route("**/*", route)
    page = await context.new_page()
    await page.goto(preview["url"])
    await page.wait_for_timeout(600)
    if group["setup"] == "public_profile_shipping_to_payment":
        # Fixed setup for a legacy payment-stage screenshot, not model execution.
        # Uses public customer data only; never queries a grounding target box.
        profile = preview["task"]["profile"]
        for key in ("name", "email", "phone", "address1", "state", "city", "postal"):
            field = page.locator("#f_" + key)
            if key in {"state", "city"}:
                await field.select_option(label=profile[key])
            else:
                await field.fill(profile[key])
        await page.get_by_role("button", name="Continue to payment →").click()
        await page.wait_for_timeout(500)
    await page.evaluate("y=>window.scrollTo(0,y)", group["scroll_y"])
    await page.wait_for_timeout(200)
    return context, page


ANNOTATE = """target => {
 const r=target.getBoundingClientRect(), style=getComputedStyle(target);
 let center=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
 while(center?.shadowRoot) {
   const inner=center.shadowRoot.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   if(!inner||inner===center) break;
   center=inner;
 }
 const before={checked:target.checked??null,aria_checked:target.getAttribute('aria-checked'),
   value:target.value??null,expanded:target.getAttribute('aria-expanded')};
 window.__coordinateAudit={events:[],target,before};
 for(const type of ['mousedown','click','focusin','change']) document.addEventListener(type,e=>{
   const path=e.composedPath(), t=path[0]||e.target;
   window.__coordinateAudit.events.push({type,isTrusted:e.isTrusted,clientX:e.clientX??null,clientY:e.clientY??null,
     target_id:t.id||null,tag:t.tagName,
     target_match:path.some(n=>n===target||(n instanceof Node&&target.contains(n))),
     label_for_target:path.some(n=>n?.tagName==='LABEL'&&n.control===target)});
 },true);
 return {exists:true,bbox_local:{x:r.x,y:r.y,width:r.width,height:r.height},
   tag:target.tagName,type:target.type||null,role:target.getAttribute('role'),
   visible:r.width>0&&r.height>0&&style.visibility!=='hidden'&&style.display!=='none',
   disabled:!!target.disabled,center_unobscured:center===target||target.contains(center),before,
   geometry:{innerWidth,innerHeight,devicePixelRatio,scrollX,scrollY}};
}"""

AFTER = """() => {
 const audit=window.__coordinateAudit, target=audit.target, current=target.isConnected?target:null;
 const r=current?.getBoundingClientRect();
 let active=document.activeElement;
 while(active?.shadowRoot?.activeElement) active=active.shadowRoot.activeElement;
 return {events:audit.events,focus_correct:active===target||target.contains(active),
   checked:current?.checked??null,aria_checked:current?.getAttribute('aria-checked')??null,
   value:current?.value??null,expanded:current?.getAttribute('aria-expanded')??null,
   target_still_connected:target.isConnected,current_exists:!!current,
   bbox_after_local:r?{x:r.x,y:r.y,width:r.width,height:r.height}:null,
   focused_tag:active?.tagName,focused_id:active?.id||null};
}"""

MAIN_POINTER_LISTENER = """() => {
 window.__coordinateAuditMainEvents=[];
 for(const type of ['mousedown','click']) document.addEventListener(type,e=>{
   window.__coordinateAuditMainEvents.push({type,isTrusted:e.isTrusted,clientX:e.clientX,clientY:e.clientY});
 },true);
}"""


async def annotate_target(page, selector):
    """Private evaluator lookup, only after prediction persistence.

    Playwright locators pierce open shadow roots; search each frame separately,
    and insist on uniqueness rather than selecting a convenient matching box.
    bounding_box supplies main-viewport CSS coordinates, including frame offsets.
    """
    matches = []
    for index, frame in enumerate(page.frames):
        locator = frame.locator(selector)
        count = await locator.count()
        matches.extend((index, frame, locator.nth(i)) for i in range(count))
    if not matches:
        return {"exists": False, "match_count": 0}, None
    if len(matches) != 1:
        raise ValueError(f"Evaluator target must be unique across frames/shadow roots; found {len(matches)}")
    index, frame, locator = matches[0]
    annotation = await locator.evaluate(ANNOTATE)
    bbox = await locator.bounding_box()
    local = annotation["bbox_local"]
    sx = bbox["width"] / local["width"] if bbox and local["width"] else 1
    sy = bbox["height"] / local["height"] if bbox and local["height"] else 1
    offset = {"x": bbox["x"] - local["x"] * sx if bbox else 0,
              "y": bbox["y"] - local["y"] * sy if bbox else 0}
    annotation.update(bbox=bbox, match_count=1,
                      frame={"index": index, "name": frame.name, "url": frame.url,
                             "is_main": frame == page.main_frame},
                      frame_offset=offset, frame_scale={"x": sx, "y": sy})
    return annotation, frame


def events_in_main_viewport(events, annotation):
    offset, scale = annotation["frame_offset"], annotation["frame_scale"]
    return [{**event,
             "main_clientX": event["clientX"] * scale["x"] + offset["x"] if event["clientX"] is not None else None,
             "main_clientY": event["clientY"] * scale["y"] + offset["y"] if event["clientY"] is not None else None}
            for event in events]


async def replay(pw, client, base_url, group, target, candidates, directory):
    browser = await pw.chromium.launch(headless=True)
    rows = {}
    try:
        for name, candidate in candidates.items():
            context = None
            try:
                context, page = await fixture_page(browser, client, base_url, group)
                png = await page.screenshot()
                (directory / (name + "-before.png")).write_bytes(png)
                actual = Image.open(io.BytesIO(png)).convert("RGB")
                original = Image.open(ROOT / group["original_image"]).convert("RGB")
                equal = actual.size == original.size and ImageChops.difference(actual, original).getbbox() is None
                # First target DOM query: always after this target's inference.json was persisted.
                await page.evaluate(MAIN_POINTER_LISTENER)
                annotation, owner_frame = await annotate_target(page, target["evaluation_selector"])
                row = {**candidate, "annotation_at": now(), "frame_pixels_equal": equal, "annotation": annotation}
                bbox = annotation.get("bbox")
                point = candidate["point"]
                row["target_hit"] = bool(equal and candidate["valid"] and bbox and
                    bbox["x"] <= point[0] < bbox["x"] + bbox["width"] and
                    bbox["y"] <= point[1] < bbox["y"] + bbox["height"])
                if equal and annotation.get("exists") and candidate["valid"]:
                    action = {"action": "click", "x": point[0], "y": point[1]}
                    validate_action(action, actual.size)
                    started = time.perf_counter()
                    await execute_action(page, action)
                    await page.wait_for_timeout(250)
                    row["browser_seconds"] = time.perf_counter() - started
                    row["after"] = await owner_frame.evaluate(AFTER)
                    after = row["after"]
                    after["events"] = events_in_main_viewport(after["events"], annotation)
                    local_after = after["bbox_after_local"]
                    scale, offset = annotation["frame_scale"], annotation["frame_offset"]
                    after["bbox_after"] = ({"x": local_after["x"] * scale["x"] + offset["x"],
                                             "y": local_after["y"] * scale["y"] + offset["y"],
                                             "width": local_after["width"] * scale["x"],
                                             "height": local_after["height"] * scale["y"]}
                                            if local_after else None)
                    after["main_document_events"] = await page.evaluate("window.__coordinateAuditMainEvents")
                    owner_pointer = any(e["type"] == "mousedown" and e["isTrusted"] and
                        abs(e["main_clientX"] - point[0]) <= 1 and
                        abs(e["main_clientY"] - point[1]) <= 1 for e in after["events"])
                    main_pointer = any(e["type"] == "mousedown" and e["isTrusted"] and
                        abs(e["clientX"] - point[0]) <= 1 and abs(e["clientY"] - point[1]) <= 1
                        for e in after["main_document_events"])
                    row["physical_pointer_verified"] = owner_pointer or main_pointer
                    row["pointer_verification_source"] = "owner_frame" if owner_pointer else "main_document" if main_pointer else None
                    row["target_received_click"] = any(e["type"] == "click" and e["isTrusted"] and e["target_match"] and
                        abs(e["main_clientX"] - point[0]) <= 1 and abs(e["main_clientY"] - point[1]) <= 1
                        for e in after["events"])
                    associated = any(e["type"] == "mousedown" and e["isTrusted"] and
                        (e["target_match"] or e["label_for_target"]) and
                        abs(e["main_clientX"] - point[0]) <= 1 and abs(e["main_clientY"] - point[1]) <= 1
                        for e in after["events"])
                    row["associated_physical_delivery"] = associated
                    changed = after["current_exists"] and any(after.get(k) != annotation["before"].get(k) for k in ("checked", "aria_checked", "value", "expanded"))
                    row["interaction_success"] = bool(row["physical_pointer_verified"] and associated and
                        (row["target_received_click"] or after["focus_correct"] or changed))
                    row["status"] = "executed"
                    await page.screenshot(path=str(directory / (name + "-after.png")))
                else:
                    row["interaction_success"] = False
                    row["status"] = "frame_changed" if not equal else "missing_target" if not annotation.get("exists") else "invalid_coordinates"
                rows[name] = row
            except Exception as exc:
                rows[name] = {**candidate, "status": "browser_execution_failure", "target_hit": False,
                              "interaction_success": False, "error_type": type(exc).__name__, "error": str(exc)}
            finally:
                if context is not None:
                    try:
                        await context.close()
                    except Exception as exc:
                        rows[name]["context_teardown_error"] = type(exc).__name__
    finally:
        try:
            await browser.close()
        except Exception as exc:
            for row in rows.values():
                row["browser_teardown_error"] = type(exc).__name__
    return rows


def snapshot_sources(directory):
    sources = ["backend/adapters/venus.py", "scripts/diagnostics/venus_worker.py", "backend/browser/visual.py",
               "scripts/diagnostics/venus_coordinate_audit.py", "scripts/diagnostics/venus_coordinate_math.py"]
    hashes = {p: sha(ROOT / p) for p in sources}
    save(directory / "source-hashes.json", hashes)
    for source in sources:
        dest = directory / "source-snapshot" / source
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, dest)
    return hashes


async def run(args):
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only a local sandbox server is accepted")
    plan = json.loads(args.plan.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.plan, args.output / "declared-plan.json")
    snapshot_sources(args.output)
    adapter = VenusAdapter(max_tokens=plan["decoding"]["max_tokens"])
    adapter.config["inference_timeout_seconds"] = plan["inference_timeout_seconds"]
    adapter.config["max_pixels"] = plan["max_pixels"]
    if adapter.metadata()["adapter_version"] != plan["baseline_adapter_version"]:
        raise ValueError("Adapter identity differs from the predeclared baseline")
    results = []
    try:
        async with httpx.AsyncClient(timeout=30) as client, async_playwright() as pw:
            for target in plan["targets"]:
                group = plan["groups"][target["group"]]
                assert sha(ROOT / group["original_image"]) == group["original_sha256"]
                assert sha(ROOT / group["prepared_image"]) == group["prepared_sha256"]
                directory = args.output / target["id"]
                directory.mkdir()
                image = Image.open(ROOT / group["original_image"]).convert("RGB")
                task = {"instruction": target["instruction"]}
                row = {"id": target["id"], "group": target["group"], "target": target["target"], "kind": target["kind"],
                       "started_at": now(), "public_task": task, "original_image": group["original_image"], "prepared_image": group["prepared_image"]}
                try:
                    row["adapter_action"] = await adapter.act(image, task, [])
                    row["adapter_status"] = "parsed_action"
                except Exception as exc:
                    row.update(adapter_status="error", error_type=type(exc).__name__, error=str(exc))
                row["prediction_saved_at"] = now()
                row["metrics"] = adapter.last_metrics
                row["metadata"] = adapter.metadata()
                save(directory / "inference.json", row)
                if adapter.last_metrics.get("actual_model") is True:
                    assert adapter.last_metrics["image_sha256"] == group["prepared_sha256"]
                    try:
                        point = native_point(adapter.last_metrics["raw_text"])
                        row["native_point"] = list(point)
                        candidates = candidate_points(point, image.size, tuple(group["prepared_size"]))
                        row["candidates"] = await replay(pw, client, args.base_url, group, target, candidates, directory)
                    except ValueError as exc:
                        row["diagnostic_action_error"] = str(exc)
                results.append(row)
                save(directory / "evaluation.json", row)
                save(args.output / "results.json", results)
                print(json.dumps({"finished": len(results), "id": target["id"], "native_point": row.get("native_point"),
                    "genuine": adapter.last_metrics.get("actual_model", False), "hits": {k: v["target_hit"] for k, v in row.get("candidates", {}).items()}}), flush=True)
    finally:
        await adapter.close()
    names = list(plan["candidate_conventions"])
    summary = {"experiment": plan["experiment"], "official_leaderboard": False, "autonomous_checkout_evaluation": False,
               "targets": len(plan["targets"]), "case_attempts": len(results), "genuine_inference_calls": sum(r["metrics"].get("actual_model") is True for r in results),
               "finite_native_click_predictions": sum("native_point" in r for r in results), "plan_sha256": sha(args.plan), "results_sha256": sha(args.output / "results.json"),
               "candidates": {name: {"valid_coordinate_predictions": sum(r.get("candidates", {}).get(name, {}).get("valid", False) for r in results),
                    "target_hits": sum(r.get("candidates", {}).get(name, {}).get("target_hit", False) for r in results),
                    "interaction_successes": sum(r.get("candidates", {}).get(name, {}).get("interaction_success", False) for r in results),
                    "frame_mismatches": sum(v.get("status") == "frame_changed" for r in results for k, v in r.get("candidates", {}).items() if k == name),
                    "missing_targets": sum(r.get("candidates", {}).get(name, {}).get("status") == "missing_target" for r in results),
                    "browser_execution_failures": sum(r.get("candidates", {}).get(name, {}).get("status") == "browser_execution_failure" for r in results)} for name in names},
               "note": "All candidates use identical saved predictions. This simplified target diagnostic is not autonomous checkout accuracy; no runtime chooses a mapping from ground truth."}
    save(args.output / "summary.json", summary)
    print(json.dumps(summary), flush=True)


async def evaluate_saved(args):
    """Re-annotate frozen outputs; this path never constructs or calls an adapter."""
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only a local sandbox server is accepted")
    plan = json.loads(args.plan.read_text())
    amendment = json.loads(args.evaluation_amendment.read_text())
    assert amendment["original_plan_sha256"] == sha(args.plan)
    assert not amendment["model_inputs_changed"] and not amendment["native_predictions_resampled"]
    assert not amendment["target_definitions_changed"] and not amendment["coordinate_formulas_changed"]
    predictions = json.loads(args.predictions.read_text())
    assert {r["id"] for r in predictions} == {t["id"] for t in plan["targets"]}
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.plan, args.output / "declared-plan.json")
    shutil.copy2(args.evaluation_amendment, args.output / "evaluation-amendment.json")
    source_hashes = snapshot_sources(args.output)
    by_id = {r["id"]: r for r in predictions}
    results = []
    async with httpx.AsyncClient(timeout=30) as client, async_playwright() as pw:
        for declaration in plan["targets"]:
            target = dict(declaration)
            override = amendment["selector_overrides"].get(target["id"])
            if override:
                assert override["before"] == target["evaluation_selector"]
                target["evaluation_selector"] = override["after"]
            group = plan["groups"][target["group"]]
            assert sha(ROOT / group["original_image"]) == group["original_sha256"]
            assert sha(ROOT / group["prepared_image"]) == group["prepared_sha256"]
            original = by_id[target["id"]]
            row = {k: v for k, v in original.items() if k != "candidates"}
            row["saved_prediction_source"] = str(args.predictions)
            row["saved_predictions_sha256"] = sha(args.predictions)
            row["inference_resampled"] = False
            directory = args.output / target["id"]
            directory.mkdir()
            if row["metrics"].get("actual_model") is True:
                try:
                    point = native_point(row["metrics"]["raw_text"])
                except ValueError as exc:
                    row["diagnostic_action_error"] = str(exc)
                else:
                    assert list(point) == row["native_point"]
                    candidates = candidate_points(point, tuple(group["image_size"]), tuple(group["prepared_size"]))
                    row["candidates"] = await replay(pw, client, args.base_url, group, target, candidates, directory)
            results.append(row)
            save(directory / "evaluation.json", row)
            save(args.output / "results.json", results)
            print(json.dumps({"evaluated": len(results), "id": target["id"], "inference_resampled": False,
                "candidates": {k: {key: v.get(key) for key in ("status", "target_hit", "interaction_success")} for k, v in row.get("candidates", {}).items()}}), flush=True)
    summary = {"experiment": plan["experiment"], "official_leaderboard": False,
               "autonomous_checkout_evaluation": False, "targets": len(plan["targets"]), "case_attempts": len(results),
               "genuine_inference_calls": sum(r["metrics"].get("actual_model") is True for r in results),
               "finite_native_click_predictions": sum("native_point" in r for r in results),
               "plan_sha256": sha(args.plan), "evaluation_amendment_sha256": sha(args.evaluation_amendment),
               "source_predictions_sha256": sha(args.predictions), "results_sha256": sha(args.output / "results.json"),
               "new_model_calls_in_this_replay": 0,
               "evaluator_source_sha256": source_hashes["scripts/diagnostics/venus_coordinate_audit.py"],
               "source_hashes_sha256": sha(args.output / "source-hashes.json"),
               "candidates": {name: {
                   key: sum(bool(r.get("candidates", {}).get(name, {}).get(source)) for r in results)
                   for key, source in (("valid_coordinate_predictions", "valid"), ("target_hits", "target_hit"),
                                       ("interaction_successes", "interaction_success"), ("physical_pointer_verified", "physical_pointer_verified"))
               } | {"statuses": {status: sum(r.get("candidates", {}).get(name, {}).get("status") == status for r in results)
                   for status in ("executed", "invalid_coordinates", "frame_changed", "missing_target", "browser_execution_failure")}}
                   for name in plan["candidate_conventions"]}}
    save(args.output / "summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT / "research/ui-venus-coordinate-plan.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, help="Replay saved outputs without any model call")
    parser.add_argument("--evaluation-amendment", type=Path)
    args = parser.parse_args()
    if args.predictions:
        if not args.evaluation_amendment:
            parser.error("Saved-prediction replay requires an explicit evaluator amendment")
        asyncio.run(evaluate_saved(args))
    else:
        asyncio.run(run(args))
