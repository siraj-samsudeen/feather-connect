"""`feather server`: binds the port itself, then runs Uvicorn on that socket in
the same process, one process per container."""

import logging
import signal
import socket
from types import FrameType
from typing import NoReturn

import uvicorn

from feather_cli.settings import Settings
from feather_server.app import create_app

log = logging.getLogger("feather")

# Windows lets a second program share a port bound with SO_REUSEADDR, which
# Uvicorn's own binding sets: there the port is bound for exclusive use.
_ADDRESS_OPTION = getattr(socket, "SO_EXCLUSIVEADDRUSE", socket.SO_REUSEADDR)

# What a host or a person at a terminal sends to stop it. Uvicorn shuts down
# gracefully, then raises the signal again to the handler it found: this one.
_STOP_SIGNALS = [sig for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGBREAK", None)) if sig is not None]


def bind(host: str, port: int) -> socket.socket:
    """The listening socket, so a taken port is found before Uvicorn starts."""
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


def _stop(signum: int, frame: FrameType | None) -> NoReturn:
    raise SystemExit(0)


def run_server(settings: Settings) -> None:
    sock = bind(settings.host, settings.port)
    host, port = sock.getsockname()[:2]
    for sig in _STOP_SIGNALS:
        signal.signal(sig, _stop)
    config = uvicorn.Config(
        create_app(settings.database_url),
        log_config=None,  # its lines go through the one logger
        proxy_headers=False,  # trusting a proxy's headers comes with real sign-in
        server_header=False,  # no server name or version for visitors
    )
    log.info("listening on http://%s:%d", host, port)
    uvicorn.Server(config).run(sockets=[sock])
