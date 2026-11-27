"""Adding users (design points 1 to 3): the first user of a tenant is always an administrator.

So an install never has users but no administrator (R10.13). A password set for someone else
works for one sign-in (`must_choose_password`), except the first user's: whoever installs the
product types it for themselves, so it is their own.

The first administrator from FCON_FIRST_ADMIN (point 1, decision 4) gets a
random one-time password instead, and only when the tenant has no users;
the row goes in with `ON CONFLICT DO NOTHING`, so of two server copies
starting together only one makes it, and only that one is given the
password to log.
"""

import secrets
from dataclasses import dataclass
from uuid import UUID

from fcon_server.store.context import Context
from fcon_server.store.errors import AlreadyExistsError
from fcon_server.store.tables import USER
from fcon_server.store.transaction import Store
from fcon_server.users.passwords import hash_password
from fcon_server.users.rights import Action, Caller, Role, require
from fcon_server.users.rules import PasswordProblem, normal_name, password_problem, user_name_problem

ACTIVE = "active"
FIRST_ADMIN_ACTOR = "system:first-admin"
ONE_TIME_PASSWORD_BYTES = 18  # 24 characters, none of them a space


@dataclass(frozen=True)
class NewUser:
    """A user an administrator asks to add: the name and password typed, the role, a display name."""

    name: str
    password: str
    role: Role = Role.VIEWER
    display_name: str | None = None


@dataclass(frozen=True)
class AddedUser:
    """The user just added: its id, its name as stored, its role, and whether it must choose a password."""

    id: UUID
    name: str
    role: Role
    must_choose_password: bool


class NameNotAllowedError(Exception):
    """The user name breaks the name rules."""

    def __init__(self, name: str) -> None:
        super().__init__(f"the user name {name!r} is not allowed")
        self.name = name


class NameTakenError(Exception):
    """A user of the tenant has this name already."""

    def __init__(self, name: str) -> None:
        super().__init__(f"the user name {name!r} is taken")
        self.name = name


class WeakPasswordError(Exception):
    """The password breaks a password rule; `problem` says which."""

    def __init__(self, problem: PasswordProblem) -> None:
        super().__init__(f"the password is {problem}")
        self.problem = problem


@dataclass(frozen=True)
class _Exists:
    """Whether the tenant has any user yet."""

    exists: bool


_ANY_USER = "SELECT EXISTS (SELECT 1 FROM fcon.user WHERE tenant_id = %(tenant_id)s) AS exists"


def add_user(store: Store, caller: Caller, new: NewUser) -> AddedUser:
    """Adds a user for an administrator, and gives back what was stored.

    The tenant's first user is made an administrator, whatever role was asked, and keeps the
    password as their own; any later one must choose their own at the first sign-in. Raises
    `NotAllowedError`, `NameNotAllowedError`, `WeakPasswordError` or `NameTakenError`; writes the
    user and its audit record.
    """
    require(store, caller, Action.MANAGE_USERS)
    name = normal_name(new.name)
    if user_name_problem(name) is not None:
        raise NameNotAllowedError(name)
    if (problem := password_problem(new.password, name)) is not None:
        raise WeakPasswordError(problem)
    password_hash = hash_password(new.password)  # before the transaction: it takes a while
    try:
        with store.transaction(caller.context) as tx:
            found = tx.fetch_one(_Exists, _ANY_USER)
            first = not (found and found.exists)
            role = Role.ADMINISTRATOR if first else new.role
            key = tx.insert(
                USER,
                {
                    "name": name,
                    "display_name": new.display_name,
                    "role": role.value,
                    "state": ACTIVE,
                    "password_hash": password_hash,
                    "must_choose_password": not first,
                },
            )
    except AlreadyExistsError:
        raise NameTakenError(name) from None
    return AddedUser(id=UUID(str(key["id"])), name=name, role=role, must_choose_password=not first)


def add_first_administrator(store: Store, context: Context, name: str) -> str | None:
    """Makes the tenant's first administrator, with a random one-time password, unless it has a user.

    Gives the one-time password of the administrator made, or None when the tenant has a user
    already (this start, or another copy, made none). Raises `NameNotAllowedError` for a name the
    rules refuse.
    """
    name = normal_name(name)
    if user_name_problem(name) is not None:
        raise NameNotAllowedError(name)
    password = secrets.token_urlsafe(ONE_TIME_PASSWORD_BYTES)
    password_hash = hash_password(password)  # before the transaction: it takes a while
    with store.transaction(context) as tx:
        found = tx.fetch_one(_Exists, _ANY_USER)
        if found and found.exists:
            return None
        key = tx.insert_if_absent(
            USER,
            {
                "name": name,
                "role": Role.ADMINISTRATOR.value,
                "state": ACTIVE,
                "password_hash": password_hash,
                "must_choose_password": True,
            },
        )
    return None if key is None else password
