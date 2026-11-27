"""/readyz's check, shared: requests that come together wait for one check.

A result is reused for a second, so a flood of requests opens no more database
connections than one request a second does.
"""

import asyncio
import threading

from fcon_server.database import DatabaseAddress, DatabaseCheck
from fcon_server.health import SharedCheck

USABLE = DatabaseCheck(address=DatabaseAddress(host="db.internal", port="5432", dbname="feather", user="feather"))


class Database:
    """A check that counts its calls and, if asked, waits to be let go."""

    def __init__(self) -> None:
        self.calls = 0
        self.let_go = threading.Event()
        self.let_go.set()
        self.now = 0.0

    def check(self) -> DatabaseCheck:
        self.calls += 1
        self.let_go.wait(timeout=5)
        return USABLE

    def clock(self) -> float:
        return self.now


def shared(database: Database, answer_within_s: float = 2.0) -> SharedCheck:
    return SharedCheck(database.check, answer_within_s=answer_within_s, clock=database.clock)


def test_requests_that_come_together_share_one_check():
    database = Database()
    database.let_go.clear()
    check = shared(database)

    async def ten_requests() -> list[DatabaseCheck | None]:
        waiting = [asyncio.create_task(check.result()) for _ in range(10)]
        await asyncio.sleep(0.1)
        database.let_go.set()
        return await asyncio.gather(*waiting)

    assert (asyncio.run(ten_requests()), database.calls) == ([USABLE] * 10, 1)


def test_a_result_is_reused_within_a_second():
    database = Database()
    check = shared(database)

    asyncio.run(check.result())
    database.now = 0.9
    asyncio.run(check.result())

    assert database.calls == 1


def test_a_result_a_second_old_is_checked_again():
    database = Database()
    check = shared(database)

    asyncio.run(check.result())
    database.now = 1.0
    asyncio.run(check.result())

    assert database.calls == 2


def test_a_check_that_does_not_answer_in_time_gives_no_result():
    database = Database()
    database.let_go.clear()
    check = shared(database, answer_within_s=0.05)

    try:
        assert asyncio.run(check.result()) is None
    finally:
        database.let_go.set()
