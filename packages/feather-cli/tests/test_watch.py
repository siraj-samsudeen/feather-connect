"""The database watch: the server's check every few seconds, in the
background; it logs through the error helper when a problem starts, once a
minute while it lasts, and when it ends."""

import logging
import threading
from collections.abc import Iterator

import pytest

from feather_cli import problems
from feather_cli.watch import DatabaseWatch
from feather_server.database import DatabaseAddress, DatabaseCheck
from feather_server.database import Problem as Kind

URL = "postgresql://feather:secret@127.0.0.1:5442/feather_issue_4"
ADDRESS = DatabaseAddress(host="127.0.0.1", port="5442", dbname="feather_issue_4", user="feather")
USABLE = DatabaseCheck(address=ADDRESS)
REFUSED = DatabaseCheck(address=ADDRESS, problem=Kind.UNREACHABLE, reason="connection refused")
MISSING = DatabaseCheck(address=ADDRESS, problem=Kind.DATABASE_MISSING)


class Database:
    """The answers the check gives, one per look, and the time of each look."""

    def __init__(self, *answers: tuple[float, DatabaseCheck]) -> None:
        self.answers = list(answers)
        self.now = 0.0
        self.urls: list[str] = []

    def check(self, url: str) -> DatabaseCheck:
        self.urls.append(url)
        self.now, answer = self.answers.pop(0)
        return answer

    def clock(self) -> float:
        return self.now


def watched(database: Database) -> DatabaseWatch:
    return DatabaseWatch(URL, check=database.check, clock=database.clock)


def look_at_every_answer(database: Database) -> None:
    watch = watched(database)
    while database.answers:
        watch.look()


def logged(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(record.levelno, record.getMessage()) for record in caplog.records]


@pytest.fixture(autouse=True)
def capture_info(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    caplog.set_level(logging.INFO)
    yield


def test_it_checks_the_database_the_settings_name():
    database = Database((0, USABLE))

    look_at_every_answer(database)

    assert database.urls == [URL]


def test_a_usable_database_is_logged_as_ready(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, USABLE)))

    assert logged(caplog) == [(logging.INFO, problems.database_usable(USABLE))]


def test_a_problem_is_logged_when_it_starts(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, REFUSED)))

    assert logged(caplog) == [(logging.WARNING, problems.database_problem(REFUSED).text())]


def test_a_problem_is_not_repeated_within_a_minute(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, REFUSED), (5, REFUSED), (59, REFUSED)))

    assert len(caplog.records) == 1


def test_a_problem_that_lasts_is_logged_again_once_a_minute(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, REFUSED), (30, REFUSED), (60, REFUSED), (90, REFUSED), (120, REFUSED)))

    assert len(caplog.records) == 3


def test_another_problem_is_logged_at_once(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, REFUSED), (5, MISSING)))

    assert logged(caplog)[1] == (logging.WARNING, problems.database_problem(MISSING).text())


def test_the_end_of_a_problem_is_logged(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, REFUSED), (5, USABLE)))

    assert logged(caplog)[1] == (logging.INFO, problems.database_usable(USABLE, again=True))


def test_a_database_that_stays_usable_is_not_logged_again(caplog: pytest.LogCaptureFixture):
    look_at_every_answer(Database((0, USABLE), (5, USABLE), (65, USABLE)))

    assert len(caplog.records) == 1


def test_the_watch_names_a_refused_port_as_refused(free_port: int, caplog: pytest.LogCaptureFixture):
    """On Windows the driver reports a refused port as a timeout: the watch
    probes the port to tell the two apart."""
    DatabaseWatch(f"postgresql://feather:feather@127.0.0.1:{free_port}/feather").look()

    assert "(connection refused)" in caplog.records[0].getMessage()


def test_a_bug_in_the_check_is_logged_as_one_with_its_traceback(caplog: pytest.LogCaptureFixture):
    def broken(_url: str) -> DatabaseCheck:
        raise RuntimeError("a bug in the check")

    DatabaseWatch(URL, check=broken).look()

    record = caplog.records[0]
    assert (record.getMessage(), record.exc_info is not None) == (problems.bug().text(), True)


def test_a_bug_that_lasts_is_logged_again_once_a_minute(caplog: pytest.LogCaptureFixture):
    now = [0.0]

    def broken(_url: str) -> DatabaseCheck:
        raise RuntimeError("a bug in the check")

    watch = DatabaseWatch(URL, check=broken, clock=lambda: now[0])
    for now[0] in (0.0, 5.0, 30.0, 60.0):
        watch.look()

    assert len(caplog.records) == 2


def test_it_looks_again_and_again_in_the_background_until_stopped():
    looked_twice = threading.Event()
    looks: list[str] = []

    def check(url: str) -> DatabaseCheck:
        looks.append(url)
        if len(looks) == 2:
            looked_twice.set()
        return USABLE

    watch = DatabaseWatch(URL, check=check, interval_s=0.01)
    watch.start()
    assert looked_twice.wait(timeout=5)
    watch.stop()

    assert not watch.running()


def test_a_watch_never_started_stops_at_once():
    watch = DatabaseWatch(URL, check=Database().check)

    watch.stop()

    assert not watch.running()
