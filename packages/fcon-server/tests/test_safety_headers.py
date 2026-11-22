"""The safety headers every response carries, errors included."""

from collections.abc import Mapping

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from fcon_server.app import create_app
from fcon_server.middleware import SafetyHeaders
from fcon_server.signing import SecretKeys

KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"

SAFETY_HEADERS = {
    "content-security-policy": (
        "default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "cache-control": "no-store",
}


def safety_headers_of(headers: Mapping[str, str]) -> dict[str, str | None]:
    return {name: headers.get(name) for name in SAFETY_HEADERS}


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/healthz"), ("HEAD", "/healthz"), ("GET", "/no-such-page"), ("POST", "/healthz")],
    ids=["an-answer", "a-head-answer", "not-found", "method-not-allowed"],
)
def test_every_answer_carries_the_safety_headers(method: str, path: str):
    client = TestClient(create_app(NO_DATABASE, keys=KEYS))

    response = client.request(method, path)

    assert safety_headers_of(response.headers) == SAFETY_HEADERS


def test_a_failure_inside_the_server_carries_the_safety_headers():
    def crash(request: Request) -> Response:
        raise RuntimeError("a bug")

    client = TestClient(SafetyHeaders(Starlette(routes=[Route("/crash", crash)])), raise_server_exceptions=False)

    response = client.get("/crash")

    assert (response.status_code, safety_headers_of(response.headers)) == (500, SAFETY_HEADERS)
