"""The `fcon users` commands: `add`, `list`, `disable`, `enable` and `set-role` (design § How it is built).

They call the users service as `system:cli` in the request's tenant (`default` until M2). The password is asked twice
on a terminal, else read as one line of stdin; it is never printed. Every refusal is a problem through the error
helper.
"""

import getpass
from collections.abc import Callable, Generator
from contextlib import contextmanager
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
from fcon_server.users.managing import (
    LastAdministratorError,
    NoSuchUserError,
    disable_user,
    enable_user,
    list_users,
    set_role,
)
from fcon_server.users.rights import Caller, Role
from fcon_server.users.rules import normal_name
from fcon_server.users.tenant import request_tenant

ACTOR = "system:cli"
APPLICATION_NAME = "fcon-cli"

type Ask = Callable[[str], str]


def read_password(stdin: TextIO, ask: Ask = getpass.getpass) -> str:
    """The new user's password: asked twice through `ask` on a terminal, else one line of `stdin`.

    Raises ProblemError when the two typed differ or no password is given.
    """
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
    """The command line as a caller with every right, as `system:cli` in the request's tenant.

    Whoever can run it can reach the database anyway.
    """
    context = Context(tenant_id=request_tenant(), actor=ACTOR, request_id=f"cli-{new_id()}")
    return Caller(context, Role.ADMINISTRATOR)


def _store(settings: DatabaseSettings) -> Store:
    """The store on the app's address; raises ProblemError when the database is not ready for a command."""
    check = diagnose_database(settings.database_url)
    if check.problem is not None:
        raise ProblemError(problems.database_not_ready_for_command(check))
    return Store(OneConnectionEach(settings.database_url, APPLICATION_NAME), SystemClock(), new_id)


def _with_article(role: Role) -> str:
    """The role with its article: "an administrator", "a viewer"."""
    return f"{'an' if role.value[0] in 'aeiou' else 'a'} {role}"


def add(
    settings: DatabaseSettings, name: str, role: Role, display_name: str | None, stdin: TextIO, out: TextIO
) -> None:
    """Add a user with the password read from `stdin`, and say on `out` who was added.

    Raises ProblemError when the database is not ready, no password is given, or the name or password is refused.
    """
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


HEADINGS = ("NAME", "ROLE", "STATE", "DISPLAY NAME")


def show_list(settings: DatabaseSettings, out: TextIO) -> None:
    """Print the users on `out` as a table of name, role, state and display name."""
    listed = list_users(_store(settings), _caller())
    if not listed:
        print("no users yet.", file=out)
        return
    lines = [HEADINGS, *((user.name, user.role.value, user.state, user.display_name or "") for user in listed)]
    widths = [max(len(line[column]) for line in lines) for column in range(len(HEADINGS) - 1)]
    for line in lines:
        cells = [cell.ljust(width) for cell, width in zip(line[:-1], widths, strict=True)]
        print("  ".join([*cells, line[-1]]).rstrip(), file=out)


@contextmanager
def _refusals() -> Generator[None]:
    """Turn the users service's refusals, no such user or the last administrator, into problems."""
    try:
        yield
    except NoSuchUserError as err:
        raise ProblemError(problems.no_such_user(err.name)) from None
    except LastAdministratorError as err:
        raise ProblemError(problems.only_administrator(str(err))) from None


def disable(settings: DatabaseSettings, name: str, out: TextIO) -> None:
    """Disable the user `name`, ending every session of theirs, and say on `out` whether that changed anything."""
    store = _store(settings)
    with _refusals():
        changed = disable_user(store, SystemClock(), _caller(), name)
    name = normal_name(name)
    print(
        f"disabled the user {name}; every session of theirs has ended." if changed else f"{name} is disabled already.",
        file=out,
    )


def enable(settings: DatabaseSettings, name: str, out: TextIO) -> None:
    """Let the disabled user `name` sign in again, and say on `out` whether that changed anything."""
    store = _store(settings)
    with _refusals():
        changed = enable_user(store, _caller(), name)
    name = normal_name(name)
    print(f"enabled the user {name}." if changed else f"{name} is active already.", file=out)


def change_role(settings: DatabaseSettings, name: str, role: Role, out: TextIO) -> None:
    """Give the user `name` the role `role`, and say on `out` whether that changed anything."""
    store = _store(settings)
    with _refusals():
        changed = set_role(store, _caller(), name, role)
    name = normal_name(name)
    print(f"{name} is now {_with_article(role)}." if changed else f"{name} is {_with_article(role)} already.", file=out)
