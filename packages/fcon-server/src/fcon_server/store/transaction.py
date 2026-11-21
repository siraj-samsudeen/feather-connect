"""The store (design decisions 1 and 2): every query runs in a transaction
opened by `Store.transaction`, carrying the context's tenant and actor.

- `tx.execute`, `tx.fetch_one` and `tx.fetch_all` take plain SQL, bind
  `%(tenant_id)s` from the context, and refuse SQL that names an `fcon` table
  with a tenant without `tenant_id = %(tenant_id)s` for each of them.
- `tx.insert` and `tx.update` write one row: they fill the tenant, the
  who-and-when columns and the row version, and write its audit record in the
  same transaction.
- `Store.transaction` never retries; `Store.run` runs a whole unit of work
  again, up to twice, on a deadlock or a serialization failure.
- Database errors become the store's own (`errors`); a statement slower than
  `slow_after` seconds is logged with its text, never its values.
"""

import logging
import re
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, LiteralString, Protocol

import psycopg
from psycopg import errors as pg_errors
from psycopg import sql
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from fcon_server.store.clock import Clock
from fcon_server.store.context import Context
from fcon_server.store.errors import (
    AlreadyExistsError,
    BusyError,
    ChangedBySomeoneElseError,
    NotFoundError,
    StoreError,
    UnscopedQueryError,
)
from fcon_server.store.ids import NewId
from fcon_server.store.tables import Table

logger = logging.getLogger("fcon.store")

SLOW_AFTER = 1.0  # seconds
RETRIES = 2
SECRET = "(secret changed)"  # noqa: S105 - what the audit log shows instead of a secret
_WITHOUT_TENANT = frozenset({"migration"})
_TABLE = re.compile(r"\bfcon\.(\w+)")
_SCOPE = re.compile(r"\btenant_id\s*=\s*%\(tenant_id\)s")

type Params = Mapping[str, object]
type Row = dict[str, object]
type Query = LiteralString | sql.Composed

_AUDIT = """
    INSERT INTO fcon.audit
        (tenant_id, id, created_at, created_by, request_id, table_name, action, row_key, before, after, reason)
    VALUES (%(tenant_id)s, %(id)s, %(created_at)s, %(created_by)s, %(request_id)s, %(table_name)s, %(action)s,
        %(row_key)s, %(before)s, %(after)s, %(reason)s)
"""


class ConnectionSource(Protocol):
    """Where the store's connections come from: psycopg_pool's
    `ConnectionPool` in the product."""

    def connection(self) -> AbstractContextManager[psycopg.Connection[Any]]: ...


@dataclass(frozen=True)
class _Changed:
    before: Row | None
    after: Row


@dataclass(frozen=True)
class _Version:
    row_version: int


def _translate(err: psycopg.Error) -> StoreError:
    if isinstance(err, pg_errors.UniqueViolation):
        return AlreadyExistsError()
    if isinstance(err, pg_errors.DeadlockDetected | pg_errors.SerializationFailure):
        return BusyError()
    return StoreError()


def _hide_secrets(table: Table, changed: _Changed) -> tuple[Row | None, Row]:
    """A secret column that changed shows as `(secret changed)`; one that did
    not is left out. Its value is never written."""
    before = None if changed.before is None else dict(changed.before)
    after = dict(changed.after)
    for column in table.secret:
        was = None if before is None else before.get(column)
        for row in (before, after):
            if row is not None and column in row:
                if was == changed.after.get(column):
                    del row[column]
                else:
                    row[column] = SECRET
    return before, after


def _table(table: Table) -> sql.Identifier:
    return sql.Identifier(*table.name.split("."))


def _equal(columns: list[str], prefix: str) -> list[sql.Composable]:
    return [sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(prefix + column)) for column in columns]


class Transaction:
    """One transaction's statements, scoped to its context's tenant."""

    def __init__(
        self,
        connection: psycopg.Connection[Any],
        context: Context,
        clock: Clock,
        new_id: NewId,
        slow_after: float,
        timer: Callable[[], float],
    ) -> None:
        self._connection = connection
        self._context = context
        self._clock = clock
        self._new_id = new_id
        self._slow_after = slow_after
        self._timer = timer

    def execute(self, query: LiteralString, params: Params | None = None) -> None:
        self._run(self._connection.cursor(), query, self._scoped(query, params))

    def fetch_one[R](self, row: type[R], query: LiteralString, params: Params | None = None) -> R | None:
        cursor = self._connection.cursor(row_factory=class_row(row))
        self._run(cursor, query, self._scoped(query, params))
        return cursor.fetchone()

    def fetch_all[R](self, row: type[R], query: LiteralString, params: Params | None = None) -> list[R]:
        cursor = self._connection.cursor(row_factory=class_row(row))
        self._run(cursor, query, self._scoped(query, params))
        return cursor.fetchall()

    def insert(self, table: Table, values: Params) -> Row:
        """Adds one row and its audit record; gives the row's key besides the
        tenant, with the `id` made by `new_id()` when the key has one."""
        now = self._clock.now()
        filled: Row = {**values, "tenant_id": self._context.tenant_id, "created_at": now}
        filled["created_by"] = self._context.actor
        if "id" in table.key and "id" not in values:
            filled["id"] = self._new_id()
        if table.changes:
            filled |= {"updated_at": now, "updated_by": self._context.actor, "row_version": 1}
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING to_jsonb(OLD) AS before, to_jsonb(NEW) AS after")
        changed = self._changed(
            query.format(
                _table(table),
                sql.SQL(", ").join(sql.Identifier(column) for column in filled),
                sql.SQL(", ").join(sql.Placeholder(column) for column in filled),
            ),
            filled,
        )
        if changed is None:  # pragma: no cover - an INSERT ... VALUES always returns its row
            raise StoreError
        self._audit(table, "insert", changed)
        return {column: filled[column] for column in table.key if column != "tenant_id"}

    def update(self, table: Table, key: Params, values: Params, row_version: int) -> int:
        """Changes one row if it is still at `row_version`, and writes its audit
        record; gives the row's new version. `key` names the key's columns
        besides the tenant."""
        if not table.changes:
            raise ValueError(f"the rows of {table.name} are only added")
        sets: Row = {**values, "updated_at": self._clock.now(), "updated_by": self._context.actor}
        where = sql.SQL(" AND ").join([sql.SQL("tenant_id = %(tenant_id)s"), *_equal(list(key), "key_")])
        params: Row = {f"set_{column}": value for column, value in sets.items()}
        params |= {f"key_{column}": value for column, value in key.items()}
        params |= {"tenant_id": self._context.tenant_id, "expected": row_version}
        query = sql.SQL(
            "UPDATE {} SET {}, row_version = row_version + 1 WHERE {} AND row_version = %(expected)s"
            " RETURNING to_jsonb(OLD) AS before, to_jsonb(NEW) AS after"
        ).format(_table(table), sql.SQL(", ").join(_equal(list(sets), "set_")), where)
        changed = self._changed(query, params)
        if changed is None:
            cursor = self._connection.cursor(row_factory=class_row(_Version))
            self._run(cursor, sql.SQL("SELECT row_version FROM {} WHERE {}").format(_table(table), where), params)
            raise NotFoundError() if cursor.fetchone() is None else ChangedBySomeoneElseError()
        self._audit(table, "update", changed)
        return int(str(changed.after["row_version"]))

    def _changed(self, query: sql.Composed, params: Row) -> _Changed | None:
        cursor = self._connection.cursor(row_factory=class_row(_Changed))
        self._run(cursor, query, params)
        return cursor.fetchone()

    def _audit(self, table: Table, action: str, changed: _Changed) -> None:
        before, after = _hide_secrets(table, changed)
        row_key = "/".join(str(changed.after[column]) for column in table.key if column != "tenant_id")
        self._run(
            self._connection.cursor(),
            _AUDIT,
            {
                "tenant_id": self._context.tenant_id,
                "id": self._new_id(),
                "created_at": self._clock.now(),
                "created_by": self._context.actor,
                "request_id": self._context.request_id,
                "table_name": table.name,
                "action": action,
                "row_key": row_key or self._context.tenant_id,
                "before": None if before is None else Jsonb(before),
                "after": Jsonb(after),
                "reason": self._context.reason,
            },
        )

    def _scoped(self, query: LiteralString, params: Params | None) -> Row:
        if params and "tenant_id" in params:
            raise UnscopedQueryError("the tenant comes from the context, never from the values")
        with_tenant = [name for name in _TABLE.findall(query) if name not in _WITHOUT_TENANT]
        if len(_SCOPE.findall(query)) < len(with_tenant):
            raise UnscopedQueryError(f"each fcon table with a tenant needs tenant_id = %(tenant_id)s: {query}")
        return {**(params or {}), "tenant_id": self._context.tenant_id}

    def _run(self, cursor: psycopg.Cursor[Any], query: Query, params: Row) -> None:
        started = self._timer()
        try:
            cursor.execute(query, params)
        except psycopg.Error as err:
            raise _translate(err) from err
        finally:
            seconds = self._timer() - started
            if seconds > self._slow_after:
                text = query if isinstance(query, str) else query.as_string(self._connection)
                logger.warning("slow statement, %.1f s: %s", seconds, text)


class Store:
    def __init__(
        self,
        source: ConnectionSource,
        clock: Clock,
        new_id: NewId,
        *,
        slow_after: float = SLOW_AFTER,
        timer: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._source = source
        self._clock = clock
        self._new_id = new_id
        self._slow_after = slow_after
        self._timer = timer

    @contextmanager
    def transaction(self, context: Context) -> Generator[Transaction]:
        """Commits when the block ends, rolls back when it raises. Never
        retries: a deadlock or serialization failure is `BusyError`."""
        try:
            with self._source.connection() as connection, connection.transaction():
                yield Transaction(connection, context, self._clock, self._new_id, self._slow_after, self._timer)
        except psycopg.Error as err:
            raise _translate(err) from err

    def run[T](self, context: Context, work: Callable[[Transaction], T]) -> T:
        """Runs `work(tx)` in a transaction; on `BusyError`, runs all of it
        again, up to twice, then lets the error through."""
        for _ in range(RETRIES):
            try:
                with self.transaction(context) as tx:
                    return work(tx)
            except BusyError:
                continue
        with self.transaction(context) as tx:
            return work(tx)
