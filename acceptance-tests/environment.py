"""behave hooks for the acceptance suite: boot the app once, one browser for
the run, one World per scenario (support/world.py)."""

import base64
import os

from pages.accessibility import AccessibilityCheck
from pages.monitor import Monitor
from pages.not_found_page import NotFoundPage
from pages.sign_in_page import SignInPage
from support import captions, stack, world


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
        stack.stop_all()  # whatever closing the browser did, the app does not outlive the run


def before_scenario(context, scenario):
    context.world = world.World(context.suite, scenario.name)
    # The page objects the steps use, one per screen or flow.
    context.monitor = Monitor(context.world)
    context.sign_in_page = SignInPage(context.world)
    context.not_found_page = NotFoundPage(context.world)
    context.accessibility = AccessibilityCheck()


def after_scenario(context, scenario):
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
