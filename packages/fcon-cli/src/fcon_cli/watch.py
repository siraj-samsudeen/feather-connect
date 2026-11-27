"""The database watch (design decision 1): fcon-server's check, every few seconds in a background thread.

The check comes with the port probe that names the cause. The watch logs through the error helper when a problem
starts, once a minute while it lasts, and when it ends, so a person reading the log knows why the server is not
ready, and when it is again. What is worth knowing about a usable database (an upgrade from a newer version, no ICU
collation, few audit months ahead) it says once.
"""

import logging
import threading
import time
from collections.abc import Callable

from fcon_cli import problems
from fcon_cli.logs import log_problem
from fcon_cli.problems import Problem
from fcon_server.database import DatabaseCheck, diagnose_database

log = logging.getLogger("fcon.database")

INTERVAL_S = 5.0
REPEAT_S = 60.0  # a problem that lasts is said again this often
STOP_WAIT_S = 1.0  # a check in progress may take longer; the thread is a daemon


class DatabaseWatch:
    """Checks the database in the background and logs what is news: a problem, its end, and each note once."""

    def __init__(
        self,
        database_url: str,
        check: Callable[[str], DatabaseCheck] = diagnose_database,
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
        self._noted: set[Problem] = set()  # the notes said already: each once
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def look(self) -> None:
        """One check, and a log line if what it found is news."""
        try:
            check = self._check(self._url)
        except Exception:  # noqa: BLE001 - a bug in the check must not end the watch
            self._say(problems.bug(), exc_info=True)
            return
        if check.problem is None:
            if self._problem is not None or not self._seen:
                log.info(problems.database_usable(check, again=self._problem is not None))
            self._problem = None
            for note in problems.database_notes(check):
                if note not in self._noted:
                    log_problem(log, note)
                    self._noted.add(note)
        else:
            self._say(problems.database_problem(check))
        self._seen = True

    def _say(self, problem: Problem, exc_info: bool = False) -> None:
        """Log a problem (a bug in the check too) when it starts, and once every REPEAT_S while it lasts."""
        now = self._clock()
        if problem != self._problem or now - self._said_at >= REPEAT_S:
            log_problem(log, problem, exc_info=exc_info)
            self._problem, self._said_at = problem, now

    def _run(self) -> None:
        """Look, then wait `interval_s`, until the watch is stopped."""
        while True:
            self.look()
            if self._stopped.wait(self._interval_s):
                return

    def start(self) -> None:
        """Start watching in a daemon thread named database-watch."""
        self._thread = threading.Thread(target=self._run, name="database-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop watching, and wait up to STOP_WAIT_S for a check in progress to end."""
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=STOP_WAIT_S)

    def running(self) -> bool:
        """Whether the background thread is still watching."""
        return self._thread is not None and self._thread.is_alive()
