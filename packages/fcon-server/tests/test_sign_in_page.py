"""The front door and the sign-in page, as a browser is answered."""

import pytest
from bs4 import BeautifulSoup, Tag
from fastapi.testclient import TestClient

from fcon_server.app import create_app

NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"
REFUSAL = "The user name or password is wrong."


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(NO_DATABASE))


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


def test_a_sign_in_is_refused_with_the_same_words(client: TestClient):
    response = client.post("/sign-in", data={"username": "alex", "password": "letmein"})

    alerts = [alert.get_text(strip=True) for alert in parse(response.text).select('[role="alert"]')]
    assert (response.status_code, alerts) == (200, [REFUSAL])


def test_a_refused_sign_in_is_titled_as_failed(client: TestClient):
    response = client.post("/sign-in", data={"username": "alex", "password": "letmein"})

    title = parse(response.text).title
    assert title is not None
    assert title.get_text().startswith("Sign-in failed")


def test_a_refused_sign_in_keeps_the_user_name_typed(client: TestClient):
    response = client.post("/sign-in", data={"username": "alex", "password": "letmein"})

    assert field_labelled(parse(response.text), "User name")["value"] == "alex"


def test_a_refused_sign_in_never_shows_the_password(client: TestClient):
    response = client.post("/sign-in", data={"username": "alex", "password": "a-secret-word"})

    assert "a-secret-word" not in response.text


def test_a_sign_in_with_empty_fields_is_refused_too(client: TestClient):
    response = client.post("/sign-in", data={})

    alerts = [alert.get_text(strip=True) for alert in parse(response.text).select('[role="alert"]')]
    assert (response.status_code, alerts) == (200, [REFUSAL])
