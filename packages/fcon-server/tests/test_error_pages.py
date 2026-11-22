"""The product's own pages for an address it does not have and for a failure
inside the server."""

import logging

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from fcon_server.app import build_app, with_middleware
from fcon_server.pages import error_view, not_found_view
from fcon_server.signing import SecretKeys

KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"
MISSING = "/runs/a-made-up-address"
FAILURE = "a made-up failure inside the server"


@pytest.fixture
def client() -> TestClient:
    """The routes without the gate, as a signed-in user reaches them: the gate
    sends anyone else to sign-in (test_signing_in.py)."""
    return TestClient(with_middleware(build_app(NO_DATABASE, keys=KEYS)))


@pytest.fixture
def crashing_client() -> TestClient:
    """The app with one more route, only here, that fails as a bug would."""
    app = build_app(NO_DATABASE, keys=KEYS)

    def crash() -> None:
        raise RuntimeError(FAILURE)

    app.add_api_route("/crash", crash)
    return TestClient(with_middleware(app), raise_server_exceptions=False)


def headings(html: str) -> list[str]:
    return [h1.get_text(strip=True) for h1 in BeautifulSoup(html, "html.parser").find_all("h1")]


def test_the_not_found_page_is_titled_page_not_found():
    assert not_found_view().title == "Page not found – Feather Connect"


def test_the_error_page_is_titled_something_went_wrong():
    assert error_view().title == "Something went wrong – Feather Connect"


@pytest.mark.parametrize("path", [MISSING, "/sign-in/"], ids=["unknown", "trailing-slash"])
def test_an_unknown_address_gets_the_not_found_page(client: TestClient, path: str):
    response = client.get(path)

    assert (response.status_code, headings(response.text)) == (404, ["Page not found"])


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_api_description_is_served_until_there_is_an_api(client: TestClient, path: str):
    assert client.get(path).status_code == 404


def test_the_not_found_page_leads_on_to_the_overview(client: TestClient):
    page = BeautifulSoup(client.get(MISSING).text, "html.parser")

    links = [(link["href"], link.get_text(strip=True).lower()) for link in page.find_all("a")]
    assert links == [("/", "go to the overview")]


def test_the_not_found_page_never_repeats_the_address(client: TestClient):
    assert "a-made-up-address" not in client.get(MISSING).text


def test_a_failure_inside_the_server_gets_the_error_page(crashing_client: TestClient):
    response = crashing_client.get("/crash")

    assert (response.status_code, headings(response.text)) == (500, ["Something went wrong"])


def test_the_error_page_never_shows_what_failed(crashing_client: TestClient):
    text = crashing_client.get("/crash").text

    assert (FAILURE in text, "Traceback" in text) == (False, False)


def test_a_failure_inside_the_server_is_logged_as_a_bug(crashing_client: TestClient, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.ERROR, logger="fcon_server"):
        crashing_client.get("/crash")

    assert [record.getMessage() for record in caplog.records if record.name == "fcon_server.pages"] == [
        "a bug: GET /crash failed inside the server (RuntimeError)"
    ]
