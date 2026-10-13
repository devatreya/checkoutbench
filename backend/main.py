"""Run dashboard/control and isolated fixture origins in one local process."""

import asyncio, os
from dotenv import load_dotenv

load_dotenv()
import uvicorn
from backend.app import app
from backend.fixtures import checkout


async def main():
    servers = [
        uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=int(os.getenv("BENCH_PORT", "8000")),
                log_level="warning",
            )
        ),
        uvicorn.Server(
            uvicorn.Config(
                checkout,
                host="127.0.0.1",
                port=int(os.getenv("CHECKOUT_PORT", "8001")),
                log_level="warning",
            )
        ),
    ]
    print(
        "CheckoutBench dashboard: http://127.0.0.1:" + os.getenv("BENCH_PORT", "8000"),
        flush=True,
    )
    await asyncio.gather(*(s.serve() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
