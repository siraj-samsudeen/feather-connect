"""The first administrator from FCON_FIRST_ADMIN (design decision 4): tried
at start, and again every few seconds in the background while the database
is not ready; only the copy that made it logs the one-time password."""

import logging
import threading

import pytest

from fcon_cli import problems
from fcon_cli.first_admin import FirstAdministrator
from fcon_server.store.errors import StoreError


class Database:
    """Not ready for the first `not_ready` tries; then it makes the
    administrator, or finds one there already (`gives` None)."""

    def __init__(self, not_ready: int = 0, gives: str | None = "one-time-pw") -> None:
        self.not_ready = not_ready
        self.gives = gives
        self.tries = 0
        self.done = threading.Event()

    def make(self) -> str | None:
        self.tries += 1
        if self.tries <= self.not_ready:
            raise StoreError
        self.done.set()
        return self.gives


def test_the_administrator_made_logs_the_one_time_password(caplog: pytest.LogCaptureFixture):
    FirstAdministrator("ann", Database().make).attempt()

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, problems.first_admin_made("ann", "one-time-pw").text())
    ]


def test_the_log_says_to_sign_in_choose_a_password_and_remove_the_setting():
    assert problems.first_admin_made("ann", "pw").text() == (
        'warning: no administrator yet; made "ann" with a one-time password: pw\n'
        "  Sign in at /sign-in and choose your own password. Remove FCON_FIRST_ADMIN afterwards."
    )


def test_an_administrator_already_there_logs_nothing(caplog: pytest.LogCaptureFixture):
    done = FirstAdministrator("ann", Database(gives=None).make).attempt()

    assert (done, caplog.records) == (True, [])


def test_a_database_not_ready_is_tried_again(caplog: pytest.LogCaptureFixture):
    done = FirstAdministrator("ann", Database(not_ready=1).make).attempt()

    assert (done, caplog.records) == (False, [])


def test_it_tries_in_the_background_until_the_database_is_ready():
    database = Database(not_ready=2)
    first = FirstAdministrator("ann", database.make, interval_s=0.01)

    first.start()
    made = database.done.wait(timeout=5)
    first.stop()

    assert (made, database.tries) == (True, 3)


def test_it_stops_trying_when_asked():
    database = Database(not_ready=1_000_000)
    first = FirstAdministrator("ann", database.make, interval_s=0.01)

    first.start()
    first.stop()
    tries = database.tries

    assert not first.running() and database.tries == tries


def test_stopping_before_it_started_does_nothing():
    first = FirstAdministrator("ann", Database().make)

    first.stop()

    assert not first.running()
