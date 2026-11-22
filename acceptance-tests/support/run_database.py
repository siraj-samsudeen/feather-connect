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
