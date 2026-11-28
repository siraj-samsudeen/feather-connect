"""Recording what a package version declares (design decisions 1 to 4 and 7).

One transaction per package version: a stable entry per name, a copy of each definition per
package version, explicit renames, and the operator's values for names the code no longer has
flagged, never dropped.
"""

import logging
from collections.abc import Callable
from typing import Any

import psycopg
import pytest
from psycopg import sql

from fcon_server.catalog.definitions import PackageDefinitions, read_definitions
from fcon_server.catalog.known_settings import Kind
from fcon_server.catalog.listing import ListedEntry, list_catalog
from fcon_server.catalog.recording import (
    ChangedDefinitionsError,
    FlaggedValue,
    KindChangedError,
    RenameAcrossKindsError,
    Renamed,
    counted,
    record,
)
from fcon_server.store.context import Context
from fcon_server.store.tables import OPERATOR_SETTING
from fcon_server.store.transaction import Store
from fcon_server.users.rights import Caller, NotAllowedError, Role

pytestmark = pytest.mark.database

ORDERS = "shop-flows.orders"


def shop(version: str = "1.0", **groups: list[dict[str, Any]]) -> PackageDefinitions:
    """The contract's example package version, with `groups` replacing its lists."""
    data: dict[str, Any] = {
        "package": "shop-flows",
        "version": version,
        "flows": [{"name": "shop-flows.daily"}],
        "datasets": [{"name": ORDERS, "key": ["order_id"], "settings": {"look-back": "1d"}}],
        "routes": [{"name": "shop-flows.orders-to-crm", "dataset": ORDERS}],
    }
    return read_definitions(data | groups)


def developer(context: Context) -> Caller:
    return Caller(context, Role.DEVELOPER)


def names(store: Store, context: Context) -> list[str]:
    return [entry.name for entry in list_catalog(store, Caller(context, Role.VIEWER))]


def count(database_url: str, context: Context, table: str) -> int:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s").format(sql.Identifier(*table.split("."))),
            (context.tenant_id,),
        ).fetchone()
    assert row is not None
    return int(row[0])


def entry_id(database_url: str, context: Context, name: str) -> object:
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT id FROM fcon.catalog_entry WHERE tenant_id = %s AND name = %s", (context.tenant_id, name)
        ).fetchone()
    assert row is not None
    return row[0]


def set_value(store: Store, database_url: str, context: Context, name: str, setting: str, value: str | None) -> None:
    """An operator's value, written through the store as the settings service will."""
    with store.transaction(context) as tx:
        tx.insert(
            OPERATOR_SETTING, {"entry_id": entry_id(database_url, context, name), "setting": setting, "value": value}
        )


def test_the_catalog_lists_what_the_package_version_declares(store: Store, tenant: Context):
    record(store, developer(tenant), shop())

    assert list_catalog(store, Caller(tenant, Role.VIEWER)) == [
        ListedEntry("shop-flows.daily", Kind.FLOW, "shop-flows", "1.0"),
        ListedEntry(ORDERS, Kind.DATASET, "shop-flows", "1.0"),
        ListedEntry("shop-flows.orders-to-crm", Kind.ROUTE, "shop-flows", "1.0"),
    ]


def test_recording_says_how_many_of_each_kind(store: Store, tenant: Context):
    recorded = record(store, developer(tenant), shop())

    assert counted(recorded) == "1 flow, 1 dataset, 1 route"


def test_the_counts_say_plurals_and_noughts(store: Store, tenant: Context):
    recorded = record(
        store, developer(tenant), shop(datasets=[{"name": ORDERS}, {"name": "shop-flows.items"}], routes=[])
    )

    assert counted(recorded) == "1 flow, 2 datasets, 0 routes"


def test_each_package_version_keeps_its_own_copy_of_each_definition(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    record(store, developer(tenant), shop("1.1"))

    assert count(database_url, tenant, "fcon.catalog_definition") == 6


def test_the_definition_is_kept_whole(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop())

    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT definition FROM fcon.catalog_definition WHERE tenant_id = %s AND name = %s",
            (tenant.tenant_id, ORDERS),
        ).fetchone()
    assert row == ({"name": ORDERS, "key": ["order_id"], "settings": {"look-back": "1d"}},)


def test_recording_the_same_version_again_with_the_same_definitions_writes_nothing(
    store: Store, tenant: Context, database_url: str
):
    record(store, developer(tenant), shop())
    audited = count(database_url, tenant, "fcon.audit")

    again = record(store, developer(tenant), shop())

    assert (again.already, count(database_url, tenant, "fcon.audit")) == (True, audited)


def test_a_first_recording_is_not_already_recorded(store: Store, tenant: Context):
    assert record(store, developer(tenant), shop()).already is False


def test_the_same_version_with_other_definitions_is_refused(store: Store, tenant: Context):
    record(store, developer(tenant), shop())

    with pytest.raises(ChangedDefinitionsError):
        record(store, developer(tenant), shop(datasets=[{"name": ORDERS, "key": ["order_number"]}]))


def test_a_refused_version_leaves_the_first_definition(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop())

    with pytest.raises(ChangedDefinitionsError):
        record(store, developer(tenant), shop(datasets=[{"name": ORDERS, "key": ["order_number"]}]))

    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT definition -> 'key' FROM fcon.catalog_definition WHERE tenant_id = %s AND name = %s",
            (tenant.tenant_id, ORDERS),
        ).fetchone()
    assert row == (["order_id"],)


def test_a_later_version_is_the_one_listed(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))
    record(store, developer(tenant), shop("1.1"))

    assert {entry.version for entry in list_catalog(store, Caller(tenant, Role.VIEWER))} == {"1.1"}


def test_an_entry_keeps_its_identity_across_versions(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    first = entry_id(database_url, tenant, ORDERS)

    record(store, developer(tenant), shop("1.1"))

    assert entry_id(database_url, tenant, ORDERS) == first


def test_a_rename_moves_the_entry_to_the_new_name(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    first = entry_id(database_url, tenant, ORDERS)

    record(
        store, developer(tenant), shop("2.0", datasets=[{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}])
    )

    assert entry_id(database_url, tenant, "shop-flows.sales-orders") == first


def test_a_rename_is_reported(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    recorded = record(
        store, developer(tenant), shop("2.0", datasets=[{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}])
    )

    assert recorded.renamed == (Renamed(ORDERS, "shop-flows.sales-orders"),)


def test_the_old_name_is_no_longer_listed_after_a_rename(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    record(
        store, developer(tenant), shop("2.0", datasets=[{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}])
    )

    assert ORDERS not in names(store, tenant)


def test_a_rename_made_in_an_earlier_version_is_not_made_again(store: Store, tenant: Context):
    renamed = [{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}]
    record(store, developer(tenant), shop("1.0"))
    record(store, developer(tenant), shop("2.0", datasets=renamed))

    assert record(store, developer(tenant), shop("2.1", datasets=renamed)).renamed == ()


def test_a_rename_whose_old_name_was_never_here_is_a_new_entry(store: Store, tenant: Context):
    record(
        store, developer(tenant), shop("2.0", datasets=[{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}])
    )

    assert "shop-flows.sales-orders" in names(store, tenant)


def test_a_new_name_without_a_rename_is_a_new_entry(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    first = entry_id(database_url, tenant, ORDERS)

    record(store, developer(tenant), shop("2.0", datasets=[{"name": "shop-flows.sales-orders"}]))

    assert entry_id(database_url, tenant, "shop-flows.sales-orders") != first


def test_a_rename_across_kinds_is_refused(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    with pytest.raises(RenameAcrossKindsError) as refused:
        record(
            store,
            developer(tenant),
            shop("2.0", datasets=[], routes=[{"name": "shop-flows.to-crm", "renamed_from": ORDERS}]),
        )

    assert str(refused.value) == ("shop-flows.to-crm, a route, cannot be renamed from shop-flows.orders, a dataset")


def test_a_name_declared_as_another_kind_is_refused(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    with pytest.raises(KindChangedError) as refused:
        record(store, developer(tenant), shop("2.0", datasets=[], flows=[{"name": ORDERS}]))

    assert str(refused.value) == "shop-flows.orders is a dataset, and cannot become a flow"


def test_a_refused_recording_writes_nothing(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))

    with pytest.raises(KindChangedError):
        record(store, developer(tenant), shop("2.0", datasets=[], flows=[{"name": ORDERS}]))

    assert count(database_url, tenant, "fcon.package_version") == 1


def test_a_name_the_new_version_no_longer_declares_is_not_listed(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    record(store, developer(tenant), shop("2.0", datasets=[]))

    assert ORDERS not in names(store, tenant)


def test_a_name_declared_again_comes_back(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    first = entry_id(database_url, tenant, ORDERS)
    record(store, developer(tenant), shop("2.0", datasets=[]))

    record(store, developer(tenant), shop("3.0"))

    assert (ORDERS in names(store, tenant), entry_id(database_url, tenant, ORDERS)) == (True, first)


def test_an_operator_value_for_a_name_no_longer_declared_is_flagged(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    set_value(store, database_url, tenant, ORDERS, "look-back", "3d")

    recorded = record(store, developer(tenant), shop("2.0", datasets=[]))

    assert recorded.flagged == (FlaggedValue(ORDERS, "look-back"),)


def test_a_cleared_value_is_not_flagged(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    set_value(store, database_url, tenant, ORDERS, "look-back", None)

    assert record(store, developer(tenant), shop("2.0", datasets=[])).flagged == ()


def test_a_value_for_a_name_still_declared_is_not_flagged(store: Store, tenant: Context, database_url: str):
    record(store, developer(tenant), shop("1.0"))
    set_value(store, database_url, tenant, ORDERS, "look-back", "3d")

    assert record(store, developer(tenant), shop("1.1")).flagged == ()


def test_an_operator_value_is_kept_when_its_name_is_no_longer_declared(
    store: Store, tenant: Context, database_url: str
):
    record(store, developer(tenant), shop("1.0"))
    set_value(store, database_url, tenant, ORDERS, "look-back", "3d")

    record(store, developer(tenant), shop("2.0", datasets=[]))

    assert count(database_url, tenant, "fcon.operator_setting") == 1


def test_another_package_leaves_this_ones_entries_alone(store: Store, tenant: Context):
    record(store, developer(tenant), shop("1.0"))

    record(store, developer(tenant), read_definitions({"package": "crm-flows", "version": "1.0"}))

    assert ORDERS in names(store, tenant)


def test_another_tenants_catalog_is_not_listed(store: Store, tenant: Context, new_tenant: Callable[[], Context]):
    record(store, developer(tenant), shop("1.0"))

    assert names(store, new_tenant()) == []


def test_an_operator_cannot_record_the_catalog(store: Store, tenant: Context):
    with pytest.raises(NotAllowedError):
        record(store, Caller(tenant, Role.OPERATOR), shop())


def test_a_recording_is_logged_with_its_counts(store: Store, tenant: Context, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="fcon.catalog"):
        record(store, developer(tenant), shop())

    assert caplog.messages == ["recorded shop-flows 1.0: 1 flow, 1 dataset, 1 route"]


def test_recording_again_is_logged_as_recorded_already(store: Store, tenant: Context, caplog: pytest.LogCaptureFixture):
    record(store, developer(tenant), shop())

    with caplog.at_level(logging.INFO, logger="fcon.catalog"):
        record(store, developer(tenant), shop())

    assert caplog.messages == ["shop-flows 1.0 is recorded already"]


def test_a_flagged_value_is_logged_as_a_warning(
    store: Store, tenant: Context, database_url: str, caplog: pytest.LogCaptureFixture
):
    record(store, developer(tenant), shop("1.0"))
    set_value(store, database_url, tenant, ORDERS, "look-back", "3d")

    with caplog.at_level(logging.WARNING, logger="fcon.catalog"):
        record(store, developer(tenant), shop("2.0", datasets=[]))

    assert caplog.messages == ["the operator's look-back of shop-flows.orders is for a name the code no longer has"]


def test_the_catalog_is_empty_before_anything_is_recorded(store: Store, tenant: Context):
    assert names(store, tenant) == []
