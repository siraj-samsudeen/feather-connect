"""Managing users (design points 2 and 10): list, disable, enable and a new role.

Each is audited through the store. Disabling ends every session at once; the
last active administrator is never disabled or demoted, checked in the same
transaction as the change.
"""

import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import ConnectionSource, Store
from fcon_server.users.accounts import AddedUser, NewUser, add_user
from fcon_server.users.managing import (
    LastAdministratorError,
    ListedUser,
    NoSuchUserError,
    disable_user,
    enable_user,
    list_users,
    set_role,
)
from fcon_server.users.rights import Caller, NotAllowedError, Role
from fcon_server.users.sessions import Attempt, sign_in, signed_in

pytestmark = pytest.mark.database

NOW = datetime.now(UTC).replace(microsecond=0)  # inside the audit log's months
PASSWORD = "blue-harbour-lamp"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def fixed_store(store_source: ConnectionSource, clock: FixedClock) -> Store:
    return Store(store_source, clock, new_id)


@pytest.fixture
def admin(tenant: Context) -> Caller:
    return Caller(replace(tenant, actor="system:cli"), Role.ADMINISTRATOR)


@pytest.fixture
def ann(fixed_store: Store, admin: Caller) -> AddedUser:
    return add_user(fixed_store, admin, NewUser("ann", PASSWORD))


@pytest.fixture
def ben(fixed_store: Store, admin: Caller, ann: AddedUser) -> AddedUser:
    return add_user(fixed_store, admin, NewUser("ben@example.com", "ben-own-password-1", Role.OPERATOR, "Ben"))


def rows(database_url: str, query: str, *params: object) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return connection.cursor(row_factory=dict_row).execute(query.encode(), params).fetchall()


def user(database_url: str, added: AddedUser) -> dict[str, Any]:
    [row] = rows(database_url, "SELECT * FROM fcon.user WHERE id = %s", added.id)
    return row


def audit(database_url: str, context: Context, action: str) -> list[dict[str, Any]]:
    return rows(
        database_url,
        "SELECT * FROM fcon.audit WHERE tenant_id = %s AND table_name = 'fcon.user' AND action = %s ORDER BY id",
        context.tenant_id,
        action,
    )


def session_of(store: Store, clock: FixedClock, context: Context, name: str, password: str) -> str:
    attempt = Attempt(name=name, password=password, address="192.0.2.10", user_agent=None)
    cookie = sign_in(store, clock, replace(context, actor="system:anonymous"), attempt)
    assert cookie is not None
    return cookie


type Act = Callable[[Store, FixedClock, Caller], object]


def listing(store: Store, clock: FixedClock, caller: Caller) -> object:
    return list_users(store, caller)


def disabling(name: str) -> Act:
    return lambda store, clock, caller: disable_user(store, clock, caller, name)


def enabling(name: str) -> Act:
    return lambda store, clock, caller: enable_user(store, caller, name)


def making_viewer(name: str) -> Act:
    return lambda store, clock, caller: set_role(store, caller, name, Role.VIEWER)


def making_operator(name: str) -> Act:
    return lambda store, clock, caller: set_role(store, caller, name, Role.OPERATOR)


# -- the list ---------------------------------------------------------------


@pytest.mark.usefixtures("ben")
def test_the_list_names_every_user_with_role_and_state(fixed_store: Store, admin: Caller):
    assert list_users(fixed_store, admin) == [
        ListedUser("ann", None, Role.ADMINISTRATOR, "active"),
        ListedUser("ben@example.com", "Ben", Role.OPERATOR, "active"),
    ]


def test_the_list_is_in_name_order(fixed_store: Store, admin: Caller):
    for name in ("cat", "Bob", "amy"):
        add_user(fixed_store, admin, NewUser(name, PASSWORD))

    assert [listed.name for listed in list_users(fixed_store, admin)] == ["amy", "bob", "cat"]


def test_the_list_has_only_the_tenants_users(fixed_store: Store, admin: Caller, new_tenant: Any):
    add_user(fixed_store, admin, NewUser("ann", PASSWORD))
    other = Caller(new_tenant(), Role.ADMINISTRATOR)
    add_user(fixed_store, other, NewUser("zed", PASSWORD))

    assert [listed.name for listed in list_users(fixed_store, admin)] == ["ann"]


@pytest.mark.parametrize(
    "act",
    [
        listing,
        disabling("ben@example.com"),
        enabling("ben@example.com"),
        making_viewer("ben@example.com"),
    ],
    ids=["list", "disable", "enable", "set-role"],
)
@pytest.mark.usefixtures("ben")
def test_only_an_administrator_manages_users(fixed_store: Store, clock: FixedClock, admin: Caller, act: Act):
    with pytest.raises(NotAllowedError):
        act(fixed_store, clock, replace(admin, role=Role.DEVELOPER))


# -- disabling and enabling -------------------------------------------------


def test_disabling_a_user_sets_them_disabled(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser, database_url: str
):
    disable_user(fixed_store, clock, admin, "ben@example.com")

    assert user(database_url, ben)["state"] == "disabled"


def test_disabling_a_user_is_audited_as_the_caller(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser, database_url: str
):
    disable_user(fixed_store, clock, admin, "ben@example.com")

    [record] = audit(database_url, admin.context, "update")
    assert (record["row_key"], record["created_by"], record["after"]["state"]) == (
        str(ben.id),
        "system:cli",
        "disabled",
    )


def test_disabling_a_user_ends_every_session_at_once(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser, database_url: str
):
    for _ in range(2):
        session_of(fixed_store, clock, admin.context, "ben@example.com", "ben-own-password-1")

    disable_user(fixed_store, clock, admin, "ben@example.com")

    assert [
        row["ended_at"] for row in rows(database_url, "SELECT ended_at FROM fcon.session WHERE user_id = %s", ben.id)
    ] == [
        NOW,
        NOW,
    ]


def test_a_session_of_a_disabled_user_no_longer_signs_in(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser
):
    cookie = session_of(fixed_store, clock, admin.context, "ben@example.com", "ben-own-password-1")

    disable_user(fixed_store, clock, admin, "ben@example.com")

    assert signed_in(fixed_store, clock, admin.context, cookie) is None


@pytest.mark.usefixtures("ben")
def test_disabling_says_whether_it_changed_anything(fixed_store: Store, clock: FixedClock, admin: Caller):
    changed = [disable_user(fixed_store, clock, admin, "ben@example.com") for _ in range(2)]

    assert changed == [True, False]


def test_enabling_a_disabled_user_sets_them_active(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser, database_url: str
):
    disable_user(fixed_store, clock, admin, "ben@example.com")

    enable_user(fixed_store, admin, "ben@example.com")

    assert user(database_url, ben)["state"] == "active"


@pytest.mark.usefixtures("ben")
def test_enabling_says_whether_it_changed_anything(fixed_store: Store, clock: FixedClock, admin: Caller):
    disable_user(fixed_store, clock, admin, "ben@example.com")

    changed = [enable_user(fixed_store, admin, "ben@example.com") for _ in range(2)]

    assert changed == [True, False]


@pytest.mark.usefixtures("ben")
def test_the_name_is_matched_whatever_its_case(fixed_store: Store, clock: FixedClock, admin: Caller):
    assert disable_user(fixed_store, clock, admin, " Ben@Example.com ")


@pytest.mark.parametrize(
    "act",
    [
        disabling("nobody"),
        enabling("nobody"),
        making_viewer("nobody"),
    ],
    ids=["disable", "enable", "set-role"],
)
@pytest.mark.usefixtures("ann")
def test_a_name_nobody_has_is_no_such_user(fixed_store: Store, clock: FixedClock, admin: Caller, act: Act):
    with pytest.raises(NoSuchUserError, match="nobody"):
        act(fixed_store, clock, admin)


# -- a new role ---------------------------------------------------------------


def test_a_new_role_is_kept(fixed_store: Store, admin: Caller, ben: AddedUser, database_url: str):
    set_role(fixed_store, admin, "ben@example.com", Role.VIEWER)

    assert user(database_url, ben)["role"] == "viewer"


def test_a_new_role_holds_from_the_users_next_page(
    fixed_store: Store, clock: FixedClock, admin: Caller, ben: AddedUser
):
    cookie = session_of(fixed_store, clock, admin.context, "ben@example.com", "ben-own-password-1")

    set_role(fixed_store, admin, "ben@example.com", Role.VIEWER)

    found = signed_in(fixed_store, clock, admin.context, cookie)
    assert found is not None and found.role == Role.VIEWER


@pytest.mark.usefixtures("ben")
def test_a_new_role_says_whether_it_changed_anything(fixed_store: Store, admin: Caller):
    changed = [set_role(fixed_store, admin, "ben@example.com", Role.VIEWER) for _ in range(2)]

    assert changed == [True, False]


@pytest.mark.usefixtures("ben")
def test_an_administrator_can_be_demoted_while_another_is_left(
    fixed_store: Store, admin: Caller, ann: AddedUser, database_url: str
):
    set_role(fixed_store, admin, "ben@example.com", Role.ADMINISTRATOR)

    set_role(fixed_store, admin, "ann", Role.OPERATOR)

    assert user(database_url, ann)["role"] == "operator"


# -- always an administrator ------------------------------------------------


@pytest.mark.parametrize(
    "act",
    [
        disabling("ann"),
        making_operator("ann"),
    ],
    ids=["disable", "demote"],
)
@pytest.mark.usefixtures("ben")
def test_the_only_administrator_is_refused_saying_why(fixed_store: Store, clock: FixedClock, admin: Caller, act: Act):
    with pytest.raises(LastAdministratorError, match=r"^ann is the only administrator; make another one first\.$"):
        act(fixed_store, clock, admin)


@pytest.mark.parametrize(
    "act",
    [
        disabling("ann"),
        making_operator("ann"),
    ],
    ids=["disable", "demote"],
)
def test_the_only_administrator_stays_one(
    fixed_store: Store, clock: FixedClock, admin: Caller, ann: AddedUser, database_url: str, act: Act
):
    with pytest.raises(LastAdministratorError):
        act(fixed_store, clock, admin)

    assert (user(database_url, ann)["role"], user(database_url, ann)["state"]) == ("administrator", "active")


def test_the_refusal_is_audited_as_refused(
    fixed_store: Store, clock: FixedClock, admin: Caller, ann: AddedUser, database_url: str
):
    with pytest.raises(LastAdministratorError):
        disable_user(fixed_store, clock, admin, "ann")

    [record] = audit(database_url, admin.context, "refused")
    assert (record["row_key"], record["created_by"], record["reason"]) == (
        str(ann.id),
        "system:cli",
        "ann is the only administrator; make another one first.",
    )


def test_a_disabled_administrator_does_not_count(fixed_store: Store, clock: FixedClock, admin: Caller, ann: AddedUser):
    add_user(fixed_store, admin, NewUser("cat", PASSWORD, Role.ADMINISTRATOR))
    disable_user(fixed_store, clock, admin, "cat")

    with pytest.raises(LastAdministratorError):
        set_role(fixed_store, admin, "ann", Role.VIEWER)


@pytest.mark.usefixtures("ann")
def test_the_only_administrator_keeps_the_role_it_has(fixed_store: Store, admin: Caller):
    assert set_role(fixed_store, admin, "ann", Role.ADMINISTRATOR) is False


def test_two_administrators_demoting_each_other_at_once_leave_one(
    fixed_store: Store, admin: Caller, ann: AddedUser, ben: AddedUser, database_url: str
):
    """One demotion holds the rows while the other waits on them.

    The second then sees the first's change and is refused.
    """
    set_role(fixed_store, admin, "ben@example.com", Role.ADMINISTRATOR)
    outcome: list[object] = []
    with psycopg.connect(database_url) as first:
        first.execute(
            "SELECT id FROM fcon.user WHERE tenant_id = %s ORDER BY id FOR UPDATE", (admin.context.tenant_id,)
        )
        first.execute("UPDATE fcon.user SET role = 'operator' WHERE id = %s", (ben.id,))

        def demote_ann() -> None:
            try:
                outcome.append(set_role(fixed_store, admin, "ann", Role.OPERATOR))
            except LastAdministratorError as err:
                outcome.append(err)

        second = threading.Thread(target=demote_ann)
        second.start()
        second.join(timeout=1)
        assert second.is_alive(), "the second demotion did not wait for the first"
        first.commit()
        second.join(timeout=10)

    assert [type(found) for found in outcome] == [LastAdministratorError]
