"""The page to choose a password, shown before any other while the user's
password was given to them (design point 9, the agreed mockup): its card,
its two fields, and a refused password saying which rule it broke. Every
label and text the steps rely on lives here; the steps only ask questions.

It is the same browser page the user signed in on (pages/sign_in_page.py).
Lookups go by role, label and visible text, as a person (or a screen reader)
finds things.
"""

from playwright.sync_api import Page

HEADING = "Choose your password"
LEAD = "The one you were given works only once."
NEW_LABEL = "New password"
AGAIN_LABEL = "The same again"
HINT = "At least 12 characters."
BUTTON = "Save password"
AUTOCOMPLETE = "new-password"


def _words(text):
    return " ".join(text.replace("’", "'").split())


class ChoosePasswordPage:
    def __init__(self, world):
        self.world = world

    @property
    def page(self) -> Page:
        return self.world.signed_out()  # the page the user signed in on

    def where(self):
        return "%s (title %r)" % (self.page.url, self.page.title())

    def problems(self):
        """Why this is not the page to choose a password: no heading, no word
        that the given one works once, no two labelled password fields, no
        hint of the rule, or no button to save."""
        problems = []
        heading = self.page.get_by_role("heading", name=HEADING, exact=True)
        if heading.count() != 1 or not heading.is_visible():
            problems.append("no visible heading %r" % HEADING)
        body = _words(self.page.locator("body").inner_text())
        for text in (LEAD, HINT):
            if text not in body:
                problems.append("the page does not say %r" % text)
        for label in (NEW_LABEL, AGAIN_LABEL):
            field = self.page.get_by_label(label, exact=True)
            if field.count() != 1:
                problems.append("%d fields labelled %r (expected 1)" % (field.count(), label))
                continue
            if not field.is_visible():
                problems.append("the %r field is not visible" % label)
            if field.get_attribute("type") != "password":
                problems.append("the %r field is of type %r, not 'password'" % (label, field.get_attribute("type")))
            if field.get_attribute("autocomplete") != AUTOCOMPLETE:
                problems.append(
                    "the %r field has autocomplete=%r, not %r" % (label, field.get_attribute("autocomplete"), AUTOCOMPLETE)
                )
        button = self.page.get_by_role("button", name=BUTTON, exact=True)
        if button.count() != 1 or not button.is_visible():
            problems.append("no visible %r button" % BUTTON)
        if problems:
            problems.append("at %s" % self.where())
        return problems

    def choose(self, password, again=None):
        """Types the password in both fields (or `again` in the second) and
        presses the button, as a person does."""
        if self.page.get_by_label(NEW_LABEL, exact=True).count() != 1:
            raise AssertionError("no field labelled %r to type into at %s" % (NEW_LABEL, self.where()))
        self.page.get_by_label(NEW_LABEL, exact=True).fill(password)
        self.page.get_by_label(AGAIN_LABEL, exact=True).fill(password if again is None else again)
        with self.page.expect_navigation():
            self.page.get_by_role("button", name=BUTTON, exact=True).click()

    def refused_because(self, reason):
        """(yes?, why): one alert, naming the rule broken in the words of the
        reason ("too short", "too common", "the user's own name")."""
        alert = self.page.get_by_role("alert")
        if alert.count() != 1:
            return False, "%d alerts on the page (expected 1) at %s" % (alert.count(), self.where())
        text = _words(alert.inner_text())
        if _words(reason).lower() not in text.lower():
            return False, "the alert says %r, which does not say %r, at %s" % (text, reason, self.where())
        return True, ""
