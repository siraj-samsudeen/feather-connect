"""`fcon users add` (design § How it is built): the users service, called
as `system:cli` in the request's tenant (`default` until M2). The password
is asked twice on a terminal, else read as one line of stdin; it is never
printed. Every refusal is a problem through the error helper."""

import getpass
from collections.abc import Callable
from typing import TextIO

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.settings import DatabaseSettings
from fcon_server.database import diagnose_database
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import NameNotAllowedError, NameTakenError, NewUser, WeakPasswordError, add_user
from fcon_server.users.rights import Caller, Role
from fcon_server.users.tenant import request_tenant

ACTOR = "system:cli"
APPLICATION_NAME = "fcon-cli"

type Ask = Callable[[str], str]


def read_password(stdin: TextIO, ask: Ask = getpass.getpass) -> str:
    if stdin.isatty():
        password = ask("Password: ")
        if ask("The same again: ") != password:
            raise ProblemError(problems.passwords_differ())
    else:
        password = stdin.readline().rstrip("\r\n")
    if not password:
        raise ProblemError(problems.no_password())
    return password


def _caller() -> Caller:
    """The command line acts with every right, as whoever can run it can
    reach the database anyway."""
    context = Context(tenant_id=request_tenant(), actor=ACTOR, request_id=f"cli-{new_id()}")
    return Caller(context, Role.ADMINISTRATOR)


def _store(settings: DatabaseSettings) -> Store:
    check = diagnose_database(settings.database_url)
    if check.problem is not None:
        raise ProblemError(problems.database_not_ready_for_command(check))
    return Store(OneConnectionEach(settings.database_url, APPLICATION_NAME), SystemClock(), new_id)


def _with_article(role: Role) -> str:
    return f"{'an' if role.value[0] in 'aeiou' else 'a'} {role}"


def add(
    settings: DatabaseSettings, name: str, role: Role, display_name: str | None, stdin: TextIO, out: TextIO
) -> None:
    store = _store(settings)
    password = read_password(stdin)
    try:
        added = add_user(store, _caller(), NewUser(name, password, role, display_name))
    except NameNotAllowedError as err:
        raise ProblemError(problems.user_name_not_allowed(err.name)) from None
    except NameTakenError as err:
        raise ProblemError(problems.user_name_taken(err.name)) from None
    except WeakPasswordError as err:
        raise ProblemError(problems.weak_password(err.problem)) from None
    print(f"added the user {added.name}, {_with_article(added.role)}.", file=out)
    if added.must_choose_password:
        print("Their password works for one sign-in; then they choose their own.", file=out)
