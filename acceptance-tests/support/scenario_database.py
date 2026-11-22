"""A scenario's own throwaway database, in the states the scenarios start
from: new, upgraded, with an applied upgrade edited since it ran, or with an
upgrade from a newer version. The suite never imports the product: it upgrades
through `fcon db upgrade` (stack.upgrade_database), and touches the database
directly only to fake what the product cannot be made to do from outside, in
the runner's record of applied upgrades, `fcon.migration`.
"""

import psycopg

from support import stack

# A recorded upgrade no file of this version has: as after going back to an older version.
NEWER_UPGRADE = "29991231T2359Z_from_a_newer_version.sql"
EDITED_CHECKSUM = "0" * 64  # SHA-256 of no file this version holds


class ScenarioDatabase:
    def __init__(self):
        self.url = stack.create_database()
        self.edited_upgrade = None  # the upgrade made to look edited, by name

    def upgrade(self):
        stack.upgrade_database(self.url)

    def _applied(self, connection):
        rows = connection.execute("SELECT name FROM fcon.migration ORDER BY name").fetchall()
        if not rows:
            raise AssertionError("the database records no applied upgrade")
        return [row[0] for row in rows]

    def edit_an_applied_upgrade(self):
        """The first applied upgrade's record no longer matches its file, as
        when the file was edited after it ran. Returns its name."""
        with psycopg.connect(self.url, autocommit=True) as connection:
            name = self._applied(connection)[0]
            connection.execute("UPDATE fcon.migration SET checksum = %s WHERE name = %s", (EDITED_CHECKSUM, name))
        self.edited_upgrade = name
        return name

    def add_newer_upgrade(self):
        """One more upgrade recorded as applied, with no file in this version."""
        with psycopg.connect(self.url, autocommit=True) as connection:
            self._applied(connection)
            connection.execute(
                "INSERT INTO fcon.migration (name, checksum, created_at, created_by)"
                " VALUES (%s, %s, now(), 'system:migration')",
                (NEWER_UPGRADE, EDITED_CHECKSUM),
            )
        return NEWER_UPGRADE

    def drop(self):
        stack.drop_database(self.url)
