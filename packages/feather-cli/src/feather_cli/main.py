"""The `feather` command."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from feather_cli.logs import configure_logging
from feather_cli.server import run_server
from feather_cli.settings import SettingsError, load_settings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="feather", description="Feather Connect's command line.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    server = commands.add_parser("server", help="start the server")
    server.add_argument("--host", help="the address to listen on (FEATHER_HOST, default 127.0.0.1)")
    server.add_argument("--port", type=int, help="the port to listen on (FEATHER_PORT, else PORT, default 8080)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = load_settings(os.environ, Path.cwd(), host=args.host, port=args.port)
    except SettingsError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    configure_logging(os.environ, sys.stderr)
    run_server(settings)
    # A stop signal ends the server with SystemExit(0) (feather_cli.server), so
    # Uvicorn returns here only if it could not start the app.
    return 1  # pragma: no cover - no test makes Uvicorn fail to start on a bound socket


def entry() -> NoReturn:
    sys.exit(main())
