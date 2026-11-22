"""`fcon server`: binds the port itself, starts the database watch, then
runs Uvicorn on that socket in the same process, one process per container."""

import errno
import ipaddress
import logging
import signal
import socket
from contextlib import ExitStack
from types import FrameType
from typing import NoReturn

import uvicorn

from fcon_cli import problems
from fcon_cli.first_admin import FirstAdministrator
from fcon_cli.logs import log_problem
from fcon_cli.problems import Problem, ProblemError
from fcon_cli.settings import Settings
from fcon_cli.watch import DatabaseWatch
from fcon_server.app import create_app
from fcon_server.signing import SecretKeys
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import FIRST_ADMIN_ACTOR, add_first_administrator
from fcon_server.users.tenant import request_tenant

log = logging.getLogger("fcon")

# Windows lets a second program share a port bound with SO_REUSEADDR, which
# Uvicorn's own binding sets: there the port is bound for exclusive use.
_ADDRESS_OPTION = getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR)

# What a host or a person at a terminal sends to stop it. Uvicorn shuts down
# gracefully, then raises the signal again to the handler it found: this one.
_STOP_SIGNALS = [sig for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", None)) if sig is not None]


# Windows has its own numbers for these, beside the C library's.
_IN_USE = {errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", errno.EADDRINUSE)}
_NOT_ALLOWED = {errno.EACCES, getattr(errno, "WSAEACCES", errno.EACCES)}
_NOT_HERE = {errno.EADDRNOTAVAIL, getattr(errno, "WSAEADDRNOTAVAIL", errno.EADDRNOTAVAIL)}


def listen_problem(err: OSError, host: str, port: int) -> Problem | None:
    """What a person can fix about a failure to listen; None for anything else."""
    if err.errno in _IN_USE:
        return problems.port_taken(host, port)
    if err.errno in _NOT_ALLOWED:
        return problems.port_not_allowed(host, port)
    if err.errno in _NOT_HERE:
        return problems.host_not_here(host)
    return None


def _open_and_listen(host: str, port: int) -> socket.socket:
    family, kind, proto, _, address = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0]
    sock = socket.socket(family, kind, proto)
    try:
        sock.setsockopt(socket.SOL_SOCKET, _ADDRESS_OPTION, 1)
        sock.bind(address)
        sock.listen()
    except OSError:
        sock.close()
        raise
    return sock


def bind(host: str, port: int) -> socket.socket:
    """The listening socket, so a taken port is found before Uvicorn starts."""
    try:
        return _open_and_listen(host, port)
    except socket.gaierror:
        raise ProblemError(problems.host_not_here(host)) from None
    except OSError as err:
        problem = listen_problem(err, host, port)
        if problem is None:  # pragma: no cover - no real bind fails otherwise on a test machine; see listen_problem
            raise  # a bug: main reports it as one
        raise ProblemError(problem) from None


def _stop(_signum: int, _frame: FrameType | None) -> NoReturn:
    raise SystemExit(0)


def announce(host: str, port: int) -> None:
    """Where it listens (the socket's own numeric address), and a warning
    when other machines can reach it: it belongs behind the host's HTTPS proxy."""
    log.info("listening on http://%s:%d", host, port)
    if not ipaddress.ip_address(host).is_loopback:
        log_problem(log, problems.listening_beyond_machine(host, port))


def first_administrator(database_url: str, name: str) -> FirstAdministrator:
    """Makes `name` the first administrator, through a connection of its own
    for each try, as `system:first-admin` in the request's tenant."""
    store = Store(OneConnectionEach(database_url, "fcon-first-admin"), SystemClock(), new_id)
    context = Context(tenant_id=request_tenant(), actor=FIRST_ADMIN_ACTOR, request_id=f"first-admin-{new_id()}")
    return FirstAdministrator(name, lambda: add_first_administrator(store, context, name))


def run_server(settings: Settings) -> None:
    sock = bind(settings.host, settings.port)
    host, port = sock.getsockname()[:2]
    for sig in _STOP_SIGNALS:
        signal.signal(sig, _stop)
    config = uvicorn.Config(
        create_app(
            settings.database_url,
            keys=SecretKeys(settings.secret_key, previous=settings.previous_secret_key),
            environment=settings.environment,
            # Plain http works only on this machine; beyond it, behind https (design point 8).
            secure_cookies=not ipaddress.ip_address(host).is_loopback,
            pool_size=settings.pool_size,
            prepare=settings.prepare,
        ),
        log_config=None,  # its lines go through the one logger
        proxy_headers=False,  # trusting a proxy's headers comes with real sign-in
        server_header=False,  # no server name or version for visitors
    )
    # In the background while the server runs: the database watch, and the
    # first administrator when FCON_FIRST_ADMIN names one.
    background: list[DatabaseWatch | FirstAdministrator] = [DatabaseWatch(settings.database_url)]
    if settings.first_admin:
        background.append(first_administrator(settings.database_url, settings.first_admin))
    with ExitStack() as running:
        for work in background:
            work.start()
            running.callback(work.stop)
        announce(host, port)
        uvicorn.Server(config).run(sockets=[sock])
