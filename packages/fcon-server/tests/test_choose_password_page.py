"""The page to choose a password (design point 9, the agreed mockup).

It is shown before any other page while the user's password was given to them.
"""

from collections.abc import Iterator

import pytest
from bs4 import BeautifulSoup, Tag
from fastapi.testclient import TestClient

from fcon_server.app import create_app
from fcon_server.pages import choose_password_view
from fcon_server.signing import SecretKeys
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.migrate import upgrade
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import NewUser, add_user
from fcon_server.users.choosing import ChoiceProblem
from fcon_server.users.rights import Caller, Role
from fcon_server.users.rules import PasswordProblem
from fcon_server.users.tenant import request_tenant

KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")
GIVEN = "given-once-0001"
CHOSEN = "ben-own-password-1"


@pytest.fixture
def client(empty_database_url: str) -> Iterator[TestClient]:
    """The app on a database with "ann", whose password is her own, and "ben", with one given him."""
    upgrade(empty_database_url, SystemClock())
    store = Store(OneConnectionEach(empty_database_url, "fcon-test"), SystemClock(), new_id)
    context = Context(tenant_id=request_tenant(), actor="system:test", request_id="test-setup")
    admin = Caller(context, Role.ADMINISTRATOR)
    add_user(store, admin, NewUser("ann", "blue-harbour-lamp"))
    add_user(store, admin, NewUser("ben", GIVEN, Role.OPERATOR))
    with TestClient(create_app(empty_database_url, keys=KEYS, secure_cookies=False, pool_size=1)) as client:
        yield client


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def sign_in(client: TestClient, name: str = "ben", password: str = GIVEN) -> None:
    field = parse(client.get("/sign-in").text).find("input", attrs={"name": "sign_in_token"})
    assert isinstance(field, Tag)
    client.post("/sign-in", data={"username": name, "password": password, "sign_in_token": str(field["value"])})


def choose_page(client: TestClient) -> BeautifulSoup:
    return parse(client.get("/choose-password").text)


def field_labelled(page: BeautifulSoup, text: str) -> Tag:
    label = page.find("label", string=text)
    assert isinstance(label, Tag), f"no label {text!r}"
    field = page.find(id=str(label["for"]))
    assert isinstance(field, Tag)
    return field


def form_token(page: BeautifulSoup) -> str:
    token = page.find("input", attrs={"name": "csrf_token"})
    assert isinstance(token, Tag), "no form token"
    return str(token["value"])


def choose(client: TestClient, password: str, again: str | None = None):
    page = choose_page(client)
    form = page.find("form")
    assert isinstance(form, Tag)
    data = {
        "csrf_token": form_token(page),
        str(field_labelled(page, "New password")["name"]): password,
        str(field_labelled(page, "The same again")["name"]): password if again is None else again,
    }
    return client.post(str(form["action"]), data=data, follow_redirects=False)


def alerts(html: str) -> list[str]:
    return [alert.get_text(strip=True) for alert in parse(html).select('[role="alert"]')]


# -- before any other page ------------------------------------------------------


@pytest.mark.database
def test_a_user_with_a_given_password_is_sent_to_choose_one(client: TestClient):
    sign_in(client)

    response = client.get("/", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/choose-password")


@pytest.mark.database
def test_a_user_choosing_a_password_may_sign_out(client: TestClient):
    sign_in(client)

    response = client.post("/sign-out", data={"csrf_token": form_token(choose_page(client))}, follow_redirects=False)

    assert response.headers["location"] == "/sign-in"


@pytest.mark.database
def test_a_user_with_their_own_password_is_sent_on_to_the_overview(client: TestClient):
    sign_in(client, "ann", "blue-harbour-lamp")

    response = client.get("/choose-password", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/")


# -- the page --------------------------------------------------------------------


@pytest.mark.database
def test_the_page_asks_the_user_to_choose_their_password(client: TestClient):
    sign_in(client)

    page = choose_page(client)

    assert [h1.get_text(strip=True) for h1 in page.find_all("h1")] == ["Choose your password"]
    assert "The one you were given works only once." in page.get_text(" ", strip=True)


@pytest.mark.database
def test_the_page_is_titled_for_choosing_a_password(client: TestClient):
    sign_in(client)

    title = choose_page(client).title

    assert title is not None and title.get_text() == "Choose your password – Feather Connect"


@pytest.mark.database
@pytest.mark.parametrize("label", ["New password", "The same again"])
def test_the_page_asks_for_a_new_password(client: TestClient, label: str):
    sign_in(client)

    field = field_labelled(choose_page(client), label)

    assert (field["type"], field["autocomplete"], field.get("required")) == ("password", "new-password", "required")


@pytest.mark.database
def test_the_page_gives_the_rule_for_a_password(client: TestClient):
    sign_in(client)

    page = choose_page(client)
    hint = page.find(id=str(field_labelled(page, "New password")["aria-describedby"]))

    assert isinstance(hint, Tag) and hint.get_text(strip=True) == "At least 12 characters."


@pytest.mark.database
def test_the_form_saves_the_password_with_the_sessions_token(client: TestClient):
    sign_in(client)

    page = choose_page(client)
    form = page.find("form")

    assert isinstance(form, Tag)
    buttons = [button.get_text(strip=True) for button in form.find_all("button")]
    assert (form["method"], form["action"], len(form_token(page)) >= 43, buttons) == (
        "post",
        "/choose-password",
        True,
        ["Save password"],
    )


# -- choosing --------------------------------------------------------------------


@pytest.mark.database
def test_a_password_chosen_leads_to_the_overview(client: TestClient):
    sign_in(client)

    response = choose(client, CHOSEN)

    assert (response.status_code, response.headers["location"], client.get("/").status_code) == (303, "/", 200)


@pytest.mark.database
def test_a_password_that_breaks_a_rule_is_refused_saying_which(client: TestClient):
    sign_in(client)

    response = choose(client, "short-one")

    assert (response.status_code, alerts(response.text)) == (
        200,
        ["The password is too short: use at least 12 characters."],
    )


@pytest.mark.database
def test_a_refused_password_leaves_the_user_to_choose_one(client: TestClient):
    sign_in(client)
    choose(client, "short-one")

    assert client.get("/", follow_redirects=False).headers["location"] == "/choose-password"


@pytest.mark.database
def test_a_refused_password_marks_the_fields_invalid(client: TestClient):
    sign_in(client)

    page = parse(choose(client, CHOSEN, CHOSEN + "x").text)

    assert [field_labelled(page, label).get("aria-invalid") for label in ("New password", "The same again")] == [
        "true",
        "true",
    ]


@pytest.mark.database
def test_a_password_chosen_already_is_not_chosen_again_from_an_old_form(client: TestClient):
    sign_in(client)
    page = choose_page(client)
    choose(client, CHOSEN)

    response = client.post(
        "/choose-password",
        data={"csrf_token": form_token(page), "new_password": CHOSEN + "-2", "password_again": CHOSEN + "-2"},
        follow_redirects=False,
    )

    assert (response.status_code, response.headers["location"]) == (303, "/")


# -- what the page says, as computed for its template -----------------------------------


@pytest.mark.parametrize(
    ("problem", "text"),
    [
        (PasswordProblem.TOO_SHORT, "The password is too short: use at least 12 characters."),
        (PasswordProblem.TOO_LONG, "The password is too long: use at most 128 characters."),
        (PasswordProblem.TOO_COMMON, "The password is too common: it is one of the most used."),
        (PasswordProblem.OWN_NAME, "The password is the user's own name: choose another."),
        (ChoiceProblem.DIFFERENT, "The two entries are not the same: type the password twice."),
    ],
    ids=["too-short", "too-long", "too-common", "own-name", "different"],
)
def test_a_refused_password_says_which_rule_it_broke(problem: PasswordProblem | ChoiceProblem, text: str):
    assert [alert.text for alert in choose_password_view(problem).alerts] == [text]


def test_the_page_shows_no_alert_before_a_password_is_chosen():
    assert choose_password_view().alerts == ()
