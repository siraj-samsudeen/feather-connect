"""The store's connections (design point 14): psycopg's pool, the same number kept open at all times.

Each is replaced after 30 minutes and checked before it is handed out, so one the database
dropped is replaced. Every connection starts with the product's limits and names itself.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

DEFAULT_SIZE = 5
MAX_LIFETIME = 30 * 60  # seconds
APPLICATION_NAME = "fcon-server"
OPTIONS = "-c statement_timeout=30s -c lock_timeout=5s -c idle_in_transaction_session_timeout=60s -c TimeZone=UTC"

type Pool = ConnectionPool[psycopg.Connection[Any]]


def make_pool(url: str, size: int = DEFAULT_SIZE, *, prepare: bool = True) -> Pool:
    """Makes the server's pool of `size` connections to `url`, not open yet.

    The server opens it when it starts, without waiting for the database. `prepare=False` turns
    prepared statements off, for a connection pooler in front of Postgres.
    """
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


class OneConnectionEach:
    """A new connection for each transaction, with the pool's limits.

    For a command that runs a few transactions and ends (`fcon users`).
    """

    def __init__(self, url: str, application_name: str) -> None:
        self._url = url
        self._application_name = application_name

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection[Any]]:
        """Opens a new connection with the product's limits, closed when the block ends."""
        with psycopg.connect(self._url, options=OPTIONS, application_name=self._application_name) as connection:
            yield connection
