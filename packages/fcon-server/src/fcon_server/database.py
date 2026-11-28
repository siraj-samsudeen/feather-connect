"""The database check: whether the database is usable, and if not, which problem it has.

It returns facts; the command line words them for a person, and /readyz says one
word.

Readiness keeps its own connection (storage-foundation, decision 3): each check
opens a fresh connection, runs its few queries and closes it, so a problem keeps
its cause. Beyond the connection it reads the database's encoding, whether the
ICU collation exists, the upgrades recorded against this version's files, and
the audit log's monthly partitions and the record blocks' daily ones.
"""

import re
import socket
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

import psycopg
from psycopg import conninfo

from fcon_server.store.clock import Clock, SystemClock
from fcon_server.store.migrate import (
    MIGRATIONS,
    MigrationStatus,
    audit_months,
    read_migrations,
    read_status,
    record_days,
)

TIMEOUT_S = 2
# Windows reports a refused port on its own machine only after about 2 s of
# retries, so the probe (diagnose_database) waits longer than the check.
PROBE_TIMEOUT_S = 5
OLDEST_SUPPORTED = 180000  # Postgres 18.0, as server_version_num counts it
ENCODING = "UTF8"
ICU_COLLATION = "und-x-icu"
_SYSTEM_CLOCK = SystemClock()

REFUSED = "connection refused"
TIMED_OUT = "timed out"
HOST_NOT_FOUND = "host not found"


class Problem(StrEnum):
    """What makes the database unusable, or the server not ready, as the check names it."""

    UNREACHABLE = "unreachable"
    LOGIN_REFUSED = "login refused"
    DATABASE_MISSING = "database missing"
    TOO_OLD = "too old"
    NOT_UTF8 = "not utf-8"
    CHANGED = "upgrade changed"
    BEHIND = "behind"
    AUDIT_MONTH_MISSING = "audit month missing"
    RECORD_DAY_MISSING = "record-block day missing"


# What stops a command from reaching the database at all; the others only
# make the server not ready (a command such as `fcon db upgrade` fixes some).
CONNECTION_PROBLEMS = frozenset({Problem.UNREACHABLE, Problem.LOGIN_REFUSED, Problem.DATABASE_MISSING, Problem.TOO_OLD})


@dataclass(frozen=True)
class DatabaseAddress:
    """Where the database is, as a person names it: never the password."""

    host: str
    port: str
    dbname: str
    user: str


@dataclass(frozen=True)
class DatabaseCheck:
    """What one check found: the database is usable when `problem` is None.

    `reason` says why it is unreachable, `version` is the version found,
    `detail` the driver's own first line; `encoding`, `icu` (whether the ICU
    collation exists), `migrations` (the upgrades against this version's files)
    `months_ahead` (the audit months made after the current one) and
    `days_ahead` (the record blocks' days made after today) once connected:
    all for the log, never for a reply.
    """

    address: DatabaseAddress
    problem: Problem | None = None
    reason: str = ""
    version: str = ""
    detail: str = ""
    encoding: str = ""
    icu: bool = True
    migrations: MigrationStatus | None = None
    months_ahead: int = 0
    days_ahead: int = 0


# libpq gives no error code at connection time, only Postgres's English text.
_TEXTS = [
    (re.compile(r'database ".*" does not exist'), Problem.DATABASE_MISSING, ""),
    (re.compile(r"password authentication failed"), Problem.LOGIN_REFUSED, ""),
    (re.compile(r"no pg_hba\.conf entry"), Problem.LOGIN_REFUSED, ""),
    (re.compile(r'role ".*" does not exist'), Problem.LOGIN_REFUSED, ""),
    (re.compile(r"connection refused"), Problem.UNREACHABLE, REFUSED),
    (re.compile(r"could not translate host name"), Problem.UNREACHABLE, HOST_NOT_FOUND),
    (re.compile(r"timeout expired"), Problem.UNREACHABLE, TIMED_OUT),
]


def address_of(url: str) -> DatabaseAddress:
    """The database address in `url`, with libpq's defaults filled in and never the password."""
    params = conninfo.conninfo_to_dict(url)
    user = str(params.get("user") or "")
    return DatabaseAddress(
        host=str(params.get("host") or "localhost"),
        port=str(params.get("port") or "5432"),
        dbname=str(params.get("dbname") or user),
        user=user,
    )


def classify(text: str) -> tuple[Problem, str]:
    """The problem the driver's text names, and why it is unreachable.

    A text it does not know is unreachable, with the driver's first line as the
    reason.
    """
    lowered = text.lower()
    for pattern, problem, reason in _TEXTS:
        if pattern.search(lowered):
            return problem, reason
    return Problem.UNREACHABLE, first_line(text)


def first_line(text: str) -> str:
    """The text's first line once trimmed, or "" for a blank text."""
    return text.strip().splitlines()[0] if text.strip() else ""


def version_text(server_version: int) -> str:
    """160004 -> "16.4"."""
    major, minor = divmod(server_version, 10000)
    return f"{major}.{minor}"


def assess_version(address: DatabaseAddress, server_version: int) -> DatabaseCheck:
    """The check of the server's version alone: too old below Postgres 18."""
    version = version_text(server_version)
    problem = Problem.TOO_OLD if server_version < OLDEST_SUPPORTED else None
    return DatabaseCheck(address=address, problem=problem, version=version)


def port_refuses(host: str, port: int) -> bool:
    """Whether the port refuses a plain connection.

    On Windows psycopg reports a refused port as a timeout, so this tells the
    two apart.
    """
    try:
        with socket.create_connection((host, port), timeout=PROBE_TIMEOUT_S):
            return False
    except OSError as err:
        return isinstance(err, ConnectionRefusedError)


def open_connection(url: str) -> psycopg.Connection[tuple[object, ...]]:
    """Open the check's own connection, every wait on it cut off after TIMEOUT_S.

    Connecting, each query and a peer that stops answering are each cut off;
    closing it sends nothing more (no transaction to commit).
    """
    timeout_ms = TIMEOUT_S * 1000
    return psycopg.connect(
        url,
        autocommit=True,
        connect_timeout=TIMEOUT_S,
        options=f"-c statement_timeout={timeout_ms}",
        tcp_user_timeout=timeout_ms,  # unacknowledged data; ignored where the system has no such option
        keepalives=1,
        keepalives_idle=1,
        keepalives_interval=1,
        keepalives_count=2,
    )


def _one(connection: psycopg.Connection[tuple[object, ...]], query: str, *params: object) -> object:
    """The first column of the query's first row, or None when it gives no row."""
    row = connection.execute(query.encode(), params).fetchone()
    return row[0] if row else None


def _partitions(connection: psycopg.Connection[tuple[object, ...]], table: str) -> set[str]:
    """The names of the partitions of `table`, such as the audit log's months."""
    rows = connection.execute(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid WHERE i.inhparent = to_regclass(%s)",
        [table],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _ahead(partitions: set[str], names: list[str]) -> tuple[bool, int]:
    """Whether the first of `names` is among the partitions, and how many in a row after it are."""
    current, *ahead = names
    count = 0
    for name in ahead:
        if name not in partitions:
            break
        count += 1
    return current in partitions, count


def _readiness_problem(encoding: str, status: MigrationStatus, partitions: tuple[bool, bool]) -> Problem | None:
    """The first problem that keeps a connected database from being ready, or None.

    `partitions` says whether this month's audit partition and today's record-block one are there.
    """
    has_current_month, has_today = partitions
    if encoding != ENCODING:
        return Problem.NOT_UTF8
    if status.changed:
        return Problem.CHANGED
    if status.waiting:
        return Problem.BEHIND
    if not has_current_month:
        return Problem.AUDIT_MONTH_MISSING
    if not has_today:
        return Problem.RECORD_DAY_MISSING
    return None


def check_database(url: str, *, clock: Clock = _SYSTEM_CLOCK, directory: Path = MIGRATIONS) -> DatabaseCheck:
    """A fresh connection and a few queries, within TIMEOUT_S seconds each."""
    address = address_of(url)
    try:
        with open_connection(url) as connection:
            connection.execute("SELECT 1")
            version = assess_version(address, connection.info.server_version)
            encoding = connection.info.parameter_status("server_encoding") or ""
            icu = _one(connection, "SELECT EXISTS (SELECT 1 FROM pg_collation WHERE collname = %s)", ICU_COLLATION)
            status = read_status(connection, read_migrations(directory))
            months = [f"audit_{month:%Y_%m}" for month in audit_months(clock.now())]
            has_current_month, months_ahead = _ahead(_partitions(connection, "fcon.audit"), months)
            days = [f"record_block_{day:%Y%m%d}" for day in record_days(clock.now())]
            has_today, days_ahead = _ahead(_partitions(connection, "fcon.record_block"), days)
    except psycopg.Error as err:  # any driver error: not ready, never a 500
        problem, reason = classify(str(err))
        return DatabaseCheck(address=address, problem=problem, reason=reason, detail=first_line(str(err)))
    return replace(
        version,
        problem=version.problem or _readiness_problem(encoding, status, (has_current_month, has_today)),
        encoding=encoding,
        icu=bool(icu),
        migrations=status,
        months_ahead=months_ahead,
        days_ahead=days_ahead,
    )


def diagnose_database(
    url: str,
    *,
    check: Callable[[str], DatabaseCheck] = check_database,
    probe: Callable[[str, int], bool] = port_refuses,
) -> DatabaseCheck:
    """The check, and when it timed out, a probe of the port to tell a refused port from a silent one.

    It is for the log, which names the cause. It can take PROBE_TIMEOUT_S more,
    so /readyz, which says one word, never does it.
    """
    result = check(url)
    if result.reason == TIMED_OUT and probe(result.address.host, int(result.address.port)):
        return replace(result, reason=REFUSED)
    return result
