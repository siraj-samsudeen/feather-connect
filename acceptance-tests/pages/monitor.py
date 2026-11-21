"""What an uptime monitor, or the host that runs the product, sees: the two
health addresses and their answers. All of the routes, status codes and
answer texts live here; the steps only ask questions."""

import json
import time

LIVENESS_PATH = "/healthz"
READINESS_PATH = "/readyz"

RUNNING = {"status": "alive"}
READY = {"status": "ready", "checks": {"database": "ok"}}
NOT_READY_DATABASE_UNAVAILABLE = {"status": "not ready", "checks": {"database": "unavailable"}}

# Readiness is live: the product's database watch looks again every 5 s, so
# an answer may take up to that, and a little more, to change.
READINESS_SETTLES_S = 15
POLL_S = 0.5

# Words that would tell a reader what the database is, whatever its address.
DATABASE_WORDS = ("postgres", "psycopg", "version", "localhost")


class Answer:
    """One reply, read once: the response is gone after its client closes."""

    def __init__(self, method, path, response):
        self.method = method
        self.path = path
        self.status = response.status
        self.headers = dict(response.headers)
        self.text = response.text() if method != "HEAD" else ""

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError:
            return None

    def __repr__(self):
        return "%s %s -> %d %s" % (self.method, self.path, self.status, self.text[:200] or "(no body)")


class Monitor:
    def __init__(self, world):
        self.world = world
        self.answers = {}  # path -> the last Answer

    def _ask(self, method, path):
        http = self.world.http()
        response = http.head(path) if method == "HEAD" else http.get(path)
        self.answers[path] = Answer(method, path, response)
        return self.answers[path]

    def check(self):
        """What a monitor asks: is it running, and is it ready to take work."""
        self._ask("GET", LIVENESS_PATH)
        self._ask("GET", READINESS_PATH)

    def quick_check(self):
        """A check that asks for no details: the headers only, no body."""
        self._ask("HEAD", LIVENESS_PATH)

    def _answer(self, path):
        if path not in self.answers:
            raise AssertionError("the monitor has not asked %s yet" % path)
        return self.answers[path]

    def says_running(self):
        """(yes?, what was answered) — running is 200 and, when a body was asked for, "alive"."""
        answer = self._answer(LIVENESS_PATH)
        if answer.method == "HEAD":
            return answer.status == 200, answer
        return answer.status == 200 and answer.json() == RUNNING, answer

    def says_ready(self):
        answer = self._answer(READINESS_PATH)
        return answer.status == 200 and answer.json() == READY, answer

    def says_not_ready_database_unavailable(self):
        answer = self._answer(READINESS_PATH)
        return answer.status == 503 and answer.json() == NOT_READY_DATABASE_UNAVAILABLE, answer

    def _readiness_becomes(self, says, timeout_s):
        """(yes?, last answer): asks for readiness again until `says` holds of
        the answer, or the time is up. The first answer is the one already
        asked for, when there is one."""
        deadline = time.monotonic() + timeout_s
        if READINESS_PATH not in self.answers:
            self._ask("GET", READINESS_PATH)
        while True:
            yes, answer = says()
            if yes or time.monotonic() >= deadline:
                return yes, answer
            time.sleep(POLL_S)
            self._ask("GET", READINESS_PATH)

    def becomes_ready(self, timeout_s=READINESS_SETTLES_S):
        return self._readiness_becomes(self.says_ready, timeout_s)

    def becomes_not_ready_database_unavailable(self, timeout_s=READINESS_SETTLES_S):
        return self._readiness_becomes(self.says_not_ready_database_unavailable, timeout_s)

    def database_details_revealed(self, database):
        """What of the database's address and nature any reply gives away,
        in its body or its headers: host, port, user, password, database
        name, or words naming the database or its version."""
        secrets = [database[key] for key in ("host", "port", "user", "password", "dbname")]
        found = []
        for answer in self.answers.values():
            seen = (answer.text + "\n" + "\n".join("%s: %s" % item for item in answer.headers.items())).lower()
            for secret in secrets + list(DATABASE_WORDS):
                if secret.lower() in seen:
                    found.append("%s %s says %r" % (answer.method, answer.path, secret))
        return found
