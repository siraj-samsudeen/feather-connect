"""Rights are checked in one place (design point 2, ADR 0016).

A table maps each action to the least role it needs, and a refusal is audited.
"""

from dataclasses import replace

import psycopg
import pytest

from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.rights import RIGHTS, Action, Caller, NotAllowedError, Role, require

CONTEXT = Context(tenant_id="default", actor="user:1", request_id="r-1")
# An allowed action never reaches the database.
NO_DATABASE = Store(
    OneConnectionEach("postgresql://nobody:secret@127.0.0.1:9/nowhere", "fcon-test"), SystemClock(), new_id
)


def test_the_roles_rise_from_viewer_to_administrator():
    assert sorted(Role, key=lambda role: role.rank) == [
        Role.VIEWER,
        Role.OPERATOR,
        Role.DEVELOPER,
        Role.ADMINISTRATOR,
    ]


def test_every_action_names_the_least_role_it_needs():
    assert set(RIGHTS) == set(Action)


def test_a_role_at_the_least_one_is_allowed():
    require(NO_DATABASE, Caller(CONTEXT, Role.VIEWER), Action.SEE_OVERVIEW)


def test_a_higher_role_is_allowed():
    require(NO_DATABASE, Caller(CONTEXT, Role.ADMINISTRATOR), Action.SEE_OVERVIEW)


@pytest.mark.database
def test_a_lower_role_is_refused(store: Store, tenant: Context):
    with pytest.raises(NotAllowedError):
        require(store, Caller(tenant, Role.OPERATOR), Action.MANAGE_USERS)


@pytest.mark.database
def test_a_refusal_is_audited_as_refused_against_the_tenant(store: Store, tenant: Context, database_url: str):
    caller = Caller(replace(tenant, actor="user:7"), Role.VIEWER)

    with pytest.raises(NotAllowedError):
        require(store, caller, Action.MANAGE_USERS)

    with psycopg.connect(database_url) as connection:
        records = connection.execute(
            "SELECT table_name, row_key, created_by, reason FROM fcon.audit"
            " WHERE tenant_id = %s AND action = 'refused'",
            (tenant.tenant_id,),
        ).fetchall()
    assert records == [("fcon.tenant", tenant.tenant_id, "user:7", "not allowed to manage users")]


@pytest.mark.parametrize(
    ("action", "least"),
    [
        ("SEE_SETTINGS", Role.VIEWER),
        ("CHANGE_SETTINGS", Role.OPERATOR),
        ("RECORD_CATALOG", Role.DEVELOPER),
    ],
    ids=["see-settings", "change-settings", "record-the-catalog"],
)
def test_the_catalogs_actions_need_their_least_role(action: str, least: Role):
    assert RIGHTS[Action[action]] == least


@pytest.mark.database
def test_a_viewer_cannot_change_settings(store: Store, tenant: Context):
    with pytest.raises(NotAllowedError):
        require(store, Caller(tenant, Role.VIEWER), Action.CHANGE_SETTINGS)


@pytest.mark.database
def test_an_operator_cannot_record_the_catalog(store: Store, tenant: Context):
    with pytest.raises(NotAllowedError):
        require(store, Caller(tenant, Role.OPERATOR), Action.RECORD_CATALOG)
