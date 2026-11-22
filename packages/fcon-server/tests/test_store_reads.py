"""The store's reads (design decision 1): plain SQL, the tenant bound from the
context, results as frozen dataclasses, and SQL that forgets the tenant refused."""

import dataclasses
from dataclasses import dataclass
from typing import LiteralString

import pytest

from fcon_server.store.context import Context
from fcon_server.store.errors import UnscopedQueryError
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import Store

pytestmark = pytest.mark.database


@dataclass(frozen=True)
class Kind:
    kind: str


@dataclass(frozen=True)
class Name:
    name: str


def test_an_id_is_a_uuid_of_version_7():
    assert new_id().version == 7


def test_ids_are_made_in_time_order():
    first = new_id()

    assert new_id() > first


def test_a_context_never_changes():
    context = Context(tenant_id="default", actor="system:test", request_id="request-1")

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.tenant_id = "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_a_context_has_no_reason_unless_given():
    assert Context(tenant_id="default", actor="system:test", request_id="request-1").reason is None


def test_a_read_finds_the_row_of_the_contexts_tenant(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        row = tx.fetch_one(Kind, "SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s")

    assert row == Kind("production")


def test_a_read_that_finds_nothing_gives_none(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        row = tx.fetch_one(
            Kind,
            "SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s AND kind = %(kind)s",
            {"kind": "sandbox"},
        )

    assert row is None


def test_a_read_of_many_rows_gives_each_as_a_frozen_dataclass(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        rows = tx.fetch_all(Kind, "SELECT kind FROM fcon.tenant t WHERE t.tenant_id = %(tenant_id)s")

    assert rows == [Kind("production")]


def test_the_record_of_upgrades_has_no_tenant_to_scope(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        rows = tx.fetch_all(Name, "SELECT name FROM fcon.migration")

    assert rows


@pytest.mark.parametrize(
    "query",
    [
        "SELECT kind FROM fcon.tenant",
        "SELECT kind FROM fcon.tenant WHERE tenant_id = 'default'",
        (
            "SELECT t.kind FROM fcon.tenant t JOIN fcon.audit a ON a.tenant_id = t.tenant_id"
            " WHERE t.tenant_id = %(tenant_id)s"
        ),
        "SELECT kind FROM fcon.tenant -- WHERE tenant_id = %(tenant_id)s",
        "SELECT kind FROM fcon.tenant /* WHERE tenant_id = %(tenant_id)s */",
        "SELECT kind FROM fcon.tenant WHERE kind <> 'tenant_id = %(tenant_id)s'",
        'SELECT kind FROM "fcon"."tenant"',
        "SELECT kind FROM FCON.Tenant",
        "SELECT kind FROM fcon . tenant",
    ],
    ids=[
        "no-tenant",
        "tenant-written-in",
        "one-table-of-a-join",
        "predicate-in-a-line-comment",
        "predicate-in-a-block-comment",
        "predicate-in-a-literal",
        "quoted-names",
        "upper-case-names",
        "spaced-names",
    ],
)
def test_a_read_that_forgets_the_tenant_is_refused(store: Store, tenant: Context, query: LiteralString):
    with store.transaction(tenant) as tx, pytest.raises(UnscopedQueryError):
        tx.fetch_all(Kind, query)


def test_a_table_named_in_a_literal_needs_no_tenant(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        row = tx.fetch_one(
            Kind,
            "SELECT current_setting('fcon.now', true) AS kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s",
        )

    assert row is not None


def test_a_statement_that_forgets_the_tenant_is_refused(store: Store, tenant: Context):
    with store.transaction(tenant) as tx, pytest.raises(UnscopedQueryError):
        tx.execute("UPDATE fcon.tenant SET kind = 'sandbox'")


def test_the_tenant_is_never_taken_from_the_callers_values(store: Store, tenant: Context):
    with store.transaction(tenant) as tx, pytest.raises(UnscopedQueryError):
        tx.fetch_one(Kind, "SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s", {"tenant_id": "default"})


def test_a_transaction_commits_its_statements(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        tx.execute("UPDATE fcon.tenant SET kind = 'sandbox' WHERE tenant_id = %(tenant_id)s")

    with store.transaction(tenant) as tx:
        assert tx.fetch_one(Kind, "SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s") == Kind("sandbox")


def test_a_transaction_left_by_an_error_changes_nothing(store: Store, tenant: Context):
    with pytest.raises(LookupError), store.transaction(tenant) as tx:
        tx.execute("UPDATE fcon.tenant SET kind = 'sandbox' WHERE tenant_id = %(tenant_id)s")
        raise LookupError

    with store.transaction(tenant) as tx:
        assert tx.fetch_one(Kind, "SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s") == Kind("production")
