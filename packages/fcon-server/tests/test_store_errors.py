"""The store's own errors (design point 14, decision 2).

Raw database errors never leave it; a deadlock or serialization failure is
"busy, try again", which `Store.run` retries twice and `Store.transaction` never
does; slow statements are logged with their text only.
"""

import itertools
import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import LiteralString

import psycopg
import pytest

from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.errors import AlreadyExistsError, BusyError, StoreError
from fcon_server.store.ids import new_id
from fcon_server.store.tables import TENANT
from fcon_server.store.transaction import ConnectionSource, Store, Transaction

pytestmark = pytest.mark.database

SERIALIZATION_FAILURE = "DO $$ BEGIN RAISE EXCEPTION 'could not serialize' USING ERRCODE = '40001'; END $$"
DEADLOCK = "DO $$ BEGIN RAISE EXCEPTION 'deadlock detected' USING ERRCODE = '40P01'; END $$"


class Unreachable:
    """A connection source whose database does not answer."""

    def __init__(self, port: int) -> None:
        self.port = port

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection[tuple[object, ...]]]:
        with psycopg.connect(host="127.0.0.1", port=self.port, connect_timeout=2) as connection:
            yield connection


def timer(step: float) -> Callable[[], float]:
    """A timer for the store: each reading is `step` seconds after the last."""
    counter = itertools.count()
    return lambda: next(counter) * step


def test_a_row_written_twice_already_exists(store: Store, tenant: Context):
    with pytest.raises(AlreadyExistsError, match="already exists"), store.transaction(tenant) as tx:
        tx.insert(TENANT, {"kind": "production"})


def test_any_other_database_error_is_the_stores_own(store: Store, tenant: Context):
    with pytest.raises(StoreError) as raised, store.transaction(tenant) as tx:
        tx.execute("SELECT 1 / 0")

    assert str(raised.value) == "the database could not do this"


def test_the_stores_own_error_keeps_the_drivers_as_its_cause(store: Store, tenant: Context):
    with pytest.raises(StoreError) as raised, store.transaction(tenant) as tx:
        tx.execute("SELECT 1 / 0")

    assert isinstance(raised.value.__cause__, psycopg.errors.DivisionByZero)


def test_a_database_that_does_not_answer_is_the_stores_own_error(free_port: int, tenant: Context):
    store = Store(Unreachable(free_port), SystemClock(), new_id)

    with pytest.raises(StoreError, match="the database could not do this"), store.transaction(tenant):
        pass


@pytest.mark.parametrize("failure", [SERIALIZATION_FAILURE, DEADLOCK], ids=["serialization", "deadlock"])
def test_a_transaction_that_meets_a_conflict_is_busy(store: Store, tenant: Context, failure: LiteralString):
    with pytest.raises(BusyError, match="busy, try again"), store.transaction(tenant) as tx:
        tx.execute(failure)


def failing(times: int, attempts: list[int]) -> Callable[[Transaction], str]:
    """Work that meets a serialization failure on its first `times` runs."""

    def work(tx: Transaction) -> str:
        attempts.append(1)
        if len(attempts) <= times:
            tx.execute(SERIALIZATION_FAILURE)
        return "done"

    return work


def test_run_runs_busy_work_again_until_it_is_done(store: Store, tenant: Context):
    attempts: list[int] = []

    assert store.run(tenant, failing(2, attempts)) == "done"
    assert len(attempts) == 3


def test_run_gives_up_after_two_retries(store: Store, tenant: Context):
    attempts: list[int] = []

    with pytest.raises(BusyError):
        store.run(tenant, failing(3, attempts))
    assert len(attempts) == 3


def test_run_never_retries_another_error(store: Store, tenant: Context):
    attempts: list[int] = []

    def work(tx: Transaction) -> None:
        attempts.append(1)
        tx.execute("SELECT 1 / 0")

    with pytest.raises(StoreError):
        store.run(tenant, work)
    assert len(attempts) == 1


def test_a_statement_over_a_second_is_logged_with_its_text(
    store_source: ConnectionSource, tenant: Context, caplog: pytest.LogCaptureFixture
):
    store = Store(store_source, SystemClock(), new_id, timer=timer(1.5))

    with caplog.at_level(logging.WARNING, logger="fcon.store"), store.transaction(tenant) as tx:
        tx.execute("SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s")

    assert [record.getMessage() for record in caplog.records] == [
        "slow statement, 1.5 s: SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s"
    ]


def test_a_statement_under_a_second_is_not_logged(
    store_source: ConnectionSource, tenant: Context, caplog: pytest.LogCaptureFixture
):
    store = Store(store_source, SystemClock(), new_id, timer=timer(0.5))

    with caplog.at_level(logging.WARNING, logger="fcon.store"), store.transaction(tenant) as tx:
        tx.execute("SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s")

    assert caplog.records == []


def test_the_threshold_for_a_slow_statement_can_be_set(
    store_source: ConnectionSource, tenant: Context, caplog: pytest.LogCaptureFixture
):
    store = Store(store_source, SystemClock(), new_id, slow_after=0.1, timer=timer(0.5))

    with caplog.at_level(logging.WARNING, logger="fcon.store"), store.transaction(tenant) as tx:
        tx.execute("SELECT kind FROM fcon.tenant WHERE tenant_id = %(tenant_id)s")

    assert len(caplog.records) == 1


def test_a_slow_write_is_logged_without_its_values(store_source: ConnectionSource, caplog: pytest.LogCaptureFixture):
    store = Store(store_source, SystemClock(), new_id, timer=timer(1.5))
    context = Context(tenant_id="test-slow" + new_id().hex[:6], actor="system:test", request_id="request-1")

    with caplog.at_level(logging.WARNING, logger="fcon.store"), store.transaction(context) as tx:
        tx.insert(TENANT, {"kind": "sandbox"})

    messages = [record.getMessage() for record in caplog.records]
    assert any("INSERT INTO" in message for message in messages)
    assert not any(context.tenant_id in message or "sandbox" in message for message in messages)
