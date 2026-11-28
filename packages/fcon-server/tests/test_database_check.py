"""The database check: usable, or which problem, against a real Postgres 18."""

import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import conninfo

from fcon_server import database
from fcon_server.database import (
    DatabaseAddress,
    Problem,
    address_of,
    check_database,
    diagnose_database,
    open_connection,
    port_refuses,
)
from fcon_server.store.clock import FixedClock, SystemClock
from fcon_server.store.migrate import MIGRATIONS, upgrade


@pytest.mark.database
def test_a_running_postgres_18_is_usable(database_url: str):
    assert check_database(database_url).problem is None


@pytest.mark.database
def test_a_database_that_does_not_exist_is_missing(database_url: str):
    url = conninfo.make_conninfo(database_url, dbname="feather_no_such_database")

    assert check_database(url).problem is Problem.DATABASE_MISSING


@pytest.mark.database
def test_a_wrong_password_is_a_refused_login(database_url: str):
    url = conninfo.make_conninfo(database_url, password="not-the-password")

    assert check_database(url).problem is Problem.LOGIN_REFUSED


def test_diagnosing_a_port_nothing_listens_on_finds_the_connection_refused(free_port: int):
    check = diagnose_database(f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")

    assert (check.problem, check.reason) == (Problem.UNREACHABLE, "connection refused")


def test_a_server_that_never_answers_is_unreachable_because_it_timed_out(silent_port: int):
    check = check_database(f"postgresql://feather:feather@127.0.0.1:{silent_port}/feather")

    assert (check.problem, check.reason) == (Problem.UNREACHABLE, "timed out")


def test_diagnosing_a_server_that_never_answers_finds_it_timed_out(silent_port: int):
    check = diagnose_database(f"postgresql://feather:feather@127.0.0.1:{silent_port}/feather")

    assert (check.problem, check.reason) == (Problem.UNREACHABLE, "timed out")


def test_the_check_names_the_database_by_host_port_name_and_user():
    address = address_of("postgresql://alex:secret@db.internal:6543/flows")

    assert address == DatabaseAddress(host="db.internal", port="6543", dbname="flows", user="alex")


def test_the_port_probe_finds_a_port_nothing_listens_on_refuses(free_port: int):
    assert port_refuses("127.0.0.1", free_port)


def test_the_port_probe_finds_a_listening_port_does_not_refuse(silent_port: int):
    assert not port_refuses("127.0.0.1", silent_port)


@pytest.mark.database
def test_a_query_on_the_checks_connection_is_cancelled_after_2_s(database_url: str):
    with open_connection(database_url) as connection, pytest.raises(psycopg.errors.QueryCanceled):
        connection.execute("SELECT pg_sleep(3)")


@pytest.mark.database
def test_closing_the_checks_connection_sends_no_commit(database_url: str):
    with open_connection(database_url) as connection:
        assert connection.autocommit


@pytest.mark.database
def test_the_checks_connection_gives_up_on_a_peer_that_stops_acknowledging(database_url: str):
    with open_connection(database_url) as connection:
        assert connection.info.get_parameters()["tcp_user_timeout"] == "2000"


def test_any_other_driver_error_is_unreachable_with_its_first_line(monkeypatch: pytest.MonkeyPatch):
    def connect(*_args: object, **_kwargs: object) -> psycopg.Connection[tuple[object, ...]]:
        raise psycopg.InterfaceError("the driver broke\nmore detail")

    monkeypatch.setattr(psycopg, "connect", connect)

    check = check_database("postgresql://feather:feather@127.0.0.1:5442/feather")

    assert (check.problem, check.reason) == (Problem.UNREACHABLE, "the driver broke")


def test_a_timeout_on_a_port_that_refuses_is_reported_as_refused():
    """Windows' psycopg reports a refused port as a timeout.

    The probe corrects it on every system, whatever the driver says there.
    """
    url = "postgresql://feather:feather@127.0.0.1:5999/feather"
    timed_out = check_database_result(url, reason="timed out")

    check = diagnose_database(url, check=lambda _url: timed_out, probe=lambda _host, _port: True)

    assert check.reason == "connection refused"


def check_database_result(url: str, reason: str):
    from fcon_server.database import DatabaseCheck

    return DatabaseCheck(address=address_of(url), problem=Problem.UNREACHABLE, reason=reason, detail="")


# -- readiness: the encoding, the collation, the upgrades, the audit months --


def upgraded(url: str) -> str:
    upgrade(url, SystemClock())
    return url


def execute(url: str, text: str) -> None:
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(text.encode())


@pytest.mark.database
def test_the_check_finds_the_databases_encoding(database_url: str):
    assert check_database(database_url).encoding == "UTF8"


@pytest.mark.database
def test_the_check_finds_the_icu_collation(database_url: str):
    assert check_database(database_url).icu


@pytest.mark.database
def test_a_database_without_icu_collation_is_still_usable(database_url: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(database, "ICU_COLLATION", "no-such-collation")

    check = check_database(database_url)

    assert (check.icu, check.problem) == (False, None)


@pytest.mark.database
def test_a_database_not_in_utf8_is_not_ready(database_url: str):
    name = f"feather_test_{uuid.uuid4().hex[:8]}"
    execute(database_url, f"CREATE DATABASE {name} ENCODING 'SQL_ASCII' LC_COLLATE 'C' LC_CTYPE 'C' TEMPLATE template0")
    try:
        check = check_database(conninfo.make_conninfo(database_url, dbname=name))
    finally:
        execute(database_url, f"DROP DATABASE {name} WITH (FORCE)")

    assert (check.problem, check.encoding) == (Problem.NOT_UTF8, "SQL_ASCII")


@pytest.mark.database
def test_a_database_with_upgrades_waiting_is_behind(empty_database_url: str):
    check = check_database(empty_database_url)

    assert check.problem is Problem.BEHIND


@pytest.mark.database
def test_the_check_carries_the_upgrades_waiting(empty_database_url: str):
    check = check_database(empty_database_url)

    assert check.migrations is not None and check.migrations.waiting == tuple(
        path.name for path in sorted(MIGRATIONS.glob("*.sql"))
    )


@pytest.mark.database
def test_a_database_with_an_applied_upgrade_edited_is_changed(empty_database_url: str):
    url = upgraded(empty_database_url)
    execute(url, "UPDATE fcon.migration SET checksum = repeat('0', 64)")

    assert check_database(url).problem is Problem.CHANGED


@pytest.mark.database
def test_a_database_with_an_upgrade_from_a_newer_version_is_usable(empty_database_url: str):
    url = upgraded(empty_database_url)
    execute(
        url,
        "INSERT INTO fcon.migration (name, checksum, created_at, created_by)"
        " VALUES ('29991231T2359Z_newer.sql', repeat('0', 64), now(), 'system:migration')",
    )

    check = check_database(url)

    assert (check.problem, check.migrations and check.migrations.newer) == (None, ("29991231T2359Z_newer.sql",))


@pytest.mark.database
def test_an_upgraded_database_has_24_audit_months_ahead(database_url: str):
    assert check_database(database_url).months_ahead == 24


@pytest.mark.database
def test_a_database_with_no_audit_month_for_now_is_not_ready(database_url: str):
    past_the_last_month = FixedClock(first_of_month_after(datetime.now(UTC), months=25))

    assert check_database(database_url, clock=past_the_last_month).problem is Problem.AUDIT_MONTH_MISSING


@pytest.mark.database
def test_a_database_with_few_audit_months_ahead_is_not_short_of_audit_months(database_url: str):
    a_month_before_the_last = FixedClock(first_of_month_after(datetime.now(UTC), months=23))

    check = check_database(database_url, clock=a_month_before_the_last)

    # So far ahead, the record blocks' 90 days have run out first.
    assert (check.problem, check.months_ahead) == (Problem.RECORD_DAY_MISSING, 1)


def first_of_month_after(now: datetime, months: int) -> datetime:
    month = now.month - 1 + months
    return datetime(now.year + month // 12, month % 12 + 1, 1, 12, tzinfo=UTC)


@pytest.mark.database
def test_an_upgraded_database_has_90_record_block_days_ahead(database_url: str):
    assert check_database(database_url).days_ahead == 90


@pytest.mark.database
def test_a_database_with_no_record_block_day_for_today_is_not_ready(database_url: str):
    past_the_last_day = FixedClock(datetime.now(UTC) + timedelta(days=91))

    assert check_database(database_url, clock=past_the_last_day).problem is Problem.RECORD_DAY_MISSING


@pytest.mark.database
def test_a_database_with_few_record_block_days_ahead_is_still_usable(database_url: str):
    a_day_before_the_last = FixedClock(datetime.now(UTC) + timedelta(days=89))

    check = check_database(database_url, clock=a_day_before_the_last)

    assert (check.problem, check.days_ahead) == (None, 1)
