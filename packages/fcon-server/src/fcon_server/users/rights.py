"""Rights, checked in one place (design point 2, ADR 0016).

`RIGHTS` maps each action to the least role it needs, and `require` checks a caller against it,
in the service layer that the dashboard, the API and the command line all call. The role is read
fresh on each request. A refusal is audited against the tenant, as the caller (design point 11).
"""

from dataclasses import dataclass
from enum import StrEnum

from fcon_server.store.context import Context
from fcon_server.store.tables import TENANT
from fcon_server.store.transaction import Store


class Role(StrEnum):
    """A user's role, from the least to the most; each has every right of the ones before it."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    DEVELOPER = "developer"
    ADMINISTRATOR = "administrator"

    @property
    def rank(self) -> int:
        """The role's place, from 0 for a viewer up to the administrator's."""
        return list(Role).index(self)


class Action(StrEnum):
    """Something a caller may be allowed to do, as `RIGHTS` names it."""

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
    """The caller's role is below the one the action needs."""

    def __init__(self, action: Action) -> None:
        super().__init__(f"not allowed to {action}")
        self.action = action


def require(store: Store, caller: Caller, action: Action) -> None:
    """Refuses a caller whose role is below the least one `action` needs.

    Raises `NotAllowedError` after writing a `refused` audit record against the tenant, in a
    transaction of its own.
    """
    if caller.role.rank < RIGHTS[action].rank:
        refused = NotAllowedError(action)
        with store.transaction(caller.context) as tx:
            tx.refuse(TENANT, "", str(refused))
        raise refused
