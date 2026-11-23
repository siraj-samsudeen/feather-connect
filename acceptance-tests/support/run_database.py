"""The run's shared database, as test support: what one scenario leaves there
must not reach the next. The run's server and database serve every scenario,
so before each one its users, their sessions and the sign-in attempts are
removed. The audit log stays: nothing may change it, and the scenarios assert
only on the records of their own requests.

The suite never imports the product; it touches the database directly only
for what the product cannot be made to do from outside (here, forget its
users), and to read what a scenario checks (how many users there are).
"""

import psycopg

from support import stack

# In the order they can be emptied: a session and an attempt point at a user.
USER_TABLES = ("fcon.session", "fcon.sign_in_attempt", "fcon.user")
USER_TABLE = "fcon.user"


def _connect(database_url):
    return psycopg.connect(database_url, autocommit=True, connect_timeout=5)


def _existing(connection, tables):
    """The tables of `tables` the database has: before the product keeps
    users, none of them."""
    found = []
    for table in tables:
        (oid,) = connection.execute("SELECT to_regclass(%s)", (table,)).fetchone()
        if oid is not None:
            found.append(table)
    return found


def reset_users(database_url=None):
    """Removes every user, session and sign-in attempt from the run's
    database (or the one given), in one transaction; a table the product does
    not have yet is skipped."""
    with _connect(database_url or stack.run_database_url()) as connection:
        tables = _existing(connection, USER_TABLES)
        if tables:
            # One statement, so the references between them never stand in the way.
            connection.execute("TRUNCATE %s" % ", ".join(tables))


def user_count(database_url=None):
    """How many users the database has; an AssertionError when it keeps no
    users at all (no such table)."""
    with _connect(database_url or stack.run_database_url()) as connection:
        if not _existing(connection, (USER_TABLE,)):
            raise AssertionError("the database has no %s table: the product keeps no users yet" % USER_TABLE)
        (count,) = connection.execute("SELECT count(*) FROM %s" % USER_TABLE).fetchone()
        return count


SESSION_TABLE = "fcon.session"


def move_sessions_back(hours, database_url=None):
    """Every session of the database (the run's, or the one given) as if it
    had been made, and last used, `hours` earlier: the time a user stays
    away, without the scenario waiting for it. The product's clock is not
    touched; only the times its sessions recorded move. Returns how many."""
    with _connect(database_url or stack.run_database_url()) as connection:
        if not _existing(connection, (SESSION_TABLE,)):
            raise AssertionError("the database has no %s table: the product keeps no sessions yet" % SESSION_TABLE)
        moved = connection.execute(
            "UPDATE %s SET created_at = created_at - make_interval(hours => %%(h)s),"
            " last_seen_at = last_seen_at - make_interval(hours => %%(h)s),"
            " expires_at = expires_at - make_interval(hours => %%(h)s)"
            " WHERE ended_at IS NULL" % SESSION_TABLE,
            {"h": hours},
        )
        return moved.rowcount


AUDIT_TABLE = "fcon.audit"
# Every column of the audit log, one JSON array of objects, oldest first: the
# same text for psycopg here and for psql in a container (pages/standard_setup.py).
_AUDIT_COLUMNS = (
    "json_build_object('created_at', created_at, 'created_by', created_by, 'request_id', request_id,"
    " 'table_name', table_name, 'action', action, 'row_key', row_key, 'before', before, 'after', after,"
    " 'reason', reason)"
)
AUDIT_QUERY_ALL = "SELECT coalesce(json_agg(%s ORDER BY created_at), '[]') FROM %s" % (_AUDIT_COLUMNS, AUDIT_TABLE)
_AUDIT_QUERY_SINCE = "SELECT coalesce(json_agg(%s ORDER BY created_at), '[]') FROM %s WHERE created_at > %%(since)s" % (
    _AUDIT_COLUMNS,
    AUDIT_TABLE,
)


def audit_mark(database_url=None):
    """When the latest audit record of the database (the run's, or the one
    given) was written, or None: what a scenario writes comes after it. The
    product's own times, so no clock of this machine is compared with them."""
    with _connect(database_url or stack.run_database_url()) as connection:
        if not _existing(connection, (AUDIT_TABLE,)):
            return None
        (mark,) = connection.execute("SELECT max(created_at) FROM %s" % AUDIT_TABLE).fetchone()
        return mark


def audit_records(since, database_url=None):
    """The audit records of the database (the run's, or the one given)
    written after `since` (every one, when None), oldest first, as dicts."""
    with _connect(database_url or stack.run_database_url()) as connection:
        if not _existing(connection, (AUDIT_TABLE,)):
            raise AssertionError("the database has no %s table" % AUDIT_TABLE)
        if since is None:
            (records,) = connection.execute(AUDIT_QUERY_ALL).fetchone()
        else:
            (records,) = connection.execute(_AUDIT_QUERY_SINCE, {"since": since}).fetchone()
        return records
