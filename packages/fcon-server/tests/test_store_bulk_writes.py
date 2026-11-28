"""The store's helpers for set-based bulk writes (ADR 0022, stored-versions design decision 3).

`tx.stamp()` gives the who-and-when values from the context and the clock; `tx.copy_rows` puts
rows in a temporary table, each with the context's tenant. The SQL that writes from it still
goes through the tenant-scope check.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytest

from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.errors import StoreError, UnscopedQueryError
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import ConnectionSource, Store

pytestmark = pytest.mark.database

NOW = datetime.now(UTC).replace(microsecond=0)
ROWS = "CREATE TEMPORARY TABLE progress_rows (tenant_id text, dataset_id uuid) ON COMMIT DROP"
WRITE = """
    INSERT INTO fcon.dataset_progress
        (tenant_id, dataset_id, created_at, created_by, updated_at, updated_by, row_version)
    SELECT r.tenant_id, r.dataset_id, %(stamped_at)s, %(stamped_by)s, %(stamped_at)s, %(stamped_by)s, 1
    FROM pg_temp.progress_rows r WHERE r.tenant_id = %(tenant_id)s
"""
UNSCOPED_WRITE = """
    INSERT INTO fcon.dataset_progress
        (tenant_id, dataset_id, created_at, created_by, updated_at, updated_by, row_version)
    SELECT r.tenant_id, r.dataset_id, %(stamped_at)s, %(stamped_by)s, %(stamped_at)s, %(stamped_by)s, 1
    FROM pg_temp.progress_rows r
"""


@dataclass(frozen=True)
class Copied:
    tenant_id: str
    dataset_id: UUID


@dataclass(frozen=True)
class Progress:
    dataset_id: UUID
    created_at: datetime
    created_by: str


@pytest.fixture
def fixed_store(store_source: ConnectionSource) -> Store:
    return Store(store_source, FixedClock(NOW), new_id)


def test_a_stamp_gives_the_clocks_time_and_the_contexts_actor(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        stamp = tx.stamp()

    assert stamp == {"stamped_at": NOW, "stamped_by": tenant.actor}


def test_copied_rows_carry_the_contexts_tenant(fixed_store: Store, tenant: Context):
    dataset_id = new_id()
    with fixed_store.transaction(tenant) as tx:
        tx.execute(ROWS)
        tx.copy_rows("progress_rows", ["dataset_id"], [[dataset_id]])
        copied = tx.fetch_all(Copied, "SELECT tenant_id, dataset_id FROM pg_temp.progress_rows")

    assert copied == [Copied(tenant.tenant_id, dataset_id)]


def test_a_set_based_write_from_copied_rows_is_stamped(fixed_store: Store, tenant: Context):
    first, second = new_id(), new_id()
    with fixed_store.transaction(tenant) as tx:
        tx.execute(ROWS)
        tx.copy_rows("progress_rows", ["dataset_id"], [[first], [second]])
        tx.execute(WRITE, tx.stamp())
        written = tx.fetch_all(
            Progress,
            "SELECT dataset_id, created_at, created_by FROM fcon.dataset_progress"
            " WHERE tenant_id = %(tenant_id)s ORDER BY dataset_id",
        )

    assert written == [Progress(dataset_id, NOW, tenant.actor) for dataset_id in sorted([first, second])]


def test_a_set_based_write_that_does_not_scope_the_tenant_is_refused(fixed_store: Store, tenant: Context):
    with pytest.raises(UnscopedQueryError), fixed_store.transaction(tenant) as tx:
        tx.execute(ROWS)
        tx.execute(UNSCOPED_WRITE, tx.stamp())


def test_copying_into_a_table_that_is_not_there_is_the_stores_error(fixed_store: Store, tenant: Context):
    with pytest.raises(StoreError), fixed_store.transaction(tenant) as tx:
        tx.copy_rows("no_such_rows", ["dataset_id"], [[new_id()]])
