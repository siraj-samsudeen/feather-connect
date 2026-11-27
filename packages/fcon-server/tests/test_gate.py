"""The gate's own pieces (decision 1, design point 5).

Where a form's token is read from, and a refusal the database cannot record.
"""

import asyncio
import logging

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from starlette.responses import Response
from starlette.types import Message, Receive, Scope, Send

from fcon_server.app import create_app
from fcon_server.gate import Gate, form_token, read_body
from fcon_server.signing import SecretKeys
from fcon_server.store.clock import SystemClock
from fcon_server.store.ids import new_id
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store

KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"


def arriving(*chunks: bytes):
    """A `receive` giving the body in `chunks`, then a disconnect."""
    messages: list[Message] = [
        {"type": "http.request", "body": chunk, "more_body": n < len(chunks) - 1} for n, chunk in enumerate(chunks)
    ]
    messages.append({"type": "http.disconnect"})

    async def receive() -> Message:
        return messages.pop(0)

    return receive


def request(content_type: str | None = None, token_header: str | None = None) -> Scope:
    headers = [(b"content-type", content_type.encode())] if content_type else []
    if token_header is not None:
        headers.append((b"x-csrf-token", token_header.encode()))
    return {"type": "http", "method": "POST", "headers": headers}


def test_the_body_is_read_whole_from_its_chunks():
    body, _ = asyncio.run(read_body(arriving(b"csrf_", b"token=abc")))

    assert body == b"csrf_token=abc"


def test_the_body_read_is_given_to_the_app_again():
    async def read_twice() -> list[Message]:
        _, again = await read_body(arriving(b"a", b"b"))
        return [await again(), await again()]

    assert asyncio.run(read_twice()) == [
        {"type": "http.request", "body": b"ab", "more_body": False},
        {"type": "http.disconnect"},
    ]


def test_the_token_is_read_from_the_forms_field():
    token, _ = asyncio.run(form_token(request("application/x-www-form-urlencoded"), arriving(b"csrf_token=abc&x=1")))

    assert token == "abc"


def test_the_header_wins_over_the_field():
    token, _ = asyncio.run(
        form_token(request("application/x-www-form-urlencoded", "from-header"), arriving(b"csrf_token=abc"))
    )

    assert token == "from-header"


def test_a_body_that_is_not_a_form_carries_no_token():
    token, _ = asyncio.run(form_token(request("application/json"), arriving(b'{"csrf_token": "abc"}')))

    assert token == ""


def test_a_refusal_the_database_cannot_record_still_gets_the_expired_page(caplog: pytest.LogCaptureFixture):
    client = TestClient(create_app(NO_DATABASE, keys=KEYS))

    response = client.post("/sign-out", headers={"Origin": "https://elsewhere.example"})

    h1 = BeautifulSoup(response.text, "html.parser").h1
    assert (response.status_code, h1.get_text(strip=True) if h1 else "") == (403, "This form has expired")
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING] == [
        "a refused form could not be audited: the database did not answer"
    ]


def test_a_websocket_is_closed_before_any_route():
    """No websocket route is open by default: the gate closes every one."""
    reached: list[Scope] = []

    async def route(scope: Scope, receive: Receive, send: Send) -> None:
        reached.append(scope)

    gate = Gate(
        route,  # pyright: ignore[reportArgumentType] - any ASGI app does
        store=Store(OneConnectionEach(NO_DATABASE, "test"), SystemClock(), new_id),
        clock=SystemClock(),
        new_id=new_id,
        open_paths=frozenset({"/live"}),
        open_prefixes=(),
        sign_in_path="/sign-in",
        error_page=Response,
        form_expired_page=Response,
        choose_password_path="/choose-password",
        while_choosing=frozenset(),
    )
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    asyncio.run(gate({"type": "websocket", "path": "/live", "headers": []}, arriving(), send))

    assert (reached, sent) == ([], [{"type": "websocket.close", "code": 1008, "reason": ""}])
