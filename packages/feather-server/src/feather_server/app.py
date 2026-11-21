"""The server's web app: what a browser, a monitor or the host is answered."""

from fastapi import FastAPI
from starlette.types import ASGIApp

from feather_server import health
from feather_server.middleware import HeadAsGet


def create_app(database_url: str) -> ASGIApp:
    """The app, talking to the database at `database_url` (a libpq address)."""
    app = FastAPI()
    app.include_router(health.router(database_url))
    return HeadAsGet(app)
