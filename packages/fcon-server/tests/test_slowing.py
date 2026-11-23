"""The slowing of repeated failures (design point 7, § Signing in): after 3
failed sign-ins in 15 minutes for one name from any address, or from one
address for any name, each further attempt waits 1 s, 2 s, 4 s and so on
after the last failure, a minute at most. An attempt during the wait is
refused without checking the password, recorded as `waited`, and is no
failure itself. A success clears that name's count. Every refusal checks one
argon2id hash, a dummy one for a made-up name. Attempts older than a day go,
at most 100 with each sign-in (decision 3)."""

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import argon2
import psycopg
import pytest
from psycopg.rows import dict_row

from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import ConnectionSource, Store
from fcon_server.users.accounts import NewUser, add_user
from fcon_server.users.rights import Caller, Role
from fcon_server.users.sessions import Attempt, sign_in

pytestmark = pytest.mark.database

NOW = datetime.now(UTC).replace(microsecond=0)  # inside the audit log's months
PASSWORD = "blue-harbour-lamp"
WRONG = "not-the-password-0"
ADDRESS = "192.0.2.10"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def fixed_store(store_source: ConnectionSource, clock: FixedClock) -> Store:
    return Store(store_source, clock, new_id)


@pytest.fixture
def anonymous(tenant: Context) -> Context:
    return replace(tenant, actor="system:anonymous")


@pytest.fixture(autouse=True)
def ann(fixed_store: Store, tenant: Context) -> None:
    add_user(fixed_store, Caller(tenant, Role.ADMINISTRATOR), NewUser("ann", PASSWORD))


class SignIn:
    """Sign-ins at the clock's time, which `later` moves on."""

    def __init__(self, store: Store, clock: FixedClock, context: Context) -> None:
        self.store, self.clock, self.context = store, clock, context

    def __call__(self, name: str = "ann", password: str = PASSWORD, address: str = ADDRESS) -> bool:
        attempt = Attempt(name=name, password=password, address=address, user_agent=None)
        return sign_in(self.store, self.clock, self.context, attempt) is not None

    def fail(self, times: int, name: str = "ann", address: str = ADDRESS) -> None:
        """`times` failures; from the fourth on, each once the wait before it
        has passed, so that it counts."""
        for done in range(times):
            if done >= 3:
                self.later(61)
            assert not self(name, WRONG, address)

    def later(self, seconds: float) -> None:
        self.clock.at += timedelta(seconds=seconds)


@pytest.fixture
def signing_in(fixed_store: Store, clock: FixedClock, anonymous: Context) -> SignIn:
    return SignIn(fixed_store, clock, anonymous)


def rows(database_url: str, query: str, *params: object) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return connection.cursor(row_factory=dict_row).execute(query.encode(), params).fetchall()


def outcomes(database_url: str, context: Context) -> list[str]:
    found = rows(
        database_url,
        "SELECT outcome FROM fcon.sign_in_attempt WHERE tenant_id = %s ORDER BY created_at, id",
        context.tenant_id,
    )
    return [row["outcome"] for row in found]


# -- one name, from any address ------------------------------------------------


def test_two_failures_do_not_slow_the_next_attempt(signing_in: SignIn):
    signing_in.fail(2)

    assert signing_in()


def test_after_3_failures_the_right_password_at_once_is_refused(signing_in: SignIn):
    signing_in.fail(3)

    assert not signing_in()


def test_an_attempt_during_the_wait_is_recorded_as_waited(signing_in: SignIn, database_url: str, anonymous: Context):
    signing_in.fail(3)

    signing_in()

    assert outcomes(database_url, anonymous) == ["refused", "refused", "refused", "waited"]


def test_failures_from_other_addresses_count_for_the_name(signing_in: SignIn):
    for address in ("192.0.2.1", "192.0.2.2", "192.0.2.3"):
        signing_in.fail(1, address=address)

    assert not signing_in()


def test_the_name_tried_counts_whatever_its_case(signing_in: SignIn):
    signing_in.fail(3, name="ANN")

    assert not signing_in()


def test_after_3_failures_the_wait_is_1_second(signing_in: SignIn):
    signing_in.fail(3)

    signing_in.later(1)

    assert signing_in()


@pytest.mark.parametrize(
    ("failures", "wait"), [(4, 2), (5, 4), (8, 32), (9, 60), (12, 60)], ids=["4", "5", "8", "9-capped", "12-capped"]
)
def test_each_failure_more_doubles_the_wait_up_to_a_minute(signing_in: SignIn, failures: int, wait: int):
    signing_in.fail(failures)

    signing_in.later(wait - 1)
    refused_before = not signing_in()
    signing_in.later(1)

    assert (refused_before, signing_in()) == (True, True)


def test_the_wait_counts_from_the_last_failure(signing_in: SignIn):
    signing_in.fail(2)
    signing_in.later(30)
    signing_in.fail(1)

    signing_in.later(0.5)

    assert not signing_in()


def test_attempts_during_the_wait_are_no_failures(signing_in: SignIn):
    """Else someone hammering the form would keep the real user out for ever."""
    signing_in.fail(3)
    for _ in range(5):
        signing_in(password=WRONG)

    signing_in.later(1)

    assert signing_in()


def test_failures_older_than_15_minutes_do_not_count(signing_in: SignIn):
    signing_in.fail(2)
    signing_in.later(15 * 60)
    signing_in.fail(1)

    assert signing_in()


def test_a_success_clears_the_names_count(signing_in: SignIn):
    signing_in.fail(3)
    signing_in.later(1)
    assert signing_in()

    signing_in.fail(2)

    assert signing_in()


def test_a_failure_for_another_name_from_another_address_does_not_count(signing_in: SignIn):
    for name, address in (("alex", "192.0.2.1"), ("sam", "192.0.2.2"), ("kim", "192.0.2.3")):
        signing_in.fail(1, name=name, address=address)

    assert signing_in()


# -- one address, any name -------------------------------------------------------


def test_3_names_failed_from_one_address_slow_that_address(signing_in: SignIn):
    for name in ("alex", "sam", "kim"):
        signing_in.fail(1, name=name)

    assert not signing_in()


def test_3_names_failed_from_one_address_leave_other_addresses_alone(signing_in: SignIn):
    for name in ("alex", "sam", "kim"):
        signing_in.fail(1, name=name)

    assert signing_in(address="198.51.100.7")


def test_the_addresss_wait_passes_too(signing_in: SignIn):
    for name in ("alex", "sam", "kim"):
        signing_in.fail(1, name=name)

    signing_in.later(1)

    assert signing_in()


# -- one argon2id check for every refusal, none while waiting -------------------


@pytest.fixture
def checks(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Each argon2id check argon2-cffi makes, by the hash it checks against."""
    made: list[str] = []
    verify = argon2.PasswordHasher.verify

    def counted(hasher: argon2.PasswordHasher, hash: str | bytes, password: str | bytes) -> bool:
        made.append(str(hash))
        return verify(hasher, hash, password)

    monkeypatch.setattr(argon2.PasswordHasher, "verify", counted)
    return made


def test_a_made_up_name_runs_one_argon2id_check(signing_in: SignIn, checks: list[str]):
    signing_in(name="alex")

    assert [check.startswith("$argon2id$") for check in checks] == [True]


def test_an_attempt_during_the_wait_checks_no_password(signing_in: SignIn, checks: list[str]):
    signing_in.fail(3)
    checks.clear()

    signing_in()

    assert checks == []


@pytest.mark.parametrize(
    "names", [("ann",) * 8, ("alex", "sam", "kim", "lee", "max", "noa", "ray", "zoe")], ids=["one-name", "one-address"]
)
def test_attempts_at_the_same_time_check_3_passwords_before_the_wait(
    signing_in: SignIn, checks: list[str], names: tuple[str, ...]
):
    """Counting, checking and recording go in one transaction, one attempt
    at a time for a name or an address, so a burst cannot all count zero."""
    start = threading.Barrier(len(names))

    def attempt(name: str) -> bool:
        start.wait()
        return signing_in(name, WRONG)

    with ThreadPoolExecutor(len(names)) as pool:
        list(pool.map(attempt, names))

    assert len(checks) == 3


# -- old attempts go -------------------------------------------------------------


def old_attempts(database_url: str, context: Context, count: int) -> None:
    with psycopg.connect(database_url) as connection:
        for _ in range(count):
            connection.execute(
                "INSERT INTO fcon.sign_in_attempt (tenant_id, id, name, address, outcome, created_at, created_by)"
                " VALUES (%s, %s, 'alex', %s, 'refused', %s, 'system:anonymous')",
                (context.tenant_id, new_id(), ADDRESS, NOW - timedelta(days=1, seconds=1)),
            )


def test_a_sign_in_removes_attempts_older_than_a_day(signing_in: SignIn, database_url: str, anonymous: Context):
    old_attempts(database_url, anonymous, 2)

    signing_in()

    assert outcomes(database_url, anonymous) == ["succeeded"]


def test_a_sign_in_removes_at_most_100_old_attempts(signing_in: SignIn, database_url: str, anonymous: Context):
    old_attempts(database_url, anonymous, 101)

    signing_in()

    assert outcomes(database_url, anonymous) == ["refused", "succeeded"]


def test_attempts_within_a_day_stay(signing_in: SignIn, database_url: str, anonymous: Context):
    signing_in.fail(1)
    signing_in.later(24 * 60 * 60)

    signing_in()

    assert outcomes(database_url, anonymous) == ["refused", "succeeded"]
