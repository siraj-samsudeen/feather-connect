"""The store (design decisions 1 and 2): every query runs in a transaction opened by `Store.transaction`.

The transaction carries the context's tenant and actor.

- `tx.execute`, `tx.fetch_one` and `tx.fetch_all` take plain SQL, bind
  `%(tenant_id)s` from the context, and refuse SQL that names an `fcon` table
  with a tenant without `tenant_id = %(tenant_id)s` for each of them, outside
  comments and literals. The check counts text, it does not parse SQL: a
  guardrail against a forgotten tenant, not a proof. Each test's own tenant
  is what shows that no query reaches another tenant's rows.
- `tx.insert` and `tx.update` write one row: they fill the tenant, the
  who-and-when columns and the row version, and write its audit record in the
  same transaction. `tx.insert_if_absent` is `tx.insert` for what must happen
  once; `tx.refuse` records a change refused for a rule, and writes nothing else.
- For set-based bulk writes (ADR 0022), which write no audit record per row:
  `tx.copy_rows` copies rows into a temporary table, each with the context's
  tenant in its `tenant_id` column, and `tx.stamp()` gives `stamped_at` and
  `stamped_by`, the clock's time and the context's actor, for the SQL that
  writes from it to name. That SQL runs through `tx.execute`, so it is
  checked like any other: `WHERE rows.tenant_id = %(tenant_id)s` scopes it.
- `Store.transaction` never retries; `Store.run` runs a whole unit of work
  again, up to twice, on a deadlock or a serialization failure.
- Database errors become the store's own (`errors`); a statement slower than
  `slow_after` seconds is logged with its text, never its values.
"""

import logging
import re
import time
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
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
_FILLED = ("created_at", "created_by", "updated_at", "updated_by", "row_version")
# A quoted name is kept; a literal or a comment is blanked, so text inside one
# neither names a table nor scopes it.
_NOISE = re.compile(r"""("(?:[^"]|"")*")|'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/""", re.DOTALL)
_TABLE = re.compile(r'(?<![\w"$])"?fcon"?\s*\.\s*"?(\w+)"?', re.IGNORECASE)
_SCOPE = re.compile(r'(?<![\w$])"?tenant_id"?\s*=\s*%\(tenant_id\)s', re.IGNORECASE)

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
    """Where the store's connections come from: psycopg_pool's `ConnectionPool` in the product."""

    def connection(self) -> AbstractContextManager[psycopg.Connection[Any]]:
        """Lends one connection for the block."""
        ...


@dataclass(frozen=True)
class _Changed:
    """A written row as it was before and as it is after; `before` is None for an insert."""

    before: Row | None
    after: Row


@dataclass(frozen=True)
class _Version:
    """A row's current version, read to tell a missing row from one changed by someone else."""

    row_version: int


def _translate(err: psycopg.Error) -> StoreError:
    """The store's error for a driver's error: already exists, busy, or a plain `StoreError`."""
    if isinstance(err, pg_errors.UniqueViolation):
        return AlreadyExistsError()
    if isinstance(err, pg_errors.DeadlockDetected | pg_errors.SerializationFailure):
        return BusyError()
    return StoreError()


def _hide_secrets(table: Table, changed: _Changed) -> tuple[Row | None, Row]:
    """The row before and after as the audit log shows them, without the secrets' values.

    A secret column that changed shows as `(secret changed)`; one that did not is left out. Its
    value is never written.
    """
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


def _refuse_filled(values: Params) -> None:
    """Refuses a caller's values for the columns the store fills itself.

    The tenant, the who-and-when columns and the row version are the store's to fill: a caller's
    value for one is a bug, never written. Raises `UnscopedQueryError` for the tenant and
    `ValueError` for the others.
    """
    if "tenant_id" in values:
        raise UnscopedQueryError("the tenant comes from the context, never from the values")
    if given := [column for column in _FILLED if column in values]:
        raise ValueError(f"the store fills {', '.join(given)}")


def _table(table: Table) -> sql.Identifier:
    """The table's full name as an SQL identifier."""
    return sql.Identifier(*table.name.split("."))


def _equal(columns: list[str], prefix: str) -> list[sql.Composable]:
    """A `column = placeholder` piece for each column, its placeholder named `prefix` and the column."""
    return [sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder(prefix + column)) for column in columns]


@dataclass(frozen=True)
class _SlowStatements:
    """When a statement is slow enough to log: longer than `after_s` seconds, read on `timer`."""

    after_s: float
    timer: Callable[[], float]


class Transaction:
    """One transaction's statements, scoped to its context's tenant."""

    def __init__(
        self, connection: psycopg.Connection[Any], context: Context, clock: Clock, new_id: NewId, slow: _SlowStatements
    ) -> None:
        self._connection = connection
        self._context = context
        self._clock = clock
        self._new_id = new_id
        self._slow = slow

    def execute(self, query: LiteralString, params: Params | None = None) -> None:
        """Runs one statement scoped to the context's tenant, with no rows back."""
        self._run(self._connection.cursor(), query, self._scoped(query, params))

    def fetch_one[R](self, row: type[R], query: LiteralString, params: Params | None = None) -> R | None:
        """Runs one query scoped to the context's tenant and gives its first row as a `row`, or None."""
        cursor = self._connection.cursor(row_factory=class_row(row))
        self._run(cursor, query, self._scoped(query, params))
        return cursor.fetchone()

    def fetch_all[R](self, row: type[R], query: LiteralString, params: Params | None = None) -> list[R]:
        """Runs one query scoped to the context's tenant and gives all its rows, each as a `row`."""
        cursor = self._connection.cursor(row_factory=class_row(row))
        self._run(cursor, query, self._scoped(query, params))
        return cursor.fetchall()

    def stamp(self) -> Row:
        """The who-and-when values for a set-based write: `stamped_at` from the clock, `stamped_by` the actor."""
        return {"stamped_at": self._clock.now(), "stamped_by": self._context.actor}

    def copy_rows(self, temporary_table: str, columns: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
        """Copies rows into the temporary table `temporary_table`, each with the context's tenant first.

        The table is in `pg_temp`, made by the caller, with a `tenant_id` column besides `columns`;
        rows are sent with `COPY`, far faster than one statement each. Only a temporary table can
        be named, so no product table is written without the tenant-scope check.
        """
        query = sql.SQL("COPY {} ({}) FROM STDIN").format(
            sql.Identifier("pg_temp", temporary_table),
            sql.SQL(", ").join(sql.Identifier(column) for column in ("tenant_id", *columns)),
        )
        try:
            with self._connection.cursor().copy(query) as copy:
                for row in rows:
                    copy.write_row((self._context.tenant_id, *row))
        except psycopg.Error as err:
            raise _translate(err) from err

    def insert(self, table: Table, values: Params) -> Row:
        """Adds one row and its audit record, and gives the row's key besides the tenant.

        The `id` is made by `new_id()` when the key has one and the values give none.
        """
        key = self._insert(table, values, if_absent=False)
        if key is None:  # pragma: no cover - an INSERT ... VALUES always returns its row
            raise StoreError
        return key

    def insert_if_absent(self, table: Table, values: Params) -> Row | None:
        """Adds the row and its audit record unless a unique rule finds one there already.

        For what must happen once (convention 13, `ON CONFLICT DO NOTHING`); gives its key, or None
        when nothing went in.
        """
        return self._insert(table, values, if_absent=True)

    def refuse(self, table: Table, row_key: str, reason: str) -> None:
        """Records a change refused for a rule (design decision 3), and writes nothing else.

        The `refused` audit record names the row and why. An empty `row_key` names the tenant.
        """
        self._write_audit(table, "refused", row_key, reason=reason)

    def _insert(self, table: Table, values: Params, *, if_absent: bool) -> Row | None:
        """Adds one row, with the columns the store fills, and its audit record; gives its key.

        With `if_absent` the row goes in with `ON CONFLICT DO NOTHING`, and None comes back when
        nothing went in.
        """
        _refuse_filled(values)
        now = self._clock.now()
        filled: Row = {**values, "tenant_id": self._context.tenant_id, "created_at": now}
        filled["created_by"] = self._context.actor
        if "id" in table.key and "id" not in values:
            filled["id"] = self._new_id()
        if table.changes:
            filled |= {"updated_at": now, "updated_by": self._context.actor, "row_version": 1}
        query = sql.SQL(
            "INSERT INTO {} ({}) VALUES ({}){} RETURNING to_jsonb(OLD) AS before, to_jsonb(NEW) AS after"
        ).format(
            _table(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in filled),
            sql.SQL(", ").join(sql.Placeholder(column) for column in filled),
            sql.SQL(" ON CONFLICT DO NOTHING" if if_absent else ""),
        )
        changed = self._changed(query, filled)
        if changed is None:
            return None
        self._audit(table, "insert", changed)
        return {column: filled[column] for column in table.key if column != "tenant_id"}

    def update(self, table: Table, key: Params, values: Params, row_version: int) -> int:
        """Changes one row if it is still at `row_version`, writes its audit record, and gives its new version.

        `key` names the key's columns besides the tenant. Raises `NotFoundError` when there is no
        such row, `ChangedBySomeoneElseError` when it is at another version, and `ValueError` for a
        table whose rows are only added.
        """
        if not table.changes:
            raise ValueError(f"the rows of {table.name} are only added")
        _refuse_filled(values)
        if "tenant_id" in key:
            raise UnscopedQueryError("the tenant comes from the context, never from the key")
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
        """Runs a write that returns the row before and after; None when it wrote nothing."""
        cursor = self._connection.cursor(row_factory=class_row(_Changed))
        self._run(cursor, query, params)
        return cursor.fetchone()

    def _audit(self, table: Table, action: str, changed: _Changed) -> None:
        """Writes the audit record of one insert or update, secrets hidden, with the context's reason."""
        before, after = _hide_secrets(table, changed)
        row_key = "/".join(str(changed.after[column]) for column in table.key if column != "tenant_id")
        self._write_audit(table, action, row_key, rows=(before, after), reason=self._context.reason)

    def _write_audit(
        self,
        table: Table,
        action: str,
        row_key: str,
        *,
        rows: tuple[Row | None, Row | None] = (None, None),
        reason: str | None,
    ) -> None:
        """Writes one audit record, stamped by the clock, the context's actor and its request id.

        An empty `row_key` names the tenant; `rows` is the row before and after the change.
        """
        before, after = rows
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
                "after": None if after is None else Jsonb(after),
                "reason": reason,
            },
        )

    def _scoped(self, query: LiteralString, params: Params | None) -> Row:
        """Gives the params with the context's tenant bound, once the SQL is checked to scope it.

        Raises `UnscopedQueryError` when the params give a tenant, or when the SQL names an `fcon`
        table with a tenant without `tenant_id = %(tenant_id)s` for each.
        """
        if params and "tenant_id" in params:
            raise UnscopedQueryError("the tenant comes from the context, never from the values")
        code = _NOISE.sub(lambda found: found[1] or " ", query)
        with_tenant = [name for name in _TABLE.findall(code) if name.lower() not in _WITHOUT_TENANT]
        if len(_SCOPE.findall(code)) < len(with_tenant):
            raise UnscopedQueryError(f"each fcon table with a tenant needs tenant_id = %(tenant_id)s: {query}")
        return {**(params or {}), "tenant_id": self._context.tenant_id}

    def _run(self, cursor: psycopg.Cursor[Any], query: Query, params: Row) -> None:
        """Runs one statement, turning a driver's error into the store's own.

        A statement slower than the store's `slow_after` seconds is logged with its text, never its values.
        """
        started = self._slow.timer()
        try:
            cursor.execute(query, params)
        except psycopg.Error as err:
            raise _translate(err) from err
        finally:
            seconds = self._slow.timer() - started
            if seconds > self._slow.after_s:
                text = query if isinstance(query, str) else query.as_string(self._connection)
                logger.warning("slow statement, %.1f s: %s", seconds, text)


class Store:
    """The way into the database: transactions scoped to a context, with the clock and the id maker."""

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
        self._slow = _SlowStatements(slow_after, timer)

    @contextmanager
    def transaction(self, context: Context) -> Generator[Transaction]:
        """Opens a transaction for `context`: commits when the block ends, rolls back when it raises.

        Never retries: a deadlock or serialization failure is `BusyError`.
        """
        try:
            with self._source.connection() as connection, connection.transaction():
                yield Transaction(connection, context, self._clock, self._new_id, self._slow)
        except psycopg.Error as err:
            raise _translate(err) from err

    def run[T](self, context: Context, work: Callable[[Transaction], T]) -> T:
        """Runs `work(tx)` in a transaction; on `BusyError`, all of it again, up to twice, then lets it through."""
        for _ in range(RETRIES):
            try:
                with self.transaction(context) as tx:
                    return work(tx)
            except BusyError:
                continue
        with self.transaction(context) as tx:
            return work(tx)
