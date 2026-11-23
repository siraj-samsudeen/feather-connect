"""Choosing one's own password (design points 2 and 3). A password given to
a user (by an administrator, the command line or the first administrator's
setting) works for one sign-in; then the user must choose their own
(`must_choose_password`) before any other page opens. The one chosen follows
the password rules and is typed twice; choosing it clears the flag and ends
every other session of the user, keeping the one it was chosen in."""

from dataclasses import dataclass
from enum import StrEnum

from fcon_server.store.clock import Clock
from fcon_server.store.tables import USER
from fcon_server.store.transaction import Store
from fcon_server.users.passwords import hash_password
from fcon_server.users.rules import PasswordProblem, password_problem
from fcon_server.users.sessions import SignedIn, end_sessions


class ChoiceProblem(StrEnum):
    DIFFERENT = "not the same twice"


class NothingToChooseError(Exception):
    """The user's password is their own already: changing it needs the old one."""


@dataclass(frozen=True)
class _Flag:
    row_version: int
    must_choose_password: bool


_USER_FOR_UPDATE = """
    SELECT row_version, must_choose_password FROM fcon.user
    WHERE tenant_id = %(tenant_id)s AND id = %(id)s
    FOR UPDATE
"""


def choose_password(
    store: Store, clock: Clock, signed_in: SignedIn, password: str, again: str
) -> PasswordProblem | ChoiceProblem | None:
    """None once chosen; otherwise the rule it broke, and nothing changes."""
    if (problem := password_problem(password, signed_in.name)) is not None:
        return problem
    if again != password:
        return ChoiceProblem.DIFFERENT
    password_hash = hash_password(password)  # before the transaction: it takes a while
    with store.transaction(signed_in.caller.context) as tx:
        user = tx.fetch_one(_Flag, _USER_FOR_UPDATE, {"id": signed_in.user_id})
        if user is None or not user.must_choose_password:
            raise NothingToChooseError
        tx.update(
            USER,
            {"id": signed_in.user_id},
            {"password_hash": password_hash, "must_choose_password": False},
            user.row_version,
        )
        end_sessions(tx, signed_in.user_id, clock.now(), keep=signed_in.session_id)
    return None
