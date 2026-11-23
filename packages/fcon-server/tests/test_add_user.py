"""Adding a user (design points 1 to 3): the first user is always an
administrator, and a password set for someone else works for one sign-in,
except the first user's, who typed it for themselves."""

from dataclasses import replace
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from fcon_server.store.context import Context
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import (
    NameNotAllowedError,
    NameTakenError,
    NewUser,
    WeakPasswordError,
    add_user,
)
from fcon_server.users.passwords import password_matches
from fcon_server.users.rights import Caller, NotAllowedError, Role
from fcon_server.users.rules import PasswordProblem

pytestmark = pytest.mark.database

PASSWORD = "blue-harbour-lamp"


def admin(context: Context) -> Caller:
    return Caller(context, Role.ADMINISTRATOR)


def user_row(database_url: str, context: Context, name: str) -> dict[str, Any]:
    with psycopg.connect(database_url) as connection:
        row = (
            connection.cursor(row_factory=dict_row)
            .execute("SELECT * FROM fcon.user WHERE tenant_id = %s AND name = %s", (context.tenant_id, name))
            .fetchone()
        )
    assert row is not None, f"no user {name!r}"
    return row


def audit_rows(database_url: str, context: Context) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return (
            connection.cursor(row_factory=dict_row)
            .execute("SELECT * FROM fcon.audit WHERE tenant_id = %s AND table_name = 'fcon.user'", (context.tenant_id,))
            .fetchall()
        )


def test_the_first_user_is_an_administrator_whatever_role_was_asked(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD, Role.VIEWER))

    assert user_row(database_url, tenant, "ann")["role"] == "administrator"


def test_the_first_users_password_is_their_own(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    assert user_row(database_url, tenant, "ann")["must_choose_password"] is False


def test_a_later_user_has_the_role_asked(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    add_user(store, admin(tenant), NewUser("ben@example.com", "given-once-0001", Role.OPERATOR))

    assert user_row(database_url, tenant, "ben@example.com")["role"] == "operator"


def test_a_later_users_password_works_for_one_sign_in(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    add_user(store, admin(tenant), NewUser("ben@example.com", "given-once-0001", Role.OPERATOR))

    assert user_row(database_url, tenant, "ben@example.com")["must_choose_password"] is True


def test_a_user_is_added_active(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    assert user_row(database_url, tenant, "ann")["state"] == "active"


def test_the_password_is_kept_as_its_hash(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    assert password_matches(user_row(database_url, tenant, "ann")["password_hash"], PASSWORD)


def test_the_name_is_kept_lowercased(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("Ann", PASSWORD))

    assert user_row(database_url, tenant, "ann")["name"] == "ann"


def test_a_display_name_is_kept_beside_the_name(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD, display_name="Ann Lee"))

    assert user_row(database_url, tenant, "ann")["display_name"] == "Ann Lee"


def test_adding_a_user_says_who_was_added(store: Store, tenant: Context):
    added = add_user(store, admin(tenant), NewUser("Ann", PASSWORD, Role.VIEWER))

    assert (added.name, added.role, added.must_choose_password) == ("ann", Role.ADMINISTRATOR, False)


def test_a_name_taken_is_refused(store: Store, tenant: Context):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    with pytest.raises(NameTakenError):
        add_user(store, admin(tenant), NewUser("ANN", "another-password-1"))


def test_a_name_outside_the_rules_is_refused(store: Store, tenant: Context):
    with pytest.raises(NameNotAllowedError):
        add_user(store, admin(tenant), NewUser("ann smith", PASSWORD))


def test_a_weak_password_is_refused_saying_why(store: Store, tenant: Context):
    with pytest.raises(WeakPasswordError) as refused:
        add_user(store, admin(tenant), NewUser("ann", "short-one"))

    assert refused.value.problem is PasswordProblem.TOO_SHORT


def test_only_an_administrator_adds_users(store: Store, tenant: Context):
    with pytest.raises(NotAllowedError):
        add_user(store, Caller(tenant, Role.OPERATOR), NewUser("ann", PASSWORD))


def test_adding_a_user_is_audited_by_the_caller(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(replace(tenant, actor="system:cli")), NewUser("ann", PASSWORD))

    [record] = audit_rows(database_url, tenant)
    assert (record["action"], record["created_by"], record["after"]["name"]) == ("insert", "system:cli", "ann")


def test_the_audit_never_shows_the_password_hash(store: Store, tenant: Context, database_url: str):
    add_user(store, admin(tenant), NewUser("ann", PASSWORD))

    [record] = audit_rows(database_url, tenant)
    assert record["after"]["password_hash"] == "(secret changed)"
