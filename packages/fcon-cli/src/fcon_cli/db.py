"""`fcon db upgrade` and `fcon db status`: the store's runner, said for a
person. Upgrades use the owner's address (FCON_MIGRATION_DATABASE_URL, else
FCON_DATABASE_URL); the status reads with the app's and changes nothing."""

from datetime import UTC, datetime
from typing import TextIO

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.settings import DatabaseSettings
from fcon_server.database import CONNECTION_PROBLEMS, diagnose_database
from fcon_server.store.clock import Clock
from fcon_server.store.migrate import MigrationStatus, UpgradeResult, migration_status, upgrade

_STATE_WIDTH = len("applied  ")


def format_time(when: datetime) -> str:
    """ISO 8601 in UTC, to the millisecond: 2026-11-21T17:30:14.666Z."""
    return when.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _usable(url: str, setting: str) -> None:
    """Reachable: a database behind or changed is what these commands are for."""
    check = diagnose_database(url)
    if check.problem in CONNECTION_PROBLEMS:
        raise ProblemError(problems.database_unusable(check, setting))


def upgrade_lines(result: UpgradeResult) -> list[str]:
    if not result.applied:
        return ["the database was already up to date."]
    count = len(result.applied)
    return [
        *(f"applied {name}" for name in result.applied),
        f"the database is up to date: {count} upgrade{'' if count == 1 else 's'} applied.",
    ]


def upgrade_database(settings: DatabaseSettings, clock: Clock, out: TextIO, err: TextIO) -> None:
    setting = (
        "FCON_MIGRATION_DATABASE_URL"
        if settings.migration_database_url != settings.database_url
        else "FCON_DATABASE_URL"
    )
    _usable(settings.migration_database_url, setting)
    result = upgrade(
        settings.migration_database_url, clock, on_wait=lambda: print(problems.waiting_for_upgrade(), file=err)
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
    _usable(settings.database_url, "FCON_DATABASE_URL")
    for line in status_lines(migration_status(settings.database_url)):
        print(line, file=out)
