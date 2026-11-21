"""The server's web app: what a browser, a monitor or the host is answered."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp

from feather_server import health, pages
from feather_server.middleware import HeadAsGet, SafetyHeaders


def create_app(database_url: str) -> ASGIApp:
    """The app, talking to the database at `database_url` (a libpq address)."""
    return with_middleware(build_app(database_url))


def build_app(database_url: str) -> FastAPI:
    """The routes and their error pages, without the middleware around them."""
    # No automatic trailing-slash redirect: FastAPI builds it as a full http://
    # address from what it saw, which behind an https proxy is the insecure one.
    app = FastAPI(redirect_slashes=False)
    app.include_router(health.router(database_url))
    app.include_router(pages.router())
    app.mount(pages.STATIC_PATH, StaticFiles(directory=pages.STATIC_DIRECTORY))
    pages.install_error_pages(app)
    return app


def with_middleware(app: ASGIApp) -> ASGIApp:
    """What holds for every answer, errors included: HEAD, the safety headers."""
    return SafetyHeaders(HeadAsGet(app), cacheable_paths=frozenset({pages.STYLESHEET_PATH}))
