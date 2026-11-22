"""The first administrator from a setting (design point 1, decision 4): the
setting that names them, the product the operator starts with it, and what
its log says. The setting's name and the log's texts live here; the steps
only ask questions.

The log goes to a file, so each line is one JSON object; its `message` field
holds the text (a line that is not JSON is taken as it is).
"""

import json
import time

from pages.server_log import ServerLog

SETTING = "FCON_FIRST_ADMIN"

# `warning: no administrator yet; made "ann" with a one-time password: …`
# `Sign in at /sign-in and choose your own password. Remove FCON_FIRST_ADMIN afterwards.`
ONE_TIME_PASSWORD = "no administrator yet; made %s with a one-time password: "
SIGN_IN_AND_CHOOSE = "Sign in at /sign-in and choose your own password."
REMOVE_SETTING = "Remove FCON_FIRST_ADMIN afterwards."
ANY_PASSWORD = "one-time password"

# The product tries at start, and again every 5 s until the database is
# ready: a log that has said nothing by then says nothing.
SETTLES_S = 15
QUIET_S = 7
POLL_S = 0.5


def _message(line):
    try:
        found = json.loads(line)
    except ValueError:
        return line
    return found.get("message", line) if isinstance(found, dict) else line


class FirstAdministrator:
    def __init__(self, world):
        self.world = world
        self.log = ServerLog(world)

    def name_in_settings(self, name):
        self.world.name_in_settings(SETTING, name)

    def start(self):
        self.world.start_own_product()

    def restart(self):
        self.world.restart_own_product()

    def _messages(self):
        return [_message(line) for line in self.log.lines()]

    def _where(self, messages):
        return "the log says:\n%s" % "\n".join(messages[-40:])

    def one_time_password(self, name):
        """(password or None, why): the password the log gives for that name,
        once the log also says to sign in and choose a new one, waiting up to
        SETTLES_S."""
        start = ONE_TIME_PASSWORD % json.dumps(name)
        deadline = time.monotonic() + SETTLES_S
        while True:
            messages = self._messages()
            given = [(m.split(start, 1)[1].split() or [""])[0] for m in messages if start in m]
            told = all(any(text in m for m in messages) for text in (SIGN_IN_AND_CHOOSE, REMOVE_SETTING))
            if (given and told) or time.monotonic() >= deadline:
                break
            time.sleep(POLL_S)
        self.world.screen.log([start, SIGN_IN_AND_CHOOSE, REMOVE_SETTING], messages)
        if len(given) != 1 or not given[0]:
            return None, "%d line(s) give a password after %r; %s" % (len(given), start, self._where(messages))
        if not told:
            return None, "the log does not say %r and %r; %s" % (SIGN_IN_AND_CHOOSE, REMOVE_SETTING, self._where(messages))
        return given[0], ""

    def gives_no_password(self):
        """(yes?, why): nothing in the log, QUIET_S after the product is ready,
        mentions a one-time password."""
        time.sleep(QUIET_S)
        messages = self._messages()
        self.world.screen.log([ANY_PASSWORD], messages)
        said = [m for m in messages if ANY_PASSWORD in m]
        return not said, "the log gives a password again: %r" % said
