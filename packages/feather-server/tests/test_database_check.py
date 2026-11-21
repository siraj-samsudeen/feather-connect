"""The database check: usable, or which problem, against a real Postgres 18."""

import psycopg
import pytest
from psycopg import conninfo

from feather_server.database import DatabaseAddress, Problem, address_of, check_database, diagnose_database, open_connection, port_refuses


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
