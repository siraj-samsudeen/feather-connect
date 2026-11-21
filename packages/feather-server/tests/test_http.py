"""How the app answers any address: HEAD, trailing slashes, safety headers."""

import pytest
from fastapi.testclient import TestClient

from feather_server.app import create_app

NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(NO_DATABASE))


def test_head_is_answered_like_get_without_the_body(client: TestClient):
    get = client.get("/healthz")

    head = client.head("/healthz")

    assert (head.status_code, head.headers["content-length"], head.content) == (200, get.headers["content-length"], b"")


def test_an_address_with_a_trailing_slash_is_not_redirected(client: TestClient):
    response = client.get("/healthz/", follow_redirects=False)

    assert response.status_code == 404
