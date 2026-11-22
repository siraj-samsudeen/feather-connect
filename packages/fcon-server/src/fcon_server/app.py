"""The server's web app: what a browser, a monitor or the host is answered."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp

from fcon_server import health, pages
from fcon_server.middleware import HeadAsGet, SafetyHeaders
from fcon_server.store.clock import SystemClock
from fcon_server.store.ids import new_id
from fcon_server.store.pool import DEFAULT_SIZE, Pool, make_pool
from fcon_server.store.transaction import Store


def create_app(database_url: str, *, pool_size: int = DEFAULT_SIZE, prepare: bool = True) -> ASGIApp:
    """The app, talking to the database at `database_url` (a libpq address)."""
    return with_middleware(build_app(database_url, pool_size=pool_size, prepare=prepare))


def _lifespan(pool: Pool) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        pool.open(wait=False)  # the database may come later: readiness says so
        try:
            yield
        finally:
            pool.close()

    return lifespan


def build_app(database_url: str, *, pool_size: int = DEFAULT_SIZE, prepare: bool = True) -> FastAPI:
    """The routes and their error pages, without the middleware around them.
    `app.state.store` is the store, on a pool open while the server runs;
    readiness keeps a connection of its own (design decision 3)."""
    pool = make_pool(database_url, pool_size, prepare=prepare)
    # No automatic trailing-slash redirect: FastAPI builds it as a full http://
    # address from what it saw, which behind an https proxy is the insecure one.
    # No API description pages until there is an API to describe.
    app = FastAPI(redirect_slashes=False, docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan(pool))
    app.state.pool = pool
    app.state.store = Store(pool, SystemClock(), new_id)
    app.include_router(health.router(database_url))
    app.include_router(pages.router())
    app.mount(pages.STATIC_PATH, StaticFiles(directory=pages.STATIC_DIRECTORY))
    pages.install_error_pages(app)
    return app


def with_middleware(app: ASGIApp) -> ASGIApp:
    """What holds for every answer, errors included: HEAD, the safety headers."""
    return SafetyHeaders(HeadAsGet(app), cacheable_paths=frozenset({pages.STYLESHEET_PATH}))
