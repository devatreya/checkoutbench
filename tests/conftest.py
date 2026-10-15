import os, sys, time, subprocess
from pathlib import Path
import httpx, pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    data = tmp_path_factory.mktemp("benchmark-data")
    port = int(os.getenv("BENCH_TEST_PORT", "8765"))
    base_url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "BENCH_PORT": str(port),
        "CHECKOUT_PORT": str(port+1),
        "BENCH_DATA_DIR": str(data),
        "BENCH_STORAGE_ROLE": "validation",
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
            if httpx.get(base_url + "/api/health").status_code == 200:
                break
        except httpx.ConnectError:
            pass
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read().decode())
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Test servers did not start")
    yield base_url
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
