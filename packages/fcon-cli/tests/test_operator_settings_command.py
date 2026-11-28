"""Tests of `fcon settings show|set|clear|list` (catalog-and-settings, the command line's contract).

They act as `system:cli` in the tenant `default`; every refusal goes through the error helper, exit code 2.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest

from fcon_cli.main import main
from fcon_server.store.clock import SystemClock
from fcon_server.store.migrate import upgrade

pytestmark = pytest.mark.database

ORDERS = "shop-flows.orders"
DATASET_SETTINGS = (
    "  A dataset's settings: look-back, full-comparison-schedule, batch-size, tries, time-limit, readiness-interval,"
    " late-data, schema-changes, alert-when-stale-after, keep-records, keep-versions, fetch-batch-size, fetch-tries,"
    " fetch-time-limit"
)
NEEDS_A_REASON = [
    "error: shop-flows.orders was not changed: a protected environment needs a reason for every change.",
    "  Say why with --reason.",
]


@pytest.fixture
def database(empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """An upgraded database of the test's own where shop-flows 1.0 is recorded, named by FCON_DATABASE_URL."""
    upgrade(empty_database_url, SystemClock())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", empty_database_url)
    monkeypatch.delenv("FCON_PROTECTED", raising=False)
    record(shop())
    yield empty_database_url


def shop(version: str = "1.0", **groups: object) -> dict[str, Any]:
    """The contract's example package version, its dataset's code giving a look-back of 1d and a batch size."""
    return {
        "package": "shop-flows",
        "version": version,
        "flows": [{"name": "shop-flows.daily"}],
        "datasets": [{"name": ORDERS, "key": ["order_id"], "settings": {"look-back": "1d", "batch-size": 5000}}],
        "routes": [{"name": "shop-flows.orders-to-crm", "dataset": ORDERS}],
    } | groups


def record(data: object) -> None:
    Path("shop.json").write_text(json.dumps(data), encoding="utf-8")
    assert main(["catalog", "record", "shop.json"]) == 0


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    capsys.readouterr()
    code = main(["settings", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def protect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FCON_PROTECTED", "on")


# -- show -------------------------------------------------------------------


def test_show_names_the_entry_and_its_package_version(database: str, capsys: pytest.CaptureFixture[str]):
    code, out, _ = run(capsys, "show", ORDERS)

    assert (code, out.splitlines()[0]) == (0, "shop-flows.orders, a dataset of shop-flows 1.0")


def test_show_gives_every_setting_in_force_by_layer(database: str, capsys: pytest.CaptureFixture[str]):
    lines = run(capsys, "show", ORDERS)[1].splitlines()

    assert (lines[1], lines[2], lines[4], lines[5]) == (
        "SETTING                   VALUE  SET BY   CHANGED",
        "look-back                 1d     code",
        "batch-size                5000   code",
        "tries                     6      default",
    )


def test_show_gives_who_changed_an_operators_value_and_when(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "set", ORDERS, "look-back", "3d")

    lines = run(capsys, "show", ORDERS)[1].splitlines()

    assert lines[1] == "SETTING                   VALUE  SET BY    CHANGED"
    assert re.fullmatch(r"look-back {17}3d {5}operator  system:cli, \d{4}-\d\d-\d\d \d\d:\d\d UTC", lines[2])


def test_show_lists_every_setting_of_the_kind(database: str, capsys: pytest.CaptureFixture[str]):
    assert len(run(capsys, "show", ORDERS)[1].splitlines()) == 2 + 14


def test_show_says_an_entry_is_no_longer_in_the_code(database: str, capsys: pytest.CaptureFixture[str]):
    record(shop("2.0", datasets=[]))

    assert run(capsys, "show", ORDERS)[1].splitlines()[0] == (
        "shop-flows.orders, a dataset no longer in the code (last in shop-flows 1.0)"
    )


def test_show_refuses_an_unknown_name(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "show", "shop-flows.nope")

    assert (code, err.splitlines()) == (
        2,
        ["error: no flow, dataset or route is named shop-flows.nope.", "  fcon catalog list shows the names."],
    )


# -- set --------------------------------------------------------------------


def test_set_says_what_was_set(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "set", ORDERS, "look-back", "3d")[:2] == (0, "set the look-back of shop-flows.orders to 3d.\n")


def test_set_to_the_same_value_says_it_is_already(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "set", ORDERS, "look-back", "3d")

    assert run(capsys, "set", ORDERS, "look-back", "3d")[:2] == (
        0,
        "the look-back of shop-flows.orders is 3d already.\n",
    )


def test_set_writes_the_reason_on_the_audit_record(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "set", ORDERS, "look-back", "3d", "--reason", "the source is late")

    with psycopg.connect(database) as connection:
        rows = connection.execute(
            "SELECT created_by, reason FROM fcon.audit WHERE table_name = 'fcon.operator_setting'"
        ).fetchall()
    assert rows == [("system:cli", "the source is late")]


def test_set_refuses_a_setting_the_code_decides(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "set", ORDERS, "key", "id")

    assert (code, err.splitlines()) == (
        2,
        ["error: the key of shop-flows.orders is decided by the code, not by a setting.", DATASET_SETTINGS],
    )


def test_set_refuses_an_unknown_setting(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "set", ORDERS, "colour", "blue")

    assert (code, err.splitlines()) == (2, ["error: a dataset has no setting named colour.", DATASET_SETTINGS])


def test_set_refuses_a_wrong_value(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "set", ORDERS, "look-back", "three days")

    assert (code, err.splitlines()) == (
        2,
        ['error: "three days" is not a look-back.', "  A look-back is a length of time, such as 3d or 12h."],
    )


def test_set_refuses_an_unknown_name(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "set", "shop-flows.nope", "look-back", "3d")[2].splitlines()[0] == (
        "error: no flow, dataset or route is named shop-flows.nope."
    )


def test_set_refuses_a_name_no_longer_in_the_code(database: str, capsys: pytest.CaptureFixture[str]):
    record(shop("2.0", datasets=[]))

    code, _, err = run(capsys, "set", ORDERS, "look-back", "3d")

    assert (code, err.splitlines()) == (
        2,
        ["error: shop-flows.orders is no longer in the code; its values can be cleared, not set."],
    )


def test_set_in_a_protected_environment_needs_a_reason(
    database: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    protect(monkeypatch)

    code, _, err = run(capsys, "set", ORDERS, "look-back", "3d")

    assert (code, err.splitlines()) == (2, NEEDS_A_REASON)


def test_set_in_a_protected_environment_takes_a_reason(
    database: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    protect(monkeypatch)

    assert run(capsys, "set", ORDERS, "look-back", "3d", "--reason", "late")[0] == 0


# -- clear ------------------------------------------------------------------


def test_clear_says_the_codes_value_is_in_force(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "set", ORDERS, "look-back", "3d")

    assert run(capsys, "clear", ORDERS, "look-back")[:2] == (
        0,
        "cleared the look-back of shop-flows.orders; the code's 1d is in force.\n",
    )


def test_clear_says_the_default_is_in_force(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "set", ORDERS, "tries", "5")

    assert run(capsys, "clear", ORDERS, "tries")[:2] == (
        0,
        "cleared the tries of shop-flows.orders; the default 6 is in force.\n",
    )


def test_clear_without_an_operator_value_says_so(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "clear", ORDERS, "look-back")[:2] == (
        0,
        "the look-back of shop-flows.orders has no operator value.\n",
    )


def test_clear_refuses_an_unknown_setting(database: str, capsys: pytest.CaptureFixture[str]):
    code, _, err = run(capsys, "clear", ORDERS, "colour")

    assert (code, err.splitlines()) == (2, ["error: a dataset has no setting named colour.", DATASET_SETTINGS])


def test_clear_refuses_an_unknown_name(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "clear", "shop-flows.nope", "look-back")[2].splitlines()[0] == (
        "error: no flow, dataset or route is named shop-flows.nope."
    )


def test_clear_in_a_protected_environment_needs_a_reason(
    database: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    run(capsys, "set", ORDERS, "look-back", "3d")
    protect(monkeypatch)

    code, _, err = run(capsys, "clear", ORDERS, "look-back")

    assert (code, err.splitlines()) == (2, NEEDS_A_REASON)


def test_clear_in_a_protected_environment_takes_a_reason(
    database: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    run(capsys, "set", ORDERS, "look-back", "3d")
    protect(monkeypatch)

    assert run(capsys, "clear", ORDERS, "look-back", "--reason", "back to the code's")[0] == 0


# -- list -------------------------------------------------------------------


def test_list_shows_every_operator_value_flagged_when_no_longer_in_the_code(
    database: str, capsys: pytest.CaptureFixture[str]
):
    run(capsys, "set", ORDERS, "look-back", "3d")
    run(capsys, "set", "shop-flows.daily", "tries", "5")
    record(shop("2.0", datasets=[]))

    assert run(capsys, "list")[:2] == (
        0,
        (
            "NAME               SETTING    VALUE  NOTE\n"
            "shop-flows.daily   tries      5\n"
            "shop-flows.orders  look-back  3d     no longer in the code\n"
        ),
    )


def test_an_empty_list_says_so(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "list")[:2] == (0, "no operator values yet.\n")
