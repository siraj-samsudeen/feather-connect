"""The first migration's tables, on the session's upgraded database.

Each test works in a transaction it rolls back, so the database stays as
upgraded.
"""

from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest

pytestmark = pytest.mark.database

AUDIT_ROW = """
    INSERT INTO fcon.audit (tenant_id, id, created_at, created_by, request_id, table_name, action, row_key)
    VALUES ('default', %s, '2026-11-21T17:30:00Z', 'system:migration', 'request-1', 'fcon.tenant', 'insert', 'x')
"""


@pytest.fixture
def connection(database_url: str) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    with psycopg.connect(database_url) as connection:
        yield connection
        connection.rollback()


def test_the_default_tenant_is_a_production_tenant(connection: psycopg.Connection[tuple[object, ...]]):
    rows = connection.execute(
        "SELECT kind, made_from, created_by, row_version FROM fcon.tenant WHERE tenant_id = 'default'"
    ).fetchall()

    assert rows == [("production", None, "system:migration", 1)]


@pytest.mark.parametrize("tenant_id", ["Default", "7-up", "test_7f3a2c", "", "a" * 41], ids=repr)
def test_a_tenant_id_outside_the_rule_is_refused(connection: psycopg.Connection[tuple[object, ...]], tenant_id: str):
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute(
            "INSERT INTO fcon.tenant VALUES (%s, 'production', NULL, now(), 'x', now(), 'x', 1)", [tenant_id]
        )


@pytest.mark.parametrize("tenant_id", ["test-7f3a2c", "a", "a" * 40], ids=repr)
def test_a_tenant_id_inside_the_rule_is_taken(connection: psycopg.Connection[tuple[object, ...]], tenant_id: str):
    connection.execute(
        "INSERT INTO fcon.tenant VALUES (%s, 'sandbox', 'default', now(), 'x', now(), 'x', 1)", [tenant_id]
    )


def test_a_tenant_of_another_kind_is_refused(connection: psycopg.Connection[tuple[object, ...]]):
    with pytest.raises(psycopg.errors.CheckViolation):
        connection.execute("INSERT INTO fcon.tenant VALUES ('other', 'trial', NULL, now(), 'x', now(), 'x', 1)")


def test_an_audit_record_can_be_added(connection: psycopg.Connection[tuple[object, ...]]):
    connection.execute(AUDIT_ROW, [uuid4()])


@pytest.mark.parametrize("change", ["UPDATE fcon.audit SET reason = 'x'", "DELETE FROM fcon.audit"])
def test_an_audit_record_is_never_changed(connection: psycopg.Connection[tuple[object, ...]], change: str):
    connection.execute(AUDIT_ROW, [uuid4()])

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        connection.execute(change.encode())


def test_the_audit_key_is_tenant_id_and_time(connection: psycopg.Connection[tuple[object, ...]]):
    row = connection.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'fcon.audit'::regclass AND contype = 'p'"
    ).fetchone()

    assert row == ("PRIMARY KEY (tenant_id, id, created_at)",)


def test_every_index_of_the_audit_log_starts_with_the_tenant(connection: psycopg.Connection[tuple[object, ...]]):
    rows = connection.execute(
        "SELECT indexdef FROM pg_indexes WHERE schemaname = 'fcon' AND tablename = 'audit'"
    ).fetchall()

    assert rows and all("(tenant_id," in str(definition) for (definition,) in rows)


def test_the_audit_log_has_no_default_partition(connection: psycopg.Connection[tuple[object, ...]]):
    row = connection.execute(
        "SELECT partdefid FROM pg_partitioned_table WHERE partrelid = 'fcon.audit'::regclass"
    ).fetchone()

    assert row == (0,)


def test_every_text_key_compares_by_character_code(connection: psycopg.Connection[tuple[object, ...]]):
    rows = connection.execute("""
        SELECT table_name || '.' || column_name, collation_name FROM information_schema.columns
        WHERE table_schema = 'fcon' AND column_name IN ('name', 'tenant_id', 'made_from', 'table_name', 'row_key')
        AND table_name IN ('migration', 'tenant', 'audit') ORDER BY 1
    """).fetchall()

    assert rows == [
        ("audit.row_key", "pg_c_utf8"),
        ("audit.table_name", "pg_c_utf8"),
        ("audit.tenant_id", "pg_c_utf8"),
        ("migration.name", "pg_c_utf8"),
        ("tenant.made_from", "pg_c_utf8"),
        ("tenant.tenant_id", "pg_c_utf8"),
    ]
