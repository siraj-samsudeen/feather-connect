"""The database check: whether the database is usable, and if not, which
problem it has. It returns facts; the command line words them for a person,
and /readyz says one word.

Readiness keeps its own connection (storage-foundation, decision 3): each
check opens a fresh connection, runs its few queries and closes it, so a
problem keeps its cause. Beyond the connection it reads the database's
encoding, whether the ICU collation exists, the upgrades recorded against
this version's files, and the audit log's monthly partitions.
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
from fcon_server.store.migrate import MIGRATIONS, MigrationStatus, audit_months, read_migrations, read_status

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
    UNREACHABLE = "unreachable"
    LOGIN_REFUSED = "login refused"
    DATABASE_MISSING = "database missing"
    TOO_OLD = "too old"
    NOT_UTF8 = "not utf-8"
    CHANGED = "upgrade changed"
    BEHIND = "behind"
    AUDIT_MONTH_MISSING = "audit month missing"


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
    """Usable when `problem` is None. `reason` says why it is unreachable,
    `version` is the version found, `detail` the driver's own first line;
    `encoding`, `icu` (whether the ICU collation exists), `migrations` (the
    upgrades against this version's files) and `months_ahead` (the audit
    months made after the current one) once connected: all for the log,
    never for a reply."""

    address: DatabaseAddress
    problem: Problem | None = None
    reason: str = ""
    version: str = ""
    detail: str = ""
    encoding: str = ""
    icu: bool = True
    migrations: MigrationStatus | None = None
    months_ahead: int = 0


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
    params = conninfo.conninfo_to_dict(url)
    user = str(params.get("user") or "")
    return DatabaseAddress(
        host=str(params.get("host") or "localhost"),
        port=str(params.get("port") or "5432"),
        dbname=str(params.get("dbname") or user),
        user=user,
    )


def classify(text: str) -> tuple[Problem, str]:
    """The problem the driver's text names, and why it is unreachable; a text
    it does not know is unreachable, with the driver's first line."""
    lowered = text.lower()
    for pattern, problem, reason in _TEXTS:
        if pattern.search(lowered):
            return problem, reason
    return Problem.UNREACHABLE, first_line(text)


def first_line(text: str) -> str:
    return text.strip().splitlines()[0] if text.strip() else ""


def version_text(server_version: int) -> str:
    """160004 -> "16.4"."""
    major, minor = divmod(server_version, 10000)
    return f"{major}.{minor}"


def assess_version(address: DatabaseAddress, server_version: int) -> DatabaseCheck:
    version = version_text(server_version)
    problem = Problem.TOO_OLD if server_version < OLDEST_SUPPORTED else None
    return DatabaseCheck(address=address, problem=problem, version=version)


def port_refuses(host: str, port: int) -> bool:
    """Whether the port refuses a plain connection: on Windows psycopg reports
    a refused port as a timeout, so this tells the two apart."""
    try:
        with socket.create_connection((host, port), timeout=PROBE_TIMEOUT_S):
            return False
    except OSError as err:
        return isinstance(err, ConnectionRefusedError)


def open_connection(url: str) -> psycopg.Connection[tuple[object, ...]]:
    """The check's connection: connecting, each query and a peer that stops
    answering are each cut off after TIMEOUT_S, and closing it sends nothing
    more (no transaction to commit)."""
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
    row = connection.execute(query.encode(), params).fetchone()
    return row[0] if row else None


def _audit_partitions(connection: psycopg.Connection[tuple[object, ...]]) -> set[str]:
    rows = connection.execute(
        "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
        " WHERE i.inhparent = to_regclass('fcon.audit')"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _months_ahead(partitions: set[str], clock: Clock) -> tuple[bool, int]:
    """Whether the current UTC month has its partition, and how many months
    in a row after it do."""
    current, *ahead = (f"audit_{month:%Y_%m}" for month in audit_months(clock.now()))
    count = 0
    for name in ahead:
        if name not in partitions:
            break
        count += 1
    return current in partitions, count


def _readiness_problem(encoding: str, status: MigrationStatus, has_current_month: bool) -> Problem | None:
    if encoding != ENCODING:
        return Problem.NOT_UTF8
    if status.changed:
        return Problem.CHANGED
    if status.waiting:
        return Problem.BEHIND
    if not has_current_month:
        return Problem.AUDIT_MONTH_MISSING
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
            has_current_month, months_ahead = _months_ahead(_audit_partitions(connection), clock)
    except psycopg.Error as err:  # any driver error: not ready, never a 500
        problem, reason = classify(str(err))
        return DatabaseCheck(address=address, problem=problem, reason=reason, detail=first_line(str(err)))
    return replace(
        version,
        problem=version.problem or _readiness_problem(encoding, status, has_current_month),
        encoding=encoding,
        icu=bool(icu),
        migrations=status,
        months_ahead=months_ahead,
    )


def diagnose_database(
    url: str,
    *,
    check: Callable[[str], DatabaseCheck] = check_database,
    probe: Callable[[str, int], bool] = port_refuses,
) -> DatabaseCheck:
    """The check, and when it timed out, a probe of the port to tell a refused
    port from a silent one: for the log, which names the cause. It can take
    PROBE_TIMEOUT_S more, so /readyz, which says one word, never does it."""
    result = check(url)
    if result.reason == TIMED_OUT and probe(result.address.host, int(result.address.port)):
        return replace(result, reason=REFUSED)
    return result
