"""The store's writes (design decision 1, points 7, 13 and 16).

`tx.insert` and `tx.update` fill the tenant, the who-and-when columns and the
row version, and write one audit record in the same transaction.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, LiteralString
from uuid import UUID

import psycopg
import pytest

from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.errors import (
    AlreadyExistsError,
    ChangedBySomeoneElseError,
    NotFoundError,
    StoreError,
    UnscopedQueryError,
)
from fcon_server.store.ids import new_id
from fcon_server.store.tables import Table
from fcon_server.store.transaction import ConnectionSource, Store

pytestmark = [pytest.mark.database, pytest.mark.usefixtures("test_tables")]

NOW = datetime.now(UTC).replace(microsecond=0)  # inside the audit log's months
FIXED_ID = UUID("01900000-0000-7000-8000-000000000001")

# Two tables of the shape every product table takes, a row that changes and a
# row only added, in the schema fcon_test: never fcon, whose tables are the
# product's own.
THING = Table("fcon_test.thing", key=("tenant_id", "id"), changes=True, secret=frozenset({"password"}))
NOTE = Table("fcon_test.note", key=("tenant_id", "id"), changes=False)

TEST_TABLES = """
    CREATE SCHEMA IF NOT EXISTS fcon_test;
    CREATE TABLE IF NOT EXISTS fcon_test.thing (
        tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
        id uuid NOT NULL,
        name text NOT NULL,
        password text,
        created_at timestamptz NOT NULL,
        created_by text NOT NULL,
        updated_at timestamptz NOT NULL,
        updated_by text NOT NULL,
        row_version bigint NOT NULL,
        PRIMARY KEY (tenant_id, id),
        CONSTRAINT thing_name UNIQUE (tenant_id, name) DEFERRABLE INITIALLY DEFERRED
    );
    CREATE TABLE IF NOT EXISTS fcon_test.note (
        tenant_id text COLLATE pg_c_utf8 NOT NULL REFERENCES fcon.tenant (tenant_id),
        id uuid NOT NULL,
        body text NOT NULL,
        created_at timestamptz NOT NULL,
        created_by text NOT NULL,
        PRIMARY KEY (tenant_id, id)
    );
"""


@dataclass(frozen=True)
class Thing:
    tenant_id: str
    id: UUID
    name: str
    created_at: datetime
    created_by: str
    updated_at: datetime
    updated_by: str
    row_version: int


@dataclass(frozen=True)
class Audit:
    created_at: datetime
    created_by: str
    request_id: str
    action: str
    row_key: str
    before: dict[str, Any] | None
    after: dict[str, Any]
    reason: str | None


THING_ROW = """
    SELECT tenant_id, id, name, created_at, created_by, updated_at, updated_by, row_version
    FROM fcon_test.thing WHERE tenant_id = %(tenant_id)s AND id = %(id)s
"""
AUDIT_ROWS = """
    SELECT created_at, created_by, request_id, action, row_key, before, after, reason
    FROM fcon.audit WHERE tenant_id = %(tenant_id)s AND table_name = %(table)s ORDER BY id
"""


@pytest.fixture(scope="module")
def test_tables(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(TEST_TABLES)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def fixed_store(store_source: ConnectionSource, clock: FixedClock) -> Store:
    """A store on the session's database with a clock the test moves."""
    return Store(store_source, clock, new_id)


def insert_thing(store: Store, context: Context, **values: object) -> UUID:
    with store.transaction(context) as tx:
        key = tx.insert(THING, {"name": "first", **values})
    assert isinstance(key["id"], UUID)
    return key["id"]


def read_thing(store: Store, context: Context, thing_id: UUID) -> Thing | None:
    with store.transaction(context) as tx:
        return tx.fetch_one(Thing, THING_ROW, {"id": thing_id})


def audits(store: Store, context: Context, table: str = "fcon_test.thing") -> list[Audit]:
    with store.transaction(context) as tx:
        return tx.fetch_all(Audit, AUDIT_ROWS, {"table": table})


def test_an_inserted_row_gets_the_contexts_tenant(fixed_store: Store, tenant: Context):
    thing = read_thing(fixed_store, tenant, insert_thing(fixed_store, tenant))

    assert thing is not None and thing.tenant_id == tenant.tenant_id


def test_an_inserted_row_gets_its_id_from_new_id(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    assert thing_id.version == 7 and read_thing(fixed_store, tenant, thing_id) is not None


def test_an_inserted_row_keeps_an_id_it_is_given(fixed_store: Store, tenant: Context):
    assert insert_thing(fixed_store, tenant, id=FIXED_ID) == FIXED_ID


def test_an_inserted_row_is_created_and_updated_by_the_actor_at_the_clocks_time(fixed_store: Store, tenant: Context):
    thing = read_thing(fixed_store, tenant, insert_thing(fixed_store, tenant))

    assert thing is not None
    assert (thing.created_at, thing.created_by, thing.updated_at, thing.updated_by) == (
        NOW,
        "system:test",
        NOW,
        "system:test",
    )


def test_an_inserted_row_starts_at_version_1(fixed_store: Store, tenant: Context):
    thing = read_thing(fixed_store, tenant, insert_thing(fixed_store, tenant))

    assert thing is not None and thing.row_version == 1


def test_a_row_only_added_gets_no_update_columns(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        key = tx.insert(NOTE, {"body": "hello"})

    assert set(key) == {"id"}


def test_an_insert_writes_an_audit_record(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    [audit] = audits(fixed_store, tenant)
    assert (audit.action, audit.row_key, audit.before, audit.after["name"]) == ("insert", str(thing_id), None, "first")


def test_an_audit_record_says_who_when_and_in_which_request(fixed_store: Store, tenant: Context):
    insert_thing(fixed_store, tenant)

    [audit] = audits(fixed_store, tenant)
    assert (audit.created_at, audit.created_by, audit.request_id) == (NOW, "system:test", tenant.request_id)


def test_an_audit_record_carries_the_contexts_reason(fixed_store: Store, tenant: Context):
    insert_thing(fixed_store, replace(tenant, reason="retried delivery 1001"))

    [audit] = audits(fixed_store, tenant)
    assert audit.reason == "retried delivery 1001"


def test_a_tenants_own_row_is_audited_under_its_id(store: Store, tenant: Context):
    [audit] = audits(store, tenant, "fcon.tenant")

    assert (audit.action, audit.row_key, audit.after["kind"]) == ("insert", tenant.tenant_id, "production")


def test_an_update_changes_the_row(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    thing = read_thing(fixed_store, tenant, thing_id)
    assert thing is not None and thing.name == "second"


def test_an_update_sets_the_next_row_version(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    with fixed_store.transaction(tenant) as tx:
        version = tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    thing = read_thing(fixed_store, tenant, thing_id)
    assert version == 2 and thing is not None and thing.row_version == 2


def test_an_update_is_by_the_actor_at_the_clocks_time(fixed_store: Store, tenant: Context, clock: FixedClock):
    thing_id = insert_thing(fixed_store, tenant)
    clock.at = NOW + timedelta(minutes=5)

    with fixed_store.transaction(replace(tenant, actor="user:someone")) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    thing = read_thing(fixed_store, tenant, thing_id)
    assert thing is not None
    assert (thing.created_at, thing.created_by, thing.updated_at, thing.updated_by) == (
        NOW,
        "system:test",
        NOW + timedelta(minutes=5),
        "user:someone",
    )


def test_an_update_writes_an_audit_record_with_the_values_before_and_after(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    audit = audits(fixed_store, tenant)[-1]
    assert audit.before is not None
    assert (audit.action, audit.row_key, audit.before["name"], audit.after["name"]) == (
        "update",
        str(thing_id),
        "first",
        "second",
    )


def test_an_update_at_an_old_version_is_changed_by_someone_else(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)
    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    with pytest.raises(ChangedBySomeoneElseError), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "third"}, row_version=1)


def test_an_update_at_an_old_version_changes_nothing(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)
    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    with pytest.raises(ChangedBySomeoneElseError), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "third"}, row_version=1)

    thing = read_thing(fixed_store, tenant, thing_id)
    assert thing is not None and (thing.name, thing.row_version) == ("second", 2)


def test_an_update_of_a_missing_row_is_not_found(fixed_store: Store, tenant: Context):
    with pytest.raises(NotFoundError), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": FIXED_ID}, {"name": "second"}, row_version=1)


def test_a_row_only_added_is_never_updated(fixed_store: Store, tenant: Context):
    with pytest.raises(ValueError, match="only added"), fixed_store.transaction(tenant) as tx:
        tx.update(NOTE, {"id": FIXED_ID}, {"body": "changed"}, row_version=1)


def test_a_secret_written_is_audited_as_changed(fixed_store: Store, tenant: Context):
    insert_thing(fixed_store, tenant, password="hunter2")

    [audit] = audits(fixed_store, tenant)
    assert audit.after["password"] == "(secret changed)"


def test_a_secret_changed_is_audited_as_changed_before_and_after(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant, password="hunter2")

    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"password": "hunter3"}, row_version=1)

    audit = audits(fixed_store, tenant)[-1]
    assert audit.before is not None
    assert (audit.before["password"], audit.after["password"]) == ("(secret changed)", "(secret changed)")


def test_a_secret_left_as_it_was_is_left_out_of_the_audit(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant, password="hunter2")

    with fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "second"}, row_version=1)

    audit = audits(fixed_store, tenant)[-1]
    assert audit.before is not None
    assert "password" not in audit.before and "password" not in audit.after


def test_a_change_and_its_audit_record_roll_back_together(fixed_store: Store, tenant: Context):
    with pytest.raises(LookupError), fixed_store.transaction(tenant) as tx:
        tx.insert(THING, {"name": "first"})
        raise LookupError

    assert audits(fixed_store, tenant) == []


def test_a_unique_rule_broken_at_commit_already_exists(fixed_store: Store, tenant: Context):
    with pytest.raises(AlreadyExistsError), fixed_store.transaction(tenant) as tx:
        tx.insert(THING, {"name": "same"})
        tx.insert(THING, {"name": "same"})  # the name's rule is checked at commit


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE fcon.audit SET reason = 'x' WHERE tenant_id = %(tenant_id)s",
        "DELETE FROM fcon.audit WHERE tenant_id = %(tenant_id)s",
    ],
    ids=["update", "delete"],
)
def test_the_store_cannot_change_an_audit_record(fixed_store: Store, tenant: Context, change: LiteralString):
    insert_thing(fixed_store, tenant)

    with pytest.raises(StoreError), fixed_store.transaction(tenant) as tx:
        tx.execute(change)

    assert len(audits(fixed_store, tenant)) == 1


def test_another_tenant_cannot_read_a_tenants_row(
    fixed_store: Store, tenant: Context, new_tenant: Callable[[], Context]
):
    thing_id = insert_thing(fixed_store, tenant)

    assert read_thing(fixed_store, new_tenant(), thing_id) is None


def test_another_tenant_cannot_update_a_tenants_row(
    fixed_store: Store, tenant: Context, new_tenant: Callable[[], Context]
):
    thing_id = insert_thing(fixed_store, tenant)

    with pytest.raises(NotFoundError), fixed_store.transaction(new_tenant()) as tx:
        tx.update(THING, {"id": thing_id}, {"name": "taken"}, row_version=1)

    thing = read_thing(fixed_store, tenant, thing_id)
    assert thing is not None and thing.name == "first"


def test_another_tenant_cannot_read_a_tenants_audit_records(
    fixed_store: Store, tenant: Context, new_tenant: Callable[[], Context]
):
    insert_thing(fixed_store, tenant)

    assert audits(fixed_store, new_tenant()) == []


FILLED_BY_THE_STORE = ["created_at", "created_by", "updated_at", "updated_by", "row_version"]


def test_an_insert_never_takes_the_tenant_from_the_callers_values(fixed_store: Store, tenant: Context):
    with pytest.raises(UnscopedQueryError), fixed_store.transaction(tenant) as tx:
        tx.insert(THING, {"name": "first", "tenant_id": "default"})


@pytest.mark.parametrize("column", FILLED_BY_THE_STORE)
def test_an_insert_refuses_a_column_the_store_fills(fixed_store: Store, tenant: Context, column: str):
    with pytest.raises(ValueError, match=column), fixed_store.transaction(tenant) as tx:
        tx.insert(THING, {"name": "first", column: "caller"})


def test_an_update_never_moves_a_row_to_another_tenant(fixed_store: Store, tenant: Context):
    thing_id = insert_thing(fixed_store, tenant)

    with pytest.raises(UnscopedQueryError), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {"tenant_id": "default"}, row_version=1)


def test_an_update_never_takes_the_tenant_from_the_callers_key(fixed_store: Store, tenant: Context):
    with pytest.raises(UnscopedQueryError), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": FIXED_ID, "tenant_id": "default"}, {"name": "second"}, row_version=1)


@pytest.mark.parametrize("column", FILLED_BY_THE_STORE)
def test_an_update_refuses_a_column_the_store_fills(fixed_store: Store, tenant: Context, column: str):
    thing_id = insert_thing(fixed_store, tenant)

    with pytest.raises(ValueError, match=column), fixed_store.transaction(tenant) as tx:
        tx.update(THING, {"id": thing_id}, {column: "caller"}, row_version=1)


# -- a row that must go in once, and a change refused for a rule ----------------


def test_a_row_added_if_absent_goes_in_with_its_audit_record(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        key = tx.insert_if_absent(NOTE, {"id": FIXED_ID, "body": "hello"})

    [audit] = audits(fixed_store, tenant, "fcon_test.note")
    assert (key, audit.action, audit.row_key) == ({"id": FIXED_ID}, "insert", str(FIXED_ID))


def test_a_row_added_if_absent_when_one_is_there_gives_nothing(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        tx.insert(NOTE, {"id": FIXED_ID, "body": "hello"})

    with fixed_store.transaction(tenant) as tx:
        key = tx.insert_if_absent(NOTE, {"id": FIXED_ID, "body": "again"})

    assert (key, len(audits(fixed_store, tenant, "fcon_test.note"))) == (None, 1)


def test_a_refusal_writes_a_refused_audit_record_with_its_reason(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        tx.refuse(THING, str(FIXED_ID), "the form's token is not the session's")

    [audit] = audits(fixed_store, tenant)
    assert (audit.action, audit.row_key, audit.reason, audit.created_by, audit.request_id) == (
        "refused",
        str(FIXED_ID),
        "the form's token is not the session's",
        "system:test",
        tenant.request_id,
    )


def test_a_refusal_changes_no_row(fixed_store: Store, tenant: Context):
    with fixed_store.transaction(tenant) as tx:
        tx.refuse(THING, str(FIXED_ID), "a rule")

    [audit] = audits(fixed_store, tenant)
    assert (audit.before, audit.after) == (None, None)
