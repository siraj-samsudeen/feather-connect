"""The World: a thin holder for the scenario's signed-in browser pages.
Steps drive page objects (pages/); they never see a selector or a URL.
`environment.py` makes one Run for the suite and one World per scenario, as
`context.world`. Lines marked PROJECT: are the ones each project fills in.
"""

import json
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import sync_playwright

from support import auth, captions, run_database, stack
from support.screen import Screen
from support.scenario_database import ScenarioDatabase
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

# A console error the browser prints for every document answered with an error
# status ("Failed to load resource: ... 404"). For the page the scenario itself
# opened, the steps check that status; for anything the page loads (a
# stylesheet), the message stays and fails the scenario.
FAILED_TO_LOAD = "Failed to load resource"

# The user's own browser, the one every page object drives unless the
# scenario turns to another (World.on): their other computer, or another tab
# of the same browser.
THE_USER = "visitor"
OTHER_COMPUTER = "other computer"
OTHER_TAB = "other tab"


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
        self.color_scheme = "light"  # the computer's appearance setting the pages follow
        self.console_errors = []  # (who, text) of every browser console error and page error
        self._documents = set()  # URLs of the documents the scenario's pages opened
        self.pages = {}  # who ('the user', 'a colleague') -> page
        self.current = THE_USER  # whose page the page objects drive (on())
        self.contexts = []  # (who, label, browser context, page), in the order opened
        self.caption = None  # VIDEO=1: the step being run, as written
        self.base_url = BASE_URL  # the product the scenario talks to: the run's server, unless replaced
        self.ignore_https_errors = False  # True once the scenario has verified the site's encryption itself
        self.database = None  # the database address that product was given, when the scenario chose it
        self._http = None  # the scenario's plain HTTP client, opened on first use
        self._servers = []  # servers started for this scenario alone
        self._database = None  # the scenario's own throwaway database (support/scenario_database.py)
        self.scenario_server = None  # the server started on it, whose log pages/server_log.py reads
        self.product_settings = {}  # FCON_* settings for the product the scenario starts itself
        self._own_product_starts = 0  # each start's log is a file of its own
        self._own_product_port = None  # a restart keeps the address the browser has open
        self._own_product_database = None
        self.screen = Screen(self)  # VIDEO=1: what a scenario without a web page shows
        # The latest audit record of the run's database when the scenario
        # began: the scenario's own records come after it (pages/audit_log.py).
        self.audit_mark = run_database.audit_mark()
        # For a product the scenario runs elsewhere (the standard setup's
        # containers): how an `fcon` command runs there, (arguments, typed) ->
        # (exit code, stdout, stderr, timed out?), and how its audit log is
        # read, (query) -> records. None: here, and in the run's database.
        self.fcon_runner = None
        self.audit_reader = None

    def _new_page(self, who, label, storage_state=None):
        """A browser context for one of the scenario's people: traced, and recorded with VIDEO=1."""
        options = {
            "base_url": self.base_url,
            "viewport": self.viewport,
            "java_script_enabled": self.javascript,
            "color_scheme": self.color_scheme,
            "ignore_https_errors": self.ignore_https_errors,
        }
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
        self._watch_console(label, page)
        self.contexts.append((who, label, browser_context, page))
        return page

    def _watch_console(self, label, page):
        """Every console error and uncaught page error is kept; environment.py
        fails the scenario on any (issue 4, point 8: it catches a script or a
        style the content policy blocks)."""

        def on_response(response):
            if response.request.resource_type == "document":
                self._documents.add(response.url)

        def on_console(message):
            if message.type != "error":
                return
            where = (message.location or {}).get("url", "")
            if message.text.startswith(FAILED_TO_LOAD) and where in self._documents:
                return  # the page's own status: the steps check it
            self.console_errors.append((label, "%s (at %s)" % (message.text, where or "?")))

        def on_page_error(error):
            self.console_errors.append((label, "page error: %s" % error))

        page.on("response", on_response)
        page.on("console", on_console)
        page.on("pageerror", on_page_error)

    def signed_in(self, who, user=None, password=None, fresh=False):
        """That person's page, already signed in without the form (support/auth.py).

        A person's sign-in is made once and shared by the run's scenarios. A
        scenario that ends it (signing out, changing a password) asks for
        `fresh=True`, a sign-in of its own, so that the scenarios after it
        don't start signed out."""
        if who in self.pages:
            return self.pages[who]
        user = user or auth.ADMIN["user"]
        password = password or auth.ADMIN["password"]
        states = self.run.signed_in_states
        if fresh:
            state = auth.signed_in_state(self.run.playwright, user, password, self.base_url)
        else:
            if user not in states:
                states[user] = auth.signed_in_state(self.run.playwright, user, password, self.base_url)
            state = states[user]
        self.pages[who] = self._new_page(slug(who), who, state)
        return self.pages[who]

    def signed_out(self, who=None):
        """A page for someone not signed in: the only way a sign-in scenario
        starts. Without `who`, the page the scenario is on now (on())."""
        who = who or self.current
        if who not in self.pages:
            self.pages[who] = self._new_page(slug(who), who)
        return self.pages[who]

    @contextmanager
    def on(self, who):
        """The page objects drive `who`'s page while inside: the user's other
        computer, or another tab."""
        previous, self.current = self.current, who
        try:
            yield
        finally:
            self.current = previous

    def new_tab(self, who, of=THE_USER):
        """Another tab of `of`'s browser: the same cookies, a page of its own."""
        browser_context = self.signed_out(of).context
        page = browser_context.new_page()
        self._watch_console(who, page)
        self.pages[who] = page
        return page

    def stay_away(self, hours):
        """As if the scenario's users had not used the dashboard for `hours`:
        their sessions' recorded times moved back (support/run_database.py)."""
        moved = run_database.move_sessions_back(hours, self.product_database_url())
        if not moved:
            raise AssertionError("no session to move back: nobody is signed in")
        self.screen.note("%d hours later (the sessions' times moved back)" % hours)

    def fail_sign_in(self, user, password):
        """Someone else's refused sign-in, from a session of their own."""
        auth.refused_sign_in(self.run.playwright, user, password, self.base_url)

    def choose_own_password(self, user, given, chosen):
        """As setup: the user signs in with the given password and chooses their own."""
        auth.choose_own_password(self.run.playwright, user, given, chosen, self.base_url)

    def open_pages(self):
        """The scenario's open pages (captions.py puts each step's caption on all of them)."""
        return list(self.pages.values())

    def use_phone(self):
        """Every page of this scenario, open now or later, is on a phone-sized screen."""
        self.viewport = PHONE
        for page in self.pages.values():
            page.set_viewport_size(PHONE)

    def use_appearance(self, scheme):
        """The computer's appearance setting, "light" or "dark", that every page
        of this scenario, open now or later, sees as `prefers-color-scheme`."""
        if scheme not in ("light", "dark"):
            raise ValueError("no appearance %r: light or dark" % scheme)
        self.color_scheme = scheme
        for page in self.pages.values():
            page.emulate_media(color_scheme=scheme)

    def without_javascript(self):
        """Every page this scenario opens from now on has JavaScript off: for the
        promise that a server-rendered page works without it. Call it before
        signed_in() or signed_out(); a browser context can't be switched after."""
        if self.pages:
            raise RuntimeError(
                "without_javascript() came after a page was opened (%s): make it the scenario's first Given."
                % ", ".join(self.pages)
            )
        self.javascript = False

    def api(self):
        """The run's signed-in session, for setup through the app's own requests."""
        return auth.api(self.run.playwright)

    # PROJECT: helpers for setup the scenarios share (create a person with
    # roles, a record, a fixture), each through self.api().

    def http(self):
        """A plain HTTP client for the scenario's product, for what a monitor
        or another program asks for without a browser."""
        if self._http is None:
            self._http = self.run.playwright.request.new_context(
                base_url=self.base_url, ignore_https_errors=self.ignore_https_errors
            )
        return self._http

    def use_product_at(self, base_url, ignore_https_errors=False):
        """From now on the scenario talks to the product at base_url (one it
        started itself, such as a container of the product's image). With
        ignore_https_errors, the browser takes the site's certificate as it
        is: only for a site whose encryption the scenario verifies itself."""
        self.base_url = base_url
        self.ignore_https_errors = ignore_https_errors
        if self._http is not None:
            self._http.dispose()
            self._http = None

    def product_without_database(self):
        """From now on the scenario talks to a product of its own whose
        database cannot be reached: a second server on a free port, given the
        address of another free port where nothing listens. The run's shared
        database is never stopped."""
        self.database = {
            "host": "127.0.0.1",
            "port": str(stack.free_port()),
            "user": "outage_probe_user",
            "password": "outage_probe_secret",
            "dbname": "outage_probe_db",
        }
        address = "postgresql://{user}:{password}@{host}:{port}/{dbname}".format(**self.database)
        self.screen.note("a product of its own, started with a database address where nothing listens")
        base_url, process = stack.start_server("server-without-database", address)
        self._servers.append(process)
        self.base_url = base_url
        if self._http is not None:
            self._http.dispose()
            self._http = None

    def product_database_url(self):
        """The address of the database the scenario's product runs on: its own,
        when it has one, else the run's."""
        return self.scenario_database or stack.run_database_url()

    @property
    def scenario_database(self):
        """The address of the scenario's own database, or None."""
        return self._database.url if self._database is not None else None

    def own_database(self, upgraded=False):
        """A new, empty database of the scenario's own (upgraded, when asked),
        dropped when the scenario ends."""
        if self._database is not None:
            raise RuntimeError("the scenario already has a database of its own")
        self._database = ScenarioDatabase()
        self.screen.note("a new, empty database of the scenario's own")
        if upgraded:
            self._database.upgrade()
            self.screen.note("that database upgraded (fcon db upgrade, as setup)")
        return self._database

    def edit_an_applied_upgrade(self):
        name = self.own_database_state().edit_an_applied_upgrade()
        self.screen.note("an applied upgrade (%s) edited since it ran" % self.own_database_state().edited_upgrade)
        return name

    def add_newer_upgrade(self):
        self.own_database_state().add_newer_upgrade()
        self.screen.note("one more upgrade recorded as applied, from a newer version")

    def own_database_state(self):
        if self._database is None:
            raise RuntimeError("the scenario has no database of its own yet")
        return self._database

    def product_on_own_database(self):
        """From now on the scenario talks to a product of its own, started on
        its own database, and waited for until it answers that it runs (it
        may not be ready)."""
        self.screen.note("$ fcon server   (on that database, waited for until it answers)")
        base_url, process = stack.start_server("server-on-scenario-database", self.own_database_state().url)
        self._servers.append(process)
        self.scenario_server = process
        self.base_url = base_url
        if self._http is not None:
            self._http.dispose()
            self._http = None

    def name_in_settings(self, name, value):
        """A setting the product the scenario starts itself is given
        (start_own_product), beside its database address and secret key."""
        self.product_settings[name] = value
        self.screen.note("%s=%s in the product's settings" % (name, value))

    def start_own_product(self, on_run_database=False):
        """From now on the scenario talks to a product of its own, started with
        the settings it named, on its own upgraded database (made now, unless
        it has one) or, with on_run_database, on the run's, and waited for
        until it is ready."""
        if on_run_database:
            database_url = stack.run_database_url()
        else:
            if self._database is None:
                self.own_database(upgraded=True)
            database_url = self.own_database_state().url
        self.screen.note("$ fcon server   (with the settings named, waited for until ready)")
        self._own_product_starts += 1
        name = "server-own-product-%d" % self._own_product_starts
        base_url, process = stack.start_server(
            name, database_url, ready_path="/readyz", settings=dict(self.product_settings), port=self._own_product_port
        )
        self._servers.append(process)
        self.scenario_server = process
        self._own_product_database = database_url
        self._own_product_port = int(base_url.rsplit(":", 1)[1])
        self.use_product_at(base_url)

    def restart_own_product(self):
        """Stops the product the scenario started (start_own_product) and starts
        it again, at the same address, with the settings named now and the same
        database; its log is a new one."""
        if self.scenario_server is None:
            raise RuntimeError("the scenario started no product of its own")
        self._servers.remove(self.scenario_server)
        stack.stop(self.scenario_server)
        self.scenario_server = None
        self.start_own_product(on_run_database=self._own_product_database == stack.run_database_url())

    def scenario_server_still_running(self):
        """The server started on the scenario's own database has not stopped
        (and so was not restarted) since it was started."""
        if self.scenario_server is None:
            raise RuntimeError("the scenario started no server of its own")
        return self.scenario_server.poll() is None

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
                browser_context.tracing.stop(path=str(TRACES / ("%s-%s.zip" % (self.order, name))))
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
        self._documents = set()
        if self._http is not None:
            self._http.dispose()
            self._http = None
        while self._servers:
            stack.stop(self._servers.pop())
        self.scenario_server = None
        if self._database is not None:
            self._database.drop()
            self._database = None
        return screenshots
