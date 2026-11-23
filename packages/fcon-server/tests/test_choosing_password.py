"""Choosing one's own password (design points 2 and 3): a password given to
a user works for one sign-in; the one they choose follows the rules, is typed
twice, clears `must_choose_password`, and ends every other session of theirs."""

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
from fcon_server.users.choosing import ChoiceProblem, NothingToChooseError, choose_password
from fcon_server.users.passwords import password_matches
from fcon_server.users.rights import Caller, Role
from fcon_server.users.rules import PasswordProblem
from fcon_server.users.sessions import Attempt, SignedIn, sign_in, signed_in

pytestmark = pytest.mark.database

NOW = datetime.now(UTC).replace(microsecond=0)
GIVEN = "given-once-0001"
CHOSEN = "ben-own-password-1"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def fixed_store(store_source: ConnectionSource, clock: FixedClock) -> Store:
    return Store(store_source, clock, new_id)


@pytest.fixture
def anonymous(tenant: Context) -> Context:
    return replace(tenant, actor="system:anonymous")


@pytest.fixture
def ben(fixed_store: Store, tenant: Context) -> AddedUser:
    admin = Caller(tenant, Role.ADMINISTRATOR)
    add_user(fixed_store, admin, NewUser("ann", "blue-harbour-lamp"))
    return add_user(fixed_store, admin, NewUser("ben", GIVEN, Role.OPERATOR))


def session(store: Store, clock: FixedClock, context: Context) -> tuple[str, SignedIn]:
    cookie = sign_in(store, clock, context, Attempt("ben", GIVEN, "192.0.2.10", None))
    assert cookie is not None
    found = signed_in(store, clock, context, cookie)
    assert found is not None
    return cookie, found


def user(database_url: str, context: Context, name: str = "ben") -> dict[str, Any]:
    with psycopg.connect(database_url) as connection:
        row = (
            connection.cursor(row_factory=dict_row)
            .execute("SELECT * FROM fcon.user WHERE tenant_id = %s AND name = %s", (context.tenant_id, name))
            .fetchone()
        )
    assert row is not None
    return row


@pytest.mark.usefixtures("ben")
def test_the_password_chosen_is_the_users_from_then_on(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    _, found = session(fixed_store, clock, anonymous)

    assert choose_password(fixed_store, clock, found, CHOSEN, CHOSEN) is None
    assert password_matches(user(database_url, anonymous)["password_hash"], CHOSEN)


@pytest.mark.usefixtures("ben")
def test_choosing_clears_must_choose_password(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    _, found = session(fixed_store, clock, anonymous)

    choose_password(fixed_store, clock, found, CHOSEN, CHOSEN)

    assert user(database_url, anonymous)["must_choose_password"] is False


def test_choosing_is_done_by_the_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str, ben: AddedUser
):
    _, found = session(fixed_store, clock, anonymous)

    choose_password(fixed_store, clock, found, CHOSEN, CHOSEN)

    assert user(database_url, anonymous)["updated_by"] == f"user:{ben.id}"


@pytest.mark.usefixtures("ben")
def test_choosing_ends_the_users_other_sessions(fixed_store: Store, clock: FixedClock, anonymous: Context):
    other, _ = session(fixed_store, clock, anonymous)
    _, found = session(fixed_store, clock, anonymous)

    choose_password(fixed_store, clock, found, CHOSEN, CHOSEN)

    assert signed_in(fixed_store, clock, anonymous, other) is None


@pytest.mark.usefixtures("ben")
def test_choosing_keeps_the_session_it_was_chosen_in(fixed_store: Store, clock: FixedClock, anonymous: Context):
    session(fixed_store, clock, anonymous)
    this, found = session(fixed_store, clock, anonymous)

    choose_password(fixed_store, clock, found, CHOSEN, CHOSEN)

    assert signed_in(fixed_store, clock, anonymous, this) is not None


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("short-one", PasswordProblem.TOO_SHORT),
        ("x" * 129, PasswordProblem.TOO_LONG),
        ("password123456", PasswordProblem.TOO_COMMON),
    ],
    ids=["too-short", "too-long", "too-common"],
)
@pytest.mark.usefixtures("ben")
def test_a_password_that_breaks_a_rule_says_which(
    fixed_store: Store, clock: FixedClock, anonymous: Context, password: str, problem: PasswordProblem
):
    _, found = session(fixed_store, clock, anonymous)

    assert choose_password(fixed_store, clock, found, password, password) == problem


@pytest.mark.usefixtures("ben")
def test_two_entries_that_differ_are_refused(fixed_store: Store, clock: FixedClock, anonymous: Context):
    _, found = session(fixed_store, clock, anonymous)

    assert choose_password(fixed_store, clock, found, CHOSEN, CHOSEN + "x") == ChoiceProblem.DIFFERENT


@pytest.mark.usefixtures("ben")
def test_a_refused_password_changes_nothing(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    _, found = session(fixed_store, clock, anonymous)

    choose_password(fixed_store, clock, found, "short-one", "short-one")

    row = user(database_url, anonymous)
    assert (row["must_choose_password"], password_matches(row["password_hash"], GIVEN)) == (True, True)


@pytest.mark.usefixtures("ben")
def test_a_user_with_their_own_password_has_nothing_to_choose(
    fixed_store: Store, clock: FixedClock, anonymous: Context
):
    _, found = session(fixed_store, clock, anonymous)
    choose_password(fixed_store, clock, found, CHOSEN, CHOSEN)

    with pytest.raises(NothingToChooseError):
        choose_password(fixed_store, clock, found, CHOSEN + "-2", CHOSEN + "-2")
