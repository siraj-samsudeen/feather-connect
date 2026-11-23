"""Managing users (design points 2 and 10): the list, disabling, enabling
and a new role, for `fcon users` now and the dashboard's pages later. Each
change is a store write, so it is audited; disabling ends every session of
the user at once.

Always an administrator (R10.13): the last active administrator is never
disabled or demoted. The check runs in the same transaction as the change,
on rows locked in the tenant in id order (convention 13): the user changed
and every active administrator. Of two administrators demoting each other at
once, the second waits for the first, then sees its change and is refused.
A refusal is audited as `refused` (decision 3)."""

from dataclasses import dataclass
from uuid import UUID

from fcon_server.store.clock import Clock
from fcon_server.store.tables import USER
from fcon_server.store.transaction import Store
from fcon_server.users.accounts import ACTIVE
from fcon_server.users.rights import Action, Caller, Role, require
from fcon_server.users.rules import normal_name
from fcon_server.users.sessions import end_sessions

DISABLED = "disabled"


@dataclass(frozen=True)
class ListedUser:
    name: str
    display_name: str | None
    role: Role
    state: str


class NoSuchUserError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"no user is named {name!r}")
        self.name = name


class LastAdministratorError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(only_administrator(name))
        self.name = name


def only_administrator(name: str) -> str:
    return f"{name} is the only administrator; make another one first."


@dataclass(frozen=True)
class _Listed:
    name: str
    display_name: str | None
    role: str
    state: str


_LIST = """
    SELECT name, display_name, role, state FROM fcon.user
    WHERE tenant_id = %(tenant_id)s
    ORDER BY name COLLATE "und-x-icu"
"""


def list_users(store: Store, caller: Caller) -> list[ListedUser]:
    require(store, caller, Action.MANAGE_USERS)
    with store.transaction(caller.context) as tx:
        found = tx.fetch_all(_Listed, _LIST)
    return [ListedUser(row.name, row.display_name, Role(row.role), row.state) for row in found]


@dataclass(frozen=True)
class _Locked:
    id: UUID
    name: str
    role: str
    state: str
    row_version: int

    @property
    def is_active_administrator(self) -> bool:
        return self.role == Role.ADMINISTRATOR and self.state == ACTIVE


# The user changed, and every active administrator: locked in id order.
_LOCK = """
    SELECT id, name, role, state, row_version FROM fcon.user
    WHERE tenant_id = %(tenant_id)s
        AND (name = %(name)s OR (role = 'administrator' AND state = 'active'))
    ORDER BY id
    FOR UPDATE
"""


def _change(
    store: Store,
    caller: Caller,
    typed_name: str,
    *,
    role: Role | None = None,
    state: str | None = None,
    clock: Clock | None = None,
) -> bool:
    """Sets the user's role or state; False when it was so already. With a
    clock, every session of the user ends too."""
    require(store, caller, Action.MANAGE_USERS)
    name = normal_name(typed_name)
    with store.transaction(caller.context) as tx:
        locked = tx.fetch_all(_Locked, _LOCK, {"name": name})
        target = next((row for row in locked if row.name == name), None)
        if target is None:
            raise NoSuchUserError(name)
        after = _Locked(target.id, name, role or target.role, state or target.state, target.row_version)
        if (after.role, after.state) == (target.role, target.state):
            return False
        others = [row for row in locked if row.id != target.id and row.is_active_administrator]
        refused = target.is_active_administrator and not after.is_active_administrator and not others
        if refused:
            tx.refuse(USER, str(target.id), only_administrator(name))
        else:
            tx.update(USER, {"id": target.id}, {"role": after.role, "state": after.state}, target.row_version)
            if clock is not None:
                end_sessions(tx, target.id, clock.now())
    if refused:
        raise LastAdministratorError(name)
    return True


def disable_user(store: Store, clock: Clock, caller: Caller, name: str) -> bool:
    """True once disabled, with every session ended; False when it was already."""
    return _change(store, caller, name, state=DISABLED, clock=clock)


def enable_user(store: Store, caller: Caller, name: str) -> bool:
    return _change(store, caller, name, state=ACTIVE)


def set_role(store: Store, caller: Caller, name: str, role: Role) -> bool:
    return _change(store, caller, name, role=role)
