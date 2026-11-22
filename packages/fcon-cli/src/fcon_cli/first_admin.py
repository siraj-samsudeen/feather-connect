"""The first administrator from FCON_FIRST_ADMIN (design decision 4): tried
when the server starts and, while the database is not ready, again every
5 seconds in a background thread until it is. Only the copy whose row went
in logs the one-time password, once, as a warning."""

import logging
import threading
from collections.abc import Callable

from fcon_cli import problems
from fcon_cli.logs import log_problem
from fcon_server.store.errors import StoreError

log = logging.getLogger("fcon.first_admin")

INTERVAL_S = 5.0
STOP_WAIT_S = 1.0  # a try in progress may take longer; the thread is a daemon

# Makes the administrator: their one-time password, or None when a user exists.
type Make = Callable[[], str | None]


class FirstAdministrator:
    def __init__(self, name: str, make: Make, interval_s: float = INTERVAL_S) -> None:
        self._name = name
        self._make = make
        self._interval_s = interval_s
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def attempt(self) -> bool:
        """One try; False while the database is not ready (the database watch
        says why)."""
        try:
            password = self._make()
        except StoreError:
            return False
        if password is not None:
            log_problem(log, problems.first_admin_made(self._name, password))
        return True

    def _run(self) -> None:
        while not self.attempt():
            if self._stopped.wait(self._interval_s):
                return

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="first-admin", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=STOP_WAIT_S)

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
