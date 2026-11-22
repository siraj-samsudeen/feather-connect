"""The product's migration files: names a person and CI can read."""

import re

from fcon_server.store.migrate import MIGRATIONS

NAME = re.compile(r"^\d{8}T\d{4}Z_[a-z0-9_]+\.sql$")
NAMES = sorted(path.name for path in MIGRATIONS.iterdir() if path.name != "__init__.py")


def test_there_is_at_least_one_migration():
    assert NAMES


def test_every_migration_is_named_by_its_utc_time_then_a_short_name():
    assert [name for name in NAMES if not NAME.match(name)] == []


def test_no_two_migrations_share_a_timestamp():
    stamps = [name.split("_", 1)[0] for name in NAMES]

    assert len(stamps) == len(set(stamps))
