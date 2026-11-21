"""Fixtures every package's tests share.

`database_url`: a throwaway database, made once per test session on the
Postgres server FEATHER_DATABASE_URL names (from the environment, else from
.env at the repo root) and dropped at the end. A test that needs it carries
the `database` mark. With no database running it fails, and says how to start
one: it never skips.
"""

import os
import socket
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import conninfo, sql

from feather_cli.settings import ENV_FILE, read_env_file

REPO_ROOT = Path(__file__).resolve().parent
START_IT = "start the database: docker compose up -d"


def _server_url() -> str:
    variables = {**read_env_file(REPO_ROOT / ENV_FILE), **os.environ}
    if url := variables.get("FEATHER_DATABASE_URL"):
        return url
    pytest.fail("FEATHER_DATABASE_URL is not set (environment or .env); " + START_IT, pytrace=False)


def _admin(url: str) -> psycopg.Connection[tuple[object, ...]]:
    try:
        return psycopg.connect(url, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as err:
        first_line = str(err).splitlines()[0] if str(err) else type(err).__name__
        pytest.fail(f"cannot reach the test database server ({first_line}).\n{START_IT}", pytrace=False)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """The address of this session's own empty database."""
    server_url = _server_url()
    name = f"feather_test_{uuid.uuid4().hex[:8]}"
    with _admin(server_url) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield conninfo.make_conninfo(server_url, dbname=name)
    finally:
        with _admin(server_url) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def free_port() -> int:
    """A port on 127.0.0.1 that nothing listens on right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def silent_port() -> Iterator[int]:
    """A port on 127.0.0.1 that takes connections and never says a word."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        yield listener.getsockname()[1]
