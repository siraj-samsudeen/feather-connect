"""The audit log refuses TRUNCATE whoever asks, the owner included (design
point 16), while an old month still leaves by detaching or dropping it. Each
test works in a transaction it rolls back, so the database stays as upgraded."""

from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from fcon_server.store.migrate import audit_months

pytestmark = pytest.mark.database

type Connection = psycopg.Connection[tuple[object, ...]]


@pytest.fixture
def owner(database_url: str) -> Iterator[Connection]:
    with psycopg.connect(database_url) as connection:
        yield connection
        connection.rollback()


def a_month() -> str:
    return f"fcon.audit_{audit_months(datetime.now(UTC))[0]:%Y_%m}"


def test_the_owner_cannot_empty_the_audit_log(owner: Connection):
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="never changed or deleted"):
        owner.execute("TRUNCATE fcon.audit")


def test_an_old_month_can_be_detached(owner: Connection):
    owner.execute(f"ALTER TABLE fcon.audit DETACH PARTITION {a_month()}".encode())


def test_an_old_month_can_be_dropped(owner: Connection):
    owner.execute(f"DROP TABLE {a_month()}".encode())
