"""Native Browser Use OpenRouter adapter with per-request accounting."""

import os, json, time, asyncio
import httpx
from backend.adapters.base import (
    Usage,
    Unavailable,
    BudgetExceeded,
    InfrastructureError,
)
from backend.adapters.catalog import require


class Meter:
    def __init__(self, meta, ledger, max_tokens):
        self.meta = meta
        self.ledger = ledger
        self.max_tokens = max_tokens
        self.usage = Usage()
        self.pending = {}
        self.budget_blocked = False

    def bound(self):
        p = self.meta.get("pricing", {})
        # Reserve the context-window ceiling, including cached/vision input tokens.
        # Provider overrides use the largest advertised rate to avoid understating caps.
        rates = [p] + p.get("overrides", [])
        prompt = max(float(x.get("prompt", p.get("prompt", 0))) for x in rates)
        completion = max(
            float(x.get("completion", p.get("completion", 0))) for x in rates
        )
        return (
            self.meta.get("context_length", 200000) * prompt
            + self.max_tokens * completion
            + float(p.get("request", 0))
            + 16 * float(p.get("image", 0))
        )

    async def request(self, request):
        amount = self.bound()
        try:
            self.ledger.reserve(amount)
        except BudgetExceeded:
            self.budget_blocked = True
            raise
        self.pending[id(request)] = (amount, time.perf_counter())

    async def response(self, response):
        await response.aread()
        reservation, started = self.pending.pop(
            id(response.request), (0, time.perf_counter())
        )
        elapsed = time.perf_counter() - started
        self.usage.inference_seconds += elapsed
        try:
            body = response.json()
        except ValueError:
            body = {}
        u = body.get("usage") or {}
        p = self.meta.get("pricing", {})
        actual = u.get("cost")
        kind = "actual" if actual is not None else "estimated"
        if actual is None:
            actual = (
                int(u.get("prompt_tokens", 0)) * float(p.get("prompt", 0))
                + int(u.get("completion_tokens", 0)) * float(p.get("completion", 0))
                + float(p.get("request", 0))
            )
            if response.status_code >= 400:
                actual = 0
            elif not u:
                actual = reservation
                kind = "reserved_unknown"
        self.ledger.settle(reservation, float(actual))
        self.usage.cost += float(actual)
        if kind != "actual":
            self.usage.cost_kind = kind
        self.usage.prompt_tokens += int(u.get("prompt_tokens", 0))
        self.usage.completion_tokens += int(u.get("completion_tokens", 0))
        self.usage.calls.append(
            dict(
                id=body.get("id"),
                model=body.get("model"),
                provider=body.get("provider"),
                status=response.status_code,
                cost=float(actual),
                cost_kind=kind,
                prompt_tokens=u.get("prompt_tokens"),
                completion_tokens=u.get("completion_tokens"),
                seconds=elapsed,
            )
        )

    def account_uncertain(self):
        for reservation, started in self.pending.values():
            self.ledger.settle(reservation, reservation)
            self.usage.cost += reservation
            self.usage.cost_kind = "reserved_unknown"
            self.usage.calls.append(
                {
                    "status": "interrupted",
                    "cost": reservation,
                    "cost_kind": "reserved_unknown",
                }
            )
        self.pending.clear()


async def run_openrouter(page, task, ctl, model, config, ledger, cdp_url):
    try:
        from browser_use import Agent, BrowserSession, Tools
        from browser_use.llm.openrouter.chat import ChatOpenRouter
    except ImportError as e:
        raise Unavailable("Install uv sync --extra agent") from e
    meta = require(model)
    if (
        meta.get("direct")
        and config["reasoning"] != "default"
        and config["reasoning"] not in meta.get("reasoning_levels", [])
    ):
        raise Unavailable("Reasoning effort is not configured for this direct adapter")
    if ledger.cap is not None and not meta.get("pricing"):
        raise Unavailable(
            "A spending cap requires configured pricing for the direct endpoint"
        )
    if config["reasoning"] != "default" and "reasoning" not in meta.get(
        "supported_parameters", []
    ):
        raise Unavailable("This exact model does not advertise reasoning parameters")
    meter = Meter(meta, ledger, config["max_tokens"])
    ctl.usage = meter.usage
    client = httpx.AsyncClient(
        timeout=config["timeout"],
        event_hooks={"request": [meter.request], "response": [meter.response]},
    )
    extra = {
        "max_tokens": config["max_tokens"],
        "extra_body": {
            "provider": {"allow_fallbacks": False, "require_parameters": True},
            "usage": {"include": True},
        },
    }
    if config["reasoning"] != "default":
        extra["extra_body"]["reasoning"] = {"effort": config["reasoning"]}
    if meta.get("direct"):
        extra = {meta.get("token_parameter", "max_tokens"): config["max_tokens"]}
        if config["reasoning"] != "default":
            extra["reasoning_effort"] = config["reasoning"]
    llm = ChatOpenRouter(
        model=meta.get("model_id", model),
        api_key=os.environ[meta.get("api_key_env", "OPENROUTER_API_KEY")],
        base_url=meta.get("base_url", "https://openrouter.ai/api/v1"),
        http_client=client,
        max_retries=0,
        extra_body=extra,
    )
    browser = BrowserSession(
        cdp_url=cdp_url,
        allowed_domains=[ctl.origin],
        keep_alive=True,
        viewport={"width": 1280, "height": 900},
    )
    tools = Tools(
        exclude_actions=[
            "search",
            "navigate",
            "go_back",
            "switch",
            "close",
            "evaluate",
            "read_file",
            "write_file",
            "replace_file",
            "extract",
            "upload_file",
            "download_file",
        ]
    )
    # No judge, fallback, planner or second model: all inference is measured on the chosen ID.
    agent = Agent(
        task=json.dumps(task),
        llm=llm,
        browser_session=browser,
        tools=tools,
        use_vision="image" in meta.get("architecture", {}).get("input_modalities", []),
        use_judge=False,
        enable_planning=False,
        message_compaction=False,
        max_failures=2,
        max_actions_per_step=1,
        final_response_after_failure=False,
        calculate_cost=False,
        available_file_paths=[],
        file_system_path=str(ctl.directory / "agent-files"),
        directly_open_url=False,
    )

    async def before(agent):
        await ctl.check()

    async def after(agent):
        output = agent.state.last_model_output
        actions = (
            [x.model_dump(exclude_none=True) for x in output.action] if output else []
        )
        errors = [str(r.error) for r in (agent.state.last_result or []) if r.error]
        for key in (
            os.getenv("OPENROUTER_API_KEY"),
            os.getenv(meta.get("api_key_env", "OPENROUTER_API_KEY")),
        ):
            if key:
                errors = [e.replace(key, "[REDACTED]")[:1000] for e in errors]
        await ctl.record("browser_use", {"actions": actions, "errors": errors})

    async def stopped():
        return (
            ctl.stopped
            or await page.get_by_role(
                "heading", name="Ready for payment authorisation"
            ).count()
            > 0
        )

    agent.register_should_stop_callback = stopped
    try:
        await agent.run(
            max_steps=config["max_steps"], on_step_start=before, on_step_end=after
        )
    finally:
        meter.account_uncertain()
        await client.aclose()
        try:
            await asyncio.wait_for(browser.stop(), timeout=10)
        except (Exception, asyncio.CancelledError):
            pass
    if meter.budget_blocked:
        raise BudgetExceeded("Next inference would exceed the batch cap")
    if any(call.get("status") in (401, 402, 403, 404) for call in meter.usage.calls):
        raise Unavailable(
            "Provider rejected credentials, balance, access, or exact model availability"
        )
    if any(
        isinstance(call.get("status"), int)
        and (call["status"] == 429 or call["status"] >= 500)
        for call in meter.usage.calls
    ):
        raise InfrastructureError("Provider rate limit or service failure")
    return meter.usage
