"""The upgrade runner (design point 2): plain SQL files in `migrations/`,
applied forwards only, each recorded in `fcon.migration` with its checksum.
It returns facts; the command line words them.

- Every file not recorded is waiting, applied in name order, even one older
  than the newest applied (expand-only files do not depend on their order).
- A recorded file whose checksum differs is changed: the upgrade applies
  nothing. A recorded name with no file is newer than this version.
- One upgrade at a time: a session advisory lock on a connection of its own.
- Each file runs in its own transaction, with `fcon.now` set from the clock,
  unless its first line is `-- fcon: no-transaction`.
- Then the audit log's months, through six ahead of the clock's (UTC).
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from fcon_server.store.clock import Clock

MIGRATIONS = Path(__file__).parent / "migrations"
NO_TRANSACTION = "-- fcon: no-transaction"
ACTOR = "system:migration"
MONTHS_AHEAD = 6
LOCK_KEY = 0x66636F6E_6462  # "fcondb": the one upgrade at a time
_OPTIONS = "-c TimeZone=UTC -c application_name=fcon-migration"

type Connection = psycopg.Connection[tuple[object, ...]]


def checksum(text: str) -> str:
    """SHA-256 of the text with its line endings made `\\n`, so a Windows
    checkout and a Linux one agree."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()


@dataclass(frozen=True)
class Migration:
    name: str
    text: str

    @property
    def in_transaction(self) -> bool:
        return self.text.split("\n", 1)[0].strip() != NO_TRANSACTION


def read_migrations(directory: Path = MIGRATIONS) -> tuple[Migration, ...]:
    """The files, in name order, with their line endings made `\\n`."""
    paths = sorted(directory.glob("*.sql"), key=lambda path: path.name)
    return tuple(Migration(path.name, path.read_bytes().decode().replace("\r\n", "\n")) for path in paths)


@dataclass(frozen=True)
class Ran:
    """A recorded upgrade and when it ran."""

    name: str
    created_at: datetime


@dataclass(frozen=True)
class MigrationStatus:
    """Each list in name order. `applied` and `changed` ran; `changed` no
    longer matches its file; `newer` ran but has no file in this version."""

    applied: tuple[Ran, ...]
    waiting: tuple[str, ...]
    newer: tuple[str, ...]
    changed: tuple[Ran, ...]


@dataclass(frozen=True)
class UpgradeResult:
    """What one upgrade did: the files it applied, or, when a file changed
    since it ran, those files and nothing applied."""

    applied: tuple[str, ...]
    changed: tuple[str, ...] = ()


def _connect(url: str) -> Connection:
    return psycopg.connect(url, autocommit=True, options=_OPTIONS)


def _records(connection: Connection) -> dict[str, tuple[str, datetime]]:
    row = connection.execute("SELECT to_regclass('fcon.migration') IS NOT NULL").fetchone()
    if row is None or not row[0]:  # a new database: nothing ran yet
        return {}
    rows = connection.execute("SELECT name, checksum, created_at FROM fcon.migration").fetchall()
    return {
        str(name): (str(digest), created_at) for name, digest, created_at in rows if isinstance(created_at, datetime)
    }


def read_status(connection: Connection, migrations: tuple[Migration, ...]) -> MigrationStatus:
    records = _records(connection)
    files = {migration.name: migration for migration in migrations}
    applied: list[Ran] = []
    changed: list[Ran] = []
    for name, (digest, created_at) in sorted(records.items()):
        if name in files:
            (applied if checksum(files[name].text) == digest else changed).append(Ran(name, created_at))
    return MigrationStatus(
        applied=tuple(applied),
        waiting=tuple(name for name in files if name not in records),
        newer=tuple(name for name in sorted(records) if name not in files),
        changed=tuple(changed),
    )


def migration_status(url: str, directory: Path = MIGRATIONS) -> MigrationStatus:
    """What has run and what waits; changes nothing."""
    with _connect(url) as connection:
        return read_status(connection, read_migrations(directory))


def _lock(connection: Connection, on_wait: Callable[[], None]) -> None:
    row = connection.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_KEY]).fetchone()
    if row is None or not row[0]:
        on_wait()
        connection.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])


def _apply(connection: Connection, migration: Migration, now: datetime) -> None:
    def record() -> None:
        connection.execute(
            "INSERT INTO fcon.migration (name, checksum, created_at, created_by) VALUES (%s, %s, %s, %s)",
            [migration.name, checksum(migration.text), now, ACTOR],
        )

    if migration.in_transaction:
        with connection.transaction():
            connection.execute("SELECT set_config('fcon.now', %s, true)", [now.isoformat()])
            connection.execute(migration.text.encode())
            record()
        return
    connection.execute("SELECT set_config('fcon.now', %s, false)", [now.isoformat()])
    connection.execute(migration.text.encode())
    with connection.transaction():
        record()


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def audit_months(now: datetime) -> tuple[date, ...]:
    """The first day of the clock's month in UTC and of each of the six after it."""
    month = now.astimezone(UTC).date().replace(day=1)
    months = [month]
    for _ in range(MONTHS_AHEAD):
        months.append(_next_month(months[-1]))
    return tuple(months)


def _make_audit_months(connection: Connection, now: datetime) -> None:
    for month in audit_months(now):
        connection.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS {} PARTITION OF fcon.audit FOR VALUES FROM ({}) TO ({})").format(
                sql.Identifier("fcon", f"audit_{month:%Y_%m}"),
                sql.Literal(f"{month.isoformat()} 00:00:00+00"),
                sql.Literal(f"{_next_month(month).isoformat()} 00:00:00+00"),
            )
        )


def upgrade(
    url: str, clock: Clock, *, directory: Path = MIGRATIONS, on_wait: Callable[[], None] = lambda: None
) -> UpgradeResult:
    """Applies every waiting file, unless one that ran has changed. `on_wait`
    is called once when another upgrade holds the lock, before waiting for it.
    A file that fails raises the driver's error; the ones before it stay."""
    migrations = read_migrations(directory)
    with _connect(url) as lock, _connect(url) as connection:
        _lock(lock, on_wait)
        status = read_status(connection, migrations)
        if status.changed:
            return UpgradeResult(applied=(), changed=tuple(ran.name for ran in status.changed))
        waiting = [migration for migration in migrations if migration.name in status.waiting]
        for migration in waiting:
            _apply(connection, migration, clock.now())
        _make_audit_months(connection, clock.now())
    return UpgradeResult(applied=tuple(migration.name for migration in waiting))
