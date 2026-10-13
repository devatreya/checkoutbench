import os, sys, time, subprocess
from pathlib import Path
import httpx, pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    data = tmp_path_factory.mktemp("benchmark-data")
    env = {
        **os.environ,
        "BENCH_PORT": "8765",
        "CHECKOUT_PORT": "8766",
        "BENCH_DATA_DIR": str(data),
        "OPENROUTER_API_KEY": "",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "backend.main"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    for _ in range(100):
        try:
            if httpx.get("http://127.0.0.1:8765/api/health").status_code == 200:
                break
        except httpx.ConnectError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read().decode())
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Test servers did not start")
    yield "http://127.0.0.1:8765"
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
async def page():
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        yield page
        await browser.close()
