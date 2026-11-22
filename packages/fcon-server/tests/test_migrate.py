"""The upgrade runner against a real Postgres 18: each test has a database of
its own and a migrations folder of its own, the product's files plus any it
adds."""

import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from fcon_server.store.clock import FixedClock
from fcon_server.store.migrate import (
    LOCK_KEY,
    MIGRATIONS,
    MigrationStatus,
    Ran,
    checksum,
    migration_status,
    upgrade,
)

NOW = datetime(2026, 11, 21, 17, 30, 14, 666000, tzinfo=UTC)
PRODUCT_FILES = sorted(path.name for path in MIGRATIONS.glob("*.sql"))

pytestmark = pytest.mark.database


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """A copy of the product's migrations, which tests add to or edit."""
    target = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, target)
    return target


def add(folder: Path, name: str, text: str) -> str:
    (folder / name).write_bytes(text.encode())
    return name


def query(url: str, text: str) -> list[tuple[object, ...]]:
    with psycopg.connect(url, options="-c TimeZone=UTC") as connection:
        return connection.execute(text.encode()).fetchall()


def test_a_new_database_has_every_upgrade_waiting(empty_database_url: str, folder: Path):
    status = migration_status(empty_database_url, folder)

    assert status == MigrationStatus(applied=(), waiting=tuple(PRODUCT_FILES), newer=(), changed=())


def test_an_upgrade_applies_every_waiting_file_in_name_order(empty_database_url: str, folder: Path):
    later = add(folder, "20261202T0000Z_later.sql", "CREATE TABLE fcon.later (n int);")
    sooner = add(folder, "20261201T0000Z_sooner.sql", "CREATE TABLE fcon.sooner (n int);")

    result = upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert result.applied == (*PRODUCT_FILES, sooner, later)


def test_an_upgraded_database_lists_each_file_applied_at_the_clocks_time(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    status = migration_status(empty_database_url, folder)

    assert status == MigrationStatus(
        applied=tuple(Ran(name, NOW) for name in PRODUCT_FILES), waiting=(), newer=(), changed=()
    )


def test_an_upgraded_database_has_nothing_more_to_apply(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert upgrade(empty_database_url, FixedClock(NOW), directory=folder).applied == ()


def test_a_file_older_than_the_newest_applied_is_applied_when_it_arrives(empty_database_url: str, folder: Path):
    add(folder, "20261202T0000Z_newest.sql", "CREATE TABLE fcon.newest (n int);")
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)
    late = add(folder, "20261201T0000Z_merged_late.sql", "CREATE TABLE fcon.merged_late (n int);")

    assert upgrade(empty_database_url, FixedClock(NOW), directory=folder).applied == (late,)


def test_each_file_is_recorded_by_the_migration_actor(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    actors = query(empty_database_url, "SELECT DISTINCT created_by FROM fcon.migration")

    assert actors == [("system:migration",)]


def test_the_checksum_ignores_windows_line_endings():
    assert checksum("CREATE TABLE a (n int);\r\nCREATE TABLE b (n int);\r\n") == checksum(
        "CREATE TABLE a (n int);\nCREATE TABLE b (n int);\n"
    )


def test_the_checksum_is_the_sha256_of_the_text():
    assert checksum("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_a_file_checked_out_with_windows_line_endings_is_not_changed(empty_database_url: str, folder: Path):
    name = add(folder, "20261201T0000Z_lines.sql", "CREATE TABLE fcon.lines (n int);\nSELECT 1;\n")
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)
    add(folder, name, "CREATE TABLE fcon.lines (n int);\r\nSELECT 1;\r\n")

    assert migration_status(empty_database_url, folder).changed == ()


def test_a_file_changed_since_it_ran_is_listed_as_changed(empty_database_url: str, folder: Path):
    name = add(folder, "20261201T0000Z_edited.sql", "CREATE TABLE fcon.edited (n int);")
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)
    add(folder, name, "CREATE TABLE fcon.edited (n bigint);")

    status = migration_status(empty_database_url, folder)

    assert (status.changed, [ran.name for ran in status.applied]) == ((Ran(name, NOW),), PRODUCT_FILES)


def test_a_changed_file_stops_the_upgrade_before_anything_is_applied(empty_database_url: str, folder: Path):
    name = add(folder, "20261201T0000Z_edited.sql", "CREATE TABLE fcon.edited (n int);")
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)
    add(folder, name, "CREATE TABLE fcon.edited (n bigint);")
    waiting = add(folder, "20261202T0000Z_waiting.sql", "CREATE TABLE fcon.waiting (n int);")

    result = upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert (result.applied, result.changed, migration_status(empty_database_url, folder).waiting) == (
        (),
        (name,),
        (waiting,),
    )


def test_a_recorded_upgrade_with_no_file_is_newer_than_this_version(empty_database_url: str, folder: Path):
    name = add(folder, "20261201T0000Z_from_a_newer_version.sql", "CREATE TABLE fcon.newer (n int);")
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)
    (folder / name).unlink()

    assert migration_status(empty_database_url, folder).newer == (name,)


def test_a_migration_reads_the_runners_clock_as_fcon_now(empty_database_url: str, folder: Path):
    add(
        folder,
        "20261201T0000Z_when.sql",
        "CREATE TABLE fcon.when_run AS SELECT current_setting('fcon.now')::timestamptz AS at;",
    )

    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert query(empty_database_url, "SELECT at FROM fcon.when_run") == [(NOW,)]


def test_a_file_that_fails_leaves_nothing_of_itself(empty_database_url: str, folder: Path):
    failing = add(folder, "20261201T0000Z_fails.sql", "CREATE TABLE fcon.half_done (n int);\nSELECT 1/0;")

    with pytest.raises(psycopg.errors.DivisionByZero):
        upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert (
        migration_status(empty_database_url, folder).waiting,
        query(empty_database_url, "SELECT to_regclass('fcon.half_done')"),
    ) == ((failing,), [(None,)])


def test_the_files_before_a_failing_one_stay_applied(empty_database_url: str, folder: Path):
    add(folder, "20261201T0000Z_fails.sql", "SELECT 1/0;")

    with pytest.raises(psycopg.errors.DivisionByZero):
        upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert [ran.name for ran in migration_status(empty_database_url, folder).applied] == PRODUCT_FILES


def test_a_no_transaction_file_runs_outside_a_transaction(empty_database_url: str, folder: Path):
    add(folder, "20261201T0000Z_table.sql", "CREATE TABLE fcon.big (n int);")
    index = add(
        folder,
        "20261202T0000Z_index.sql",
        "-- fcon: no-transaction\nCREATE INDEX CONCURRENTLY IF NOT EXISTS big_n ON fcon.big (n);\n",
    )

    assert upgrade(empty_database_url, FixedClock(NOW), directory=folder).applied[-1] == index


def test_a_no_transaction_file_of_two_statements_is_refused_before_anything_is_applied(
    empty_database_url: str, folder: Path
):
    add(folder, "20261201T0000Z_table.sql", "CREATE TABLE fcon.big (n int);")
    two = add(
        folder,
        "20261202T0000Z_two.sql",
        "-- fcon: no-transaction\nCREATE INDEX CONCURRENTLY big_n ON fcon.big (n);\nDROP TABLE fcon.big;\n",
    )

    with pytest.raises(ValueError, match=two):
        upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert migration_status(empty_database_url, folder).applied == ()


def test_a_comment_or_a_literal_is_not_a_second_statement(empty_database_url: str, folder: Path):
    add(folder, "20261201T0000Z_table.sql", "CREATE TABLE fcon.big (n int);")
    index = add(
        folder,
        "20261202T0000Z_index.sql",
        "-- fcon: no-transaction\n-- outside a transaction; on a big table\n"
        "CREATE INDEX CONCURRENTLY big_n ON fcon.big (n) WHERE n::text <> ';'; /* one; statement */\n",
    )

    assert upgrade(empty_database_url, FixedClock(NOW), directory=folder).applied[-1] == index


def test_a_no_transaction_file_saved_with_a_byte_order_mark_runs_outside_a_transaction(
    empty_database_url: str, folder: Path
):
    add(folder, "20261201T0000Z_table.sql", "CREATE TABLE fcon.big (n int);")
    index = add(
        folder,
        "20261202T0000Z_index.sql",
        "﻿-- fcon: no-transaction\nCREATE INDEX CONCURRENTLY big_n ON fcon.big (n);\n",
    )

    assert upgrade(empty_database_url, FixedClock(NOW), directory=folder).applied[-1] == index


def test_a_no_transaction_file_reads_the_runners_clock_too(empty_database_url: str, folder: Path):
    add(
        folder,
        "20261201T0000Z_when.sql",
        "-- fcon: no-transaction\nCREATE TABLE fcon.when_run AS SELECT current_setting('fcon.now')::timestamptz AS at;",
    )

    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert query(empty_database_url, "SELECT at FROM fcon.when_run") == [(NOW,)]


def test_an_upgrade_waits_for_another_to_finish(empty_database_url: str, folder: Path):
    with psycopg.connect(empty_database_url, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock(%s)", [LOCK_KEY])
        waited: list[bool] = []

        def other_finishes() -> None:
            waited.append(True)
            other.execute("SELECT pg_advisory_unlock(%s)", [LOCK_KEY])

        result = upgrade(empty_database_url, FixedClock(NOW), directory=folder, on_wait=other_finishes)

    assert (waited, result.applied) == ([True], tuple(PRODUCT_FILES))


def test_an_upgrade_alone_does_not_say_it_waits(empty_database_url: str, folder: Path):
    waited: list[bool] = []

    upgrade(empty_database_url, FixedClock(NOW), directory=folder, on_wait=lambda: waited.append(True))

    assert waited == []


AUDIT_PARTITIONS = """
    SELECT child.relname::text FROM pg_inherits
    JOIN pg_class child ON child.oid = pg_inherits.inhrelid
    WHERE pg_inherits.inhparent = 'fcon.audit'::regclass ORDER BY 1
"""


def test_an_upgrade_makes_the_audit_months_through_six_ahead(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    assert [name for (name,) in query(empty_database_url, AUDIT_PARTITIONS)] == [
        "audit_2026_11",
        "audit_2026_12",
        "audit_2027_01",
        "audit_2027_02",
        "audit_2027_03",
        "audit_2027_04",
        "audit_2027_05",
    ]


def test_an_upgrade_with_nothing_waiting_still_makes_the_months_ahead(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    upgrade(empty_database_url, FixedClock(datetime(2027, 1, 1, tzinfo=UTC)), directory=folder)

    assert [name for (name,) in query(empty_database_url, AUDIT_PARTITIONS)][-2:] == ["audit_2027_06", "audit_2027_07"]


def test_an_audit_month_runs_from_its_first_instant_in_utc(empty_database_url: str, folder: Path):
    upgrade(empty_database_url, FixedClock(NOW), directory=folder)

    bounds = query(
        empty_database_url,
        "SELECT pg_get_expr(relpartbound, oid, true) FROM pg_class WHERE oid = 'fcon.audit_2026_12'::regclass",
    )

    assert bounds == [("FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00')",)]


def test_the_months_are_counted_in_utc_whatever_the_clocks_zone(empty_database_url: str, folder: Path):
    late_in_october_west_of_utc = datetime(2026, 10, 31, 22, 0, tzinfo=timezone(timedelta(hours=-5)))

    upgrade(empty_database_url, FixedClock(late_in_october_west_of_utc), directory=folder)

    assert query(empty_database_url, AUDIT_PARTITIONS)[0] == ("audit_2026_11",)
