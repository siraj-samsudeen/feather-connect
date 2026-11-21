"""The database check: whether the database is usable, and if not, which
problem it has. It returns facts; the command line words them for a person,
and /readyz says one word."""

from dataclasses import dataclass
from enum import StrEnum


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
    address: DatabaseAddress
    problem: Problem | None = None
    reason: str = ""
    version: str = ""
    detail: str = ""


def check_database(url: str) -> DatabaseCheck:
    raise NotImplementedError


def assess_version(address: DatabaseAddress, server_version: int) -> DatabaseCheck:
    raise NotImplementedError


def classify(text: str) -> tuple[Problem, str]:
    raise NotImplementedError
