"""The `fcon` command.

Every problem it stops for is said through the error helper (fcon_cli.problems) on stderr, with exit code 2.
"""

import argparse
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, NoReturn

from fcon_cli import catalog as catalog_commands
from fcon_cli import operator_settings as settings_commands
from fcon_cli import problems
from fcon_cli import users as user_commands
from fcon_cli.db import show_status, upgrade_database
from fcon_cli.logs import configure_logging
from fcon_cli.problems import ProblemError
from fcon_cli.server import run_server
from fcon_cli.settings import Settings, load_database_settings, load_settings
from fcon_server.store.clock import Clock, SystemClock
from fcon_server.users.rights import Role

PROBLEM_EXIT = 2  # a mistake only a person can fix
BUG_EXIT = 1


TEXT_WIDTH = 100  # usage and help wrap here, whatever the terminal's width


class Formatter(argparse.HelpFormatter):
    """argparse's help layout, wrapped at TEXT_WIDTH whatever the terminal's width."""

    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=TEXT_WIDTH)


class Parser(argparse.ArgumentParser):
    """argparse, with its usage errors said through the error helper.

    Its text is the same on a terminal, in CI and in a log: no colour (Python 3.14 colours it when FORCE_COLOR is set)
    and a fixed width.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs["color"] = False
        kwargs.setdefault("formatter_class", Formatter)
        super().__init__(**kwargs)

    def error(self, message: str) -> NoReturn:
        """Stop with a usage problem: argparse's message and the command's usage."""
        raise ProblemError(problems.usage(message, self.format_usage()))


def _parser() -> argparse.ArgumentParser:
    """The command line's parser: `server`, `db`, `users`, `catalog` and `settings`, each with its own commands."""
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
    users_commands.add_parser("list", help="list the users, with their role and state")
    disable = users_commands.add_parser("disable", help="disable a user: every session of theirs ends at once")
    disable.add_argument("name", help="the user's name")
    enable = users_commands.add_parser("enable", help="let a disabled user sign in again")
    enable.add_argument("name", help="the user's name")
    set_role = users_commands.add_parser("set-role", help="give a user another role, from their next page")
    set_role.add_argument("name", help="the user's name")
    set_role.add_argument("role", choices=[r.value for r in Role], help="the new role")
    catalog = commands.add_parser("catalog", help="record what a package version declares, or list the catalog")
    catalog_commands_parser = catalog.add_subparsers(dest="catalog_command", required=True, metavar="command")
    record = catalog_commands_parser.add_parser(
        "record", help="record the flows, datasets and routes a package version's definitions file declares"
    )
    record.add_argument("file", help="the definitions file: JSON in UTF-8, at most 1 MB")
    catalog_commands_parser.add_parser("list", help="list every flow, dataset and route the code declares now")
    _add_settings_parser(commands)
    return parser


def _add_settings_parser(commands: Any) -> None:
    """`fcon settings`: show, set, clear and list the operator's settings of flows, datasets and routes."""
    settings = commands.add_parser("settings", help="see and change the operator's settings of the catalog")
    settings_parser = settings.add_subparsers(dest="settings_command", required=True, metavar="command")
    show = settings_parser.add_parser("show", help="show every setting of a flow, dataset or route, and who set it")
    show.add_argument("name", help="the flow's, dataset's or route's full name")
    change = settings_parser.add_parser("set", help="set the operator's value of a setting")
    change.add_argument("name", help="the flow's, dataset's or route's full name")
    change.add_argument("setting", help="the setting's name, such as look-back")
    change.add_argument("value", help="the value, such as 3d")
    clear = settings_parser.add_parser(
        "clear", help="clear the operator's value: the code's or the default is in force"
    )
    clear.add_argument("name", help="the flow's, dataset's or route's full name")
    clear.add_argument("setting", help="the setting's name, such as look-back")
    for each in (change, clear):
        each.add_argument("--reason", help="why, for the audit log (needed when FCON_PROTECTED is on)")
    settings_parser.add_parser("list", help="list every value operators have set, flagged when no longer in the code")


def _users_command(args: argparse.Namespace) -> None:
    """Run the `fcon users` command in `args` against the database the settings name."""
    settings = load_database_settings(os.environ, Path.cwd())
    match args.users_command:
        case "add":
            role = Role.ADMINISTRATOR if args.admin else Role(args.role or Role.VIEWER)
            user_commands.add(settings, args.name, role, args.display_name, sys.stdin, sys.stdout)
        case "list":
            user_commands.show_list(settings, sys.stdout)
        case "disable":
            user_commands.disable(settings, args.name, sys.stdout)
        case "enable":
            user_commands.enable(settings, args.name, sys.stdout)
        case _:
            user_commands.change_role(settings, args.name, Role(args.role), sys.stdout)


def _catalog_command(args: argparse.Namespace) -> None:
    """Run the `fcon catalog` command in `args` against the database the settings name.

    The catalog's log lines (one per recording, a warning per flagged value) go to stderr.
    """
    settings = load_database_settings(os.environ, Path.cwd())
    configure_logging("", sys.stderr)
    if args.catalog_command == "record":
        catalog_commands.record_file(settings, args.file, sys.stdout)
    else:
        catalog_commands.show_list(settings, sys.stdout)


def _settings_command(args: argparse.Namespace) -> None:
    """Run the `fcon settings` command in `args` against the database the settings name."""
    settings = load_database_settings(os.environ, Path.cwd())
    match args.settings_command:
        case "show":
            settings_commands.show(settings, args.name, sys.stdout)
        case "set":
            settings_commands.set_value(settings, (args.name, args.setting, args.value), args.reason, sys.stdout)
        case "clear":
            settings_commands.clear(settings, args.name, args.setting, args.reason, sys.stdout)
        case _:
            settings_commands.show_list(settings, sys.stdout)


def _database_command(command: str, clock: Clock) -> None:
    """Run `fcon db upgrade`, or `fcon db status` for any other command, against the database the settings name."""
    settings = load_database_settings(os.environ, Path.cwd())
    if command == "upgrade":
        upgrade_database(settings, clock, sys.stdout, sys.stderr)
    else:
        show_status(settings, sys.stdout)


def main(
    argv: Sequence[str] | None = None, serve: Callable[[Settings], None] = run_server, clock: Clock | None = None
) -> int:
    """Run the command in `argv` (else the process's arguments) and give its exit code.

    0 when it succeeds, 2 for a problem a person can fix, 1 for a bug, said on stderr with its traceback. `serve`
    starts the server once the settings are read, and `clock` says when upgrades ran (a test gives its own of each).
    """
    try:
        args = _parser().parse_args(argv)
        if args.command == "db":
            _database_command(args.db_command, clock or SystemClock())
            return 0
        if args.command == "users":
            _users_command(args)
            return 0
        if args.command == "catalog":
            _catalog_command(args)
            return 0
        if args.command == "settings":
            _settings_command(args)
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
    """Run the command and end the process with its exit code."""
    sys.exit(main())
