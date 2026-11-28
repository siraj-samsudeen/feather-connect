"""The operator's settings (design decisions 5 to 9): the value in force, setting and clearing it.

The operator's value is in force, else the code's, else the product's default. A value is set
only to one of its type, only on an entry the code still declares, and, in a protected
environment, only with a reason; every change and every refusal is audited.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest

from fcon_server.catalog.definitions import PackageDefinitions, read_definitions
from fcon_server.catalog.known_settings import BadValueError, DecidedByCodeError, Kind, UnknownSettingError
from fcon_server.catalog.operator_settings import (
    InForce,
    Layer,
    NeedsAReasonError,
    NoSuchEntryError,
    NotInCodeError,
    OperatorValue,
    clear_setting,
    effective_settings,
    list_operator_values,
    set_setting,
)
from fcon_server.catalog.recording import record
from fcon_server.store.clock import FixedClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import ConnectionSource, Store
from fcon_server.users.rights import Caller, NotAllowedError, Role

pytestmark = pytest.mark.database

ORDERS = "shop-flows.orders"
AT = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


def shop(version: str = "1.0", **groups: list[dict[str, Any]]) -> PackageDefinitions:
    """The contract's example package version, its dataset's code giving a look-back of 1d."""
    data: dict[str, Any] = {
        "package": "shop-flows",
        "version": version,
        "flows": [{"name": "shop-flows.daily"}],
        "datasets": [{"name": ORDERS, "key": ["order_id"], "settings": {"look-back": "1d", "batch-size": 5000}}],
        "routes": [{"name": "shop-flows.orders-to-crm", "dataset": ORDERS}],
    }
    return read_definitions(data | groups)


@pytest.fixture
def clocked(store_source: ConnectionSource) -> Store:
    """The store on the session's database, its clock fixed at AT."""
    return Store(store_source, FixedClock(AT), new_id)


@pytest.fixture
def recorded(clocked: Store, tenant: Context) -> Context:
    """A tenant where shop-flows 1.0 has been recorded."""
    record(clocked, Caller(tenant, Role.DEVELOPER), shop())
    return tenant


def operator(context: Context, reason: str | None = None) -> Caller:
    return Caller(replace(context, reason=reason), Role.OPERATOR)


def viewer(context: Context) -> Caller:
    return Caller(context, Role.VIEWER)


def in_force(store: Store, context: Context, setting: str, name: str = ORDERS) -> InForce:
    shown = effective_settings(store, viewer(context), name)
    return next(each for each in shown.settings if each.setting == setting)


def audit(database_url: str, context: Context, action: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(database_url) as connection:
        return connection.execute(
            "SELECT row_key, created_by, reason, after->>'setting', after->>'value' FROM fcon.audit"
            " WHERE tenant_id = %s AND table_name = 'fcon.operator_setting' AND action = %s ORDER BY created_at, id",
            (context.tenant_id, action),
        ).fetchall()


def writes(database_url: str, context: Context) -> int:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT count(*) FROM fcon.audit WHERE tenant_id = %s AND action <> 'refused'", (context.tenant_id,)
        ).fetchone()
    assert row is not None
    return int(row[0])


# -- the value in force -----------------------------------------------------


def test_the_entry_is_shown_with_its_kind_and_package_version(clocked: Store, recorded: Context):
    shown = effective_settings(clocked, viewer(recorded), ORDERS)

    assert (shown.name, shown.kind, shown.package, shown.version, shown.is_in_code) == (
        ORDERS,
        Kind.DATASET,
        "shop-flows",
        "1.0",
        True,
    )


def test_every_setting_of_the_kind_is_shown_in_the_lists_order(clocked: Store, recorded: Context):
    shown = effective_settings(clocked, viewer(recorded), ORDERS)

    assert [each.setting for each in shown.settings][:3] == ["look-back", "full-comparison-schedule", "batch-size"]


def test_the_codes_value_is_in_force_without_an_operator_value(clocked: Store, recorded: Context):
    assert in_force(clocked, recorded, "look-back") == InForce("look-back", "1d", Layer.CODE)


def test_the_products_default_is_in_force_without_a_value_in_the_code(clocked: Store, recorded: Context):
    assert in_force(clocked, recorded, "retries") == InForce("retries", "3", Layer.DEFAULT)


def test_the_operators_value_is_in_force_with_who_set_it_and_when(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    assert in_force(clocked, recorded, "look-back") == InForce("look-back", "3d", Layer.OPERATOR, "system:test", AT)


def test_the_latest_versions_code_value_is_in_force(clocked: Store, recorded: Context):
    record(
        clocked,
        Caller(recorded, Role.DEVELOPER),
        shop("1.1", datasets=[{"name": ORDERS, "settings": {"look-back": "2d"}}]),
    )

    assert in_force(clocked, recorded, "look-back").value == "2d"


def test_an_unknown_name_has_no_settings(clocked: Store, recorded: Context):
    with pytest.raises(NoSuchEntryError):
        effective_settings(clocked, viewer(recorded), "shop-flows.nope")


def test_another_tenants_entry_is_unknown(clocked: Store, recorded: Context, new_tenant: Any):
    with pytest.raises(NoSuchEntryError):
        effective_settings(clocked, viewer(new_tenant()), ORDERS)


def test_an_entry_no_longer_in_the_code_says_so(clocked: Store, recorded: Context):
    record(clocked, Caller(recorded, Role.DEVELOPER), shop("2.0", datasets=[]))

    shown = effective_settings(clocked, viewer(recorded), ORDERS)

    assert (shown.is_in_code, shown.version) == (False, "1.0")


# -- setting a value ----------------------------------------------------------


def test_a_value_is_set_in_its_canonical_spelling(clocked: Store, recorded: Context):
    changed = set_setting(clocked, operator(recorded), ORDERS, "look-back", " 03d ", protected=False)

    assert (changed.value, changed.already) == ("3d", False)


def test_a_set_is_audited_with_its_reason(clocked: Store, recorded: Context, database_url: str):
    set_setting(clocked, operator(recorded, "the source is late"), ORDERS, "look-back", "3d", protected=False)

    assert [row[1:] for row in audit(database_url, recorded, "insert")] == [
        ("system:test", "the source is late", "look-back", "3d")
    ]


def test_setting_it_again_updates_the_same_row(clocked: Store, recorded: Context, database_url: str):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    set_setting(clocked, operator(recorded), ORDERS, "look-back", "4d", protected=False)

    assert [row[4] for row in audit(database_url, recorded, "update")] == ["4d"]


def test_the_same_value_again_is_already_set_and_writes_nothing(clocked: Store, recorded: Context, database_url: str):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    before = writes(database_url, recorded)

    changed = set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    assert (changed.already, writes(database_url, recorded)) == (True, before)


def test_a_wrong_value_is_refused(clocked: Store, recorded: Context):
    with pytest.raises(BadValueError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "three days", protected=False)


def test_a_setting_the_code_decides_is_refused(clocked: Store, recorded: Context):
    with pytest.raises(DecidedByCodeError):
        set_setting(clocked, operator(recorded), ORDERS, "key", "id", protected=False)


def test_a_set_on_an_unknown_name_is_refused(clocked: Store, recorded: Context):
    with pytest.raises(NoSuchEntryError):
        set_setting(clocked, operator(recorded), "shop-flows.nope", "look-back", "3d", protected=False)


def test_a_set_on_a_name_no_longer_in_the_code_is_refused(clocked: Store, recorded: Context):
    record(clocked, Caller(recorded, Role.DEVELOPER), shop("2.0", datasets=[]))

    with pytest.raises(NotInCodeError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)


@pytest.mark.parametrize(
    ("name", "setting", "value", "refused"),
    [
        (ORDERS, "look-back", "three days", "'three days' is not a look-back."),
        (ORDERS, "key", "id", "the key of a dataset is decided by the code."),
        (ORDERS, "colour", "red", "a dataset has no setting named colour."),
        ("shop-flows.nope", "look-back", "3d", "no flow, dataset or route is named shop-flows.nope."),
    ],
)
def test_a_refused_set_is_audited(  # noqa: PLR0913  # the fixtures, and one refusal's four facts
    clocked: Store, recorded: Context, database_url: str, name: str, setting: str, value: str, refused: str
):
    with pytest.raises(Exception, match="."):
        set_setting(clocked, operator(recorded), name, setting, value, protected=False)

    assert audit(database_url, recorded, "refused") == [(f"{name}/{setting}", "system:test", refused, None, None)]


def test_a_refused_set_on_a_name_no_longer_in_the_code_is_audited(
    clocked: Store, recorded: Context, database_url: str
):
    record(clocked, Caller(recorded, Role.DEVELOPER), shop("2.0", datasets=[]))

    with pytest.raises(NotInCodeError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    refused = f"{ORDERS} is no longer in the code; its values can be cleared, not set."
    assert audit(database_url, recorded, "refused") == [(f"{ORDERS}/look-back", "system:test", refused, None, None)]


def test_a_refused_clear_is_audited(clocked: Store, recorded: Context, database_url: str):
    with pytest.raises(UnknownSettingError):
        clear_setting(clocked, operator(recorded), ORDERS, "colour", protected=False)

    refused = "a dataset has no setting named colour."
    assert audit(database_url, recorded, "refused") == [(f"{ORDERS}/colour", "system:test", refused, None, None)]


def test_a_protected_environment_refuses_a_set_without_a_reason(clocked: Store, recorded: Context):
    with pytest.raises(NeedsAReasonError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=True)


def test_a_refusal_for_no_reason_writes_nothing(clocked: Store, recorded: Context):
    with pytest.raises(NeedsAReasonError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=True)

    assert in_force(clocked, recorded, "look-back").layer is Layer.CODE


def test_a_refusal_for_no_reason_is_audited(clocked: Store, recorded: Context, database_url: str):
    with pytest.raises(NeedsAReasonError):
        set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=True)

    reason = f"{ORDERS} was not changed: a protected environment needs a reason for every change."
    assert audit(database_url, recorded, "refused") == [(f"{ORDERS}/look-back", "system:test", reason, None, None)]


def test_a_protected_environment_takes_a_set_with_a_reason(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded, "the source is late"), ORDERS, "look-back", "3d", protected=True)

    assert in_force(clocked, recorded, "look-back").value == "3d"


def test_a_viewer_cannot_set_a_value(clocked: Store, recorded: Context):
    with pytest.raises(NotAllowedError):
        set_setting(clocked, viewer(recorded), ORDERS, "look-back", "3d", protected=False)


def test_a_viewers_refused_set_is_audited(clocked: Store, recorded: Context, database_url: str):
    with pytest.raises(NotAllowedError):
        set_setting(clocked, viewer(recorded), ORDERS, "look-back", "3d", protected=False)

    with psycopg.connect(database_url) as connection:
        reasons = connection.execute(
            "SELECT reason FROM fcon.audit WHERE tenant_id = %s AND action = 'refused'", (recorded.tenant_id,)
        ).fetchall()
    assert reasons == [("not allowed to change settings",)]


def test_a_viewer_sees_the_settings(clocked: Store, recorded: Context):
    assert effective_settings(clocked, viewer(recorded), ORDERS).name == ORDERS


# -- clearing a value ---------------------------------------------------------


def test_clearing_puts_the_codes_value_back_in_force(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    cleared = clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False)

    assert (cleared.had_value, cleared.in_force) == (True, InForce("look-back", "1d", Layer.CODE))


def test_clearing_keeps_the_row_with_no_value(clocked: Store, recorded: Context, database_url: str):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False)

    assert [row[4] for row in audit(database_url, recorded, "update")] == [None]


def test_clearing_without_an_operator_value_writes_nothing(clocked: Store, recorded: Context, database_url: str):
    before = writes(database_url, recorded)

    cleared = clear_setting(clocked, operator(recorded), ORDERS, "retries", protected=False)

    assert (cleared.had_value, cleared.in_force.layer, writes(database_url, recorded)) == (False, Layer.DEFAULT, before)


def test_clearing_twice_finds_no_operator_value(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False)

    assert clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False).had_value is False


def test_a_cleared_value_can_be_set_again(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False)

    set_setting(clocked, operator(recorded), ORDERS, "look-back", "5d", protected=False)

    assert in_force(clocked, recorded, "look-back").value == "5d"


def test_a_value_can_be_cleared_on_a_name_no_longer_in_the_code(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    record(clocked, Caller(recorded, Role.DEVELOPER), shop("2.0", datasets=[]))

    assert clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False).had_value is True


def test_clearing_an_unknown_setting_is_refused(clocked: Store, recorded: Context):
    with pytest.raises(UnknownSettingError):
        clear_setting(clocked, operator(recorded), ORDERS, "colour", protected=False)


def test_clearing_on_an_unknown_name_is_refused(clocked: Store, recorded: Context):
    with pytest.raises(NoSuchEntryError):
        clear_setting(clocked, operator(recorded), "shop-flows.nope", "look-back", protected=False)


def test_a_protected_environment_refuses_a_clear_without_a_reason(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded, "why"), ORDERS, "look-back", "3d", protected=True)

    with pytest.raises(NeedsAReasonError):
        clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=True)


def test_a_viewer_cannot_clear_a_value(clocked: Store, recorded: Context):
    with pytest.raises(NotAllowedError):
        clear_setting(clocked, viewer(recorded), ORDERS, "look-back", protected=False)


# -- every operator value -----------------------------------------------------


def test_every_operator_value_is_listed_by_name_then_setting(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    set_setting(clocked, operator(recorded), ORDERS, "batch-size", "100", protected=False)
    set_setting(clocked, operator(recorded), "shop-flows.daily", "retries", "5", protected=False)

    assert list_operator_values(clocked, viewer(recorded)) == [
        OperatorValue("shop-flows.daily", "retries", "5", is_in_code=True),
        OperatorValue(ORDERS, "batch-size", "100", is_in_code=True),
        OperatorValue(ORDERS, "look-back", "3d", is_in_code=True),
    ]


def test_a_cleared_value_is_not_listed(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    clear_setting(clocked, operator(recorded), ORDERS, "look-back", protected=False)

    assert list_operator_values(clocked, viewer(recorded)) == []


def test_a_value_for_a_name_no_longer_in_the_code_is_listed_flagged(clocked: Store, recorded: Context):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)
    record(clocked, Caller(recorded, Role.DEVELOPER), shop("2.0", datasets=[]))

    assert list_operator_values(clocked, viewer(recorded)) == [
        OperatorValue(ORDERS, "look-back", "3d", is_in_code=False)
    ]


def test_another_tenants_values_are_not_listed(clocked: Store, recorded: Context, new_tenant: Any):
    set_setting(clocked, operator(recorded), ORDERS, "look-back", "3d", protected=False)

    assert list_operator_values(clocked, viewer(new_tenant())) == []
