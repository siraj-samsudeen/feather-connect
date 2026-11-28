"""The `fcon settings` commands: `show`, `set`, `clear` and `list` (catalog-and-settings, the command line's contract).

They act as `system:cli` in the request's tenant, through the settings service. `set` and `clear` take `--reason`,
written on the change's audit record; in a protected environment (FCON_PROTECTED=on) a change needs one. Every
refusal is a problem through the error helper.
"""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC
from typing import TextIO

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.services import cli_caller, open_store
from fcon_cli.settings import DatabaseSettings
from fcon_cli.table import print_table
from fcon_server.catalog.known_settings import BadValueError, DecidedByCodeError, UnknownSettingError
from fcon_server.catalog.operator_settings import (
    EntrySettings,
    InForce,
    Layer,
    NeedsAReasonError,
    NoSuchEntryError,
    NotInCodeError,
    clear_setting,
    effective_settings,
    list_operator_values,
    set_setting,
)

SHOW_HEADINGS = ("SETTING", "VALUE", "SET BY", "CHANGED")
LIST_HEADINGS = ("NAME", "SETTING", "VALUE", "NOTE")
NO_LONGER_IN_THE_CODE = "no longer in the code"


@contextmanager
def _refusals(name: str) -> Generator[None]:
    """Turn the settings service's refusals of a change to the entry `name` into problems."""
    try:
        yield
    except NoSuchEntryError:
        raise ProblemError(problems.no_such_entry(name)) from None
    except DecidedByCodeError as err:
        raise ProblemError(problems.decided_by_code(name, err.kind, err.setting)) from None
    except UnknownSettingError as err:
        raise ProblemError(problems.no_such_setting(err.kind, err.setting)) from None
    except BadValueError as err:
        raise ProblemError(problems.bad_setting_value(err.value, err.setting, err.expected)) from None
    except NotInCodeError as err:
        raise ProblemError(problems.not_in_code(str(err))) from None
    except NeedsAReasonError as err:
        raise ProblemError(problems.needs_a_reason(str(err))) from None


def _title(shown: EntrySettings) -> str:
    """The entry, its kind and the package version it is from: "shop-flows.orders, a dataset of shop-flows 1.0"."""
    version = f"{shown.package} {shown.version}"
    if shown.is_in_code:
        return f"{shown.name}, a {shown.kind} of {version}"
    return f"{shown.name}, a {shown.kind} no longer in the code (last in {version})"


def _changed(value: InForce) -> str:
    """Who changed an operator's value and when, in UTC to the minute; empty for the code's or the default."""
    if value.changed_at is None:
        return ""
    return f"{value.changed_by}, {value.changed_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC"


def show(settings: DatabaseSettings, name: str, out: TextIO) -> None:
    """Print on `out` the entry `name` and every setting of its kind in force, who set it, and when."""
    with _refusals(name):
        shown = effective_settings(open_store(settings), cli_caller(), name)
    print(_title(shown), file=out)
    rows = [(value.setting, value.value, value.layer.value, _changed(value)) for value in shown.settings]
    print_table([SHOW_HEADINGS, *rows], out)


def set_value(settings: DatabaseSettings, change: tuple[str, str, str], reason: str | None, out: TextIO) -> None:
    """Set the operator's value of a setting, `change` being the entry's name, the setting and the value; say so."""
    name, setting, value = change
    store = open_store(settings)
    with _refusals(name):
        changed = set_setting(store, cli_caller(reason), name, setting, value, protected=settings.protected)
    if changed.already:
        print(f"the {setting} of {name} is {changed.value} already.", file=out)
    else:
        print(f"set the {setting} of {name} to {changed.value}.", file=out)


def clear(settings: DatabaseSettings, name: str, setting: str, reason: str | None, out: TextIO) -> None:
    """Clear the operator's value of `setting` of the entry `name`, and say on `out` what is in force now."""
    store = open_store(settings)
    with _refusals(name):
        cleared = clear_setting(store, cli_caller(reason), name, setting, protected=settings.protected)
    if not cleared.had_value:
        print(f"the {setting} of {name} has no operator value.", file=out)
        return
    below = cleared.in_force
    source = "the code's" if below.layer is Layer.CODE else "the default"
    print(f"cleared the {setting} of {name}; {source} {below.value} is in force.", file=out)


def show_list(settings: DatabaseSettings, out: TextIO) -> None:
    """Print on `out` every operator's value in the tenant, flagged when its entry is no longer in the code."""
    values = list_operator_values(open_store(settings), cli_caller())
    if not values:
        print("no operator values yet.", file=out)
        return
    rows = [
        (value.name, value.setting, value.value, "" if value.is_in_code else NO_LONGER_IN_THE_CODE) for value in values
    ]
    print_table([LIST_HEADINGS, *rows], out)
