"""The error helper: every message a person reads says what is wrong and what
to do. Issue 4, point 5 pins six texts exactly; the others keep their shape."""

import pytest

from feather_cli import problems
from feather_cli.problems import Level, Problem
from feather_server.database import DatabaseAddress, DatabaseCheck
from feather_server.database import Problem as Kind

LOCAL = DatabaseAddress(host="127.0.0.1", port="5442", dbname="feather_issue_4", user="feather")
REMOTE = DatabaseAddress(host="db.internal", port="5432", dbname="feather", user="feather")


def test_a_problem_is_its_level_what_is_wrong_and_what_to_do_indented():
    problem = Problem(Level.WARNING, "something is wrong.", ("Do this.", "Or that."))

    assert problem.text() == "warning: something is wrong.\n  Do this.\n  Or that."


def test_the_missing_database_address():
    assert problems.database_url_missing().text() == (
        "error: FEATHER_DATABASE_URL is not set.\n"
        "  Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather\n"
        "  For development: copy .env.example to .env, then run: docker compose up -d"
    )


def test_a_taken_port():
    assert problems.port_taken("127.0.0.1", 8080).text() == (
        "error: port 8080 on 127.0.0.1 is already in use.\n"
        "  Stop the program using it, or pick another port: FEATHER_PORT=8081 (or --port 8081)"
    )


def test_an_unreachable_database_on_this_machine():
    check = DatabaseCheck(address=LOCAL, problem=Kind.UNREACHABLE, reason="connection refused")

    assert problems.database_problem(check).text() == (
        "warning: cannot reach the database at 127.0.0.1:5442 (connection refused). Not ready.\n"
        "  Start it: docker compose up -d"
    )


def test_a_missing_database_on_this_machine():
    check = DatabaseCheck(address=LOCAL, problem=Kind.DATABASE_MISSING)

    assert problems.database_problem(check).text() == (
        "warning: the database feather_issue_4 does not exist on 127.0.0.1:5442. Not ready.\n"
        "  Create it: docker compose exec db createdb -U feather feather_issue_4"
    )


def test_a_refused_login():
    check = DatabaseCheck(address=REMOTE, problem=Kind.LOGIN_REFUSED)

    assert problems.database_problem(check).text() == (
        "warning: the database at db.internal:5432 refused the login of user feather. Not ready.\n"
        "  Check the user and password in FEATHER_DATABASE_URL."
    )


def test_a_postgres_older_than_18():
    check = DatabaseCheck(address=REMOTE, problem=Kind.TOO_OLD, version="16.4")

    assert problems.database_problem(check).text() == (
        "warning: Postgres 16.4 found at db.internal:5432; Feather Connect needs 18 or later. Not ready."
    )


@pytest.mark.parametrize("host", ["localhost", "::1"])
def test_every_name_of_this_machine_gets_the_development_hint(host: str):
    check = DatabaseCheck(address=DatabaseAddress(host, "5442", "feather", "feather"), problem=Kind.UNREACHABLE)

    assert "docker compose up -d" in problems.database_problem(check).text()


def test_an_unreachable_database_elsewhere_gets_no_development_hint():
    check = DatabaseCheck(address=REMOTE, problem=Kind.UNREACHABLE, reason="timed out")

    assert problems.database_problem(check).text() == (
        "warning: cannot reach the database at db.internal:5432 (timed out). Not ready.\n"
        "  Check the host and port in FEATHER_DATABASE_URL, and that the database server is running."
    )


def test_a_missing_database_elsewhere_gets_no_development_hint():
    check = DatabaseCheck(address=REMOTE, problem=Kind.DATABASE_MISSING)

    assert problems.database_problem(check).text() == (
        "warning: the database feather does not exist on db.internal:5432. Not ready.\n"
        "  Create it on that server, or correct its name in FEATHER_DATABASE_URL."
    )


def test_a_usable_database_is_named_as_ready():
    assert problems.database_usable(DatabaseCheck(address=LOCAL)) == (
        "the database feather_issue_4 at 127.0.0.1:5442 is usable. Ready."
    )


def test_a_database_usable_again_says_so():
    assert problems.database_usable(DatabaseCheck(address=LOCAL), again=True) == (
        "the database feather_issue_4 at 127.0.0.1:5442 is usable again. Ready."
    )


def test_an_address_that_is_not_postgres_never_repeats_the_address():
    assert problems.database_url_not_postgres().text() == (
        "error: FEATHER_DATABASE_URL is not a Postgres address.\n"
        "  Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather"
    )


def test_a_port_that_is_not_a_port_number():
    assert problems.port_not_a_number("FEATHER_PORT", "eighty").text() == (
        "error: FEATHER_PORT is not a port number: eighty.\n"
        "  Use a number from 1 to 65535, for example: FEATHER_PORT=8080 (or --port 8080)"
    )


def test_an_unknown_log_format():
    assert problems.log_format_unknown("yaml").text() == (
        "error: FEATHER_LOG_FORMAT is not text or json: yaml.\n"
        "  Set it to text or json, or leave it unset: text on a terminal, json elsewhere."
    )


def test_a_port_this_machine_does_not_allow():
    assert problems.port_not_allowed("0.0.0.0", 80).text() == (  # noqa: S104
        "error: this machine does not allow listening on port 80 on 0.0.0.0.\n"
        "  Ports below 1024 need extra rights, and Windows reserves some ranges for itself.\n"
        "  Pick another port: FEATHER_PORT=8080 (or --port 8080)"
    )


def test_a_port_not_allowed_above_1024_suggests_the_next_one():
    assert "FEATHER_PORT=50001 (or --port 50001)" in problems.port_not_allowed("127.0.0.1", 50000).text()


def test_a_host_that_is_not_this_machine():
    assert problems.host_not_here("192.0.2.1").text() == (
        "error: cannot listen on 192.0.2.1: it is not an address of this machine.\n"
        "  Use 127.0.0.1 for this machine only, or 0.0.0.0 for every network: FEATHER_HOST=127.0.0.1 (or --host)"
    )


def test_listening_beyond_this_machine():
    assert problems.listening_beyond_machine("0.0.0.0", 8080).text() == (  # noqa: S104
        "warning: listening on 0.0.0.0:8080 can be reached from other machines.\n"
        "  Put it behind the host's HTTPS proxy, or keep it on this machine: FEATHER_HOST=127.0.0.1"
    )


def test_a_command_line_mistake_shows_the_usage():
    problem = problems.usage("argument --port: invalid int value: 'x'", "usage: feather server [--port PORT]\n")

    assert problem.text() == (
        "error: argument --port: invalid int value: 'x'.\n"
        "  usage: feather server [--port PORT]\n"
        "  For every option: feather --help"
    )


def test_a_bug_says_it_is_one():
    assert problems.bug().text() == "error: this is a bug in Feather Connect; please report it with the lines below."
