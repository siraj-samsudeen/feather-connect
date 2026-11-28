"""Tests of the error helper: every message a person reads says what is wrong and what to do.

Issue 4, point 5 pins six texts exactly; the others keep their shape.
"""

from datetime import UTC, datetime

import pytest

from fcon_cli import problems
from fcon_cli.problems import Level, Problem
from fcon_server.database import DatabaseAddress, DatabaseCheck
from fcon_server.database import Problem as Kind
from fcon_server.store.migrate import MigrationStatus, Ran

LOCAL = DatabaseAddress(host="127.0.0.1", port="5442", dbname="feather_issue_4", user="feather")
REMOTE = DatabaseAddress(host="db.internal", port="5432", dbname="feather", user="feather")


def test_a_problem_is_its_level_what_is_wrong_and_what_to_do_indented():
    problem = Problem(Level.WARNING, "something is wrong.", ("Do this.", "Or that."))

    assert problem.text() == "warning: something is wrong.\n  Do this.\n  Or that."


def test_the_missing_database_address():
    assert problems.database_url_missing().text() == (
        "error: FCON_DATABASE_URL is not set.\n"
        "  Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather\n"
        "  For development: copy .env.example to .env, then run: docker compose up -d"
    )


def test_a_taken_port():
    assert problems.port_taken("127.0.0.1", 8080).text() == (
        "error: port 8080 on 127.0.0.1 is already in use.\n"
        "  Stop the program using it, or pick another port: FCON_PORT=8081 (or --port 8081)"
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
        "  Check the user and password in FCON_DATABASE_URL."
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
        "  Check the host and port in FCON_DATABASE_URL, and that the database server is running."
    )


def test_a_missing_database_elsewhere_gets_no_development_hint():
    check = DatabaseCheck(address=REMOTE, problem=Kind.DATABASE_MISSING)

    assert problems.database_problem(check).text() == (
        "warning: the database feather does not exist on db.internal:5432. Not ready.\n"
        "  Create it on that server, or correct its name in FCON_DATABASE_URL."
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
        "error: FCON_DATABASE_URL is not a Postgres address.\n"
        "  Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather"
    )


def test_a_port_that_is_not_a_port_number():
    assert problems.port_not_a_number("FCON_PORT", "eighty").text() == (
        "error: FCON_PORT is not a port number: eighty.\n"
        "  Use a number from 1 to 65535, for example: FCON_PORT=8080 (or --port 8080)"
    )


def test_an_unknown_log_format():
    assert problems.log_format_unknown("yaml").text() == (
        "error: FCON_LOG_FORMAT is not text or json: yaml.\n"
        "  Set it to text or json, or leave it unset: text on a terminal, json elsewhere."
    )


def test_a_pool_size_that_is_not_a_number():
    assert problems.pool_size_not_a_number("many").text() == (
        "error: FCON_DATABASE_POOL_SIZE is not a number of connections: many.\n"
        "  Use a whole number from 1 up, or leave it unset for 5."
    )


def test_an_unknown_prepare_setting():
    assert problems.prepare_unknown("no").text() == (
        "error: FCON_DATABASE_PREPARE is not on or off: no.\n"
        "  Set it to off when a connection pooler sits in front of Postgres; leave it unset otherwise."
    )


def test_a_port_this_machine_does_not_allow():
    assert problems.port_not_allowed("0.0.0.0", 80).text() == (  # noqa: S104
        "error: this machine does not allow listening on port 80 on 0.0.0.0.\n"
        "  Ports below 1024 need extra rights, and Windows reserves some ranges for itself.\n"
        "  Pick another port: FCON_PORT=8080 (or --port 8080)"
    )


def test_a_port_not_allowed_above_1024_suggests_the_next_one():
    assert "FCON_PORT=50001 (or --port 50001)" in problems.port_not_allowed("127.0.0.1", 50000).text()


def test_a_host_that_is_not_this_machine():
    assert problems.host_not_here("192.0.2.1").text() == (
        "error: cannot listen on 192.0.2.1: it is not an address of this machine.\n"
        "  Use 127.0.0.1 for this machine only, or 0.0.0.0 for every network: FCON_HOST=127.0.0.1 (or --host)"
    )


def test_listening_beyond_this_machine():
    assert problems.listening_beyond_machine("0.0.0.0", 8080).text() == (  # noqa: S104
        "warning: listening on 0.0.0.0:8080 can be reached from other machines.\n"
        "  Put it behind the host's HTTPS proxy, or keep it on this machine: FCON_HOST=127.0.0.1"
    )


def test_a_command_line_mistake_shows_the_usage():
    problem = problems.usage("argument --port: invalid int value: 'x'", "usage: fcon server [--port PORT]\n")

    assert problem.text() == (
        "error: argument --port: invalid int value: 'x'.\n"
        "  usage: fcon server [--port PORT]\n"
        "  For every option: fcon --help"
    )


def test_a_bug_says_it_is_one():
    assert problems.bug().text() == "error: this is a bug in Feather Connect; please report it with the lines below."


# -- fcon db -------------------------------------------------------------


def test_a_command_stops_with_an_error_for_an_unreachable_database():
    check = DatabaseCheck(address=LOCAL, problem=Kind.UNREACHABLE, reason="connection refused")

    assert problems.database_unusable(check, "FCON_DATABASE_URL").text() == (
        "error: cannot reach the database at 127.0.0.1:5442 (connection refused).\n  Start it: docker compose up -d"
    )


def test_a_command_names_the_setting_it_read_the_address_from():
    check = DatabaseCheck(address=REMOTE, problem=Kind.LOGIN_REFUSED)

    assert problems.database_unusable(check, "FCON_MIGRATION_DATABASE_URL").text() == (
        "error: the database at db.internal:5432 refused the login of user feather.\n"
        "  Check the user and password in FCON_MIGRATION_DATABASE_URL."
    )


def test_a_command_says_a_missing_database_elsewhere_is_named_in_its_setting():
    check = DatabaseCheck(address=REMOTE, problem=Kind.DATABASE_MISSING)

    assert problems.database_unusable(check, "FCON_MIGRATION_DATABASE_URL").text() == (
        "error: the database feather does not exist on db.internal:5432.\n"
        "  Create it on that server, or correct its name in FCON_MIGRATION_DATABASE_URL."
    )


def test_a_command_says_an_unreachable_database_elsewhere_is_named_in_its_setting():
    check = DatabaseCheck(address=REMOTE, problem=Kind.UNREACHABLE, reason="timed out")

    assert problems.database_unusable(check, "FCON_MIGRATION_DATABASE_URL").text() == (
        "error: cannot reach the database at db.internal:5432 (timed out).\n"
        "  Check the host and port in FCON_MIGRATION_DATABASE_URL, and that the database server is running."
    )


def test_a_command_stops_for_a_postgres_older_than_18():
    check = DatabaseCheck(address=REMOTE, problem=Kind.TOO_OLD, version="16.4")

    assert problems.database_unusable(check, "FCON_DATABASE_URL").text() == (
        "error: Postgres 16.4 found at db.internal:5432; Feather Connect needs 18 or later."
    )


def test_a_changed_upgrade_names_the_file_and_says_to_restore_it():
    assert problems.upgrade_changed("20261121T1530Z_first_tables.sql").text() == (
        "error: upgrade 20261121T1530Z_first_tables.sql has changed since it ran.\n"
        "  Restore it; never edit a migration that ran."
    )


def test_an_upgrade_that_waits_for_another_says_so():
    assert problems.waiting_for_upgrade() == "waiting for another upgrade of the database to finish..."


# -- readiness beyond the connection (storage-foundation, point 9) ---------

APPLIED = Ran("20261121T1530Z_first_tables.sql", datetime(2026, 11, 21, tzinfo=UTC))


def status(waiting: int = 0, newer: int = 0, changed: tuple[Ran, ...] = ()) -> MigrationStatus:
    return MigrationStatus(
        applied=(),
        waiting=tuple(f"2026112{n}T0000Z_waiting.sql" for n in range(waiting)),
        newer=tuple(f"2999010{n}T0000Z_newer.sql" for n in range(newer)),
        changed=changed,
    )


def test_a_database_two_upgrades_behind():
    check = DatabaseCheck(address=LOCAL, problem=Kind.BEHIND, migrations=status(waiting=2))

    assert problems.database_problem(check).text() == (
        "warning: the database is 2 upgrades behind this version. Not ready.\n  Run: fcon db upgrade"
    )


def test_a_database_one_upgrade_behind():
    check = DatabaseCheck(address=LOCAL, problem=Kind.BEHIND, migrations=status(waiting=1))

    assert problems.database_problem(check).text().startswith("warning: the database is 1 upgrade behind")


def test_a_database_with_a_changed_upgrade():
    check = DatabaseCheck(address=LOCAL, problem=Kind.CHANGED, migrations=status(changed=(APPLIED,)))

    assert problems.database_problem(check).text() == (
        "error: upgrade 20261121T1530Z_first_tables.sql has changed since it ran.\n"
        "  Restore it; never edit a migration that ran."
    )


def test_a_database_not_in_utf8():
    check = DatabaseCheck(address=LOCAL, problem=Kind.NOT_UTF8, encoding="SQL_ASCII")

    assert problems.database_problem(check).text() == (
        "warning: the database feather_issue_4 uses the encoding SQL_ASCII; Feather Connect needs UTF8. Not ready.\n"
        "  Make a new database in UTF-8 (createdb -E UTF8 -T template0 <name>), point FCON_DATABASE_URL at it,"
        " then run: fcon db upgrade"
    )


def test_a_database_with_no_audit_month_for_now():
    check = DatabaseCheck(address=LOCAL, problem=Kind.AUDIT_MONTH_MISSING)

    assert problems.database_problem(check).text() == (
        "warning: the audit log has no partition for this month, so no change can be saved. Not ready.\n"
        "  Run: fcon db upgrade"
    )


def test_a_usable_database_has_no_notes():
    assert (
        problems.database_notes(DatabaseCheck(address=LOCAL, migrations=status(), months_ahead=6, days_ahead=90)) == ()
    )


def test_a_database_with_an_upgrade_from_a_newer_version_is_noted():
    check = DatabaseCheck(address=LOCAL, migrations=status(newer=1), months_ahead=6, days_ahead=90)

    assert [note.text() for note in problems.database_notes(check)] == [
        "info: the database has 1 upgrade newer than this version; expand-only upgrades keep it working."
    ]


def test_two_upgrades_from_a_newer_version_are_counted():
    check = DatabaseCheck(address=LOCAL, migrations=status(newer=2), months_ahead=6, days_ahead=90)

    assert problems.database_notes(check)[0].what.startswith("the database has 2 upgrades newer")


def test_a_database_without_icu_is_warned_that_lists_sort_by_character_code():
    check = DatabaseCheck(address=LOCAL, icu=False, migrations=status(), months_ahead=6, days_ahead=90)

    assert [note.text() for note in problems.database_notes(check)] == [
        "warning: the database has no ICU collation (und-x-icu), so lists sort by character code."
    ]


def test_fewer_than_three_audit_months_ahead_is_warned():
    check = DatabaseCheck(address=LOCAL, migrations=status(), months_ahead=2, days_ahead=90)

    assert [note.text() for note in problems.database_notes(check)] == [
        "warning: the audit log has partitions for only 2 months after this one.\n  Run: fcon db upgrade"
    ]


def test_three_audit_months_ahead_are_enough():
    check = DatabaseCheck(address=LOCAL, migrations=status(), months_ahead=3, days_ahead=90)

    assert problems.database_notes(check) == ()


def test_a_database_not_ready_has_no_notes():
    check = DatabaseCheck(address=LOCAL, problem=Kind.BEHIND, icu=False, migrations=status(waiting=1, newer=1))

    assert problems.database_notes(check) == ()


def test_a_missing_secret_key_says_how_to_make_one():
    assert problems.secret_key_missing().text() == (
        "error: FCON_SECRET_KEY is not set.\n"
        "  Every install needs one of at least 32 random characters. Make one with:\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )


def test_a_short_secret_key_never_shows_the_key():
    assert problems.secret_key_too_short("FCON_SECRET_KEY").text() == (
        "error: FCON_SECRET_KEY is shorter than 32 characters.\n"
        "  Make a longer one with:\n"
        '  python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )


def test_a_forwarded_request_with_no_proxy_trusted_names_the_setting():
    assert problems.untrusted_forwarding().text() == (
        "warning: requests carry X-Forwarded-For, but no proxy is trusted; set FCON_TRUSTED_PROXIES."
    )


def test_a_database_with_no_record_block_day_for_today():
    check = DatabaseCheck(address=LOCAL, problem=Kind.RECORD_DAY_MISSING)

    assert problems.database_problem(check).text() == (
        "warning: the record blocks have no partition for today, so no read can be stored. Not ready.\n"
        "  Run: fcon db upgrade"
    )


def test_fewer_than_30_record_block_days_ahead_is_warned():
    check = DatabaseCheck(address=LOCAL, migrations=status(), months_ahead=6, days_ahead=29)

    assert [note.text() for note in problems.database_notes(check)] == [
        "warning: the record blocks have partitions for only 29 days after today.\n  Run: fcon db upgrade"
    ]


def test_30_record_block_days_ahead_are_enough():
    check = DatabaseCheck(address=LOCAL, migrations=status(), months_ahead=6, days_ahead=30)

    assert problems.database_notes(check) == ()
