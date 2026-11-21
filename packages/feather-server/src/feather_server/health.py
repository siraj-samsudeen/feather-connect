"""Health and readiness: what the host and an uptime monitor ask."""

from fastapi import APIRouter

LIVENESS_PATH = "/healthz"


def router(database_url: str) -> APIRouter:  # noqa: ARG001 - readiness will use it
    routes = APIRouter()

    @routes.get(LIVENESS_PATH)
    def healthz() -> dict[str, str]:
        """Up while the process is: never touches the database, so an outage
        does not make the host restart the server."""
        return {"status": "alive"}

    return routes
