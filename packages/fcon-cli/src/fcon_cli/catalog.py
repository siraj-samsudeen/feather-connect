"""The `fcon catalog` commands: `record <file>` and `list` (catalog-and-settings, the command line's contract).

`record` stands in for the install path until packaging comes (design § Context): it reads one package version's
definitions file and records it through the catalog's service. Both act as `system:cli` in the request's tenant.
Every refusal is a problem through the error helper.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.services import cli_caller, open_store
from fcon_cli.settings import DatabaseSettings
from fcon_server.catalog.definitions import LARGEST, CodeValueError, NotDefinitionsError, parse_definitions
from fcon_server.catalog.known_settings import DecidedByCodeError, UnknownSettingError
from fcon_server.catalog.listing import list_catalog
from fcon_server.catalog.recording import (
    ChangedDefinitionsError,
    KindChangedError,
    Recorded,
    RenameAcrossKindsError,
    counted,
    record,
)


def _code_value_problem(err: CodeValueError) -> problems.Problem:
    """The problem for a code value of a setting that is wrong, unknown, or decided by the code."""
    refused = err.refused
    if isinstance(refused, DecidedByCodeError):
        return problems.decided_by_code(err.name, refused.kind, refused.setting)
    if isinstance(refused, UnknownSettingError):
        return problems.no_such_setting(refused.kind, refused.setting)
    return problems.bad_setting_value(refused.value, refused.setting, refused.expected)


@contextmanager
def _refusals(file: str) -> Generator[None]:
    """Turn the catalog's refusals of a definitions file into problems."""
    try:
        yield
    except NotDefinitionsError as err:
        raise ProblemError(problems.not_definitions_file(file, err.what, err.expected)) from None
    except CodeValueError as err:
        raise ProblemError(_code_value_problem(err)) from None
    except ChangedDefinitionsError as err:
        raise ProblemError(problems.recorded_with_other_definitions(err.package, err.version)) from None
    except KindChangedError as err:
        raise ProblemError(problems.kind_changed(str(err))) from None
    except RenameAcrossKindsError as err:
        raise ProblemError(problems.rename_across_kinds(str(err))) from None


def _read(file: str) -> bytes:
    """The file's bytes, one more than the largest a definitions file may be at most; ProblemError when unreadable."""
    try:
        with Path(file).open("rb") as opened:
            return opened.read(LARGEST + 1)
    except OSError:
        raise ProblemError(problems.definitions_file_unreadable(file)) from None


def _say(recorded: Recorded, out: TextIO) -> None:
    """Print on `out` the renames, what was recorded, then a warning for each flagged operator value."""
    if recorded.already:
        print(f"{recorded.package} {recorded.version} is recorded already.", file=out)
        return
    for renamed in recorded.renamed:
        print(f"renamed {renamed.old} to {renamed.new}.", file=out)
    print(f"recorded {recorded.package} {recorded.version}: {counted(recorded)}.", file=out)
    for value in recorded.flagged:
        print(problems.flagged_value(value.name, value.setting).text(), file=out)


def record_file(settings: DatabaseSettings, file: str, out: TextIO) -> None:
    """Record the package version in the definitions file `file`, and say on `out` what was recorded."""
    store = open_store(settings)
    raw = _read(file)
    with _refusals(file):
        recorded = record(store, cli_caller(), parse_definitions(raw))
    _say(recorded, out)


HEADINGS = ("NAME", "KIND", "PACKAGE VERSION")


def show_list(settings: DatabaseSettings, out: TextIO) -> None:
    """Print on `out` every entry the code declares now, as a table of name, kind and package version."""
    listed = list_catalog(open_store(settings), cli_caller())
    if not listed:
        print("the catalog is empty.", file=out)
        return
    lines = [HEADINGS, *((entry.name, entry.kind.value, f"{entry.package} {entry.version}") for entry in listed)]
    widths = [max(len(line[column]) for line in lines) for column in range(len(HEADINGS) - 1)]
    for line in lines:
        cells = [cell.ljust(width) for cell, width in zip(line[:-1], widths, strict=True)]
        print("  ".join([*cells, line[-1]]), file=out)
