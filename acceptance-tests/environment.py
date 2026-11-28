"""behave hooks for the acceptance suite: boot the app once, one browser for
the run, one World per scenario (support/world.py)."""

import base64
import os

from pages.accessibility import AccessibilityCheck
from pages.another_site import AnotherSite
from pages.audit_log import AuditLog
from pages.choose_password_page import ChoosePasswordPage
from pages.container_host import ContainerHost
from pages.data_commands import DataCommands
from pages.database_commands import DatabaseCommands
from pages.first_admin import FirstAdministrator
from pages.form_expired_page import FormExpiredPage
from pages.monitor import Monitor
from pages.not_found_page import NotFoundPage
from pages.overview_page import OverviewPage
from pages.own_product import OwnProduct
from pages.server_log import ServerLog
from pages.sign_in_page import SignInPage
from pages.standard_setup import StandardSetup
from pages.terminal import Terminal
from pages.user_commands import UserCommands
from support import auth, captions, docker, run_database, stack, world


# Capabilities whose scenarios open no web page: with VIDEO=1 they are shown on
# a terminal-like page of the test's own (support/screen.py).
SCREEN_FEATURES = ("Database upgrades", "Logs and health", "Stored data")


def before_all(context):
    if not os.environ.get("OPENSPEC_ACCEPTANCE"):
        raise RuntimeError(
            "Run the suite via `python run_acceptance.py` (not plain `behave`).\n"
            "The wrapper extracts Gherkin from openspec/**/spec.md and composes the effective spec."
        )
    stack.start_all()
    context.suite = world.Run()


def after_all(context):
    suite = getattr(context, "suite", None)
    try:
        if suite is not None:
            suite.close()
    finally:
        try:
            docker.stop_all()  # the run's containers, networks and image
        finally:
            stack.stop_all()  # whatever closing the browser did, the app does not outlive the run


def before_scenario(context, scenario):
    # The run's database starts every scenario with no users, sessions or
    # sign-in attempts; the sign-ins kept for the run go with them.
    run_database.reset_users()
    context.suite.signed_in_states.clear()
    auth.dispose_api()
    context.world = world.World(context.suite, scenario.name)
    # The page objects the steps use, one per screen or flow.
    context.monitor = Monitor(context.world)
    context.sign_in_page = SignInPage(context.world)
    context.not_found_page = NotFoundPage(context.world)
    context.overview = OverviewPage(context.world)
    context.choose_password = ChoosePasswordPage(context.world)
    context.form_expired = FormExpiredPage(context.world)
    context.another_site = AnotherSite(context.world)
    context.first_admin = FirstAdministrator(context.world)
    context.user_commands = UserCommands(context.world)
    context.audit_log = AuditLog(context.world)
    context.own_product = OwnProduct(context.world)
    context.accessibility = AccessibilityCheck()
    context.terminal = Terminal(context.world)
    context.database_commands = DatabaseCommands(context.world)
    context.data_commands = DataCommands(context.world)
    context.server_log = ServerLog(context.world)
    context.container_host = ContainerHost(context.world)
    context.standard_setup = StandardSetup(context.world, context.container_host)
    if scenario.feature.name in SCREEN_FEATURES:
        context.world.screen.open()  # VIDEO=1 only: these scenarios open no web page


def after_scenario(context, scenario):
    terminal = getattr(context, "terminal", None)
    if terminal is not None:
        terminal.close()  # the other program lets go of its port
    standard_setup = getattr(context, "standard_setup", None)
    container_host = getattr(context, "container_host", None)
    try:
        if standard_setup is not None:
            standard_setup.close()  # `docker compose down -v`, before its Postgres and network go
    finally:
        if container_host is not None:
            container_host.close()  # the scenario's containers and network, their logs kept
    scenario_world = getattr(context, "world", None)
    if scenario_world is None:
        return
    failed = scenario.status.name in ("failed", "error", "hook_error")
    console_errors = list(scenario_world.console_errors)
    for shot in scenario_world.close(failed or bool(console_errors)):
        _embed_in_report(context, shot)
    # Any error in the browser's console fails the scenario, even when every
    # step passed: it is how a script or a style the content policy blocks shows.
    if console_errors and not failed:
        raise AssertionError(
            "the browser's console showed %d error(s):\n%s"
            % (len(console_errors), "\n".join("  %s: %s" % item for item in console_errors))
        )


def before_step(context, step):
    if world.VIDEO:
        captions.before_step(context.world, step)


def after_step(context, step):
    if world.VIDEO:
        captions.after_step(context.world, step)


def _embed_in_report(context, screenshot):
    """A failed scenario's screenshot goes into the HTML report, under its last
    step; the file stays in reports/screenshots/ either way."""
    data = base64.b64encode(screenshot.read_bytes()).decode("ascii")
    for formatter in context._runner.formatters:
        if hasattr(formatter, "embedding"):
            try:
                formatter.embedding("image/png", data, screenshot.name)
            except Exception:  # noqa: BLE001 - the report is a convenience; the file is the record
                pass
