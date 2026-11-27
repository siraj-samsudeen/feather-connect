"""The first administrator from FCON_FIRST_ADMIN (design point 1, decision 4).

It is made once, on a start with no users, with a one-time password; nothing is
made when any user exists.
"""

from dataclasses import replace
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from fcon_server.store.context import Context
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import (
    FIRST_ADMIN_ACTOR,
    NameNotAllowedError,
    NewUser,
    add_first_administrator,
    add_user,
)
from fcon_server.users.passwords import password_matches
from fcon_server.users.rights import Caller, Role

pytestmark = pytest.mark.database


@pytest.fixture
def first_admin(tenant: Context) -> Context:
    return replace(tenant, actor=FIRST_ADMIN_ACTOR)


def user_rows(database_url: str, context: Context) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return (
            connection.cursor(row_factory=dict_row)
            .execute("SELECT * FROM fcon.user WHERE tenant_id = %s", (context.tenant_id,))
            .fetchall()
        )


def test_the_one_time_password_is_the_new_administrators(store: Store, first_admin: Context, database_url: str):
    password = add_first_administrator(store, first_admin, "ann")

    [user] = user_rows(database_url, first_admin)
    assert password is not None and password_matches(user["password_hash"], password)


def test_the_first_administrator_must_choose_a_password(store: Store, first_admin: Context, database_url: str):
    add_first_administrator(store, first_admin, "Ann")

    [user] = user_rows(database_url, first_admin)
    assert (user["name"], user["role"], user["must_choose_password"]) == ("ann", "administrator", True)


def test_the_first_administrator_is_made_by_the_setting(store: Store, first_admin: Context, database_url: str):
    add_first_administrator(store, first_admin, "ann")

    [user] = user_rows(database_url, first_admin)
    assert user["created_by"] == "system:first-admin"


def test_each_one_time_password_is_new(store: Store, new_tenant: Any):
    first = add_first_administrator(store, replace(new_tenant(), actor=FIRST_ADMIN_ACTOR), "ann")
    second = add_first_administrator(store, replace(new_tenant(), actor=FIRST_ADMIN_ACTOR), "ann")

    assert first != second


def test_nothing_is_made_once_any_user_exists(store: Store, first_admin: Context, database_url: str):
    add_user(store, Caller(first_admin, Role.ADMINISTRATOR), NewUser("ben", "ben-own-password-1"))

    password = add_first_administrator(store, first_admin, "ann")

    assert (password, [user["name"] for user in user_rows(database_url, first_admin)]) == (None, ["ben"])


def test_a_second_start_makes_nothing(store: Store, first_admin: Context):
    add_first_administrator(store, first_admin, "ann")

    assert add_first_administrator(store, first_admin, "ann") is None


def test_a_name_that_breaks_the_rules_is_not_allowed(store: Store, first_admin: Context):
    with pytest.raises(NameNotAllowedError):
        add_first_administrator(store, first_admin, "ann smith")
