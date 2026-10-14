"""Separate checkout origin: no catalogue, evaluator, profiles or results endpoints."""

from pathlib import Path
from uuid import uuid4
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from scenarios.catalog import CITIES

ROOT = Path(__file__).resolve().parent.parent
checkout = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
SESSIONS = {}


def new_session(s, agent_mode="standard"):
    if s.get("benchmark_version") == "2.1":
        from backend.workflows_v21 import init

        token = uuid4().hex
        SESSIONS[token] = init(s, agent_mode)
        return token
    if s.get("benchmark_version") == "2.0":
        from backend.workflows import init

        token = uuid4().hex
        SESSIONS[token] = init(s, agent_mode)
        return token
    token = uuid4().hex
    SESSIONS[token] = {
        "scenario": s,
        "values": {},
        "card": {},
        "stage": "shipping",
        "method": s["initial_state"]["method"],
        "app": "PhonePe",
        "attempts": 0,
        "retries": 0,
        "validation_errors": 0,
    }
    return token


@checkout.middleware("http")
async def secure(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; form-action 'self'; base-uri 'none'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@checkout.get("/assets/{name}")
def asset(name: str):
    if name not in (
        "checkout.js",
        "checkout.css",
        "card.html",
        "card.js",
        "v2.js",
        "v21.js",
        "v21.css",
        "v21-extension.js",
        "v2.css",
        "v2-base.css",
    ):
        raise HTTPException(404)
    return FileResponse(ROOT / "checkout_fixtures" / name)


@checkout.get("/checkout/{token}")
def page(token: str):
    if token not in SESSIONS:
        raise HTTPException(404)
    return FileResponse(
        ROOT
        / "checkout_fixtures"
        / (
            "v21.html"
            if SESSIONS[token]["scenario"].get("benchmark_version") == "2.1"
            else "v2.html"
            if SESSIONS[token]["scenario"].get("benchmark_version") == "2.0"
            else "index.html"
        )
    )


def session(token):
    if token not in SESSIONS:
        raise HTTPException(404)
    return SESSIONS[token]


@checkout.get("/session/{token}")
def config(token: str):
    st = session(token)
    s = st["scenario"]
    if s.get("benchmark_version") in ("2.0", "2.1"):
        raise HTTPException(404)
    return dict(
        theme=s["theme"],
        features=s["features"],
        fields=s["fields"],
        cities=CITIES,
        seed=s["seed"],
        method=st["method"],
        prefill={
            "name": "Wrong Saved Recipient",
            "phone": "9000000099",
            "address1": "99 Old Sample Road",
            "postal": "999999",
        }
        if "prefill" in s["features"]
        else {},
    )


@checkout.post("/session/{token}/input")
async def inputs(token: str, request: Request):
    st = session(token)
    if st["scenario"].get("benchmark_version") in ("2.0", "2.1"):
        raise HTTPException(404)
    data = await request.json()
    st["values"].update({k: str(v)[:300] for k, v in data.get("values", {}).items()})
    for k in ("method", "app", "card", "vpa"):
        if k in data:
            st[k] = data[k]
    return {"ok": True}


@checkout.post("/session/{token}/advance")
async def advance(token: str, request: Request):
    st = session(token)
    if st["scenario"].get("benchmark_version") in ("2.0", "2.1"):
        raise HTTPException(404)
    data = await request.json()
    action = data.get("action")
    s = st["scenario"]
    if action == "shipping":
        values = data.get("values", {})
        st["values"] = values
        errors = {}
        for f in s["fields"]:
            k = f["key"]
            v = str(values.get(k, "")).strip()
            if f["required"] and not v:
                errors[k] = "This field is required."
        for prefix in ("", "billing_") if "billing" in s["features"] else ("",):
            if prefix:
                for k in ("name", "address1", "state", "city", "postal"):
                    if not str(values.get(prefix + k, "")).strip():
                        errors[prefix + k] = "This field is required."
            if not re.fullmatch(r"\d{6}", str(values.get(prefix + "postal", ""))):
                errors[prefix + "postal"] = "Use a six-digit postal PIN."
            if values.get(prefix + "city") not in CITIES.get(
                values.get(prefix + "state"), []
            ):
                errors[prefix + "city"] = "Choose a city in the selected state."
        if not re.fullmatch(r"\d{10}", re.sub(r"\D", "", str(values.get("phone", "")))):
            errors["phone"] = "Use a 10-digit mobile number."
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(values.get("email", ""))):
            errors["email"] = "Enter a valid email address."
        if errors:
            st["validation_errors"] += 1
            return {"errors": errors}
        st["stage"] = "payment"
        return {"stage": "payment"}
    if action == "pay" and st["stage"] in ("payment", "failure"):
        st["attempts"] += 1
        st.update({k: data.get(k) for k in ("method", "app", "card", "vpa")})
        err = None
        if st["method"] not in ("upi_app", "upi_qr", "upi_vpa", "card"):
            err = "Select a payment method."
        if st["method"] == "card":
            c = st.get("card") or {}
            if (
                re.sub(r"\s", "", c.get("cardNumber", "")) != "4242424242424242"
                or c.get("expiry") != "12/30"
                or c.get("cvv") != "123"
                or not c.get("cardName")
            ):
                err = "Use the documented test card, expiry 12/30 and test CVV 123."
            elif "card_error" in s["features"] and st["attempts"] == 1:
                err = "Simulated card validation error. Re-enter the test card number and retry."
        if st["method"] == "upi_app" and st["app"] not in (
            "PhonePe",
            "Google Pay",
            "Paytm",
            "BHIM",
        ):
            err = "Choose a UPI app."
        if st["method"] == "upi_vpa" and not str(st.get("vpa", "")).endswith(
            "@example.invalid"
        ):
            err = "Use the synthetic @example.invalid identifier."
        if err:
            st["validation_errors"] += 1
            return {"error": err}
        if "failure" in s["features"] and st["attempts"] == 1:
            st["stage"] = "failure"
            return {"stage": "failure"}
        st["stage"] = "bank" if s["theme"] == "cashfree" else "authorisation_ready"
        return {"stage": st["stage"]}
    if action == "retry" and st["stage"] == "failure":
        st["retries"] += 1
        st["stage"] = "payment"
        return {"stage": "payment"}
    if action == "prepare" and st["stage"] == "bank":
        st["stage"] = "authorisation_ready"
        return {"stage": st["stage"]}
    raise HTTPException(409, "Invalid checkout transition")


@checkout.get("/v2/{token}/state")
def state_v2(token: str):
    from backend.workflows import public

    st = session(token)
    if st["scenario"].get("benchmark_version") != "2.0":
        raise HTTPException(404)
    return public(st, token)


@checkout.post("/v2/{token}/action")
async def action_v2(token: str, request: Request):
    import asyncio
    from backend.workflows import transition, public

    st = session(token)
    if st["scenario"].get("benchmark_version") != "2.0":
        raise HTTPException(404)
    data = await request.json()
    await asyncio.sleep(st["scenario"]["difficulty_config"]["network_delay_ms"] / 1000)
    if data.get("action") in ("show_qr", "qr_refresh", "qr_fullsize"):
        from backend.qr import LEVELS

        await asyncio.sleep(LEVELS[st["scenario"].get("qr", "Q0")].delay_ms / 1000)
    transition(st, data.get("action"), data, token)
    return public(st, token)


@checkout.get("/v2/{token}/qr")
def qr_v2(token: str):
    from fastapi.responses import Response

    qr = session(token).get("qr")
    if not qr:
        raise HTTPException(404)
    return Response(qr["image"], media_type=qr["report"]["mime"])


@checkout.get("/v2/{token}/challenge")
@checkout.get("/v2/{token}/component")
@checkout.get("/v2/{token}/gateway")
def subpage_v2(token: str):
    session(token)
    return FileResponse(ROOT / "checkout_fixtures/v2.html")


def v21_session(token):
    st = session(token)
    if st["scenario"].get("benchmark_version") != "2.1":
        raise HTTPException(404)
    return st


@checkout.get("/v21/{token}/state")
def state_v21(token: str):
    from backend.workflows_v21 import public

    return public(v21_session(token), token)


@checkout.post("/v21/{token}/action")
async def action_v21(token: str, request: Request):
    import asyncio
    from backend.workflows_v21 import transition, public
    from backend.qr import LEVELS

    st = v21_session(token)
    data = await request.json()
    await asyncio.sleep(st["scenario"]["difficulty_config"]["network_delay_ms"] / 1000)
    if data.get("action") in ("show_qr", "qr_refresh", "qr_fullsize"):
        await asyncio.sleep(LEVELS[st["scenario"].get("qr", "Q0")].delay_ms / 1000)
    transition(st, data.get("action"), data, token)
    return public(st, token)


@checkout.get("/v21/{token}/qr")
def qr_v21(token: str):
    from fastapi.responses import Response

    qr = v21_session(token).get("qr")
    if not qr:
        raise HTTPException(404)
    return Response(qr["image"], media_type=qr["report"]["mime"])


@checkout.get("/v21/{token}/challenge")
@checkout.get("/v21/{token}/component")
@checkout.get("/v21/{token}/gateway")
@checkout.get("/v21/{token}/provider")
@checkout.get("/v21/{token}/verification")
def subpage_v21(token: str):
    v21_session(token)
    return FileResponse(ROOT / "checkout_fixtures/v21.html")


@checkout.get("/v21/{token}/extension")
def extension_v21(token: str):
    import json, html
    from fastapi.responses import HTMLResponse
    from backend.workflows_v21 import public

    st = v21_session(token)
    if st["scenario"]["family"] != "shopify":
        raise HTTPException(404)
    d = public(st, token)
    payload = {
        "fields": [f for f in d["fields"] if f.get("section") == "shipping"],
        "values": d["values"],
    }
    # Non-executable data, escaped against script termination. Opaque-origin sandbox has no checkout DOM access.
    encoded = json.dumps(payload).replace("<", "\\u003c")
    return HTMLResponse(
        '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/assets/v21.css"></head><body><main id="extension"></main><script type="application/json" id="context">'
        + encoded
        + '</script><script src="/assets/v21-extension.js" defer></script></body></html>'
    )
