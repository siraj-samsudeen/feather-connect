"""Rights, checked in one place (design point 2, ADR 0016): `RIGHTS` maps
each action to the least role it needs, and `require` checks a caller
against it, in the service layer that the dashboard, the API and the
command line all call. The role is read fresh on each request."""

from dataclasses import dataclass
from enum import StrEnum

from fcon_server.store.context import Context


class Role(StrEnum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    ADMINISTRATOR = "administrator"

    @property
    def rank(self) -> int:
        return list(Role).index(self)


class Action(StrEnum):
    SEE_OVERVIEW = "see the overview"
    MANAGE_USERS = "manage users"


RIGHTS = {
    Action.SEE_OVERVIEW: Role.VIEWER,
    Action.MANAGE_USERS: Role.ADMINISTRATOR,
}


@dataclass(frozen=True)
class Caller:
    """Who asks: the request's or command's context, and the role it acts with."""

    context: Context
    role: Role


class NotAllowedError(Exception):
    def __init__(self, action: Action) -> None:
        super().__init__(f"not allowed to {action}")
        self.action = action


def require(caller: Caller, action: Action) -> None:
    if caller.role.rank < RIGHTS[action].rank:
        raise NotAllowedError(action)
