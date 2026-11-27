"""The rights an upgrade grants (design point 17).

An app user other than the owner reads and writes every `fcon` table, and only
reads and adds to the audit log. The owner is the test server's administrator;
the app user is a login role made for the test session (`app_role`).
"""

from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg import conninfo, errors

from fcon_server.store.clock import FixedClock
from fcon_server.store.migrate import upgrade

NOW = datetime(2026, 11, 21, 17, 30, 14, 666000, tzinfo=UTC)
AUDIT_ROW = """
    INSERT INTO fcon.audit (tenant_id, id, created_at, created_by, request_id, table_name, action, row_key, after)
    VALUES ('default', gen_random_uuid(), %s, 'system:test', 'test', 'fcon.tenant', 'insert', 'default', '{}')
"""

pytestmark = pytest.mark.database

type Connection = psycopg.Connection[tuple[object, ...]]


def as_user(url: str, role: tuple[str, str]) -> str:
    user, password = role
    return conninfo.make_conninfo(url, user=user, password=password)


@pytest.fixture
def granted(empty_database_url: str, app_role: tuple[str, str]) -> Iterator[Connection]:
    """A connection as the app user to a database upgraded by the owner."""
    upgrade(empty_database_url, FixedClock(NOW), app_user=app_role[0])
    with psycopg.connect(as_user(empty_database_url, app_role), autocommit=True) as connection:
        yield connection


def test_the_app_user_adds_to_the_audit_log(granted: Connection):
    granted.execute(AUDIT_ROW, [NOW])

    assert granted.execute("SELECT count(*) FROM fcon.audit").fetchone() == (1,)


def test_the_app_user_cannot_change_an_audit_record(granted: Connection):
    with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table audit"):
        granted.execute("UPDATE fcon.audit SET reason = 'edited' WHERE false")


def test_the_app_user_cannot_delete_an_audit_record(granted: Connection):
    with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table audit"):
        granted.execute("DELETE FROM fcon.audit WHERE false")


def test_the_app_user_cannot_empty_the_audit_log(granted: Connection):
    with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table audit"):
        granted.execute("TRUNCATE fcon.audit")


def test_the_app_user_cannot_change_an_audit_month_directly(granted: Connection):
    with pytest.raises(errors.InsufficientPrivilege, match="permission denied for table audit_2026_11"):
        granted.execute("DELETE FROM fcon.audit_2026_11 WHERE false")


def test_the_app_user_reads_and_writes_the_tenants(granted: Connection):
    granted.execute(
        "INSERT INTO fcon.tenant (tenant_id, kind, created_at, created_by, updated_at, updated_by, row_version)"
        " VALUES ('test-app', 'production', %s, 'system:test', %s, 'system:test', 1)",
        [NOW, NOW],
    )
    granted.execute("UPDATE fcon.tenant SET row_version = 2 WHERE tenant_id = 'test-app'")
    granted.execute("DELETE FROM fcon.tenant WHERE tenant_id = 'test-app'")

    assert granted.execute("SELECT tenant_id FROM fcon.tenant").fetchall() == [("default",)]


def test_without_an_app_user_nothing_is_granted(empty_database_url: str, app_role: tuple[str, str]):
    upgrade(empty_database_url, FixedClock(NOW))

    with (
        psycopg.connect(as_user(empty_database_url, app_role)) as connection,
        pytest.raises(errors.InsufficientPrivilege),
    ):
        connection.execute("SELECT count(*) FROM fcon.tenant")


def test_an_app_user_that_is_the_owner_is_granted_nothing(empty_database_url: str):
    with psycopg.connect(empty_database_url) as connection:
        owner = str((connection.execute("SELECT current_user").fetchone() or ("",))[0])

    upgrade(empty_database_url, FixedClock(NOW), app_user=owner)

    with psycopg.connect(empty_database_url) as connection:
        acl = connection.execute("SELECT relacl FROM pg_class WHERE oid = 'fcon.tenant'::regclass").fetchone()
    assert acl == (None,)
