"""People start a scenario already signed in: their session comes from the
same request the sign-in form makes, so the form is typed only in scenarios
about signing in. Setup (records, roles, people) goes through one signed-in
session per run; what a scenario then does and checks goes through the browser.
Lines marked PROJECT: are the ones each project fills in.
"""

import os

from bs4 import BeautifulSoup

from support.stack import BASE_URL

# PROJECT: the seeded administrator of a fresh acceptance database.
ADMIN = {
    "user": os.environ.get("ACCEPTANCE_ADMIN_USER", "admin"),
    "password": os.environ.get("ACCEPTANCE_ADMIN_PASSWORD", "admin"),
}

# PROJECT: the sign-in page, and the names of its form fields.
SIGN_IN_PATH = "/login"
USER_FIELD = "username"
PASSWORD_FIELD = "password"


def _hidden_fields(html, form_action):
    """The hidden fields of the page's form that posts to `form_action`: the
    CSRF token a server-rendered form carries, whatever the app names it."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", attrs={"action": form_action}) or soup.find("form")
    if form is None:
        return {}
    return {
        field["name"]: field.get("value", "")
        for field in form.find_all("input", attrs={"type": "hidden"})
        if field.get("name")
    }


def signed_in_state(playwright, user, password):
    """A Playwright storage state for a new browser context, signed in as this
    person without typing the form: load the sign-in page, then post what the
    form would post, hidden fields included."""
    session = playwright.request.new_context(base_url=BASE_URL)
    try:
        page = session.get(SIGN_IN_PATH)
        if not page.ok:
            raise RuntimeError("the sign-in page answered %d" % page.status)
        form = _hidden_fields(page.text(), SIGN_IN_PATH)
        form.update({USER_FIELD: user, PASSWORD_FIELD: password})
        answer = session.post(SIGN_IN_PATH, form=form)
        # A server-rendered form that refuses a sign-in often answers 200 with
        # the form again, so the status alone proves nothing: a sign-in that
        # worked has left the sign-in page.
        # PROJECT: if the app shows the sign-in form somewhere else on a
        # failure, check for that instead.
        if not answer.ok or answer.url.rstrip("/").endswith(SIGN_IN_PATH):
            raise RuntimeError("sign-in as %s failed: %d at %s" % (user, answer.status, answer.url))
        return session.storage_state()
    finally:
        session.dispose()


_admin_session = None  # one signed-in session per run, opened on first use


def api(playwright):
    """The run's session as the administrator, for setup: `get`, `post(form=...)`
    for the app's own forms, `post(data=...)` for a JSON API.

    PROJECT: if setup goes through a JSON API with a bearer token, return
    playwright.request.new_context(base_url=BASE_URL, extra_http_headers={...}).
    """
    global _admin_session
    if _admin_session is None:
        state = signed_in_state(playwright, ADMIN["user"], ADMIN["password"])
        _admin_session = playwright.request.new_context(base_url=BASE_URL, storage_state=state)
    return _admin_session


def form_fields(session, path, form_action=None):
    """The hidden fields of the form on `path`, to post with a setup request:
    a server-rendered app refuses a post without its CSRF token."""
    return _hidden_fields(session.get(path).text(), form_action or path)


def dispose_api():
    """Ends the run's setup session, if one was opened."""
    global _admin_session
    if _admin_session is not None:
        _admin_session.dispose()
        _admin_session = None
