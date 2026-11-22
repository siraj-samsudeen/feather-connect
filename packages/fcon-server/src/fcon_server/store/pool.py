"""The store's connections (design point 14): psycopg's pool, the same
number kept open at all times, each replaced after 30 minutes and checked
before it is handed out, so one the database dropped is replaced. Every
connection starts with the product's limits and names itself."""

from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

DEFAULT_SIZE = 5
MAX_LIFETIME = 30 * 60  # seconds
APPLICATION_NAME = "fcon-server"
OPTIONS = "-c statement_timeout=30s -c lock_timeout=5s -c idle_in_transaction_session_timeout=60s -c TimeZone=UTC"

type Pool = ConnectionPool[psycopg.Connection[Any]]


def make_pool(url: str, size: int = DEFAULT_SIZE, *, prepare: bool = True) -> Pool:
    """Not open yet: the server opens it when it starts, without waiting for
    the database. `prepare=False` turns prepared statements off, for a
    connection pooler in front of Postgres."""
    kwargs: dict[str, Any] = {"options": OPTIONS, "application_name": APPLICATION_NAME}
    if not prepare:
        kwargs["prepare_threshold"] = None
    return ConnectionPool(
        url,
        min_size=size,
        max_size=size,
        max_lifetime=MAX_LIFETIME,
        kwargs=kwargs,
        check=ConnectionPool.check_connection,
        open=False,
    )
