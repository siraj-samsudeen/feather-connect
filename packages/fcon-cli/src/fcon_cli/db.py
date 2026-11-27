"""The `fcon db upgrade` and `fcon db status` commands: the store's migration runner, worded for a person.

Upgrades use the owner's address (FCON_MIGRATION_DATABASE_URL, else FCON_DATABASE_URL); the status reads with the
app's address and changes nothing.
"""

from datetime import UTC, datetime
from typing import TextIO

from psycopg import conninfo

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.settings import DatabaseSettings
from fcon_server.database import CONNECTION_PROBLEMS, diagnose_database
from fcon_server.store.clock import Clock
from fcon_server.store.migrate import MigrationStatus, UpgradeResult, migration_status, upgrade

_STATE_WIDTH = len("applied  ")


def format_time(when: datetime) -> str:
    """The time in UTC as ISO 8601, to the millisecond: 2026-11-21T17:30:14.666Z."""
    return when.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _usable(url: str, setting: str) -> None:
    """Stop with a problem when the database at `url` cannot be reached, refuses the login, is missing or too old.

    `setting` names the variable the address came from. A database behind or changed is not refused: that is what
    these commands are for.
    """
    check = diagnose_database(url)
    if check.problem in CONNECTION_PROBLEMS:
        raise ProblemError(problems.database_unusable(check, setting))


def upgrade_lines(result: UpgradeResult) -> list[str]:
    """The lines that report an upgrade: each upgrade applied and how many, or that there was nothing to apply."""
    if not result.applied:
        return ["the database was already up to date."]
    count = len(result.applied)
    return [
        *(f"applied {name}" for name in result.applied),
        f"the database is up to date: {count} upgrade{'' if count == 1 else 's'} applied.",
    ]


def app_user(settings: DatabaseSettings) -> str | None:
    """The user of the app's address when the owner's address is another one, else None.

    The upgrade grants the app's rights to this user (design point 17). An address without a user names none: libpq's
    default user is the owner's too.
    """
    if settings.migration_database_url == settings.database_url:
        return None
    user = conninfo.conninfo_to_dict(settings.database_url).get("user")
    return None if user is None else str(user)


def upgrade_database(settings: DatabaseSettings, clock: Clock, out: TextIO, err: TextIO) -> None:
    """Apply every waiting upgrade through the owner's address, and print what was applied on `out`.

    `clock` stamps when each upgrade ran. While another upgrade holds the database, a line saying so goes to `err`.
    Raises ProblemError when the database cannot be used, or when an upgrade that ran has changed since.
    """
    setting = (
        "FCON_MIGRATION_DATABASE_URL"
        if settings.migration_database_url != settings.database_url
        else "FCON_DATABASE_URL"
    )
    _usable(settings.migration_database_url, setting)
    result = upgrade(
        settings.migration_database_url,
        clock,
        on_wait=lambda: print(problems.waiting_for_upgrade(), file=err),
        app_user=app_user(settings),
    )
    if result.changed:
        raise ProblemError(problems.upgrade_changed(result.changed[0]))
    for line in upgrade_lines(result):
        print(line, file=out)


def status_lines(status: MigrationStatus) -> list[str]:
    """Every upgrade in name order, with its state, and when it ran if it did."""
    entries = [
        *(("applied", ran.name, format_time(ran.created_at)) for ran in status.applied),
        *(("waiting", name, "") for name in status.waiting),
        *(("newer", name, "") for name in status.newer),
        *(("changed", ran.name, format_time(ran.created_at)) for ran in status.changed),
    ]
    lines = [
        f"{state:<{_STATE_WIDTH}}{name}{f'  {when}' if when else ''}"
        for state, name, when in sorted(entries, key=lambda entry: entry[1])
    ]
    return [*lines, f"{len(status.applied)} applied, {len(status.waiting)} waiting."]


def show_status(settings: DatabaseSettings, out: TextIO) -> None:
    """Print every upgrade with its state, then a count, on `out`; read through the app's address, changing nothing.

    Raises ProblemError when the database cannot be used.
    """
    _usable(settings.database_url, "FCON_DATABASE_URL")
    for line in status_lines(migration_status(settings.database_url)):
        print(line, file=out)
