"""The front door and the sign-in page, as a browser is answered.

Signing in itself is in test_signing_in.py.
"""

import pytest
from bs4 import BeautifulSoup, Tag
from fastapi.testclient import TestClient

from fcon_server.app import create_app
from fcon_server.signing import SecretKeys

NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"
KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(NO_DATABASE, keys=KEYS))


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def field_labelled(page: BeautifulSoup, label_text: str) -> Tag:
    label = page.find("label", string=label_text)
    assert isinstance(label, Tag), f"no label {label_text!r}"
    field = page.find(id=str(label["for"]))
    assert isinstance(field, Tag)
    return field


def test_the_front_door_sends_a_visitor_to_sign_in(client: TestClient):
    response = client.get("/", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/sign-in")


def test_the_sign_in_page_names_the_product(client: TestClient):
    page = parse(client.get("/sign-in").text)

    assert [h1.get_text(strip=True) for h1 in page.find_all("h1")] == ["Feather Connect"]


def test_the_sign_in_page_asks_for_the_user_name(client: TestClient):
    field = field_labelled(parse(client.get("/sign-in").text), "User name")

    assert (field["name"], field["autocomplete"]) == ("username", "username")


def test_the_sign_in_page_asks_for_the_password(client: TestClient):
    field = field_labelled(parse(client.get("/sign-in").text), "Password")

    assert (field["name"], field["type"], field["autocomplete"]) == ("password", "password", "current-password")


def test_the_sign_in_form_posts_to_sign_in_with_its_button(client: TestClient):
    form = parse(client.get("/sign-in").text).find("form")

    assert isinstance(form, Tag)
    buttons = [button.get_text(strip=True) for button in form.find_all("button")]
    assert (form["method"], form["action"], buttons) == ("post", "/sign-in", ["Sign in"])
