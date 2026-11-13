"""The World: a thin holder for the scenario's signed-in browser pages.
Steps drive page objects (pages/); they never see a selector or a URL.
`environment.py` makes one Run for the suite and one World per scenario, as
`context.world`. Lines marked PROJECT: are the ones each project fills in.
"""

import json
import os
import re
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

from support import auth, captions
from support.stack import BASE_URL

# For a person watching or debugging; agents and CI set none of these, and
# browser checks run headless.
# HEADED=1: a visible browser, slowed down so each action can be followed.
# PWDEBUG=1: Playwright's Inspector, pausing before each action (headed).
# VIDEO=1: a slowed-down video of every scenario in reports/videos/, headless.
HEADED = os.environ.get("HEADED") == "1"
PWDEBUG = os.environ.get("PWDEBUG", "0") not in ("", "0")
VIDEO = os.environ.get("VIDEO") == "1"
# How slow a VIDEO=1 run is, in ms per browser action.
VIDEO_SLOWMO = int(os.environ.get("VIDEO_SLOWMO", "400"))

# In CI (or with TRACE=1) every context is traced; a failed scenario's traces
# are kept, the rest discarded. Open one with `playwright show-trace <zip>`.
# Locally a failure is simply rerun, so tracing's cost isn't paid.
TRACE = bool(os.environ.get("CI")) or os.environ.get("TRACE") == "1"

ACCEPTANCE = Path(__file__).resolve().parents[1]
REPORTS = ACCEPTANCE / "reports"
TRACES = REPORTS / "traces"
SCREENSHOTS = REPORTS / "screenshots"
VIDEOS = REPORTS / "videos"
VIDEO_SCRATCH = VIDEOS / ".recording"


def verifier_width():
    """The desktop screen is the UI verifier's width (ui_verifier_width in
    .copier-answers.yml)."""
    try:
        answers = (ACCEPTANCE.parent / ".copier-answers.yml").read_text(encoding="utf-8")
    except OSError:
        return 1280
    found = re.search(r"^ui_verifier_width:\s*(\d+)\s*$", answers, re.MULTILINE)
    return int(found.group(1)) if found else 1280


DESKTOP = {"width": verifier_width(), "height": 900}
PHONE = {"width": 375, "height": 812}


def slug(text):
    """"The list shows 3 more" -> "the-list-shows-3-more"."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _launch_options():
    if PWDEBUG:
        return {"headless": False}  # the Inspector does the pausing
    if HEADED:
        return {"headless": False, "slow_mo": 400}
    if VIDEO:
        return {"headless": True, "slow_mo": VIDEO_SLOWMO}
    return {"headless": True}


class Run:
    """What the whole suite shares: one browser, and each person's sign-in."""

    def __init__(self):
        # Only this run's traces and screenshots are in reports/. Videos are
        # replaced only by a run that records new ones, so a later plain run
        # doesn't delete the ones to review.
        shutil.rmtree(TRACES, ignore_errors=True)
        shutil.rmtree(SCREENSHOTS, ignore_errors=True)
        if VIDEO:
            shutil.rmtree(VIDEOS, ignore_errors=True)
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(**_launch_options())
        self.signed_in_states = {}  # user -> storage state, captured once per run
        self.scenario_count = 0  # run order, for the videos' names

    def close(self):
        auth.dispose_api()
        self.browser.close()
        self.playwright.stop()
        shutil.rmtree(VIDEO_SCRATCH, ignore_errors=True)


class World:
    """One scenario's people and their pages."""

    def __init__(self, run, scenario_name):
        run.scenario_count += 1
        self.run = run
        self.order = "%02d" % run.scenario_count
        self.name = scenario_name
        self.slug = slug(scenario_name)
        self.viewport = DESKTOP
        self.javascript = True
        self.pages = {}  # who ('the user', 'a colleague') -> page
        self.contexts = []  # (who, label, browser context, page), in the order opened
        self.caption = None  # VIDEO=1: the step being run, as written

    def _new_page(self, who, label, storage_state=None):
        """A browser context for one of the scenario's people: traced, and recorded with VIDEO=1."""
        options = {"base_url": BASE_URL, "viewport": self.viewport, "java_script_enabled": self.javascript}
        if storage_state is not None:
            options["storage_state"] = storage_state
        if VIDEO:
            options["record_video_dir"] = str(VIDEO_SCRATCH)
            options["record_video_size"] = self.viewport
        browser_context = self.run.browser.new_context(**options)
        if PWDEBUG:
            browser_context.set_default_timeout(0)  # a person is stepping through
        if TRACE:
            browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)
        if VIDEO:
            captions.install(browser_context)
        page = browser_context.new_page()
        self.contexts.append((who, label, browser_context, page))
        return page

    def signed_in(self, who, user=None, password=None):
        """That person's page, already signed in without the form (support/auth.py)."""
        if who in self.pages:
            return self.pages[who]
        user = user or auth.ADMIN["user"]
        password = password or auth.ADMIN["password"]
        states = self.run.signed_in_states
        if user not in states:
            states[user] = auth.signed_in_state(self.run.playwright, user, password)
        self.pages[who] = self._new_page(slug(who), who, states[user])
        return self.pages[who]

    def signed_out(self, who="visitor"):
        """A page for someone not signed in: the only way a sign-in scenario starts."""
        if who not in self.pages:
            self.pages[who] = self._new_page(slug(who), who)
        return self.pages[who]

    def open_pages(self):
        """The scenario's open pages (captions.py puts each step's caption on all of them)."""
        return list(self.pages.values())

    def use_phone(self):
        """Every page of this scenario, open now or later, is on a phone-sized screen."""
        self.viewport = PHONE
        for page in self.pages.values():
            page.set_viewport_size(PHONE)

    def without_javascript(self):
        """Every page this scenario opens from now on has JavaScript off: for the
        promise that a server-rendered page works without it. Call it before
        signed_in() or signed_out(); a browser context can't be switched after."""
        self.javascript = False

    def api(self):
        """The run's signed-in session, for setup through the app's own requests."""
        return auth.api(self.run.playwright)

    # PROJECT: helpers for setup the scenarios share (create a person with
    # roles, a record, a fixture), each through self.api().

    def close(self, failed):
        """Ends the scenario: keeps a failed one's screenshots and traces, and a
        VIDEO=1 run's clips. Returns the screenshots it saved."""
        # "<slug>" when the scenario opened one browser, "<slug>-<who>" for each when more.
        many = len(self.contexts) > 1
        screenshots = []
        for who, label, browser_context, page in self.contexts:
            name = "%s-%s" % (self.slug, who) if many else self.slug
            if failed:
                shot = SCREENSHOTS / ("%s-%s.png" % (self.order, name))
                try:
                    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shot), full_page=True)
                    screenshots.append(shot)
                except Exception:  # noqa: BLE001 - a page that is gone has nothing to show
                    pass
            if TRACE and failed:
                TRACES.mkdir(parents=True, exist_ok=True)
                browser_context.tracing.stop(path=str(TRACES / ("%s.zip" % name)))
            elif TRACE:
                browser_context.tracing.stop()
            video = page.video if VIDEO else None
            browser_context.close()
            if video:
                clip = "%s-%s.webm" % (self.order, name)
                video.save_as(str(VIDEOS / clip))
                video.delete()
                # What scripts/video_journey.py puts on each clip's title card.
                entry = {"file": clip, "order": self.order, "scenario": self.name, "who": label}
                with (VIDEOS / "clips.jsonl").open("a", encoding="utf-8") as clips:
                    clips.write(json.dumps(entry) + "\n")
        self.contexts = []
        self.pages = {}
        return screenshots
