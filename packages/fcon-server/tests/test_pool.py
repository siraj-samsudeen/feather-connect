"""The store's connection pool (design point 14): opened when the server
starts, without waiting for the database, and closed when it stops."""

import time
from dataclasses import dataclass

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fcon_server.app import build_app
from fcon_server.store.context import Context
from fcon_server.store.transaction import Store

STARTS_WITHIN_S = 2


@dataclass(frozen=True)
class Setting:
    value: str


def setting_of(app: FastAPI, context: Context, name: str) -> str:
    store: Store = app.state.store
    with store.transaction(context) as tx:
        row = tx.fetch_one(Setting, "SELECT current_setting(%(name)s) AS value", {"name": name})
    assert row is not None
    return row.value


@pytest.mark.database
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("statement_timeout", "30s"),
        ("lock_timeout", "5s"),
        ("idle_in_transaction_session_timeout", "1min"),
        ("TimeZone", "UTC"),
        ("application_name", "fcon-server"),
    ],
)
def test_each_connection_of_the_store_starts_with_the_products_settings(
    database_url: str, tenant: Context, name: str, value: str
):
    app = build_app(database_url)

    with TestClient(app):
        assert setting_of(app, tenant, name) == value


def test_the_pool_keeps_5_connections_by_default():
    pool = build_app("postgresql://unused").state.pool

    assert (pool.min_size, pool.max_size) == (5, 5)


def test_the_pool_keeps_the_number_of_connections_it_is_given():
    pool = build_app("postgresql://unused", pool_size=12).state.pool

    assert (pool.min_size, pool.max_size) == (12, 12)


def test_each_connection_is_replaced_after_30_minutes():
    assert build_app("postgresql://unused").state.pool.max_lifetime == 30 * 60


@pytest.mark.database
def test_prepared_statements_are_used_by_default(database_url: str):
    app = build_app(database_url)

    with TestClient(app), app.state.pool.connection() as connection:
        assert connection.prepare_threshold == 5


@pytest.mark.database
def test_prepared_statements_can_be_turned_off(database_url: str):
    app = build_app(database_url, prepare=False)

    with TestClient(app), app.state.pool.connection() as connection:
        assert connection.prepare_threshold is None


def test_the_server_starts_without_waiting_for_the_database(free_port: int):
    """On Windows a refused connection takes seconds, so stopping takes a
    while here: the pool's workers finish their attempts first."""
    app = build_app(f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")
    started = time.monotonic()

    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert time.monotonic() - started < STARTS_WITHIN_S


@pytest.mark.database
def test_the_pool_is_closed_when_the_server_stops(database_url: str):
    app = build_app(database_url)

    with TestClient(app):
        pass

    assert app.state.pool.closed


@pytest.mark.database
def test_a_connection_lost_while_idle_is_replaced_before_use(database_url: str, tenant: Context):
    app = build_app(database_url, pool_size=1)

    with TestClient(app):
        with app.state.pool.connection() as connection:
            lost = connection.info.backend_pid
        with psycopg.connect(database_url, autocommit=True) as other:
            other.execute("SELECT pg_terminate_backend(%s)", [lost])

        assert setting_of(app, tenant, "application_name") == "fcon-server"
