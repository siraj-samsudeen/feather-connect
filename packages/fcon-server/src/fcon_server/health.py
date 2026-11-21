"""Health and readiness: what the host and an uptime monitor ask.

Both are open to anyone, so neither says where the database is or what went
wrong with it: the real error goes to the server's log only.
"""

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from fcon_server.database import TIMEOUT_S, DatabaseCheck, check_database

LIVENESS_PATH = "/healthz"
READINESS_PATH = "/readyz"

READY = {"status": "ready", "checks": {"database": "ok"}}
NOT_READY = {"status": "not ready", "checks": {"database": "unavailable"}}

FRESH_S = 1.0  # a result younger than this answers the next request too


def readiness(check: DatabaseCheck | None) -> tuple[int, dict[str, Any]]:
    """The status and body /readyz answers: one word for every problem, and
    for no answer in time."""
    return (200, READY) if check is not None and check.problem is None else (503, NOT_READY)


class SharedCheck:
    """One check for every request that comes while it runs, and its result
    for a second after: a flood of requests holds one worker thread and one
    database connection at most."""

    def __init__(
        self,
        check: Callable[[], DatabaseCheck],
        answer_within_s: float = TIMEOUT_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._check = check
        self._answer_within_s = answer_within_s
        self._clock = clock
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readiness")
        self._lock = threading.Lock()
        self._running: Future[DatabaseCheck] | None = None
        self._last: tuple[float, DatabaseCheck] | None = None

    def _run(self) -> DatabaseCheck:
        check = self._check()
        with self._lock:
            self._last = (self._clock(), check)
        return check

    def _current(self) -> Future[DatabaseCheck]:
        with self._lock:
            if self._last is not None and self._clock() - self._last[0] < FRESH_S:
                done: Future[DatabaseCheck] = Future()
                done.set_result(self._last[1])
                return done
            if self._running is None or self._running.done():
                self._running = self._worker.submit(self._run)
            return self._running

    async def result(self) -> DatabaseCheck | None:
        """The check's result, or None when it gives none within
        answer_within_s; it carries on, and its result serves the next request."""
        try:
            async with asyncio.timeout(self._answer_within_s):
                # shield: one request giving up does not cancel the others' check
                return await asyncio.shield(asyncio.wrap_future(self._current()))
        except TimeoutError:
            return None


def router(database_url: str) -> APIRouter:
    routes = APIRouter()
    database = SharedCheck(lambda: check_database(database_url))

    @routes.get(LIVENESS_PATH)
    async def healthz() -> dict[str, str]:
        """Up while the process is: never touches the database, so an outage
        does not make the host restart the server. Async, so it answers even
        when every worker thread is busy."""
        return {"status": "alive"}

    @routes.get(READINESS_PATH)
    async def readyz() -> JSONResponse:
        """Ready to take work: the database answers, live, within its 2 s."""
        status, body = readiness(await database.result())
        return JSONResponse(body, status_code=status)

    return routes
