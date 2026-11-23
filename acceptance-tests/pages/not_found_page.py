"""The product's own page for an address it does not have. Its route, texts
and the way on to sign-in live here; the steps only ask questions."""

import re
from urllib.parse import urlparse

from playwright.sync_api import Page

from support.auth import SIGN_IN_PATH

# An address the dashboard does not have: the page of a run that was never made.
MISSING_RUN_PATH = "/runs/42"

STATUS = 404
HEADING = "Page not found"
SIGN_IN_LINK = "Sign in"  # the link's name contains this, in any case


class NotFoundPage:
    def __init__(self, world):
        self.world = world
        self.response = None

    @property
    def page(self) -> Page:
        return self.world.signed_out()

    def open_missing_run(self):
        self.response = self.page.goto(MISSING_RUN_PATH)

    def at_missing_run(self):
        """(yes?, why): the browser is at the address of run 42."""
        path = urlparse(self.page.url).path
        return path == MISSING_RUN_PATH, "at %s, not %s" % (self.where(), MISSING_RUN_PATH)

    def where(self):
        return "%s (answered %s, title %r)" % (
            self.page.url,
            self.response.status if self.response else "nothing",
            self.page.title(),
        )

    def not_found_problems(self):
        """Why this is not the product's not-found page: a 404, with the
        heading saying so."""
        problems = []
        if self.response is None or self.response.status != STATUS:
            problems.append("the answer was not %d" % STATUS)
        heading = self.page.get_by_role("heading", name=HEADING, exact=True)
        if heading.count() != 1 or not heading.is_visible():
            problems.append("no visible heading %r" % HEADING)
        if problems:
            problems.append("at %s" % self.where())
        return problems

    def _sign_in_link(self):
        return self.page.get_by_role("link", name=re.compile(SIGN_IN_LINK, re.IGNORECASE))

    def go_on_to_sign_in(self):
        """Follows the page's link to sign-in, as a visitor would; (yes?, why not)."""
        link = self._sign_in_link()
        if link.count() != 1:
            return False, "%d links named like %r (expected 1) at %s" % (link.count(), SIGN_IN_LINK, self.where())
        link.click()
        self.page.wait_for_load_state()
        path = urlparse(self.page.url).path
        return path == SIGN_IN_PATH, "the link led to %s" % self.page.url
