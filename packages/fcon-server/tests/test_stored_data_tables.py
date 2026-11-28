"""The stored data's tables keep their own rules (stored-versions, design § Tables, decisions 2, 4 and 5).

The keys, the who-and-when columns and the tenant-first indexes are checked for every table by
`test_tables`; these are the rules particular to these tables.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import psycopg
import pytest
from psycopg.types.json import Jsonb

from fcon_server.store.context import Context
from fcon_server.store.errors import AlreadyExistsError, StoreError
from fcon_server.store.ids import new_id
from fcon_server.store.tables import PARTITION, RECORD_BLOCK, VERSION
from fcon_server.store.transaction import Store

pytestmark = pytest.mark.database


@dataclass(frozen=True)
class Day:
    name: str


def broken_rule(error: StoreError) -> str | None:
    cause = error.__cause__
    return cause.diag.constraint_name if isinstance(cause, psycopg.Error) else None


def query(url: str, text: bytes, params: list[object]) -> list[tuple[object, ...]]:
    with psycopg.connect(url) as connection:
        return connection.execute(text, params).fetchall()


def a_partition(store: Store, tenant: Context) -> UUID:
    with store.transaction(tenant) as tx:
        key = tx.insert(PARTITION, {"dataset_id": new_id(), "values": Jsonb({}), "values_key": "{}"})
    assert isinstance(key["id"], UUID)
    return key["id"]


def a_version(partition_id: UUID, **values: object) -> dict[str, object]:
    return {
        "dataset_id": new_id(),
        "partition_id": partition_id,
        "read_id": new_id(),
        "kind": "complete",
        "state": "open",
        "read_started_at": datetime.now(UTC),
        **values,
    }


def test_record_state_keeps_half_of_each_page_free(database_url: str):
    rows = query(database_url, b"SELECT reloptions FROM pg_class WHERE oid = 'fcon.record_state'::regclass", [])

    assert rows == [(["fillfactor=50"],)]


def test_no_index_covers_the_last_changed_version(database_url: str):
    """So a seal's update of record state stays HOT (decision 2)."""
    rows = query(
        database_url,
        b"SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)"
        b" WHERE i.indrelid = 'fcon.record_state'::regclass AND a.attname = 'changed_version_id'",
        [],
    )

    assert rows == [(0,)]


def test_no_foreign_key_checks_the_last_changed_version(database_url: str):
    rows = query(
        database_url,
        b"SELECT count(*) FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)"
        b" WHERE c.conrelid = 'fcon.record_state'::regclass AND c.contype = 'f' AND a.attname = 'changed_version_id'",
        [],
    )

    assert rows == [(0,)]


def test_record_blocks_are_split_by_their_time_made(database_url: str):
    rows = query(
        database_url,
        b"SELECT pg_get_partkeydef('fcon.record_block'::regclass)",
        [],
    )

    assert rows == [("RANGE (created_at)",)]


def test_a_partition_holds_one_open_version_at_a_time(store: Store, tenant: Context):
    partition_id = a_partition(store, tenant)
    with store.transaction(tenant) as tx:
        tx.insert(VERSION, a_version(partition_id))

    with pytest.raises(AlreadyExistsError), store.transaction(tenant) as tx:
        tx.insert(VERSION, a_version(partition_id))


def test_a_sealed_version_has_its_number(store: Store, tenant: Context):
    partition_id = a_partition(store, tenant)

    with pytest.raises(StoreError) as refused, store.transaction(tenant) as tx:
        tx.insert(VERSION, a_version(partition_id, state="sealed", commit_number=1))

    assert broken_rule(refused.value) == "version_sealed_numbered"


def test_two_versions_of_a_partition_never_share_a_number(store: Store, tenant: Context):
    partition_id = a_partition(store, tenant)
    sealed = {"state": "sealed", "number": 1, "commit_number": 1}
    with store.transaction(tenant) as tx:
        tx.insert(VERSION, a_version(partition_id, **sealed))

    with pytest.raises(AlreadyExistsError), store.transaction(tenant) as tx:
        tx.insert(VERSION, a_version(partition_id, **sealed))


def test_a_block_kept_in_the_database_has_its_data(store: Store, tenant: Context):
    partition_id = a_partition(store, tenant)
    with store.transaction(tenant) as tx:
        version = tx.insert(VERSION, a_version(partition_id))

    with pytest.raises(StoreError) as refused, store.transaction(tenant) as tx:
        tx.insert(RECORD_BLOCK, {"version_id": version["id"], "number": 1, "kind": "records", "row_count": 0})

    assert broken_rule(refused.value) == "record_block_data_here"


def test_a_block_made_today_goes_in_todays_partition(store: Store, tenant: Context):
    partition_id = a_partition(store, tenant)
    with store.transaction(tenant) as tx:
        version = tx.insert(VERSION, a_version(partition_id))
        block = {"version_id": version["id"], "number": 1, "kind": "records", "row_count": 0, "data": b"x"}
        tx.insert(RECORD_BLOCK, block)
        where = tx.fetch_one(
            Day, "SELECT tableoid::regclass::text AS name FROM fcon.record_block WHERE tenant_id = %(tenant_id)s"
        )

    assert where == Day(f"fcon.record_block_{datetime.now(UTC):%Y%m%d}")
