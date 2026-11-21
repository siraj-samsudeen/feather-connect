"""The one stylesheet every page uses: served by the app itself, and the one
answer a browser may keep."""

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from fcon_server.app import create_app

NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(NO_DATABASE))


@pytest.mark.parametrize("path", ["/sign-in", "/runs/42"], ids=["sign-in", "not-found"])
def test_every_page_links_a_stylesheet_the_app_serves(client: TestClient, path: str):
    page = BeautifulSoup(client.get(path).text, "html.parser")
    hrefs = [str(link["href"]) for link in page.select('link[rel="stylesheet"]')]

    answers = [(client.get(href).status_code, client.get(href).headers["content-type"]) for href in hrefs]
    assert answers == [(200, "text/css; charset=utf-8")]


def test_a_browser_may_keep_the_stylesheet_if_it_checks_it_is_current(client: TestClient):
    response = client.get("/static/fcon.css")

    assert (response.headers["cache-control"], "etag" in response.headers) == ("no-cache", True)


def test_the_sign_in_page_is_never_kept(client: TestClient):
    assert client.get("/sign-in").headers["cache-control"] == "no-store"
