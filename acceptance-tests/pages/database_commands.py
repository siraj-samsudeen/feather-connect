"""The operator's terminal for the database: `fcon db upgrade` and `fcon db
status` typed at a prompt, and what they printed. The commands, their output's
shape and the texts the steps rely on live here; the steps only ask questions.

The upgrades of this version are the files of the store's `migrations/`
folder: the suite reads their names, never the product's code.
"""

import re
from datetime import UTC, datetime

from support import stack

MIGRATIONS = stack.REPO_ROOT / "packages" / "fcon-server" / "src" / "fcon_server" / "store" / "migrations"

CHANGED_UPGRADE_EXIT = 2  # the error helper's exit code for a mistake only a person can fix
TRACEBACK = "Traceback"

APPLIED_COUNT = re.compile(r"^the database is up to date: (\d+) upgrades? applied\.$")
ALREADY_UP_TO_DATE = "the database was already up to date."
RESTORE = "Restore it; never edit a migration that ran."


def changed_upgrade(name):
    return "error: upgrade %s has changed since it ran." % name


def upgrades_of_this_version():
    """The names of this version's upgrade files, in order. A version with
    none is a mistake of the suite's or the product's, never a pass."""
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    if not names:
        raise AssertionError("this version has no upgrades: no *.sql in %s" % MIGRATIONS)
    return names


class Result:
    def __init__(self, command, exit_code, output, errors, timed_out):
        self.command = command
        self.exit_code = exit_code
        self.output = output
        self.errors = errors
        self.timed_out = timed_out

    def lines(self):
        return (self.output + "\n" + self.errors).splitlines()

    def ended_well(self):
        return (
            not self.timed_out
            and self.exit_code == 0
            and TRACEBACK not in self.output + self.errors
            and not any(line.startswith("error:") for line in self.lines())
        )

    def __repr__(self):
        return "`fcon %s`: exit %s%s, output:\n%s%s" % (
            self.command,
            self.exit_code,
            " (timed out: stopped)" if self.timed_out else "",
            self.output or "(nothing on stdout)\n",
            ("--- stderr ---\n" + self.errors) if self.errors else "",
        )


class StatusLine:
    """One upgrade in `fcon db status`: its state, its name, and when it ran."""

    def __init__(self, state, name, ran_at):
        self.state = state
        self.name = name
        self.ran_at = ran_at

    def __repr__(self):
        return "%s %s %s" % (self.state, self.name, self.ran_at or "")


STATES = ("applied", "waiting", "newer", "changed")


def _parse_time(text):
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        return None  # not UTC
    return when.astimezone(UTC)


class DatabaseCommands:
    def __init__(self, world):
        self.world = world
        self.result = None
        self.results = []  # every command of the scenario, in order

    def _settings(self):
        if self.world.scenario_database is None:
            raise AssertionError("the scenario has no database of its own yet")
        return {"FCON_DATABASE_URL": self.world.scenario_database}

    def _finish(self, command, process):
        code, out, err, timed_out = stack.finish_fcon(process)
        result = Result(command, code, out, err, timed_out)
        self.world.screen.command("fcon " + command, out + err, code)
        self.results.append(result)
        self.result = result
        return result

    # -- the commands ----------------------------------------------------

    def upgrade(self):
        return self._finish("db upgrade", stack.start_fcon(["db", "upgrade"], self._settings()))

    def status(self):
        return self._finish("db status", stack.start_fcon(["db", "status"], self._settings()))

    def upgrade_twice_at_once(self):
        """Two `fcon db upgrade` started together, as by two copies of the product being deployed."""
        processes = [stack.start_fcon(["db", "upgrade"], self._settings()) for _ in range(2)]
        return [self._finish("db upgrade", process) for process in processes]

    # -- what happened ---------------------------------------------------

    def _last(self):
        if self.result is None:
            raise AssertionError("no command has been run yet")
        return self.result

    def listed(self):
        """The upgrades `fcon db status` listed, in order. (lines, result)."""
        result = self._last()
        if result.command != "db status" or result.exit_code != 0:
            raise AssertionError("expected a `fcon db status` that ended well; %r" % result)
        found = []
        for line in result.output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] in STATES:
                found.append(StatusLine(parts[0], parts[1], _parse_time(parts[2]) if len(parts) > 2 else None))
        return found, result

    def all_listed_as(self, state, with_time=False):
        """(yes?, why): every upgrade of this version is listed, each in that
        state (and with a UTC time it ran, when asked)."""
        found, result = self.listed()
        expected = upgrades_of_this_version()
        by_name = {line.name: line for line in found}
        wrong = [
            name
            for name in expected
            if name not in by_name or by_name[name].state != state or (with_time and by_name[name].ran_at is None)
        ]
        if wrong:
            return False, "not listed as %s%s: %r; %r" % (state, " with a UTC time" if with_time else "", wrong, result)
        return True, result

    def none_listed_as(self, state):
        found, result = self.listed()
        named = [line.name for line in found if line.state == state]
        return not named, "listed as %s: %r; %r" % (state, named, result)

    def told_how_many_applied(self):
        """(yes?, why): every upgrade is named as applied, and the count is
        the number of this version's upgrades."""
        result = self._last()
        if not result.ended_well():
            return False, result
        expected = upgrades_of_this_version()
        lines = result.lines()
        missing = [name for name in expected if "applied %s" % name not in lines]
        counts = [int(found.group(1)) for found in map(APPLIED_COUNT.match, lines) if found]
        if missing or counts != [len(expected)]:
            return False, "expected %d upgrade(s) applied, missing %r; %r" % (len(expected), missing, result)
        return True, result

    def told_already_up_to_date(self):
        result = self._last()
        return result.ended_well() and ALREADY_UP_TO_DATE in result.lines(), result

    def all_ended_well(self, results):
        bad = [result for result in results if not result.ended_well()]
        return not bad, bad

    def refused(self):
        """(yes?, why): the upgrade stopped with the exit code for a mistake to fix."""
        result = self._last()
        return (not result.timed_out and result.exit_code == CHANGED_UPGRADE_EXIT), result

    def told_upgrade_changed(self, name):
        """(yes?, why): the changed upgrade is named, with to restore it, and no stack trace."""
        result = self._last()
        lines = [line.strip() for line in result.lines()]
        ok = changed_upgrade(name) in lines and RESTORE in lines and TRACEBACK not in result.output + result.errors
        return ok, result
