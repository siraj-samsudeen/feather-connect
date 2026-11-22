"""The sign-in page, as a visitor sees it in the browser: the front door, the
form, a refused sign-in, and what the page looks like. Every route, label and
text the steps rely on lives here; the steps only ask questions.

Lookups go by role, label and visible text, as a person (or a screen reader)
finds things, so the checks hold whatever the markup's classes are."""

import re
from urllib.parse import quote, urlparse

from playwright.sync_api import Page

from support.auth import PASSWORD_FIELD, SIGN_IN_PATH, USER_FIELD

DASHBOARD_PATH = "/"
# Where a sign-in link says to go on to: `/sign-in?next=<address>`. This one
# is another site's, written as a browser reads `//host/path`: not a path here.
NEXT_PARAMETER = "next"
ANOTHER_SITE = "//elsewhere.example/runs/42"

PRODUCT_NAME = "Feather Connect"
USER_LABEL = "User name"
PASSWORD_LABEL = "Password"
BUTTON = "Sign in"
USER_AUTOCOMPLETE = "username"
PASSWORD_AUTOCOMPLETE = "current-password"

REFUSAL = "The user name or password is wrong."
REFUSED_TITLE_START = "Sign-in failed"

# Words that would tell which half of a sign-in was wrong.
HINTS = (
    "unknown user",
    "no such user",
    "user not found",
    "user does not exist",
    "wrong password",
    "incorrect password",
    "invalid password",
    "password is incorrect",
    "password is wrong",
    "user name is wrong",
)

# A background darker than this relative luminance is the dark appearance,
# lighter than LIGHT the light one (0 is black, 1 is white).
DARK = 0.2
LIGHT = 0.8


def relative_luminance(rgb):
    """WCAG 2.1's relative luminance of an (r, g, b) colour, 0-255 each."""

    def channel(value):
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _parse_colour(css):
    """"rgb(1, 2, 3)" / "rgba(1, 2, 3, 0.5)" -> ((1, 2, 3), alpha)."""
    numbers = [float(n) for n in re.findall(r"[\d.]+", css)]
    if len(numbers) < 3:
        raise AssertionError("cannot read the colour %r" % css)
    alpha = numbers[3] if len(numbers) > 3 else 1.0
    return tuple(int(n) for n in numbers[:3]), alpha


class SignInPage:
    def __init__(self, world):
        self.world = world
        self.response = None  # the answer to the last navigation or form post

    @property
    def page(self) -> Page:
        return self.world.signed_out()

    # --- getting there -----------------------------------------------------

    def open_dashboard(self):
        """What a visitor types: the product's front page."""
        self.response = self.page.goto(DASHBOARD_PATH)

    def open(self):
        self.response = self.page.goto(SIGN_IN_PATH)

    def follow_link_to_another_site(self):
        """A sign-in link, as someone could send it, that names another site as
        the page to go on to."""
        self.response = self.page.goto("%s?%s=%s" % (SIGN_IN_PATH, NEXT_PARAMETER, quote(ANOTHER_SITE, safe="")))

    def sign_in(self, user, password):
        """Types the form and presses the button, as a person does (with
        scripts off too: the browser posts the form itself)."""
        if not self.is_at_sign_in():
            self.open()
        if self.page.get_by_label(USER_LABEL, exact=True).count() != 1:
            raise AssertionError("no sign-in form to type into: no field labelled %r at %s" % (USER_LABEL, self.where()))
        self.page.get_by_label(USER_LABEL, exact=True).fill(user)
        self.page.get_by_label(PASSWORD_LABEL, exact=True).fill(password)
        with self.page.expect_navigation() as navigation:
            self.page.get_by_role("button", name=BUTTON, exact=True).click()
        self.response = navigation.value

    # --- what the page says ------------------------------------------------

    def where(self):
        return "%s (answered %s, title %r)" % (
            self.page.url,
            self.response.status if self.response else "nothing",
            self.page.title(),
        )

    def signed_in(self):
        """(yes?, why): the last sign-in left the sign-in page."""
        return not self.is_at_sign_in(), "still at the sign-in page: %s" % self.where()

    def is_at_sign_in(self):
        return urlparse(self.page.url).path == SIGN_IN_PATH

    def names_the_product(self):
        """(yes?, why not) — at /sign-in, with the product's name as the page's main heading."""
        if not self.is_at_sign_in():
            return False, "not at %s: %s" % (SIGN_IN_PATH, self.where())
        heading = self.page.get_by_role("heading", level=1, name=PRODUCT_NAME, exact=True)
        if heading.count() != 1 or not heading.is_visible():
            return False, "no visible main heading %r at %s" % (PRODUCT_NAME, self.where())
        return True, ""

    def form_problems(self):
        """What is missing from the form: the two labelled fields, named as the
        app's form posts them and filled by a password manager, and the button."""
        problems = []
        fields = (
            (USER_LABEL, USER_FIELD, USER_AUTOCOMPLETE, None),
            (PASSWORD_LABEL, PASSWORD_FIELD, PASSWORD_AUTOCOMPLETE, "password"),
        )
        for label, name, autocomplete, kind in fields:
            field = self.page.get_by_label(label, exact=True)
            if field.count() != 1:
                problems.append("%d fields labelled %r (expected 1)" % (field.count(), label))
                continue
            if not field.is_visible():
                problems.append("the %r field is not visible" % label)
            if field.get_attribute("name") != name:
                problems.append("the %r field is named %r, not %r" % (label, field.get_attribute("name"), name))
            if field.get_attribute("autocomplete") != autocomplete:
                problems.append(
                    "the %r field has autocomplete=%r, not %r" % (label, field.get_attribute("autocomplete"), autocomplete)
                )
            if kind and field.get_attribute("type") != kind:
                problems.append("the %r field is of type %r, not %r" % (label, field.get_attribute("type"), kind))
        button = self.page.get_by_role("button", name=BUTTON, exact=True)
        if button.count() != 1 or not button.is_visible():
            problems.append("no visible %r button" % BUTTON)
        if problems:
            problems.append("at %s" % self.where())
        return problems

    def refusal_problems(self):
        """Why this does not look like a refused sign-in: still on the sign-in
        page, the form shown again, nobody let in."""
        problems = []
        if not self.is_at_sign_in():
            problems.append("left the sign-in page")
        problems.extend(self.form_problems())
        return problems

    def _alert(self):
        return self.page.get_by_role("alert")

    def message_problems(self):
        """Why the refusal message is not the one agreed: the exact words, in
        an alert linked to the form, and no hint of which half was wrong."""
        problems = []
        alert = self._alert()
        if alert.count() != 1:
            return ["%d alerts on the page (expected 1) at %s" % (alert.count(), self.where())]
        text = " ".join(alert.inner_text().split())
        if text != REFUSAL:
            problems.append("the alert says %r, not %r" % (text, REFUSAL))
        alert_id = alert.get_attribute("id")
        if not alert_id:
            problems.append("the alert has no id, so nothing can be linked to it")
        elif not self._linked_to_form(alert_id):
            problems.append(
                "the alert (#%s) is not linked to the form: neither the form nor both fields name it "
                "in aria-describedby" % alert_id
            )
        # The agreed words themselves end in "password is wrong": look for hints in the rest.
        body = " ".join(self.page.locator("body").inner_text().split()).lower().replace(REFUSAL.lower(), "")
        problems.extend("the page hints which half was wrong: %r" % hint for hint in HINTS if hint in body)
        invalid = [
            self.page.get_by_label(label, exact=True).get_attribute("aria-invalid")
            for label in (USER_LABEL, PASSWORD_LABEL)
        ]
        if invalid[0] != invalid[1]:
            problems.append("only one field is marked invalid (aria-invalid %r and %r)" % tuple(invalid))
        if problems:
            problems.append("at %s" % self.where())
        return problems

    def _linked_to_form(self, alert_id):
        def described_by(locator):
            return (locator.get_attribute("aria-describedby") or "").split()

        form = self.page.locator("form").filter(has=self.page.get_by_label(PASSWORD_LABEL, exact=True))
        if form.count() == 1 and alert_id in described_by(form):
            return True
        return all(
            alert_id in described_by(self.page.get_by_label(label, exact=True))
            for label in (USER_LABEL, PASSWORD_LABEL)
        )

    def title_says_failed(self):
        title = self.page.title()
        return title.startswith(REFUSED_TITLE_START), "the title is %r" % title

    # --- appearance and size -----------------------------------------------

    def background_luminance(self):
        """The relative luminance of what the page shows behind its content:
        the body's background, else the root's, else the browser's white."""
        colours = self.page.evaluate(
            "() => [document.body, document.documentElement]"
            ".map(el => el ? getComputedStyle(el).backgroundColor : '')"
        )
        for css in colours:
            if not css:
                continue
            rgb, alpha = _parse_colour(css)
            if alpha > 0:
                return relative_luminance(rgb), css
        return 1.0, "transparent (the browser's white)"

    def shown_in(self, appearance):
        """(yes?, what was seen) — the page's background is dark, or light."""
        luminance, css = self.background_luminance()
        seen = "background %s, luminance %.2f, at %s" % (css, luminance, self.where())
        if appearance == "dark":
            return luminance < DARK, seen
        return luminance > LIGHT, seen
