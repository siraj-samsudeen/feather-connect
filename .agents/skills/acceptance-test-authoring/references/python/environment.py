"""behave hooks for the acceptance suite: boot the app once, one browser for
the run, one World per scenario (support/world.py)."""

import base64
import os

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
    if suite is not None:
        suite.close()
    stack.stop_all()


def before_scenario(context, scenario):
    context.world = world.World(context.suite, scenario.name)
    # PROJECT: attach the page objects the steps use, one per screen or flow:
    # context.signup_page = SignupPage(context.world)


def after_scenario(context, scenario):
    scenario_world = getattr(context, "world", None)
    if scenario_world is None:
        return
    failed = scenario.status.name in ("failed", "error", "hook_error")
    for shot in scenario_world.close(failed):
        _embed_in_report(context, shot)


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
