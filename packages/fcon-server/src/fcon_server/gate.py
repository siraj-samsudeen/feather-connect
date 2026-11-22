"""The gate (decision 1): ASGI middleware in front of every route, so pages
are closed by default. A route needs a signed-in user unless it is on the
one short open list; a forgotten entry makes a page too closed, which shows
at once. An address that is no route at all goes on to the not-found page,
signed in or not.

For every request it makes the context: the request's tenant (decision 2), a
request id, and `system:anonymous` until a session says who it is. For a
closed route it reads the `fcon_session` cookie, loads the session and its
user (ending one that has run out), and puts them on the request as
`request.state.signed_in`; with no session it sends the visitor to sign-in.

Not yet here, each with the step that needs it: sending a user who must
choose a password to that page; refusing a POST, PUT, PATCH or DELETE whose
Origin names another site or whose form token is not the session's; the
`next` address to come back to after signing in."""

import logging
from collections.abc import Callable

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection
from starlette.responses import RedirectResponse, Response
from starlette.routing import Match
from starlette.types import Receive, Scope, Send

from fcon_server.store.clock import Clock
from fcon_server.store.context import Context, bind
from fcon_server.store.errors import StoreError
from fcon_server.store.ids import NewId
from fcon_server.store.transaction import Store
from fcon_server.users.sessions import SignedIn, signed_in
from fcon_server.users.tenant import request_tenant

logger = logging.getLogger("fcon.gate")

SESSION_COOKIE = "fcon_session"
ANONYMOUS = "system:anonymous"


class Gate:
    def __init__(
        self,
        app: FastAPI,
        *,
        store: Store,
        clock: Clock,
        new_id: NewId,
        open_paths: frozenset[str],
        open_prefixes: tuple[str, ...],
        sign_in_path: str,
        error_page: Callable[[], Response],
    ) -> None:
        self.app = app
        self.store = store
        self.clock = clock
        self.new_id = new_id
        self.open_paths = open_paths
        self.open_prefixes = open_prefixes
        self.sign_in_path = sign_in_path
        self.error_page = error_page

    def _is_open(self, path: str) -> bool:
        return path in self.open_paths or path.startswith(self.open_prefixes)

    def _is_a_route(self, scope: Scope) -> bool:
        return any(route.matches(scope)[0] is not Match.NONE for route in self.app.router.routes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        context = Context(tenant_id=request_tenant(), actor=ANONYMOUS, request_id=self.new_id().hex)
        state = scope.setdefault("state", {})
        state["context"] = context
        state["signed_in"] = None
        with bind(context):
            if self._is_open(scope["path"]) or not self._is_a_route(scope):
                await self.app(scope, receive, send)
                return
            session_id = HTTPConnection(scope).cookies.get(SESSION_COOKIE)
            try:
                found = await self._session(context, session_id)
            except StoreError:
                logger.warning("a page could not read its session: the database did not answer")
                await self.error_page()(scope, receive, send)
                return
            if found is None:
                await RedirectResponse(self.sign_in_path, status_code=303)(scope, receive, send)
                return
            state["context"] = found.caller.context
            state["signed_in"] = found
            with bind(found.caller.context):
                await self.app(scope, receive, send)

    async def _session(self, context: Context, session_id: str | None) -> SignedIn | None:
        if not session_id:
            return None
        return await run_in_threadpool(signed_in, self.store, self.clock, context, session_id)
