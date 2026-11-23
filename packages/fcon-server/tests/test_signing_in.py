"""Signing in through the pages, and the pages behind it (design points 4, 5,
6 and 9, decisions 1 and 2): the sign-in form's own token, the session's
cookie, the gate in front of every route, and the overview."""

from collections.abc import Iterator

import httpx2 as httpx
import psycopg
import pytest
from bs4 import BeautifulSoup, Tag
from fastapi.testclient import TestClient

from fcon_server.app import create_app
from fcon_server.proxies import trusted_proxies
from fcon_server.signing import SecretKeys
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.migrate import upgrade
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import NewUser, add_user
from fcon_server.users.rights import Caller, Role
from fcon_server.users.tenant import request_tenant

pytestmark = pytest.mark.database

KEYS = SecretKeys("a-test-secret-key-of-32-characters-or-more")
NO_DATABASE = "postgresql://nobody:secret@127.0.0.1:9/nowhere"
PASSWORD = "blue-harbour-lamp"
REFUSAL = "The user name or password is wrong."


@pytest.fixture
def site_database(empty_database_url: str) -> str:
    """A database of the test's own, upgraded, with "ann" as its first user:
    the pages work in the tenant `default`, which the session's database shares."""
    upgrade(empty_database_url, SystemClock())
    store = Store(OneConnectionEach(empty_database_url, "fcon-test"), SystemClock(), new_id)
    context = Context(tenant_id=request_tenant(), actor="system:test", request_id="test-setup")
    add_user(store, Caller(context, Role.ADMINISTRATOR), NewUser("ann", PASSWORD))
    add_user(store, Caller(context, Role.ADMINISTRATOR), NewUser("ben", "given-once-0001", Role.OPERATOR))
    return empty_database_url


@pytest.fixture
def client(site_database: str) -> Iterator[TestClient]:
    with TestClient(
        create_app(site_database, keys=KEYS, environment="staging", secure_cookies=False, pool_size=1)
    ) as client:
        yield client


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def sign_in_token(client: TestClient) -> str:
    field = parse(client.get("/sign-in").text).find("input", attrs={"name": "sign_in_token"})
    assert isinstance(field, Tag), "no sign-in token in the form"
    return str(field["value"])


def sign_in(client: TestClient, name: str = "ann", password: str = PASSWORD):
    token = sign_in_token(client)
    return client.post(
        "/sign-in", data={"username": name, "password": password, "sign_in_token": token}, follow_redirects=False
    )


def heading(html: str) -> str:
    h1 = parse(html).h1
    return h1.get_text(strip=True) if h1 else ""


def alerts(html: str) -> list[str]:
    return [alert.get_text(strip=True) for alert in parse(html).select('[role="alert"]')]


def set_cookie(response: httpx.Response, name: str) -> str:
    [header] = [value for value in response.headers.get_list("set-cookie") if value.startswith(name + "=")]
    return header


# -- the sign-in form's own token ---------------------------------------------


def test_the_sign_in_form_carries_the_token_of_its_cookie(client: TestClient):
    token = sign_in_token(client)

    assert client.cookies.get("fcon_sign_in") == token


def test_the_sign_in_cookie_is_for_the_sign_in_page_alone(client: TestClient):
    response = client.get("/sign-in")

    attributes = set_cookie(response, "fcon_sign_in").lower()
    assert ("httponly" in attributes, "samesite=lax" in attributes, "path=/sign-in" in attributes) == (True, True, True)


def test_the_sign_in_page_keeps_a_token_still_valid(client: TestClient):
    assert sign_in_token(client) == sign_in_token(client)


def test_a_sign_in_without_the_token_is_refused_as_expired(client: TestClient):
    client.get("/sign-in")

    response = client.post("/sign-in", data={"username": "ann", "password": PASSWORD})

    assert (response.status_code, heading(response.text)) == (
        403,
        "This form has expired",
    )


def test_a_sign_in_with_a_token_not_its_cookies_is_refused_as_expired(client: TestClient):
    token = sign_in_token(client)
    client.cookies.clear()
    client.get("/sign-in")

    response = client.post("/sign-in", data={"username": "ann", "password": PASSWORD, "sign_in_token": token})

    assert response.status_code == 403


def test_the_expired_form_says_to_reload_and_leads_to_the_overview(client: TestClient):
    page = parse(client.post("/sign-in", data={"username": "ann", "password": PASSWORD}).text)

    links = [(a.get_text(strip=True), a["href"]) for a in page.find_all("a")]
    assert ("Reload the page and try again." in page.get_text(), links) == (True, [("Go to the overview", "/")])


# -- signing in ---------------------------------------------------------------


def test_a_wrong_password_is_refused_with_the_same_words(client: TestClient):
    response = sign_in(client, password="letmein")

    assert (response.status_code, alerts(response.text)) == (200, [REFUSAL])


def test_a_name_nobody_has_is_refused_with_the_same_words(client: TestClient):
    response = sign_in(client, name="alex")

    assert (response.status_code, alerts(response.text)) == (200, [REFUSAL])


def test_a_refused_sign_in_is_titled_as_failed(client: TestClient):
    title = parse(sign_in(client, password="letmein").text).title

    assert title is not None and title.get_text().startswith("Sign-in failed")


def test_a_refused_sign_in_keeps_the_user_name_typed(client: TestClient):
    field = parse(sign_in(client, name="alex").text).find("input", attrs={"name": "username"})

    assert isinstance(field, Tag) and field["value"] == "alex"


def test_a_refused_sign_in_never_shows_the_password(client: TestClient):
    assert "a-secret-word" not in sign_in(client, password="a-secret-word").text


def test_a_sign_in_with_empty_fields_is_refused_too(client: TestClient):
    response = sign_in(client, name="", password="")

    assert (response.status_code, alerts(response.text)) == (200, [REFUSAL])


def test_a_refused_sign_in_can_be_tried_again_from_its_form(client: TestClient):
    refused = parse(sign_in(client, password="letmein").text)
    field = refused.find("input", attrs={"name": "sign_in_token"})
    assert isinstance(field, Tag)

    response = client.post(
        "/sign-in", data={"username": "ann", "password": PASSWORD, "sign_in_token": str(field["value"])}
    )

    assert response.url.path == "/"


def test_the_right_password_leads_to_the_overview(client: TestClient):
    response = sign_in(client)

    assert (response.status_code, response.headers["location"]) == (303, "/")


def test_the_session_cookie_is_kept_from_scripts_and_other_sites(client: TestClient):
    attributes = set_cookie(sign_in(client), "fcon_session").lower()

    assert ("httponly" in attributes, "samesite=lax" in attributes, "path=/" in attributes) == (True, True, True)


def test_the_session_cookie_is_not_secure_on_a_server_of_this_machine_alone(client: TestClient):
    assert "secure" not in set_cookie(sign_in(client), "fcon_session").lower()


def test_the_session_cookie_is_secure_otherwise(site_database: str):
    with TestClient(create_app(site_database, keys=KEYS, pool_size=1), base_url="https://testserver") as client:
        assert "secure" in set_cookie(sign_in(client), "fcon_session").lower()


def test_a_sign_in_ends_the_sign_in_cookie(client: TestClient):
    sign_in(client)

    assert client.cookies.get("fcon_sign_in") is None


def test_a_sign_in_through_a_trusted_proxy_is_recorded_from_the_visitors_address(site_database: str):
    app = create_app(site_database, keys=KEYS, pool_size=1, trusted_proxies=trusted_proxies("172.16.0.0/12"))
    with TestClient(app, base_url="https://testserver", client=("172.20.0.3", 50000)) as client:
        client.headers["X-Forwarded-For"] = "203.0.113.7"
        sign_in(client)

    with psycopg.connect(site_database) as connection:
        [address] = connection.execute("SELECT address FROM fcon.sign_in_attempt").fetchone() or [None]

    assert address == "203.0.113.7"


# -- the gate and the overview --------------------------------------------------


def test_a_visitor_not_signed_in_is_sent_to_sign_in(client: TestClient):
    response = client.get("/", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/sign-in")


def test_a_session_id_nobody_was_given_is_sent_to_sign_in(client: TestClient):
    client.cookies.set("fcon_session", "made-up")

    response = client.get("/", follow_redirects=False)

    assert response.headers["location"] == "/sign-in"


def test_a_user_signed_in_sees_the_overview(client: TestClient):
    sign_in(client)

    page = parse(client.get("/").text)

    assert [h1.get_text(strip=True) for h1 in page.find_all("h1")] == ["Overview"]


def test_the_overview_says_nothing_is_there_yet(client: TestClient):
    sign_in(client)

    page = parse(client.get("/").text)

    assert page.main is not None
    assert "Nothing to watch yet. Flows appear here once they exist." in page.main.get_text(" ", strip=True)


def test_the_overview_is_titled_for_itself(client: TestClient):
    sign_in(client)

    title = parse(client.get("/").text).title

    assert title is not None and title.get_text() == "Overview – Feather Connect"


def banner(client: TestClient) -> Tag:
    header = parse(client.get("/").text).find("header")
    assert isinstance(header, Tag), "no page header"
    return header


def test_the_header_names_the_product(client: TestClient):
    sign_in(client)

    assert "Feather Connect" in banner(client).get_text(" ", strip=True)


def test_the_header_names_the_environment(client: TestClient):
    sign_in(client)

    label = banner(client).select_one(".environment")

    assert label is not None and label.get_text(strip=True) == "staging"


def test_the_header_says_who_is_signed_in_with_which_role(client: TestClient):
    sign_in(client)

    who = banner(client).select_one(".who")

    assert who is not None and who.get_text(strip=True) == "ann · administrator"


def test_the_header_signs_out_with_a_form_carrying_the_sessions_token(client: TestClient):
    sign_in(client)

    form = banner(client).find("form")

    assert isinstance(form, Tag)
    token = form.find("input", attrs={"name": "csrf_token", "type": "hidden"})
    buttons = [button.get_text(strip=True) for button in form.find_all("button")]
    assert (form["method"], form["action"], isinstance(token, Tag) and len(str(token["value"])) >= 43, buttons) == (
        "post",
        "/sign-out",
        True,
        ["Sign out"],
    )


def test_a_signed_in_user_is_shown_with_their_own_role(client: TestClient):
    sign_in(client, name="ben", password="given-once-0001")
    token = parse(client.get("/choose-password").text).find("input", attrs={"name": "csrf_token"})
    assert isinstance(token, Tag)
    chosen = "ben-own-password-1"
    client.post(
        "/choose-password",
        data={"csrf_token": str(token["value"]), "new_password": chosen, "password_again": chosen},
    )

    who = banner(client).select_one(".who")

    assert who is not None and who.get_text(strip=True) == "ben · operator"


@pytest.mark.parametrize("path", ["/sign-in", "/healthz", "/static/fcon.css"])
def test_the_open_pages_need_no_sign_in(client: TestClient, path: str):
    assert client.get(path, follow_redirects=False).status_code == 200


def test_a_signed_in_user_at_an_address_with_no_page_is_told_it_is_not_found(client: TestClient):
    sign_in(client)

    response = client.get("/runs/42", follow_redirects=False)

    assert (response.status_code, heading(response.text)) == (404, "Page not found")


def test_a_visitor_not_signed_in_at_an_address_with_no_page_is_sent_to_sign_in(client: TestClient):
    response = client.get("/runs/42", follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/sign-in?next=%2Fruns%2F42")


# -- back to the page asked for --------------------------------------------------


def test_the_page_asked_for_goes_to_sign_in_with_its_query(client: TestClient):
    response = client.get("/runs?page=2", follow_redirects=False)

    assert response.headers["location"] == "/sign-in?next=%2Fruns%3Fpage%3D2"


def test_a_form_sent_without_a_session_is_sent_to_sign_in_alone(client: TestClient):
    response = client.post("/sign-out", follow_redirects=False)

    assert response.headers["location"] == "/sign-in"


def test_the_sign_in_form_carries_the_page_asked_for(client: TestClient):
    field = parse(client.get("/sign-in?next=/runs/42").text).find("input", attrs={"name": "next"})

    assert isinstance(field, Tag) and (field["type"], field["value"]) == ("hidden", "/runs/42")


def test_the_sign_in_form_leaves_out_a_page_on_another_site(client: TestClient):
    field = parse(client.get("/sign-in?next=//elsewhere.example/runs/42").text).find("input", attrs={"name": "next"})

    assert isinstance(field, Tag) and field["value"] == ""


def sign_in_to(client: TestClient, next_path: str, password: str = PASSWORD):
    token = sign_in_token(client)
    return client.post(
        "/sign-in",
        data={"username": "ann", "password": password, "sign_in_token": token, "next": next_path},
        follow_redirects=False,
    )


def test_a_sign_in_goes_back_to_the_page_asked_for(client: TestClient):
    assert sign_in_to(client, "/runs/42?tab=log").headers["location"] == "/runs/42?tab=log"


@pytest.mark.parametrize(
    "next_path",
    ["//elsewhere.example/runs/42", "https://elsewhere.example/", "/\\elsewhere.example", "/\t/elsewhere.example", ""],
    ids=["two-slashes", "full-address", "backslash", "control-character", "empty"],
)
def test_a_sign_in_to_a_page_not_on_this_site_goes_to_the_overview(client: TestClient, next_path: str):
    assert sign_in_to(client, next_path).headers["location"] == "/"


def test_a_refused_sign_in_keeps_the_page_asked_for(client: TestClient):
    page = parse(sign_in_to(client, "/runs/42", password="letmein").text)

    field = page.find("input", attrs={"name": "next"})
    assert isinstance(field, Tag) and field["value"] == "/runs/42"


def test_a_database_out_of_reach_gives_the_error_page_to_a_signed_in_visitor():
    client = TestClient(create_app(NO_DATABASE, keys=KEYS, pool_size=1), raise_server_exceptions=False)
    client.cookies.set("fcon_session", "some-session")

    response = client.get("/")

    assert (response.status_code, heading(response.text)) == (
        500,
        "Something went wrong",
    )


# -- signing out, and forms checked against their session ------------------------


def form_token(client: TestClient) -> str:
    field = parse(client.get("/").text).find("input", attrs={"name": "csrf_token"})
    assert isinstance(field, Tag), "no form token on the overview"
    return str(field["value"])


def signed_in_still(client: TestClient) -> bool:
    return client.get("/", follow_redirects=False).status_code == 200


def refusals(database_url: str) -> list[tuple[str, str, str | None]]:
    with psycopg.connect(database_url) as connection:
        found = connection.execute(
            "SELECT table_name, row_key, reason FROM fcon.audit WHERE action = 'refused' ORDER BY id"
        ).fetchall()
    return [(str(table), str(key), None if reason is None else str(reason)) for table, key, reason in found]


def test_signing_out_leads_to_sign_in(client: TestClient):
    sign_in(client)

    response = client.post("/sign-out", data={"csrf_token": form_token(client)}, follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (303, "/sign-in")


def test_signed_out_the_dashboard_asks_to_sign_in_again(client: TestClient):
    sign_in(client)
    kept = client.cookies.get("fcon_session")
    client.post("/sign-out", data={"csrf_token": form_token(client)})
    client.cookies.set("fcon_session", str(kept))

    assert not signed_in_still(client)


def test_signing_out_ends_the_session_cookie(client: TestClient):
    sign_in(client)

    client.post("/sign-out", data={"csrf_token": form_token(client)})

    assert client.cookies.get("fcon_session") is None


def test_a_form_without_its_token_is_refused_as_expired(client: TestClient):
    sign_in(client)

    response = client.post("/sign-out")

    assert (response.status_code, heading(response.text), signed_in_still(client)) == (
        403,
        "This form has expired",
        True,
    )


def test_a_form_with_another_token_is_refused_as_expired(client: TestClient):
    sign_in(client)

    response = client.post("/sign-out", data={"csrf_token": "not-the-sessions"})

    assert (response.status_code, signed_in_still(client)) == (403, True)


def test_a_refused_form_is_audited_against_its_session(client: TestClient, site_database: str):
    sign_in(client)
    with psycopg.connect(site_database) as connection:
        row = connection.execute("SELECT id FROM fcon.session WHERE ended_at IS NULL").fetchone()
    assert row is not None

    client.post("/sign-out", data={"csrf_token": "not-the-sessions"})

    assert refusals(site_database) == [("fcon.session", str(row[0]), "the form's token is not the session's")]


def test_the_form_token_may_come_in_a_header(client: TestClient):
    sign_in(client)

    response = client.post("/sign-out", headers={"X-CSRF-Token": form_token(client)}, follow_redirects=False)

    assert response.status_code == 303


def test_a_form_from_this_site_is_accepted(client: TestClient):
    sign_in(client)

    response = client.post(
        "/sign-out",
        data={"csrf_token": form_token(client)},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )

    assert response.status_code == 303


@pytest.mark.parametrize("origin", ["https://elsewhere.example", "null"])
def test_a_form_from_another_site_is_refused_even_with_the_token(client: TestClient, origin: str):
    sign_in(client)

    response = client.post("/sign-out", data={"csrf_token": form_token(client)}, headers={"Origin": origin})

    assert (response.status_code, heading(response.text), signed_in_still(client)) == (
        403,
        "This form has expired",
        True,
    )


def test_a_form_from_another_site_is_refused_without_a_session_too(client: TestClient, site_database: str):
    response = client.post("/sign-out", headers={"Origin": "https://elsewhere.example"}, follow_redirects=False)

    assert (response.status_code, refusals(site_database)) == (
        403,
        [("fcon.session", "default", "the form came from another site")],
    )


def test_a_sign_in_from_another_site_is_refused(client: TestClient):
    token = sign_in_token(client)

    response = client.post(
        "/sign-in",
        data={"username": "ann", "password": PASSWORD, "sign_in_token": token},
        headers={"Origin": "https://elsewhere.example"},
    )

    assert response.status_code == 403
