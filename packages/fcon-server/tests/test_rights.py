"""Rights are checked in one place (design point 2, ADR 0016): a table maps
each action to the least role it needs."""

import pytest

from fcon_server.store.context import Context
from fcon_server.users.rights import RIGHTS, Action, Caller, NotAllowedError, Role, require

CONTEXT = Context(tenant_id="default", actor="user:1", request_id="r-1")


def test_the_roles_rise_from_viewer_to_administrator():
    assert sorted(Role, key=lambda role: role.rank) == [
        Role.VIEWER,
        Role.OPERATOR,
        Role.DEVELOPER,
        Role.ADMINISTRATOR,
    ]


def test_every_action_names_the_least_role_it_needs():
    assert set(RIGHTS) == set(Action)


def test_a_role_at_the_least_one_is_allowed():
    require(Caller(CONTEXT, Role.VIEWER), Action.SEE_OVERVIEW)


def test_a_higher_role_is_allowed():
    require(Caller(CONTEXT, Role.ADMINISTRATOR), Action.SEE_OVERVIEW)


def test_a_lower_role_is_refused():
    with pytest.raises(NotAllowedError):
        require(Caller(CONTEXT, Role.OPERATOR), Action.MANAGE_USERS)
