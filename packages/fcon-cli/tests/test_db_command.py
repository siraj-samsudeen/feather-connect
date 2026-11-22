"""`fcon db upgrade` and `fcon db status`: what the operator is told, against a
database of each test's own."""

import io
import threading
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import conninfo

from fcon_cli import problems
from fcon_cli.db import app_user, format_time, status_lines, upgrade_database, upgrade_lines
from fcon_cli.main import main
from fcon_cli.settings import DatabaseSettings
from fcon_server.store.clock import FixedClock
from fcon_server.store.migrate import LOCK_KEY, MIGRATIONS, MigrationStatus, Ran, UpgradeResult

NOW = datetime(2026, 11, 21, 17, 30, 14, 666000, tzinfo=UTC)
FILES = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
WAIT_S = 10


@pytest.fixture
def database(empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    """The commands' settings point at the test's own database; no .env."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", empty_database_url)
    monkeypatch.delenv("FCON_MIGRATION_DATABASE_URL", raising=False)
    return empty_database_url


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, list[str], str]:
    code = main(list(argv), clock=FixedClock(NOW))
    captured = capsys.readouterr()
    return code, captured.out.splitlines(), captured.err


# -- fcon db upgrade -----------------------------------------------------


@pytest.mark.database
def test_an_upgrade_names_each_file_it_applied_then_how_many(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "db", "upgrade") == (
        0,
        [*(f"applied {name}" for name in FILES), f"the database is up to date: {len(FILES)} upgrades applied."],
        "",
    )


def test_more_than_one_upgrade_applied_is_said_in_the_plural():
    lines = upgrade_lines(UpgradeResult(applied=("a.sql", "b.sql")))

    assert lines[-1] == "the database is up to date: 2 upgrades applied."


@pytest.mark.database
def test_an_upgrade_with_nothing_waiting_says_the_database_was_up_to_date(
    database: str, capsys: pytest.CaptureFixture[str]
):
    run(capsys, "db", "upgrade")

    assert run(capsys, "db", "upgrade") == (0, ["the database was already up to date."], "")


@pytest.mark.database
def test_an_upgrade_refuses_a_file_changed_since_it_ran(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "db", "upgrade")
    with psycopg.connect(database) as connection:
        connection.execute("UPDATE fcon.migration SET checksum = 'edited' WHERE name = %s", [FILES[0]])

    assert run(capsys, "db", "upgrade") == (2, [], problems.upgrade_changed(FILES[0]).text() + "\n")


@pytest.mark.database
def test_an_upgrade_uses_the_owners_address_when_it_is_set(
    database: str, free_port: int, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setenv("FCON_DATABASE_URL", f"postgresql://feather:feather@127.0.0.1:{free_port}/nowhere")
    monkeypatch.setenv("FCON_MIGRATION_DATABASE_URL", database)

    assert run(capsys, "db", "upgrade")[0] == 0


@pytest.mark.database
def test_an_upgrade_with_the_owners_address_grants_the_app_user_its_rights(
    database: str, app_role: tuple[str, str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    app_url = conninfo.make_conninfo(database, user=app_role[0], password=app_role[1])
    monkeypatch.setenv("FCON_DATABASE_URL", app_url)
    monkeypatch.setenv("FCON_MIGRATION_DATABASE_URL", database)

    run(capsys, "db", "upgrade")

    with psycopg.connect(app_url) as connection:
        assert connection.execute("SELECT tenant_id FROM fcon.tenant").fetchall() == [("default",)]


def test_an_app_address_without_a_user_names_no_app_user():
    assert app_user(DatabaseSettings(database_url="dbname=app", migration_database_url="dbname=owner")) is None


def test_an_upgrade_stops_for_a_database_it_cannot_reach(
    free_port: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")
    monkeypatch.delenv("FCON_MIGRATION_DATABASE_URL", raising=False)

    assert run(capsys, "db", "upgrade") == (
        2,
        [],
        (
            f"error: cannot reach the database at 127.0.0.1:{free_port} (connection refused).\n"
            "  Start it: docker compose up -d\n"
        ),
    )


def test_the_database_commands_stop_for_a_settings_mistake(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FCON_DATABASE_URL", raising=False)

    assert run(capsys, "db", "status") == (2, [], problems.database_url_missing().text() + "\n")


@pytest.mark.database
def test_an_upgrade_says_when_it_waits_for_another(empty_database_url: str):
    settings = DatabaseSettings(database_url=empty_database_url, migration_database_url=empty_database_url)
    out, err = io.StringIO(), io.StringIO()
    with psycopg.connect(empty_database_url, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])
        upgrading = threading.Thread(target=upgrade_database, args=(settings, FixedClock(NOW), out, err))
        upgrading.start()
        deadline = time.monotonic() + WAIT_S
        while not err.getvalue() and time.monotonic() < deadline:
            time.sleep(0.05)
        other.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])
        upgrading.join(WAIT_S)

    assert err.getvalue() == problems.waiting_for_upgrade() + "\n"


# -- fcon db status ------------------------------------------------------


@pytest.mark.database
def test_the_status_of_a_new_database_lists_every_file_waiting(database: str, capsys: pytest.CaptureFixture[str]):
    assert run(capsys, "db", "status") == (
        0,
        [*(f"waiting  {name}" for name in FILES), f"0 applied, {len(FILES)} waiting."],
        "",
    )


@pytest.mark.database
def test_the_status_changes_nothing(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "db", "status")

    with psycopg.connect(database) as connection:
        assert connection.execute("SELECT to_regnamespace('fcon')").fetchone() == (None,)


@pytest.mark.database
def test_the_status_of_an_upgraded_database_lists_when_each_file_ran(database: str, capsys: pytest.CaptureFixture[str]):
    run(capsys, "db", "upgrade")

    assert run(capsys, "db", "status") == (
        0,
        [*(f"applied  {name}  2026-11-21T17:30:14.666Z" for name in FILES), f"{len(FILES)} applied, 0 waiting."],
        "",
    )


def test_the_status_stops_for_a_database_it_cannot_reach(
    free_port: int, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")

    code, _, err = run(capsys, "db", "status")

    assert (code, err.splitlines()[0]) == (
        2,
        f"error: cannot reach the database at 127.0.0.1:{free_port} (connection refused).",
    )


def test_the_status_lists_every_upgrade_in_name_order_with_its_state():
    status = MigrationStatus(
        applied=(Ran("1_a.sql", NOW),),
        waiting=("2_b.sql",),
        newer=("4_d.sql",),
        changed=(Ran("3_c.sql", NOW),),
    )

    assert status_lines(status) == [
        "applied  1_a.sql  2026-11-21T17:30:14.666Z",
        "waiting  2_b.sql",
        "changed  3_c.sql  2026-11-21T17:30:14.666Z",
        "newer    4_d.sql",
        "1 applied, 1 waiting.",
    ]


def test_a_time_is_shown_in_utc_to_the_millisecond():
    assert format_time(datetime(2026, 11, 21, 12, 30, 14, 666999, tzinfo=timezone(timedelta(hours=-5)))) == (
        "2026-11-21T17:30:14.666Z"
    )
