"""Real Chromium/Browser Use execution, with a scripted LLM (no paid inference)."""

import asyncio, json, socket, tempfile, re, os
from pathlib import Path
import pytest, httpx
from playwright.async_api import async_playwright
from backend.adapters.base import Ledger
from backend.adapters import catalog
from backend.adapters.openrouter import run_openrouter


async def test_native_openrouter_browser_action(server, tmp_path, monkeypatch):
    from browser_use.llm.openrouter.chat import ChatOpenRouter
    from openai import AsyncOpenAI

    async with httpx.AsyncClient() as client:
        info = (await client.post(server + "/api/preview/T01")).json()
    monkeypatch.setenv("OPENROUTER_API_KEY", "unit-test-not-a-real-key")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "false")
    monkeypatch.setenv("BROWSER_USE_CLOUD_SYNC", "false")
    mid = "test/scripted-browser-use"
    monkeypatch.setitem(
        catalog.CATALOG,
        mid,
        {
            "id": mid,
            "context_length": 10000,
            "pricing": {"prompt": "0", "completion": "0"},
            "supported_parameters": [],
            "architecture": {"input_modalities": ["text"]},
        },
    )
    requests = []

    async def completion(request):
        data = json.loads(request.content)
        requests.append(data)
        text = json.dumps(data["messages"])
        # Find the visible email input's Browser Use index, not a fixture/scoring selector.
        match = re.search(
            r'(\d+)\]<input[^>]*(?:type=email|type="email"|id=f_email)', text
        )
        if not match:
            match = re.search(r"(\d+)\]<input[^>]*email", text)
        if len(requests) == 1:
            assert match, text[-14000:]
            action = {
                "input": {
                    "index": int(match.group(1)),
                    "text": "browser-use-proof@example.test",
                    "clear": True,
                }
            }
        else:
            action = {
                "done": {"text": "Scripted integration test complete", "success": True}
            }
        output = {
            "thinking": "Scripted test; no model inference.",
            "evaluation_previous_goal": "Proceed",
            "memory": "Integration test",
            "next_goal": "Enter test email" if len(requests) == 1 else "Finish",
            "action": [action],
        }
        return httpx.Response(
            200,
            json={
                "id": "mock-completion",
                "object": "chat.completion",
                "created": 0,
                "model": mid,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": json.dumps(output)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 30,
                    "total_tokens": 130,
                    "cost": 0,
                },
            },
        )

    def get_client(llm):
        if not hasattr(llm, "_client"):
            # Keep production accounting hooks, but replace the network transport.
            llm.http_client._transport = httpx.MockTransport(completion)
            llm._client = AsyncOpenAI(
                api_key="test",
                base_url="https://unit.test/v1",
                http_client=llm.http_client,
                max_retries=0,
            )
        return llm._client

    monkeypatch.setattr(ChatOpenRouter, "get_client", get_client)

    class Control:
        origin = "http://127.0.0.1:8766"
        directory = tmp_path
        stopped = False

        def __init__(self):
            self.events = []

        async def check(self):
            pass

        async def record(self, kind, detail):
            self.events.append((kind, detail))

    ctl = Control()
    async with async_playwright() as pw:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as userdir:
            context = await pw.chromium.launch_persistent_context(
                userdir,
                headless=True,
                viewport={"width": 1280, "height": 900},
                args=[f"--remote-debugging-port={port}"],
            )
            page = context.pages[0]
            await page.goto(info["url"])
            await page.locator("#shipping").wait_for()
            try:
                usage = await asyncio.wait_for(
                    run_openrouter(
                        page,
                        {
                            "instruction": "Enter the test email in the email field, then stop.",
                            "profile": {"email": "browser-use-proof@example.test"},
                        },
                        ctl,
                        mid,
                        {
                            "reasoning": "default",
                            "max_tokens": 1024,
                            "timeout": 30,
                            "max_steps": 3,
                        },
                        Ledger(),
                        f"http://127.0.0.1:{port}",
                    ),
                    timeout=60,
                )
                assert (
                    await page.locator("[name=email]").input_value()
                    == "browser-use-proof@example.test"
                )
                assert usage.prompt_tokens >= 100 and ctl.events
                assert all(r["model"] == mid for r in requests)
                assert all("success_conditions" not in json.dumps(r) for r in requests)
            finally:
                await context.close()
