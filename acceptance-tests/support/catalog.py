"""A scenario's dataset in the catalog, as test support. Until packages can be
installed from outside, nothing in the product can be made to define a
dataset, so the suite writes its catalog entry straight into the database:
the one thing it fakes for the stored-data scenarios.

The catalog's table, `fcon.catalog_entry`, belongs to issue 34. When the
run's database does not have it yet, the smallest stand-in is made here, in
the acceptance support only: (tenant_id, id, kind, name). Once issue 34 is on
main the real table is always there and the stand-in is never made.

Every other required column of the real table is filled generically, from
its type, so the suite does not depend on the details of issue 34's table.
"""

import uuid
from datetime import UTC, datetime

import psycopg
from psycopg import sql
from psycopg.types.json import Json, Jsonb

TABLE = "fcon.catalog_entry"
TENANT = "default"
ACTOR = "system:acceptance"
KIND = "dataset"
DATASET_PREFIX = "shop-flows.orders_"

STAND_IN = (
    "CREATE TABLE IF NOT EXISTS fcon.catalog_entry ("
    " tenant_id text NOT NULL, id uuid NOT NULL, kind text NOT NULL, name text NOT NULL,"
    " PRIMARY KEY (tenant_id, id))"
)
REQUIRED_COLUMNS = (
    "SELECT column_name, data_type FROM information_schema.columns"
    " WHERE table_schema = 'fcon' AND table_name = 'catalog_entry'"
    " AND is_nullable = 'NO' AND column_default IS NULL ORDER BY ordinal_position"
)


def _value(column, data_type, name, now):
    """What a scenario's dataset gives a required column."""
    known = {
        "tenant_id": TENANT,
        "id": uuid.uuid4(),
        "kind": KIND,
        "name": name,
        "created_by": ACTOR,
        "updated_by": ACTOR,
        "row_version": 1,
    }
    if column in known:
        return known[column]
    by_type = {
        "uuid": uuid.uuid4(),
        "jsonb": Jsonb({}),
        "json": Json({}),
        "boolean": False,
        "integer": 0,
        "bigint": 0,
        "smallint": 0,
        "numeric": 0,
        "timestamp with time zone": now,
    }
    return by_type.get(data_type, name)  # text and the rest: the dataset's name


def add_dataset(database_url):
    """A dataset of the scenario's own in the catalog of that database, under
    the default tenant. Returns its full name, unique to the scenario."""
    name = DATASET_PREFIX + uuid.uuid4().hex[:6]
    now = datetime.now(UTC)
    with psycopg.connect(database_url, autocommit=True, connect_timeout=5) as connection:
        (found,) = connection.execute("SELECT to_regclass(%s)", (TABLE,)).fetchone()
        if found is None:
            connection.execute(STAND_IN)
        columns = connection.execute(REQUIRED_COLUMNS).fetchall()
        values = {column: _value(column, data_type, name, now) for column, data_type in columns}
        for column in ("tenant_id", "kind", "name"):
            values.setdefault(column, _value(column, "text", name, now))
        connection.execute(
            sql.SQL("INSERT INTO fcon.catalog_entry ({}) VALUES ({})").format(
                sql.SQL(", ").join(map(sql.Identifier, values)),
                sql.SQL(", ").join([sql.Placeholder()] * len(values)),
            ),
            list(values.values()),
        )
    return name
