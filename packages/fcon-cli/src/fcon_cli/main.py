"""The `fcon` command. Every problem it stops for is said through the error
helper (fcon_cli.problems) on stderr, with exit code 2."""

import argparse
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn

from fcon_cli import problems
from fcon_cli.db import show_status, upgrade_database
from fcon_cli.logs import configure_logging
from fcon_cli.problems import ProblemError
from fcon_cli.server import run_server
from fcon_cli.settings import Settings, load_database_settings, load_settings
from fcon_cli.users import add as add_user
from fcon_server.store.clock import Clock, SystemClock
from fcon_server.users.rights import Role

PROBLEM_EXIT = 2  # a mistake only a person can fix
BUG_EXIT = 1


TEXT_WIDTH = 100  # usage and help wrap here, whatever the terminal's width


class Formatter(argparse.HelpFormatter):
    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=TEXT_WIDTH)


class Parser(argparse.ArgumentParser):
    """argparse, with its usage errors said through the error helper. Its text
    is the same on a terminal, in CI and in a log: no colour (Python 3.14
    colours it when FORCE_COLOR is set) and a fixed width."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["color"] = False
        kwargs.setdefault("formatter_class", Formatter)
        super().__init__(**kwargs)

    def error(self, message: str) -> NoReturn:
        raise ProblemError(problems.usage(message, self.format_usage()))


def _parser() -> argparse.ArgumentParser:
    parser = Parser(prog="fcon", description="Feather Connect's command line.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    server = commands.add_parser("server", help="start the server")
    server.add_argument("--host", help="the address to listen on (FCON_HOST, default 127.0.0.1)")
    server.add_argument("--port", type=int, help="the port to listen on (FCON_PORT, else PORT, default 8080)")
    db = commands.add_parser("db", help="upgrade the database, or see what has been applied")
    db_commands = db.add_subparsers(dest="db_command", required=True, metavar="command")
    db_commands.add_parser(
        "upgrade", help="apply every waiting upgrade (FCON_MIGRATION_DATABASE_URL, else FCON_DATABASE_URL)"
    )
    db_commands.add_parser("status", help="list the upgrades applied, with when they ran, and those waiting")
    users = commands.add_parser("users", help="add the people who sign in to the dashboard")
    users_commands = users.add_subparsers(dest="users_command", required=True, metavar="command")
    add = users_commands.add_parser(
        "add", help="add a user; the password is asked for, or read as one line of stdin when not a terminal"
    )
    add.add_argument("name", help="1 to 64 lowercase letters, digits and . _ - @ +; an email address works")
    role = add.add_mutually_exclusive_group()
    role.add_argument("--admin", action="store_true", help="an administrator (the first user always is)")
    role.add_argument("--role", choices=[r.value for r in Role], help="the user's role (default viewer)")
    add.add_argument("--display-name", help="the name shown beside the user name")
    return parser


def _users_command(args: argparse.Namespace) -> None:
    settings = load_database_settings(os.environ, Path.cwd())
    role = Role.ADMINISTRATOR if args.admin else Role(args.role or Role.VIEWER)
    add_user(settings, args.name, role, args.display_name, sys.stdin, sys.stdout)


def _database_command(command: str, clock: Clock) -> None:
    settings = load_database_settings(os.environ, Path.cwd())
    if command == "upgrade":
        upgrade_database(settings, clock, sys.stdout, sys.stderr)
    else:
        show_status(settings, sys.stdout)


def main(
    argv: Sequence[str] | None = None, serve: Callable[[Settings], None] = run_server, clock: Clock | None = None
) -> int:
    """`serve` starts the server once the settings are read, and `clock` says
    when upgrades ran (a test gives its own of each)."""
    try:
        args = _parser().parse_args(argv)
        if args.command == "db":
            _database_command(args.db_command, clock or SystemClock())
            return 0
        if args.command == "users":
            _users_command(args)
            return 0
        settings = load_settings(os.environ, Path.cwd(), host=args.host, port=args.port)
        configure_logging(settings.log_format, sys.stderr)
        serve(settings)
    except ProblemError as err:
        print(err.problem.text(), file=sys.stderr)
        return PROBLEM_EXIT
    except Exception:  # noqa: BLE001 - any other failure is a bug, said as one
        print(problems.bug().text(), file=sys.stderr)
        print(traceback.format_exc().rstrip(), file=sys.stderr)
        return BUG_EXIT
    # A stop signal ends the server with SystemExit(0) (fcon_cli.server), so
    # Uvicorn returns here only if it could not start the app.
    return BUG_EXIT  # pragma: no cover - no test makes Uvicorn fail to start on a bound socket


def entry() -> NoReturn:
    sys.exit(main())
