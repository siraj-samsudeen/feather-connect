"""A page on another site that sends the dashboard a form, as a forger would
put it on their own site: its address, and the form it sends. The browser
reaches it through Playwright's routing, so no other server is started and no
name is looked up; the browser takes it for another site all the same, and
sends that site's address as the form's Origin.

It opens in the page the scenario is on now (World.on): the user's own
browser, with their session's cookie."""

from html import escape

from playwright.sync_api import Page

ORIGIN = "http://another-site.test"
PAGE_PATH = "/offer"
SIGN_OUT_PATH = "/sign-out"
FORM_TOKEN_FIELD = "csrf_token"  # noqa: S105 - a field name
FORGED_TOKEN = "a-token-the-forger-made-up"  # noqa: S105 - not the session's
BUTTON = "See the offer"

FORGED_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>An offer</title></head>
<body><main><h1>An offer</h1>
<form method="post" action="%(action)s">
<input type="hidden" name="%(field)s" value="%(token)s">
<button type="submit">%(button)s</button>
</form></main></body></html>
"""


class AnotherSite:
    def __init__(self, world):
        self.world = world

    @property
    def page(self) -> Page:
        return self.world.signed_out()

    def send_sign_out_form(self):
        """Opens the other site's page and presses its button: a sign-out form
        posted to the dashboard, with a token the forger made up."""
        action = self.world.base_url.rstrip("/") + SIGN_OUT_PATH
        html = FORGED_PAGE % {
            "action": escape(action),
            "field": FORM_TOKEN_FIELD,
            "token": FORGED_TOKEN,
            "button": BUTTON,
        }
        self.page.route(
            ORIGIN + "/**", lambda route: route.fulfill(status=200, content_type="text/html", body=html)
        )
        self.page.goto(ORIGIN + PAGE_PATH)
        with self.page.expect_navigation():
            self.page.get_by_role("button", name=BUTTON, exact=True).click()
