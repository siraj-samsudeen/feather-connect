"""The page a refused form leads to (design point 5, the agreed mockup):
status 403, "This form has expired", and to reload the page. Its status and
texts live here; the steps only ask questions.

It is the page the scenario is on now (World.on), the one whose form was sent.
"""

from playwright.sync_api import Page

STATUS = 403
HEADING = "This form has expired"
RELOAD = "Reload the page and try again."


def _words(text):
    return " ".join(text.split())


class FormExpiredPage:
    def __init__(self, world):
        self.world = world

    @property
    def page(self) -> Page:
        return self.world.signed_out()

    def _status(self):
        """The status the page's own document was answered with, as the
        browser recorded it."""
        return self.page.evaluate("() => performance.getEntriesByType('navigation')[0]?.responseStatus ?? null")

    def where(self):
        return "%s (answered %s, title %r)" % (self.page.url, self._status(), self.page.title())

    def problems(self):
        """Why this is not the form-expired page: not a 403, no heading
        saying the form expired, or no word to reload the page."""
        problems = []
        if self._status() != STATUS:
            problems.append("the answer was not %d" % STATUS)
        heading = self.page.get_by_role("heading", name=HEADING, exact=True)
        if heading.count() != 1 or not heading.is_visible():
            problems.append("no visible heading %r" % HEADING)
        if RELOAD not in _words(self.page.locator("body").inner_text()):
            problems.append("the page does not say %r" % RELOAD)
        if problems:
            problems.append("at %s" % self.where())
        return problems
