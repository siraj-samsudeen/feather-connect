"""Health and readiness: what the host and an uptime monitor ask.

Both are open to anyone, so neither says where the database is or what went
wrong with it: the real error goes to the server's log only.
"""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from feather_server.database import DatabaseCheck, check_database

LIVENESS_PATH = "/healthz"
READINESS_PATH = "/readyz"

READY = {"status": "ready", "checks": {"database": "ok"}}
NOT_READY = {"status": "not ready", "checks": {"database": "unavailable"}}


def readiness(check: DatabaseCheck) -> tuple[int, dict[str, Any]]:
    """The status and body /readyz answers: one word for every problem."""
    return (200, READY) if check.problem is None else (503, NOT_READY)


def router(database_url: str) -> APIRouter:
    routes = APIRouter()

    @routes.get(LIVENESS_PATH)
    def healthz() -> dict[str, str]:
        """Up while the process is: never touches the database, so an outage
        does not make the host restart the server."""
        return {"status": "alive"}

    @routes.get(READINESS_PATH)
    def readyz() -> JSONResponse:
        """Ready to take work: the database answers, live, within its 2 s."""
        status, body = readiness(check_database(database_url))
        return JSONResponse(body, status_code=status)

    return routes
