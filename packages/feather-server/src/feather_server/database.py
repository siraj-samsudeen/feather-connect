"""The database check: whether the database is usable, and if not, which
problem it has. It returns facts; the command line words them for a person,
and /readyz says one word.

No connection pool yet (design decision 2): each check opens a fresh
connection, runs one query and closes it, so a problem keeps its cause.
"""

import re
import socket
from dataclasses import dataclass
from enum import StrEnum

import psycopg
from psycopg import conninfo

TIMEOUT_S = 2
# Windows reports a refused port on its own machine only after about 2 s of
# retries, so the probe waits longer than the check.
PROBE_TIMEOUT_S = 5
OLDEST_SUPPORTED = 180000  # Postgres 18.0, as server_version_num counts it

REFUSED = "connection refused"
TIMED_OUT = "timed out"
HOST_NOT_FOUND = "host not found"


class Problem(StrEnum):
    UNREACHABLE = "unreachable"
    LOGIN_REFUSED = "login refused"
    DATABASE_MISSING = "database missing"
    TOO_OLD = "too old"


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
    `version` is the version found, `detail` the driver's own first line:
    all for the log, never for a reply."""

    address: DatabaseAddress
    problem: Problem | None = None
    reason: str = ""
    version: str = ""
    detail: str = ""


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
    return "%d.%d" % divmod(server_version, 10000)


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


def check_database(url: str) -> DatabaseCheck:
    """A fresh connection and one query, within TIMEOUT_S seconds each."""
    address = address_of(url)
    try:
        with psycopg.connect(url, connect_timeout=TIMEOUT_S) as connection:
            connection.execute("SELECT 1")
            server_version = connection.info.server_version
    except psycopg.OperationalError as err:
        problem, reason = classify(str(err))
        if reason == TIMED_OUT:
            reason = REFUSED if port_refuses(address.host, int(address.port)) else TIMED_OUT
        return DatabaseCheck(address=address, problem=problem, reason=reason, detail=first_line(str(err)))
    return assess_version(address, server_version)
