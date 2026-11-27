"""The server's web app: what a browser, a monitor or the host is answered."""

from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp

from fcon_server import health, pages
from fcon_server.gate import Gate
from fcon_server.middleware import HeadAsGet, SafetyHeaders
from fcon_server.proxies import RealAddress, TrustedProxies
from fcon_server.signing import SecretKeys
from fcon_server.store.clock import Clock, SystemClock
from fcon_server.store.ids import new_id
from fcon_server.store.pool import DEFAULT_SIZE, Pool, make_pool
from fcon_server.store.transaction import Store

DEFAULT_ENVIRONMENT = "development"
_SYSTEM_CLOCK = SystemClock()


def create_app(  # noqa: PLR0913  # keyword-only settings with defaults: each caller names only the few that differ
    database_url: str,
    *,
    keys: SecretKeys,
    environment: str = DEFAULT_ENVIRONMENT,
    secure_cookies: bool = True,
    pool_size: int = DEFAULT_SIZE,
    prepare: bool = True,
    clock: Clock = _SYSTEM_CLOCK,
    trusted_proxies: TrustedProxies | None = None,
    on_untrusted_forwarding: Callable[[], None] = lambda: None,
) -> ASGIApp:
    """The server's whole app, talking to the database at `database_url` (a libpq address).

    `secure_cookies` is False only for a server on its own machine alone, over
    plain http (design point 8). Forwarded headers are believed only from
    `trusted_proxies`; with none, `on_untrusted_forwarding` is called on the
    first request that carries one.
    """
    app = build_app(
        database_url,
        keys=keys,
        environment=environment,
        secure_cookies=secure_cookies,
        pool_size=pool_size,
        prepare=prepare,
        clock=clock,
    )
    gate = Gate(
        app,
        store=app.state.store,
        clock=clock,
        new_id=new_id,
        open_paths=pages.OPEN_PATHS | {health.LIVENESS_PATH, health.READINESS_PATH},
        open_prefixes=pages.OPEN_PREFIXES,
        sign_in_path=pages.SIGN_IN_PATH,
        error_page=pages.error_page,
        form_expired_page=pages.form_expired_page,
        choose_password_path=pages.CHOOSE_PASSWORD_PATH,
        while_choosing=pages.WHILE_CHOOSING,
    )
    return with_middleware(RealAddress(gate, trusted_proxies, on_untrusted_forwarding))


def _lifespan(pool: Pool) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    """The app's lifespan: the store's pool opens when the server starts and closes when it stops."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        """Open the pool without waiting for the database, and close it when the server stops."""
        pool.open(wait=False)  # the database may come later: readiness says so
        try:
            yield
        finally:
            pool.close()

    return lifespan


def build_app(  # noqa: PLR0913  # keyword-only settings with defaults: each caller names only the few that differ
    database_url: str,
    *,
    keys: SecretKeys,
    environment: str = DEFAULT_ENVIRONMENT,
    secure_cookies: bool = True,
    pool_size: int = DEFAULT_SIZE,
    prepare: bool = True,
    clock: Clock = _SYSTEM_CLOCK,
) -> FastAPI:
    """The routes and their error pages, without the middleware around them.

    `app.state.store` is the store, on a pool open while the server runs;
    readiness keeps a connection of its own (design decision 3).
    """
    pool = make_pool(database_url, pool_size, prepare=prepare)
    # No automatic trailing-slash redirect: FastAPI builds it as a full http://
    # address from what it saw, which behind an https proxy is the insecure one.
    # No API description pages until there is an API to describe.
    app = FastAPI(redirect_slashes=False, docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan(pool))
    app.state.pool = pool
    app.state.clock = clock
    app.state.store = Store(pool, clock, new_id)
    app.state.site = pages.Site(keys=keys, environment=environment, secure_cookies=secure_cookies)
    app.include_router(health.router(database_url))
    app.include_router(pages.router())
    app.mount(pages.STATIC_PATH, StaticFiles(directory=pages.STATIC_DIRECTORY))
    pages.install_error_pages(app)
    return app


def with_middleware(app: ASGIApp) -> ASGIApp:
    """What holds for every answer, errors included: HEAD, the safety headers."""
    return SafetyHeaders(HeadAsGet(app), cacheable_paths=frozenset({pages.STYLESHEET_PATH}))
