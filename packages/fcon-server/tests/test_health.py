"""What a monitor is told at /healthz."""

import asyncio

import anyio.to_thread
import httpx2
from fastapi.testclient import TestClient

from fcon_server.app import create_app
from fcon_server.signing import SecretKeys

# Nothing listens here: /healthz must answer without the database.
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"


KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")


def test_healthz_says_the_process_is_alive():
    client = TestClient(create_app(NO_DATABASE, keys=KEYS))

    response = client.get("/healthz")

    assert (response.status_code, response.json()) == (200, {"status": "alive"})


async def _healthz_with_every_worker_thread_taken() -> int:
    workers = anyio.to_thread.current_default_thread_limiter()
    workers.total_tokens = 1
    holder = object()
    await workers.acquire_on_behalf_of(holder)  # the only worker thread, held as a slow /readyz would
    try:
        transport = httpx2.ASGITransport(app=create_app(NO_DATABASE, keys=KEYS))
        async with httpx2.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with asyncio.timeout(2):
                return (await client.get("/healthz")).status_code
    finally:
        workers.release_on_behalf_of(holder)


def test_healthz_answers_while_every_worker_thread_is_busy():
    assert asyncio.run(_healthz_with_every_worker_thread_taken()) == 200
