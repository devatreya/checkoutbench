import os, time, importlib.util, json
import httpx
from backend.adapters.base import Unavailable

CANDIDATES = [
    ("openai/gpt-6-astra", "GPT-6 Astra"),
    ("openai/gpt-6-sol", "GPT-6 Sol"),
    ("openai/gpt-6-luna", "GPT-6 Luna"),
    ("anthropic/claude-fable-5.1", "Claude Fable 5.1"),
    ("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5"),
    ("anthropic/claude-haiku-5.5", "Claude Haiku 5.5"),
]
CATALOG = {}
FETCHED = 0
ERROR = None


def direct_models():
    """Explicit operator-configured OpenAI-compatible adapters; never automatic fallbacks."""
    try:
        rows = json.loads(os.getenv("DIRECT_MODELS_JSON", "[]"))
        if not isinstance(rows, list):
            return {}
        return {
            r["id"]: r
            for r in rows
            if isinstance(r, dict)
            and str(r.get("id", "")).startswith("direct/")
            and r.get("model_id")
            and r.get("base_url")
            and r.get("api_key_env")
        }
    except (ValueError, KeyError):
        return {}


def direct_entry(row):
    available = (
        bool(os.getenv(row["api_key_env"]))
        and importlib.util.find_spec("browser_use") is not None
    )
    return dict(
        id=row["id"],
        name=row.get("name", row["model_id"]),
        kind="direct",
        backend="Browser Use + direct OpenAI-compatible API",
        available=available,
        reason=None
        if available
        else "Direct provider credential or Browser Use missing",
        pricing=row.get("pricing"),
        vision=row.get("vision", False),
        tools=True,
        reasoning=bool(row.get("reasoning_levels")),
        reasoning_levels=["default"] + row.get("reasoning_levels", []),
        parameters=None,
    )


async def refresh():
    global CATALOG, FETCHED, ERROR
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://openrouter.ai/api/v1/models")
            r.raise_for_status()
        CATALOG = {m["id"]: m for m in r.json()["data"]}
        FETCHED = time.time()
        ERROR = None
    except Exception as e:
        ERROR = f"Catalogue lookup failed: {type(e).__name__}"
    return models()


def entry(mid, name=None):
    m = CATALOG.get(mid)
    installed = importlib.util.find_spec("browser_use") is not None
    reason = (
        None
        if m and os.getenv("OPENROUTER_API_KEY") and installed
        else (
            "Not in the current OpenRouter catalogue"
            if not m
            else "OPENROUTER_API_KEY is not configured"
            if not os.getenv("OPENROUTER_API_KEY")
            else "Install the agent extra"
        )
    )
    params = m.get("supported_parameters", []) if m else []
    return dict(
        id=mid,
        name=name or (m or {}).get("name", mid),
        kind="openrouter",
        backend="Browser Use + OpenRouter",
        available=reason is None,
        reason=reason,
        pricing=(m or {}).get("pricing"),
        vision="image" in (m or {}).get("architecture", {}).get("input_modalities", []),
        tools="tools" in params,
        reasoning="reasoning" in params,
        reasoning_levels=["default", "minimal", "low", "medium", "high", "xhigh", "max"]
        if "reasoning" in params
        else ["default"],
        reasoning_note="Effort values are provider-validated; unsupported values fail explicitly.",
        context_length=(m or {}).get("context_length"),
        parameters=None,
        shortlist=mid in dict(CANDIDATES),
    )


def models():
    from backend.adapters.specialists import specialist_catalog

    specialists = specialist_catalog()
    # Adapter metadata is normalized here rather than claiming local weights exist.
    rows = [
        dict(
            id="reference",
            name="Deterministic reference",
            kind="reference",
            backend="Playwright · fixture validation",
            available=True,
            reason=None,
            parameters=None,
            pricing=None,
            reasoning_levels=["default"],
        )
    ]
    rows += [entry(mid, name) for mid, name in CANDIDATES]
    rows += specialists
    rows += [direct_entry(r) for r in direct_models().values()]
    return {
        "models": rows,
        "catalogue_count": len(CATALOG),
        "fetched_at": FETCHED,
        "catalogue_error": ERROR,
        "credentials_configured": bool(os.getenv("OPENROUTER_API_KEY")),
    }


def require(mid):
    if mid in direct_models():
        r = direct_models()[mid]
        if not os.getenv(r["api_key_env"]):
            raise Unavailable("Direct provider credential is not configured")
        return {
            **r,
            "direct": True,
            "context_length": r.get("context_length", 200000),
            "architecture": {
                "input_modalities": ["text", "image"] if r.get("vision") else ["text"]
            },
            "supported_parameters": ["reasoning"] if r.get("reasoning_levels") else [],
        }
    if mid not in CATALOG:
        raise Unavailable(
            "Exact model ID is absent from the verified catalogue. No substitute was selected."
        )
    if not os.getenv("OPENROUTER_API_KEY"):
        raise Unavailable("OPENROUTER_API_KEY is not configured")
    return CATALOG[mid]
