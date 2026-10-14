"""Optional read-only official-sandbox validation. Separate from scored local fixtures."""

import os, re
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/sandboxes", tags=["optional sandbox validation"])
PROVIDERS = ("stripe", "shopify", "razorpay", "cashfree")


class Validation(BaseModel):
    object_id: str = Field(default="", max_length=120, pattern=r"^[A-Za-z0-9_-]*$")


def config(provider):
    if provider not in PROVIDERS:
        raise HTTPException(404)
    prefix = "BENCH_SANDBOX_" + provider.upper() + "_"
    get = lambda key: os.getenv(prefix + key, "")
    if get("ENABLED") != "1":
        raise HTTPException(
            409,
            "Sandbox validation disabled; explicitly configure test credentials first",
        )
    key, secret = get("KEY"), get("SECRET")
    if provider == "stripe" and not key.startswith("sk_test_"):
        raise HTTPException(409, "Stripe test secret key required")
    if provider == "razorpay" and (not key.startswith("rzp_test_") or not secret):
        raise HTTPException(409, "Razorpay test credentials required")
    if provider == "cashfree" and (not key or not secret):
        raise HTTPException(409, "Cashfree sandbox credentials required")
    if provider == "shopify" and (
        not key
        or get("TEST_GATEWAY_CONFIRMED") != "1"
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", get("STORE"))
    ):
        raise HTTPException(
            409,
            "Explicit development store, token and test-gateway confirmation required",
        )
    return get, key, secret


@router.get("")
def status():
    result = []
    for provider in PROVIDERS:
        try:
            config(provider)
            enabled = True
        except HTTPException:
            enabled = False
        result.append(
            dict(
                provider=provider,
                enabled=enabled,
                mode="read-only test object validation",
                affects_benchmark=False,
            )
        )
    return result


@router.post("/{provider}/validate")
async def validate(provider: str, body: Validation):
    get, key, secret = config(provider)
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, trust_env=False
    ) as client:
        try:
            if provider == "stripe":
                if not body.object_id.startswith("cs_test_"):
                    raise HTTPException(400, "A test Checkout Session ID is required")
                response = await client.get(
                    "https://api.stripe.com/v1/checkout/sessions/" + body.object_id,
                    auth=(key, ""),
                )
            elif provider == "razorpay":
                if not body.object_id.startswith("order_"):
                    raise HTTPException(400, "A test order ID is required")
                response = await client.get(
                    "https://api.razorpay.com/v1/orders/" + body.object_id,
                    auth=(key, secret),
                )
            elif provider == "cashfree":
                if not body.object_id:
                    raise HTTPException(400, "A sandbox order ID is required")
                response = await client.get(
                    "https://sandbox.cashfree.com/pg/orders/" + body.object_id,
                    headers={
                        "x-client-id": key,
                        "x-client-secret": secret,
                        "x-api-version": "2025-01-01",
                    },
                )
            else:
                response = await client.post(
                    "https://" + get("STORE") + "/admin/api/2026-10/graphql.json",
                    headers={"X-Shopify-Access-Token": key},
                    json={
                        "query": "{ shop { plan { partnerDevelopment shopifyPlus } } }"
                    },
                )
            if response.status_code != 200:
                raise HTTPException(
                    502,
                    "Sandbox request rejected; no provider response body or credentials logged",
                )
            obj = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(
                502, "Sandbox unavailable or invalid response"
            ) from None
    if provider == "stripe":
        if obj.get("livemode") is not False:
            raise HTTPException(409, "Live-mode or unverifiable object rejected")
        evidence = {
            k: obj.get(k)
            for k in ("status", "payment_status", "ui_mode", "payment_method_types")
        }
    elif provider == "shopify":
        plan = ((obj.get("data") or {}).get("shop") or {}).get("plan") or {}
        if plan.get("partnerDevelopment") is not True:
            raise HTTPException(409, "Store is not a verified development store")
        evidence = {
            "development_store": True,
            "plus": plan.get("shopifyPlus"),
            "gateway_confirmation": "operator-configured; not independently verified",
        }
    else:
        evidence = {
            "order_status": obj.get("order_status", obj.get("status")),
            "environment": "sandbox"
            if provider == "cashfree"
            else "test key namespace",
        }
    return dict(
        provider=provider,
        scope="read-only official test-object verification",
        evidence=evidence,
        ui_fidelity_validated=False,
        affects_benchmark=False,
    )
