"""The overview, the dashboard's first page behind sign-in, as a signed-in
user sees it in the browser: the product's name, who is signed in with which
role, and a body that says nothing is there yet. Every route and text the
steps rely on lives here (the agreed mockup, issue 16); the steps only ask
questions.

It is the same browser page the sign-in form was typed on (pages/sign_in_page.py).
Lookups go by role and visible text, as a person (or a screen reader) finds things.
"""

from urllib.parse import urlparse

from playwright.sync_api import Page

from support.auth import SIGN_IN_PATH

PATH = "/"
SIGN_OUT = "Sign out"
PRODUCT_NAME = "Feather Connect"
HEADING = "Overview"
NOTHING_YET = "Nothing to watch yet. Flows appear here once they exist."
# Who is signed in, on the right of the header: "<name> · <role>".
WHO_SEPARATOR = " · "


def _words(text):
    return " ".join(text.split())


class OverviewPage:
    def __init__(self, world):
        self.world = world

    @property
    def page(self) -> Page:
        return self.world.signed_out()  # the page the user signed in on

    def where(self):
        return "%s (title %r)" % (self.page.url, self.page.title())

    def _banner_text(self):
        banner = self.page.get_by_role("banner")
        if banner.count() != 1:
            return None
        return _words(banner.inner_text())

    def problems(self):
        """Why this is not the overview: not at its address, no heading
        "Overview", no word that nothing is there yet, or no header naming the product."""
        problems = []
        at = urlparse(self.page.url)
        if at.netloc != urlparse(self.world.base_url).netloc:
            problems.append("not on the product's own site")
        if at.path != PATH:
            problems.append("not at %s" % PATH)
        heading = self.page.get_by_role("heading", name=HEADING, exact=True)
        if heading.count() != 1 or not heading.is_visible():
            problems.append("no visible heading %r" % HEADING)
        if NOTHING_YET not in _words(self.page.locator("body").inner_text()):
            problems.append("the page does not say %r" % NOTHING_YET)
        banner = self._banner_text()
        if banner is None or PRODUCT_NAME not in banner:
            problems.append("no page header naming %r (header: %r)" % (PRODUCT_NAME, banner))
        if problems:
            problems.append("at %s" % self.where())
        return problems

    def open(self):
        """The dashboard's address typed again, in the same browser."""
        self.page.goto(PATH)

    def sign_out(self):
        """Presses Sign out in the header, as a person does; an AssertionError
        unless it leads to the sign-in page."""
        button = self.page.get_by_role("banner").get_by_role("button", name=SIGN_OUT, exact=True)
        if button.count() != 1:
            raise AssertionError("no %r button in the page header at %s" % (SIGN_OUT, self.where()))
        with self.page.expect_navigation():
            button.click()
        if urlparse(self.page.url).path != SIGN_IN_PATH:
            raise AssertionError("signing out did not lead to %s: at %s" % (SIGN_IN_PATH, self.where()))

    def shown_as(self, name, role):
        """(yes?, why): the header says who is signed in, "<name> · <role>"."""
        banner = self._banner_text()
        expected = "%s%s%s" % (name, WHO_SEPARATOR, role)
        if banner is None:
            return False, "no page header (banner) at %s" % self.where()
        return expected.lower() in banner.lower(), "the header says %r, not %r, at %s" % (banner, expected, self.where())
