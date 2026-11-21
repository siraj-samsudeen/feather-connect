"""The database check's rules that need no server: the version rule, and how
the driver's text is read."""

import pytest

from feather_server.database import DatabaseAddress, Problem, assess_version, classify

ADDRESS = DatabaseAddress(host="db.internal", port="5432", dbname="feather", user="feather")


def test_postgres_18_is_usable():
    assert assess_version(ADDRESS, 180000).problem is None


def test_postgres_older_than_18_is_too_old():
    assert assess_version(ADDRESS, 170009).problem is Problem.TOO_OLD


@pytest.mark.parametrize(
    ("server_version", "shown"),
    [(160004, "16.4"), (180007, "18.7"), (190000, "19.0")],
    ids=["16.4", "18.7", "19.0"],
)
def test_the_version_found_is_shown_as_major_and_minor(server_version: int, shown: str):
    assert assess_version(ADDRESS, server_version).version == shown


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ('connection to server at "10.0.0.5", port 5432 failed: FATAL:  database "flows" does not exist',
         (Problem.DATABASE_MISSING, "")),
        ('connection to server at "10.0.0.5", port 5432 failed: FATAL:  password authentication failed for user "a"',
         (Problem.LOGIN_REFUSED, "")),
        ('connection to server at "10.0.0.5", port 5432 failed: FATAL:  no pg_hba.conf entry for host "10.0.0.9"',
         (Problem.LOGIN_REFUSED, "")),
        ('connection to server at "10.0.0.5", port 5432 failed: FATAL:  role "a" does not exist',
         (Problem.LOGIN_REFUSED, "")),
        ('connection to server at "10.0.0.5", port 5432 failed: Connection refused\n\tIs the server running?',
         (Problem.UNREACHABLE, "connection refused")),
        ('could not translate host name "db.internal" to address: Name or service not known',
         (Problem.UNREACHABLE, "host not found")),
        ("connection timeout expired", (Problem.UNREACHABLE, "timed out")),
    ],
    ids=["database-missing", "wrong-password", "no-hba-entry", "no-such-role", "refused", "unknown-host", "timeout"],
)
def test_the_drivers_text_is_read_as_a_problem(text: str, kind: tuple[Problem, str]):
    assert classify(text) == kind


def test_a_text_it_does_not_recognise_is_unreachable_with_the_drivers_first_line():
    assert classify("SSL error: certificate verify failed\nmore") == (
        Problem.UNREACHABLE,
        "SSL error: certificate verify failed",
    )
