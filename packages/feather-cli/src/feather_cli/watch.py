"""The database watch (design decision 1): feather-server's check, every few
seconds in a background thread. It logs through the error helper when a
problem starts, once a minute while it lasts, and when it ends, so a person
reading the log knows why the server is not ready, and when it is again."""

import logging
import threading
import time
from collections.abc import Callable

from feather_cli import problems
from feather_cli.logs import log_problem
from feather_cli.problems import Problem
from feather_server.database import DatabaseCheck, check_database

log = logging.getLogger("feather.database")

INTERVAL_S = 5.0
REPEAT_S = 60.0  # a problem that lasts is said again this often
STOP_WAIT_S = 1.0  # a check in progress may take longer; the thread is a daemon


class DatabaseWatch:
    def __init__(
        self,
        database_url: str,
        check: Callable[[str], DatabaseCheck] = check_database,
        interval_s: float = INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = database_url
        self._check = check
        self._interval_s = interval_s
        self._clock = clock
        self._seen = False  # whether any look has answered yet
        self._problem: Problem | None = None  # the problem it last said, while it lasts
        self._said_at = 0.0
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def look(self) -> None:
        """One check, and a log line if what it found is news."""
        try:
            check = self._check(self._url)
        except Exception:  # noqa: BLE001 - a bug in the check must not end the watch
            log_problem(log, problems.bug(), exc_info=True)
            return
        if check.problem is None:
            if self._problem is not None or not self._seen:
                log.info(problems.database_usable(check, again=self._problem is not None))
            self._problem = None
        else:
            problem = problems.database_problem(check)
            now = self._clock()
            if problem != self._problem or now - self._said_at >= REPEAT_S:
                log_problem(log, problem)
                self._problem, self._said_at = problem, now
        self._seen = True

    def _run(self) -> None:
        while True:
            self.look()
            if self._stopped.wait(self._interval_s):
                return

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="database-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=STOP_WAIT_S)

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
