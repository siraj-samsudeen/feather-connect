"""The gate (decision 1): ASGI middleware in front of every route, so pages
are closed by default. A route needs a signed-in user unless it is on the
one short open list; a forgotten entry makes a page too closed, which shows
at once. An address that is no route at all is closed too: only a signed-in
user is told it is not found, so a stranger can't tell which addresses
exist.

For every request it makes the context: the request's tenant (decision 2), a
request id, and `system:anonymous` until a session says who it is. For a
closed route it reads the `fcon_session` cookie, loads the session and its
user (ending one that has run out), and puts them on the request as
`request.state.signed_in`; with no session it sends the visitor to sign-in,
naming the page asked for (`/sign-in?next=...`) when it was a GET.

A POST, PUT, PATCH or DELETE whose Origin names another site is refused
before anything else, signed in or not; one behind sign-in whose form token
(the field `csrf_token`, or the header `X-CSRF-Token`) is not the session's
is refused too. Both get the form-expired page (403) and a refused audit
record (design point 5).

A user who must choose a password is sent to that page from every other
but signing out.

A websocket is closed (1008) before any route: none is open by default."""

import hmac
import logging
from collections.abc import Callable
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.responses import RedirectResponse, Response
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.types import Message, Receive, Scope, Send
from starlette.websockets import WebSocketClose

from fcon_server.store.clock import Clock
from fcon_server.store.context import Context, bind
from fcon_server.store.errors import StoreError
from fcon_server.store.ids import NewId
from fcon_server.store.transaction import Store
from fcon_server.users.sessions import FOREIGN_ORIGIN, WRONG_FORM_TOKEN, SignedIn, refuse_form, signed_in
from fcon_server.users.tenant import request_tenant

logger = logging.getLogger("fcon.gate")

SESSION_COOKIE = "fcon_session"
ANONYMOUS = "system:anonymous"
CHANGES = frozenset({"POST", "PUT", "PATCH", "DELETE"})
FORM_TOKEN_FIELD = "csrf_token"  # noqa: S105 - a field name, not a secret
FORM_TOKEN_HEADER = "x-csrf-token"  # noqa: S105 - a header's name, not a secret
FORM = "application/x-www-form-urlencoded"


def comes_from_another_site(headers: Headers) -> bool:
    """An Origin that is not this site's own (`null` included); a request
    without one is left to the form token."""
    origin = headers.get("origin")
    return origin is not None and urlsplit(origin).netloc != headers.get("host", "")


async def read_body(receive: Receive) -> tuple[bytes, Receive]:
    """The whole body, and a `receive` that gives it to the app again."""
    body, more = b"", True
    while more:
        message = await receive()
        body += message.get("body", b"")
        more = message.get("more_body", False)
    given = False

    async def again() -> Message:
        nonlocal given
        if given:
            return await receive()
        given = True
        return {"type": "http.request", "body": body, "more_body": False}

    return body, again


async def form_token(scope: Scope, receive: Receive) -> tuple[str, Receive]:
    """The token in the header `X-CSRF-Token`, else in the form's field."""
    headers = Headers(scope=scope)
    if (token := headers.get(FORM_TOKEN_HEADER)) is not None:
        return token, receive
    body, receive = await read_body(receive)
    if not headers.get("content-type", "").startswith(FORM):
        return "", receive
    return parse_qs(body.decode("latin-1")).get(FORM_TOKEN_FIELD, [""])[0], receive


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
        form_expired_page: Callable[[], Response],
        choose_password_path: str,
        while_choosing: frozenset[str],
    ) -> None:
        self.app = app
        self.store = store
        self.clock = clock
        self.new_id = new_id
        self.open_paths = open_paths
        self.open_prefixes = open_prefixes
        self.sign_in_path = sign_in_path
        self.error_page = error_page
        self.form_expired_page = form_expired_page
        self.choose_password_path = choose_password_path
        self.while_choosing = while_choosing

    def _is_open(self, path: str) -> bool:
        return path in self.open_paths or path.startswith(self.open_prefixes)

    def _sign_in_address(self, scope: Scope) -> str:
        """Sign-in, naming the page a GET asked for, unless it was the overview."""
        asked = scope["path"] + (f"?{scope['query_string'].decode('latin-1')}" if scope["query_string"] else "")
        if scope["method"] != "GET" or asked == "/":
            return self.sign_in_path
        return f"{self.sign_in_path}?{urlencode({'next': asked})}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":  # none is open by default: a route needing one opens it here
            await WebSocketClose(WS_1008_POLICY_VIOLATION)(scope, receive, send)
            return
        if scope["type"] != "http":  # lifespan
            await self.app(scope, receive, send)
            return
        context = Context(tenant_id=request_tenant(), actor=ANONYMOUS, request_id=self.new_id().hex)
        state = scope.setdefault("state", {})
        state["context"] = context
        state["signed_in"] = None
        with bind(context):
            changes = scope["method"] in CHANGES
            if changes and comes_from_another_site(Headers(scope=scope)):
                await self._refuse(scope, receive, send, context, None, FOREIGN_ORIGIN)
                return
            if self._is_open(scope["path"]):
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
                await RedirectResponse(self._sign_in_address(scope), status_code=303)(scope, receive, send)
                return
            state["context"] = found.caller.context
            state["signed_in"] = found
            with bind(found.caller.context):
                if changes:
                    token, receive = await form_token(scope, receive)
                    if not hmac.compare_digest(token.encode(), found.form_token.encode()):
                        await self._refuse(scope, receive, send, found.caller.context, found, WRONG_FORM_TOKEN)
                        return
                if found.must_choose_password and scope["path"] not in self.while_choosing:
                    await RedirectResponse(self.choose_password_path, status_code=303)(scope, receive, send)
                    return
                await self.app(scope, receive, send)

    async def _refuse(
        self, scope: Scope, receive: Receive, send: Send, context: Context, found: SignedIn | None, reason: str
    ) -> None:
        """The form-expired page (403), with a refused audit record."""
        session_id = None if found is None else found.session_id
        try:
            await run_in_threadpool(refuse_form, self.store, context, session_id, reason)
        except StoreError:
            logger.warning("a refused form could not be audited: the database did not answer")
        await self.form_expired_page()(scope, receive, send)

    async def _session(self, context: Context, session_id: str | None) -> SignedIn | None:
        if not session_id:
            return None
        return await run_in_threadpool(signed_in, self.store, self.clock, context, session_id)
