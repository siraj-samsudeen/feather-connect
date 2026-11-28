"""Tests of `fcon catalog record` and `fcon catalog list` (catalog-and-settings, the command line's contract).

They act as `system:cli` in the tenant `default`; every refusal goes through the error helper, exit code 2.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from fcon_cli.main import main
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.migrate import upgrade
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.tables import OPERATOR_SETTING
from fcon_server.store.transaction import Store

pytestmark = pytest.mark.database

ORDERS = "shop-flows.orders"


@pytest.fixture
def database(empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """An upgraded database of the test's own, named by FCON_DATABASE_URL; no .env."""
    upgrade(empty_database_url, SystemClock())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", empty_database_url)
    yield empty_database_url


def shop(version: str = "1.0", **groups: list[dict[str, Any]]) -> dict[str, Any]:
    """The contract's example package version, with `groups` replacing its lists."""
    return {
        "package": "shop-flows",
        "version": version,
        "flows": [{"name": "shop-flows.daily", "settings": {"schedule": "0 6 * * *"}}],
        "datasets": [{"name": ORDERS, "key": ["order_id"], "settings": {"look-back": "1d", "batch-size": 5000}}],
        "routes": [{"name": "shop-flows.orders-to-crm", "dataset": ORDERS, "write_mode": "upsert"}],
    } | groups


def written(data: object, name: str = "shop.json") -> str:
    Path(name).write_text(json.dumps(data), encoding="utf-8")
    return name


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(["catalog", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def record(capsys: pytest.CaptureFixture[str], data: object) -> tuple[int, str, str]:
    return run(capsys, "record", written(data))


def set_value(database_url: str, name: str, setting: str, value: str) -> None:
    """An operator's value in the tenant default, written through the store as the settings service will."""
    store = Store(OneConnectionEach(database_url, "fcon-test"), SystemClock(), new_id)
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            "SELECT id FROM fcon.catalog_entry WHERE tenant_id = 'default' AND name = %s", (name,)
        ).fetchone()
    assert row is not None
    with store.transaction(Context("default", "system:test", "test-1")) as tx:
        tx.insert(OPERATOR_SETTING, {"entry_id": row[0], "setting": setting, "value": value})


def test_recording_says_what_was_recorded(database: str, capsys: pytest.CaptureFixture[str]):
    assert record(capsys, shop())[:2] == (0, "recorded shop-flows 1.0: 1 flow, 1 dataset, 1 route.\n")


def test_recording_acts_as_the_command_line_in_the_default_tenant(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    with psycopg.connect(database) as connection:
        rows = connection.execute("SELECT tenant_id, created_by FROM fcon.package_version").fetchall()
    assert rows == [("default", "system:cli")]


def test_recording_again_says_it_is_recorded_already(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    assert record(capsys, shop())[:2] == (0, "shop-flows 1.0 is recorded already.\n")


def test_the_same_version_with_other_definitions_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    assert record(capsys, shop(datasets=[{"name": ORDERS, "key": ["order_number"]}])) == (
        2,
        "",
        "error: shop-flows 1.0 is recorded already, with other definitions.\n"
        "  A recorded version never changes: give the changed code a new version.\n",
    )


def test_a_rename_is_said_before_what_was_recorded(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    _, out, _ = record(capsys, shop("2.0", datasets=[{"name": "shop-flows.sales-orders", "renamed_from": ORDERS}]))

    assert out == (
        "renamed shop-flows.orders to shop-flows.sales-orders.\nrecorded shop-flows 2.0: 1 flow, 1 dataset, 1 route.\n"
    )


def test_a_value_for_a_name_the_code_no_longer_has_is_warned_of(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())
    set_value(database, ORDERS, "look-back", "3d")

    _, out, _ = record(capsys, shop("2.0", datasets=[]))

    assert out == (
        "recorded shop-flows 2.0: 1 flow, 0 datasets, 1 route.\n"
        "warning: the operator's look-back of shop-flows.orders is for a name the code no longer has.\n"
        "  Clear it with: fcon settings clear shop-flows.orders look-back\n"
    )


def test_a_file_that_is_not_json_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    Path("broken.json").write_text('{"package": ', encoding="utf-8")

    code, _, err = run(capsys, "record", "broken.json")

    assert (code, err.splitlines()) == (
        2,
        [
            "error: broken.json is not a definitions file: it is not JSON (Expecting value at line 1, column 13).",
            "  Give one JSON object: package, version, and lists of flows, datasets and routes.",
        ],
    )


def test_a_file_that_breaks_a_rule_is_refused_saying_what_is_expected(
    database: str, capsys: pytest.CaptureFixture[str]
):
    code, _, err = record(capsys, shop(package="Shop"))

    assert (code, err.splitlines()) == (
        2,
        [
            'error: shop.json is not a definitions file: the package "Shop" is not a package name.',
            "  A package name is 1 to 64 of a-z, 0-9 and -, starting with a letter.",
        ],
    )


def test_a_file_that_cannot_be_read_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "record", "missing.json")

    assert (code, err.splitlines()) == (
        2,
        [
            "error: missing.json is not a definitions file: it cannot be read.",
            "  Give the path of a definitions file, JSON in UTF-8.",
        ],
    )


def test_a_wrong_code_value_is_refused_saying_what_is_expected(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = record(capsys, shop(datasets=[{"name": ORDERS, "settings": {"look-back": "three days"}}]))

    assert (code, err) == (
        2,
        'error: "three days" is not a look-back.\n  A look-back is a length of time, such as 3d or 12h.\n',
    )


DATASET_SETTINGS = (
    "  A dataset's settings: look-back, full-comparison-schedule, batch-size, retries, time-limit, readiness-interval,"
    " late-data, schema-changes, alert-when-stale-after, keep-records, keep-versions, fetch-batch-size, fetch-retries,"
    " fetch-time-limit\n"
)


def test_an_unknown_setting_in_the_code_is_refused_naming_the_kinds_settings(
    database: str, capsys: pytest.CaptureFixture[str]
):
    code, _, err = record(capsys, shop(datasets=[{"name": ORDERS, "settings": {"colour": "blue"}}]))

    assert (code, err) == (2, "error: a dataset has no setting named colour.\n" + DATASET_SETTINGS)


def test_a_code_decided_name_among_the_settings_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = record(capsys, shop(datasets=[{"name": ORDERS, "settings": {"key": "order_id"}}]))

    assert (code, err) == (
        2,
        "error: the key of shop-flows.orders is decided by the code, not by a setting.\n" + DATASET_SETTINGS,
    )


def test_a_name_declared_as_another_kind_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    code, _, err = record(capsys, shop("2.0", datasets=[], flows=[{"name": ORDERS}]))

    assert (code, err.splitlines()[0]) == (2, "error: shop-flows.orders is a dataset, and cannot become a flow.")


def test_a_rename_across_kinds_is_refused(database: str, capsys: pytest.CaptureFixture[str]):
    record(capsys, shop())

    code, _, err = record(
        capsys, shop("2.0", datasets=[], routes=[{"name": "shop-flows.to-crm", "renamed_from": ORDERS}])
    )

    assert (code, err.splitlines()[0]) == (
        2,
        "error: shop-flows.to-crm, a route, cannot be renamed from shop-flows.orders, a dataset.",
    )


def test_the_list_shows_every_entry_in_the_code_with_its_package_version(
    database: str, capsys: pytest.CaptureFixture[str]
):
    record(capsys, shop())

    assert run(capsys, "list")[:2] == (
        0,
        "NAME                      KIND     PACKAGE VERSION\n"
        "shop-flows.daily          flow     shop-flows 1.0\n"
        "shop-flows.orders         dataset  shop-flows 1.0\n"
        "shop-flows.orders-to-crm  route    shop-flows 1.0\n",
    )


def test_an_empty_catalog_says_so(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "list")[:2] == (0, "the catalog is empty.\n")
