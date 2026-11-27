"""Each table description matches the table the migrations made (design § The store).

Every product table is described.
"""

import psycopg
import pytest

from fcon_server.store.tables import TABLES, Table

pytestmark = pytest.mark.database

WHO_AND_WHEN = {"tenant_id", "created_at", "created_by"}
CHANGES = {"updated_at", "updated_by", "row_version"}
NOT_DESCRIBED = {"fcon.migration", "fcon.audit"}  # written by the runner and by the store itself


def query(url: str, text: bytes, params: list[object]) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as connection:
        return connection.execute(text, params).fetchall()


def columns(url: str, table: Table) -> set[str]:
    schema, name = table.name.split(".")
    rows = query(
        url,
        b"SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
        [schema, name],
    )
    return {str(column) for (column,) in rows}


def primary_key(url: str, table: Table) -> tuple[str, ...]:
    rows = query(
        url,
        b"SELECT a.attname FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum, n)"
        b" JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum"
        b" WHERE i.indrelid = %s::regclass AND i.indisprimary ORDER BY k.n",
        [table.name],
    )
    return tuple(str(column) for (column,) in rows)


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_a_described_key_is_the_tables_primary_key(database_url: str, table: Table):
    assert primary_key(database_url, table) == table.key


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_a_described_table_has_the_tenant_and_who_made_it(database_url: str, table: Table):
    assert WHO_AND_WHEN <= columns(database_url, table)


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_a_described_table_has_the_update_columns_when_its_rows_change(database_url: str, table: Table):
    assert (CHANGES <= columns(database_url, table)) == table.changes


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_a_described_secret_is_a_column_of_the_table(database_url: str, table: Table):
    assert table.secret <= columns(database_url, table)


def looks_secret(column: str) -> bool:
    return column == "password" or column.endswith(("_hash", "_token", "_secret"))


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_every_column_that_holds_a_secret_is_described_as_one(database_url: str, table: Table):
    """So the audit log never shows it: the store leaves a secret's value out."""
    assert {column for column in columns(database_url, table) if looks_secret(column)} == table.secret


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_every_index_starts_with_the_tenant(database_url: str, table: Table):
    rows = query(
        database_url,
        b"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]"
        b" WHERE i.indrelid = %s::regclass",
        [table.name],
    )

    assert rows and {str(column) for (column,) in rows} == {"tenant_id"}


def test_every_product_table_is_described(database_url: str):
    rows = query(
        database_url,
        b"SELECT 'fcon.' || relname FROM pg_class WHERE relnamespace = 'fcon'::regnamespace"
        b" AND relkind IN ('r', 'p') AND NOT relispartition",
        [],
    )

    assert {str(name) for (name,) in rows} - NOT_DESCRIBED == {table.name for table in TABLES}
