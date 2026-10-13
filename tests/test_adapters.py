import json
import httpx, pytest
from backend.adapters.base import Ledger, BudgetExceeded
from backend.adapters.openrouter import Meter
from backend.adapters.specialists import (
    parse_tinyclick,
    parse_mai,
    parse_venus,
    SpecialistOutputError,
    specialist_catalog,
)


async def test_paid_accounting_and_cap_before_request():
    ledger = Ledger(0.1)
    meta = {
        "context_length": 1000,
        "pricing": {"prompt": "0.00001", "completion": "0.00002"},
    }
    meter = Meter(meta, ledger, 100)

    async def reply(req):
        return httpx.Response(
            200,
            json={
                "id": "test-generation",
                "model": "exact/model",
                "provider": "Test Provider",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cost": 0.003},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(reply),
        event_hooks={"request": [meter.request], "response": [meter.response]},
    ) as c:
        await c.post("https://unit.test/chat/completions", json={})
    assert meter.usage.cost == 0.003 and ledger.spent == 0.003 and ledger.reserved == 0
    assert (
        meter.usage.prompt_tokens == 100
        and meter.usage.calls[0]["provider"] == "Test Provider"
    )
    ledger.cap = 0.0031
    with pytest.raises(BudgetExceeded):
        await meter.request(httpx.Request("POST", "https://unit.test"))
    assert len(meter.usage.calls) == 1


async def test_interrupted_billable_request_keeps_reservation():
    ledger = Ledger()
    meter = Meter(
        {"context_length": 100, "pricing": {"prompt": ".001", "completion": ".001"}},
        ledger,
        50,
    )
    await meter.request(httpx.Request("POST", "https://unit.test"))
    meter.account_uncertain()
    assert (
        ledger.spent == pytest.approx(0.15)
        and meter.usage.cost_kind == "reserved_unknown"
    )


@pytest.mark.parametrize(
    "raw",
    [
        '<action>__import__(module="os")</action>',
        '<action>Click(box=__import__("os").system("id"))</action>',
        "<action>Click(box=[99999,99999])</action>",
    ],
)
def test_venus_rejects_arbitrary_code_and_out_of_bounds(raw):
    with pytest.raises(SpecialistOutputError):
        parse_venus(raw, (1280, 900))


def test_specialists_distinct_capabilities():
    rows = {r["id"]: r for r in specialist_catalog()}
    assert rows["cua-s1"]["capability"] == "field_classification"
    assert rows["tinyclick"]["capability"] == "visual_grounding"
    assert rows["mai-ui"]["capability"] == "gui_agent"
    assert rows["hybrid"]["model_id"].startswith("cua-ai/")


@pytest.mark.parametrize(
    "url",
    [
        "https://api.stripe.com/v1/payment_intents",
        "https://api.razorpay.com/v1/payments",
        "https://api.cashfree.com/pg/orders",
        "http://127.0.0.1:8000/api/results",
        "http://127.0.0.1:8001/api/scenarios",
        "http://127.0.0.1:8001/session/another",
        "http://127.0.0.1.evil.test:8001/checkout/token",
        "file:///etc/passwd",
        "http://127.0.0.1:8001/session/token/../../api/results",
    ],
)
def test_browser_allowlist_blocks_payment_and_private_urls(url):
    from backend.browser.security import allowed_url

    assert not allowed_url(url, "http://127.0.0.1:8001", "token")


def test_browser_allowlist_exact_session():
    from backend.browser.security import allowed_url

    assert allowed_url(
        "http://127.0.0.1:8001/checkout/token?screen=bank",
        "http://127.0.0.1:8001",
        "token",
    )
    assert allowed_url(
        "http://127.0.0.1:8001/assets/card.html", "http://127.0.0.1:8001", "token"
    )


async def test_cua_native_option_contract(monkeypatch):
    from backend.adapters.specialists import CuaS1Adapter

    monkeypatch.setenv("CUA_S1_ENDPOINT", "http://localhost:9999")
    adapter = CuaS1Adapter()

    async def score(path, payload):
        assert path == "/score"
        assert payload["options"] == [
            "fill name: Example Person",
            "fill billing city: New Delhi",
            "check",
            "click",
            "skip",
        ]
        assert 'ELEMENT Edit "Recipient name"' in payload["contexts"][0]
        return {"probabilities": [[0.9, 0.025, 0.025, 0.025, 0.025]]}

    monkeypatch.setattr(adapter, "_post", score)
    rows = await adapter.score_fields(
        [
            {
                "id": "dom-field",
                "element_id": "0:dom-field",
                "label": "Recipient name",
                "value": "",
            }
        ],
        {"name": "Example Person", "billing": {"city": "New Delhi"}},
    )
    assert rows[0]["element_id"] == "0:dom-field"
    assert rows[0]["value"] == "Example Person" and rows[0]["confidence"] == 0.9


def test_native_coordinate_and_action_formats():
    tiny = parse_tinyclick("<loc_500><loc_500>", (1280, 900))
    assert 630 <= tiny["x"] <= 650 and 440 <= tiny["y"] <= 460
    mai = parse_mai(
        '<tool_call>{"name":"mobile_use","arguments":{"action":"click","coordinate":[999,999]}}</tool_call>',
        (1280, 900),
    )
    assert mai["x"] == 1279 and mai["y"] == 899
    venus = parse_venus(
        "<action>Click(box=(320,225))</action>", (1280, 900), (640, 450)
    )
    assert venus["x"] == 640 and venus["y"] == 450
    assert (
        parse_venus("<action>Type(content='synthetic')</action>", (1280, 900))["submit"]
        is True
    )


def test_direct_adapter_is_explicit_and_credential_gated(monkeypatch):
    from backend.adapters.catalog import direct_models, direct_entry, require
    from backend.adapters.base import Unavailable

    monkeypatch.setenv(
        "DIRECT_MODELS_JSON",
        json.dumps(
            [
                {
                    "id": "direct/test-model",
                    "model_id": "exact-provider-id",
                    "base_url": "https://provider.example/v1",
                    "api_key_env": "TEST_DIRECT_KEY",
                }
            ]
        ),
    )
    monkeypatch.delenv("TEST_DIRECT_KEY", raising=False)
    assert not direct_entry(direct_models()["direct/test-model"])["available"]
    with pytest.raises(Unavailable):
        require("direct/test-model")
    monkeypatch.setenv("TEST_DIRECT_KEY", "synthetic-test-key")
    meta = require("direct/test-model")
    assert meta[
        "model_id"
    ] == "exact-provider-id" and "synthetic-test-key" not in json.dumps(meta)
