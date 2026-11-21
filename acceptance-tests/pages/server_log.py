"""What a server started for one scenario wrote to its log. The texts the
readiness checks write live here; the steps only ask questions."""

import time

from support import stack

# The texts the readiness checks write: in a terminal a line holds each, and in
# JSON (as here, the log going to a file) the message field does.
RUN_UPGRADE = "Run: fcon db upgrade"
RESTORE = "Restore it; never edit a migration that ran."

# The database watch looks every 5 s; the first look is at start.
LOG_SETTLES_S = 15
POLL_S = 0.5


def behind(count):
    return "the database is %d upgrade%s behind this version. Not ready." % (count, "" if count == 1 else "s")


def changed(name):
    return "upgrade %s has changed since it ran." % name


class ServerLog:
    def __init__(self, world):
        self.world = world

    def lines(self):
        process = self.world.scenario_server
        if process is None:
            raise AssertionError("the scenario started no server of its own")
        return stack.log_path(process).read_text(encoding="utf-8", errors="replace").splitlines()

    def says_within(self, texts, timeout_s=LOG_SETTLES_S):
        """(yes?, the log's end): every one of the texts is in the log, each on
        a line of its own or in a line's message, waiting up to the timeout."""
        deadline = time.monotonic() + timeout_s
        while True:
            lines = self.lines()
            missing = [text for text in texts if not any(text in line for line in lines)]
            if not missing or time.monotonic() >= deadline:
                return not missing, "missing %r; the log ends:\n%s" % (missing, "\n".join(lines[-40:]))
            time.sleep(POLL_S)

    def says_behind(self, count):
        return self.says_within([behind(count), RUN_UPGRADE])

    def says_changed(self, name):
        return self.says_within([changed(name), RESTORE])
