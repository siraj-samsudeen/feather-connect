"""Signing in and the session it makes (design points 4 and 7, § How it is
built): every attempt is recorded; a session lives in the database, the
browser holds only its random id, and it ends after 12 hours idle or 7 days."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from argon2 import PasswordHasher
from psycopg.rows import dict_row

from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import ConnectionSource, Store
from fcon_server.users.accounts import AddedUser, NewUser, add_user
from fcon_server.users.passwords import password_matches
from fcon_server.users.rights import Caller, Role
from fcon_server.users.sessions import Attempt, sign_in, sign_out, signed_in

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
def anonymous(tenant: Context) -> Context:
    return replace(tenant, actor="system:anonymous")


@pytest.fixture
def ann(fixed_store: Store, tenant: Context) -> AddedUser:
    return add_user(fixed_store, Caller(tenant, Role.ADMINISTRATOR), NewUser("ann", PASSWORD))


def attempt(name: str = "ann", password: str = PASSWORD) -> Attempt:
    return Attempt(name=name, password=password, address="192.0.2.10", user_agent="a browser")


def rows(database_url: str, query: str, *params: object) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return connection.cursor(row_factory=dict_row).execute(query.encode(), params).fetchall()


def sessions(database_url: str, context: Context) -> list[dict[str, Any]]:
    return rows(database_url, "SELECT * FROM fcon.session WHERE tenant_id = %s", context.tenant_id)


def attempts(database_url: str, context: Context) -> list[tuple[str, str, str]]:
    found = rows(
        database_url,
        "SELECT name, address, outcome FROM fcon.sign_in_attempt WHERE tenant_id = %s ORDER BY id",
        context.tenant_id,
    )
    return [(row["name"], row["address"], row["outcome"]) for row in found]


# -- signing in ------------------------------------------------------------


@pytest.mark.usefixtures("ann")
def test_the_right_password_gives_a_session_id(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt()) is not None


@pytest.mark.usefixtures("ann")
def test_the_session_id_is_32_random_bytes(fixed_store: Store, clock: FixedClock, anonymous: Context):
    cookie = sign_in(fixed_store, clock, anonymous, attempt())

    assert cookie is not None and len(cookie) >= 43  # 32 bytes, URL-safe base64


@pytest.mark.usefixtures("ann")
def test_the_database_keeps_only_the_ids_hash(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    cookie = sign_in(fixed_store, clock, anonymous, attempt())

    assert cookie is not None
    assert [row["id_hash"] for row in sessions(database_url, anonymous)] == [
        hashlib.sha256(cookie.encode()).hexdigest()
    ]


@pytest.mark.usefixtures("ann")
def test_every_sign_in_gets_a_new_id(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt()) != sign_in(fixed_store, clock, anonymous, attempt())


def test_the_session_records_how_and_from_where_it_was_made(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str, ann: AddedUser
):
    sign_in(fixed_store, clock, anonymous, attempt())

    [row] = sessions(database_url, anonymous)
    assert (row["user_id"], row["made_by"], row["address"], row["user_agent"], row["created_by"]) == (
        ann.id,
        "password",
        "192.0.2.10",
        "a browser",
        f"user:{ann.id}",
    )


@pytest.mark.usefixtures("ann")
def test_a_session_lasts_7_days_at_most(fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str):
    sign_in(fixed_store, clock, anonymous, attempt())

    assert sessions(database_url, anonymous)[0]["expires_at"] == NOW + timedelta(days=7)


@pytest.mark.usefixtures("ann")
def test_the_name_is_matched_whatever_its_case(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt(name=" ANN ")) is not None


@pytest.mark.usefixtures("ann")
def test_a_wrong_password_is_refused(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt(password="letmein")) is None


@pytest.mark.usefixtures("ann")
def test_a_name_nobody_has_is_refused(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt(name="alex")) is None


@pytest.mark.usefixtures("ann")
def test_a_password_over_128_characters_is_refused(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert sign_in(fixed_store, clock, anonymous, attempt(password=PASSWORD + "x" * 200)) is None


def test_a_disabled_user_is_refused(fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str):
    add_user(fixed_store, Caller(anonymous, Role.ADMINISTRATOR), NewUser("ann", PASSWORD))
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE fcon.user SET state = 'disabled' WHERE tenant_id = %s", (anonymous.tenant_id,))

    assert sign_in(fixed_store, clock, anonymous, attempt()) is None


@pytest.mark.usefixtures("ann")
def test_a_refused_sign_in_makes_no_session(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    sign_in(fixed_store, clock, anonymous, attempt(password="letmein"))

    assert sessions(database_url, anonymous) == []


@pytest.mark.usefixtures("ann")
def test_every_attempt_is_recorded_with_its_outcome(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    sign_in(fixed_store, clock, anonymous, attempt(name="Alex"))
    sign_in(fixed_store, clock, anonymous, attempt())

    assert attempts(database_url, anonymous) == [
        ("alex", "192.0.2.10", "refused"),
        ("ann", "192.0.2.10", "succeeded"),
    ]


@pytest.mark.usefixtures("ann")
def test_the_audit_never_shows_the_session_id_or_form_token(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str
):
    sign_in(fixed_store, clock, anonymous, attempt())

    [record] = rows(
        database_url,
        "SELECT after FROM fcon.audit WHERE tenant_id = %s AND table_name = 'fcon.session'",
        anonymous.tenant_id,
    )
    assert (record["after"]["id_hash"], record["after"]["form_token"]) == ("(secret changed)", "(secret changed)")


def test_a_hash_made_weaker_than_now_is_redone_at_sign_in(
    fixed_store: Store, clock: FixedClock, anonymous: Context, database_url: str, ann: AddedUser
):
    weaker = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE fcon.user SET password_hash = %s WHERE id = %s", (weaker, ann.id))

    sign_in(fixed_store, clock, anonymous, attempt())

    [user] = rows(database_url, "SELECT password_hash FROM fcon.user WHERE id = %s", ann.id)
    assert (
        user["password_hash"].startswith("$argon2id$v=19$m=19456,t=2,p=1$"),
        password_matches(user["password_hash"], PASSWORD),
    ) == (True, True)


def test_a_user_changed_while_the_hash_is_redone_still_signs_in(
    fixed_store: Store,
    clock: FixedClock,
    anonymous: Context,
    database_url: str,
    ann: AddedUser,
    monkeypatch: pytest.MonkeyPatch,
):
    """The new hash waits for the next sign-in; this one goes on."""
    weaker = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE fcon.user SET password_hash = %s WHERE id = %s", (weaker, ann.id))
    hash_now = PasswordHasher.hash

    def changed_meanwhile(hasher: PasswordHasher, password: str | bytes, *, salt: bytes | None = None) -> str:
        with psycopg.connect(database_url) as connection:
            connection.execute("UPDATE fcon.user SET row_version = row_version + 1 WHERE id = %s", (ann.id,))
        return hash_now(hasher, password, salt=salt)

    monkeypatch.setattr(PasswordHasher, "hash", changed_meanwhile)

    assert sign_in(fixed_store, clock, anonymous, attempt()) is not None


# -- the session, on each request -----------------------------------------


@pytest.fixture
def cookie(fixed_store: Store, clock: FixedClock, anonymous: Context, ann: AddedUser) -> str:
    made = sign_in(fixed_store, clock, anonymous, attempt())
    assert made is not None
    return made


def test_a_session_says_who_is_signed_in(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, ann: AddedUser
):
    found = signed_in(fixed_store, clock, anonymous, cookie)

    assert found is not None
    assert (found.user_id, found.name, found.role, found.must_choose_password) == (
        ann.id,
        "ann",
        Role.ADMINISTRATOR,
        False,
    )


def test_a_session_carries_its_form_token(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    found = signed_in(fixed_store, clock, anonymous, cookie)

    assert found is not None and found.form_token == sessions(database_url, anonymous)[0]["form_token"]


def test_a_session_acts_as_its_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, ann: AddedUser
):
    found = signed_in(fixed_store, clock, anonymous, cookie)

    assert found is not None and found.caller.context.actor == f"user:{ann.id}"


@pytest.mark.usefixtures("cookie")
def test_an_id_nobody_was_given_is_no_session(fixed_store: Store, clock: FixedClock, anonymous: Context):
    assert signed_in(fixed_store, clock, anonymous, "made-up") is None


def test_a_session_idle_for_12_hours_has_ended(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    clock.at = NOW + timedelta(hours=12)

    assert (signed_in(fixed_store, clock, anonymous, cookie), sessions(database_url, anonymous)[0]["ended_at"]) == (
        None,
        NOW + timedelta(hours=12),
    )


def test_a_session_ended_stays_ended(fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str):
    clock.at = NOW + timedelta(hours=12)
    signed_in(fixed_store, clock, anonymous, cookie)
    clock.at = NOW

    assert signed_in(fixed_store, clock, anonymous, cookie) is None


def test_a_session_used_within_12_hours_goes_on(fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str):
    clock.at = NOW + timedelta(hours=11)

    assert signed_in(fixed_store, clock, anonymous, cookie) is not None


def test_a_session_in_use_ends_after_7_days(fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str):
    for hours in range(11, 7 * 24, 11):
        clock.at = NOW + timedelta(hours=hours)
        signed_in(fixed_store, clock, anonymous, cookie)
    clock.at = NOW + timedelta(days=7)

    assert signed_in(fixed_store, clock, anonymous, cookie) is None


def test_a_session_of_a_disabled_user_has_ended(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    with psycopg.connect(database_url) as connection:
        connection.execute("UPDATE fcon.user SET state = 'disabled' WHERE tenant_id = %s", (anonymous.tenant_id,))

    assert signed_in(fixed_store, clock, anonymous, cookie) is None


def test_last_seen_is_written_once_a_minute_has_passed(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    clock.at = NOW + timedelta(minutes=1)

    signed_in(fixed_store, clock, anonymous, cookie)

    assert sessions(database_url, anonymous)[0]["last_seen_at"] == NOW + timedelta(minutes=1)


def test_last_seen_is_not_written_within_a_minute(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    clock.at = NOW + timedelta(seconds=59)

    signed_in(fixed_store, clock, anonymous, cookie)

    assert sessions(database_url, anonymous)[0]["row_version"] == 1


def test_last_seen_is_written_by_the_sessions_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str, ann: AddedUser
):
    clock.at = NOW + timedelta(minutes=1)

    signed_in(fixed_store, clock, anonymous, cookie)

    assert sessions(database_url, anonymous)[0]["updated_by"] == f"user:{ann.id}"


def test_a_session_that_ran_out_is_ended_by_its_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str, ann: AddedUser
):
    clock.at = NOW + timedelta(hours=12)

    signed_in(fixed_store, clock, anonymous, cookie)

    assert sessions(database_url, anonymous)[0]["updated_by"] == f"user:{ann.id}"


# -- signing out ------------------------------------------------------------


def open_sessions(database_url: str, context: Context) -> list[dict[str, Any]]:
    return [row for row in sessions(database_url, context) if row["ended_at"] is None]


def test_signing_out_ends_every_session_of_the_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    sign_in(fixed_store, clock, anonymous, attempt())  # another computer
    found = signed_in(fixed_store, clock, anonymous, cookie)
    assert found is not None

    sign_out(fixed_store, clock, found)

    assert open_sessions(database_url, anonymous) == []


def test_signing_out_leaves_other_users_sessions(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str
):
    add_user(fixed_store, Caller(anonymous, Role.ADMINISTRATOR), NewUser("ben", "ben-own-password-1"))
    sign_in(fixed_store, clock, anonymous, attempt("ben", "ben-own-password-1"))
    found = signed_in(fixed_store, clock, anonymous, cookie)
    assert found is not None

    sign_out(fixed_store, clock, found)

    assert len(open_sessions(database_url, anonymous)) == 1


def test_signing_out_is_audited_as_the_user(
    fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str, database_url: str, ann: AddedUser
):
    found = signed_in(fixed_store, clock, anonymous, cookie)
    assert found is not None

    sign_out(fixed_store, clock, found)

    [record] = rows(
        database_url,
        "SELECT created_by, after FROM fcon.audit WHERE tenant_id = %s AND table_name = 'fcon.session'"
        " AND action = 'update'",
        anonymous.tenant_id,
    )
    assert (record["created_by"], record["after"]["ended_at"] is not None) == (f"user:{ann.id}", True)


def test_a_session_signed_out_is_no_session(fixed_store: Store, clock: FixedClock, anonymous: Context, cookie: str):
    found = signed_in(fixed_store, clock, anonymous, cookie)
    assert found is not None
    sign_out(fixed_store, clock, found)

    assert signed_in(fixed_store, clock, anonymous, cookie) is None
