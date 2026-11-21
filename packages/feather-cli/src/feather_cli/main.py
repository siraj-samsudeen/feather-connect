"""The `feather` command. Every problem it stops for is said through the error
helper (feather_cli.problems) on stderr, with exit code 2."""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from feather_cli import problems
from feather_cli.logs import configure_logging
from feather_cli.problems import ProblemError
from feather_cli.server import run_server
from feather_cli.settings import load_settings

PROBLEM_EXIT = 2  # a mistake only a person can fix


class Parser(argparse.ArgumentParser):
    """argparse, with its usage errors said through the error helper."""

    def error(self, message: str) -> NoReturn:
        raise ProblemError(problems.usage(message, self.format_usage()))


def _parser() -> argparse.ArgumentParser:
    parser = Parser(prog="feather", description="Feather Connect's command line.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    server = commands.add_parser("server", help="start the server")
    server.add_argument("--host", help="the address to listen on (FEATHER_HOST, default 127.0.0.1)")
    server.add_argument("--port", type=int, help="the port to listen on (FEATHER_PORT, else PORT, default 8080)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        settings = load_settings(os.environ, Path.cwd(), host=args.host, port=args.port)
    except ProblemError as err:
        print(err.problem.text(), file=sys.stderr)
        return PROBLEM_EXIT
    configure_logging(settings.log_format, sys.stderr)
    run_server(settings)
    # A stop signal ends the server with SystemExit(0) (feather_cli.server), so
    # Uvicorn returns here only if it could not start the app.
    return 1  # pragma: no cover - no test makes Uvicorn fail to start on a bound socket


def entry() -> NoReturn:
    sys.exit(main())
