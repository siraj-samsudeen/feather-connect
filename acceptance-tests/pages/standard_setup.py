"""The standard setup on one machine, as its operator runs it: the checkout's
`deploy/compose.yaml` (the upgrade `migrate`, the product `server` and the
proxy `caddy`), against a Postgres 18 server outside it (the stand-in of
pages/container_host.py). Every service name, setting, path and port the
setup's scenarios rely on lives here; the steps only ask questions.

The suite runs the operator's own compose file, under a project name of its
own, with two files it writes in reports/ (design, decision 3):

- an env file: the site's name `localhost` (for which Caddy makes its own
  certificate, from its own authority) and the database's two full addresses,
  whose host is the stand-in Postgres container's name;
- an override file: `migrate` and `server` join the scenario's network (an
  external one), so they reach that Postgres by name; caddy's ports move to
  free ones of 127.0.0.1; every container carries the run's label, so
  docker.stop_all() finds what a scenario left behind.

The suite trusts Caddy's root certificate, copied out of the proxy, and no
other: an encrypted answer is one verified against it, for the site's name.
"""

import http.client
import json
import socket
import ssl
import time
from datetime import UTC, datetime

from support import docker, stack
from support.auth import SIGN_IN_PATH

COMPOSE_FILE = stack.REPO_ROOT / "deploy" / "compose.yaml"
REPORTS = stack.ACCEPTANCE / "reports"

UPGRADE_SERVICE = "migrate"
PRODUCT_SERVICE = "server"
PROXY_SERVICE = "caddy"

SITE_NAME = "localhost"
SITE_SETTING = "FCON_DOMAIN"
DATABASE_SETTING = "FCON_DATABASE_URL"
MIGRATION_DATABASE_SETTING = "FCON_MIGRATION_DATABASE_URL"

# Where Caddy keeps the root certificate of its own authority (its data volume is /data).
CADDY_ROOT_CERTIFICATE = "/data/caddy/pki/authorities/local/root.crt"
PROXY_PLAIN_PORT = 80
PROXY_ENCRYPTED_PORT = 443

READINESS_PATH = "/readyz"
READY = {"status": "ready", "checks": {"database": "ok"}}
UPGRADED = "the database is up to date: "  # then "N upgrades applied."
REDIRECTS = (301, 302, 307, 308)

UP_TIMEOUT_S = docker.BUILD_TIMEOUT_S  # `up --build` may build the image
PROXY_ANSWERS_S = 60  # Caddy makes its authority and the site's certificate as it starts
READY_S = 30
REQUEST_TIMEOUT_S = 5


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _docker_time(text):
    """A time `docker inspect` gives (RFC 3339, nanoseconds, UTC) as a datetime, to the microsecond."""
    base, _, fraction = text.rstrip("Z").partition(".")
    return datetime.fromisoformat(base).replace(tzinfo=UTC).replace(microsecond=int((fraction + "000000")[:6]))


class Answer:
    """One reply over HTTP(S), read whole."""

    def __init__(self, scheme, path, response):
        self.scheme = scheme
        self.path = path
        self.status = response.status
        self.headers = {name.lower(): value for name, value in response.getheaders()}
        self.text = response.read().decode("utf-8", errors="replace")

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError:
            return None

    def __repr__(self):
        return "%s GET %s -> %d %s" % (self.scheme, self.path, self.status, self.text[:200] or "(no body)")


class StandardSetup:
    def __init__(self, world, container_host):
        self.world = world
        self.host = container_host  # the Postgres server outside the setup
        self.project = None
        self.env_file = None
        self.override_file = None
        self.root_certificate = None
        self.plain_port = None
        self.encrypted_port = None
        self.started = False
        self.plain_answer = None

    # --- docker compose -------------------------------------------------------

    def _compose(self, *arguments, timeout=docker.COMMAND_TIMEOUT_S, check=True):
        return docker.docker(
            "compose", "-p", self.project, "-f", str(COMPOSE_FILE), "-f", str(self.override_file),
            "--env-file", str(self.env_file), *arguments, timeout=timeout, check=check,
        )  # fmt: skip

    def _logs(self, service=None):
        code, out, err = self._compose("logs", "--no-color", *([service] if service else []), check=False)
        return out + err if code == 0 else "(no log: %s)" % (err.strip() or out.strip())

    def _container(self, service):
        """The id of the service's container, running or not."""
        _code, out, _err = self._compose("ps", "--all", "--quiet", service)
        ids = out.split()
        if not ids:
            raise AssertionError("the setup has no `%s` service container; its log:\n%s" % (service, self._logs()))
        return ids[0]

    def _state(self, service):
        _code, out, _err = docker.docker("inspect", "--format", "{{json .State}}", self._container(service))
        return json.loads(out)

    # --- the operator's steps -------------------------------------------------

    def prepare(self):
        """The setup on one machine: the database server outside it, with a
        new, empty database, and the site's name, `localhost`; no certificate
        yet (its volumes are new)."""
        self.host.new_postgres_database()
        self.project = self.host.network()  # the scenario's own name, lowercase: a valid project name
        self.plain_port, self.encrypted_port = _free_port(), _free_port()
        REPORTS.mkdir(parents=True, exist_ok=True)
        self.env_file = REPORTS / ("%s.env" % self.project)
        self.env_file.write_text(
            "%s=%s\n%s=%s\n%s=%s\n%s=%s\n" % (
                SITE_SETTING, SITE_NAME,
                MIGRATION_DATABASE_SETTING, self.host.owner_address,
                DATABASE_SETTING, self.host.app_address,
                stack.SECRET_KEY_SETTING, stack.SECRET_KEY,
            ),
            encoding="utf-8",
        )  # fmt: skip
        self.override_file = REPORTS / ("%s.override.yaml" % self.project)
        self.override_file.write_text(self._override(), encoding="utf-8")
        self.world.screen.note("the standard setup, for the site %s, on a new, empty database" % SITE_NAME)

    def _override(self):
        label = '      %s: "%s"\n' % (docker.LABEL, docker.RUN_NAME)
        joined = "    networks:\n      - default\n      - outside\n"
        return (
            "# Written by the acceptance suite (pages/standard_setup.py) for one scenario.\n"
            "networks:\n"
            "  outside:\n"
            "    name: %(network)s\n"
            "    external: true\n"
            "services:\n"
            "  %(upgrade)s:\n"
            "    image: %(image)s\n%(joined)s"
            "    labels:\n%(label)s"
            "  %(product)s:\n"
            "    image: %(image)s\n%(joined)s"
            "    labels:\n%(label)s"
            "  %(proxy)s:\n"
            "    ports: !override\n"
            '      - "127.0.0.1:%(plain)d:%(plain_target)d"\n'
            '      - "127.0.0.1:%(encrypted)d:%(encrypted_target)d"\n'
            "    labels:\n%(label)s"
        ) % {
            "network": self.host.network(),
            "image": docker.IMAGE,
            "joined": joined,
            "label": label,
            "upgrade": UPGRADE_SERVICE,
            "product": PRODUCT_SERVICE,
            "proxy": PROXY_SERVICE,
            "plain": self.plain_port,
            "plain_target": PROXY_PLAIN_PORT,
            "encrypted": self.encrypted_port,
            "encrypted_target": PROXY_ENCRYPTED_PORT,
        }

    def start(self):
        """`docker compose up -d --build`, as the operator starts it; then
        waits until the proxy answers over an encrypted connection."""
        if self.project is None:
            raise RuntimeError("the setup was not prepared: its first Given prepares it")
        docker.image()  # built once per run, under the run's tag the override names
        self.world.screen.note("$ docker compose -f deploy/compose.yaml up -d --build")
        self.started = True
        code, out, err = self._compose("up", "--detach", "--build", timeout=UP_TIMEOUT_S, check=False)
        if code != 0:
            raise AssertionError(
                "`docker compose up -d --build` failed (exit %d):\n%s\nthe setup's log:\n%s"
                % (code, (out + err).strip(), self._logs())
            )
        self.root_certificate = self._copy_root_certificate()
        if not docker.wait_until(self._proxy_answers, PROXY_ANSWERS_S):
            raise AssertionError(
                "the proxy did not answer over an encrypted connection within %d s; the setup's log:\n%s"
                % (PROXY_ANSWERS_S, self._logs())
            )
        # The browser goes through the proxy too; the connection itself is verified by encrypted_get().
        self.world.use_product_at("https://%s:%d" % (SITE_NAME, self.encrypted_port), ignore_https_errors=True)

    def run(self):
        self.prepare()
        self.start()

    def _copy_root_certificate(self):
        target = REPORTS / ("%s-caddy-root.crt" % self.project)

        def copied():
            code, _out, _err = self._compose(
                "cp", "%s:%s" % (PROXY_SERVICE, CADDY_ROOT_CERTIFICATE), str(target), check=False
            )
            return code == 0 and target.exists()

        if not docker.wait_until(copied, PROXY_ANSWERS_S, poll_s=1):
            raise AssertionError(
                "the proxy made no root certificate at %s within %d s; its log:\n%s"
                % (CADDY_ROOT_CERTIFICATE, PROXY_ANSWERS_S, self._logs(PROXY_SERVICE))
            )
        return target

    def close(self):
        """`docker compose down -v`: the setup's containers, networks and
        volumes go; its log stays in reports/logs/ (environment.py, after the
        scenario, before the Postgres server and its network go)."""
        if not self.started:
            return
        self.started = False
        try:
            stack.LOGS.mkdir(parents=True, exist_ok=True)
            (stack.LOGS / ("%s.log" % self.project)).write_text(self._logs(), encoding="utf-8")
        except (docker.DockerError, OSError):
            pass  # no log to keep
        self._compose("down", "--volumes", "--remove-orphans", check=False)
        for path in (self.env_file,):
            if path is not None:
                path.unlink(missing_ok=True)

    # --- reaching the site from the machine ----------------------------------

    def encrypted_get(self, path):
        """GET path at https://localhost, connecting to the proxy's port of
        127.0.0.1, trusting only Caddy's root certificate: the answer, or
        raises ssl.SSLError when the connection is not verified."""
        trust = ssl.create_default_context(cafile=str(self.root_certificate))
        raw = socket.create_connection(("127.0.0.1", self.encrypted_port), timeout=REQUEST_TIMEOUT_S)
        connection = http.client.HTTPConnection(SITE_NAME, self.encrypted_port, timeout=REQUEST_TIMEOUT_S)
        connection.sock = trust.wrap_socket(raw, server_hostname=SITE_NAME)
        try:
            connection.request("GET", path, headers={"Host": SITE_NAME})
            return Answer("https", path, connection.getresponse())
        finally:
            connection.close()

    def plain_get(self, path):
        """GET path at http://localhost (the proxy's plain port), without following a redirect."""
        connection = http.client.HTTPConnection("127.0.0.1", self.plain_port, timeout=REQUEST_TIMEOUT_S)
        try:
            connection.request("GET", path, headers={"Host": SITE_NAME})
            return Answer("http", path, connection.getresponse())
        finally:
            connection.close()

    def _proxy_answers(self):
        try:
            self.encrypted_get(READINESS_PATH)
            return True
        except (OSError, http.client.HTTPException):
            return False  # ssl.SSLError is an OSError: Caddy may not have its certificate yet

    # --- what the operator sees -----------------------------------------------

    def becomes_ready(self, timeout_s=READY_S):
        """(yes?, the last answer): the product answers through the proxy,
        over a verified encrypted connection, that it is ready to take work."""
        deadline = time.monotonic() + timeout_s
        while True:
            try:
                answer = self.encrypted_get(READINESS_PATH)
            except (OSError, http.client.HTTPException) as error:
                answer = "no answer: %s" % error
            else:
                self.world.screen.request("GET", READINESS_PATH, answer.status, answer.text)
                if answer.status == 200 and answer.json() == READY:
                    return True, answer
            if time.monotonic() >= deadline:
                return False, answer
            time.sleep(0.5)

    def upgraded_by_itself_problems(self):
        """Why it is not the setup that upgraded the database: the scenario
        ran no upgrade, and the setup's upgrade says the database is up to date."""
        problems = []
        if self.host.upgrade_result is not None:
            problems.append("the scenario upgraded the database by hand")
        said = self._logs(UPGRADE_SERVICE)
        if UPGRADED not in said:
            problems.append("the setup's `%s` did not say %r; its log:\n%s" % (UPGRADE_SERVICE, UPGRADED, said))
        return problems

    def upgrade_order_problems(self):
        """Why the upgrade had not finished, well, before the product started."""
        upgrade, product = self._state(UPGRADE_SERVICE), self._state(PRODUCT_SERVICE)
        problems = []
        if upgrade.get("Running") or upgrade.get("ExitCode") != 0:
            problems.append(
                "`%s` %s; its log:\n%s" % (
                    UPGRADE_SERVICE,
                    "is still running" if upgrade.get("Running") else "exited %s" % upgrade.get("ExitCode"),
                    self._logs(UPGRADE_SERVICE),
                )
            )  # fmt: skip
            return problems
        finished, started = _docker_time(upgrade["FinishedAt"]), _docker_time(product["StartedAt"])
        if finished > started:
            problems.append(
                "`%s` finished at %s, after `%s` started at %s"
                % (UPGRADE_SERVICE, finished.isoformat(), PRODUCT_SERVICE, started.isoformat())
            )
        return problems

    def sign_in_encrypted_problems(self):
        """Why the sign-in page does not arrive over a connection verified
        against the proxy's own authority, for the site's name."""
        try:
            answer = self.encrypted_get(SIGN_IN_PATH)
        except ssl.SSLError as error:
            return ["the connection to https://%s was not verified: %s" % (SITE_NAME, error)]
        except (OSError, http.client.HTTPException) as error:
            return ["no encrypted answer at https://%s%s: %s" % (SITE_NAME, SIGN_IN_PATH, error)]
        if answer.status != 200 or "text/html" not in answer.headers.get("content-type", ""):
            return ["https://%s%s did not answer with the page: %r" % (SITE_NAME, SIGN_IN_PATH, answer)]
        return []

    def reachable_from_outside_problems(self):
        """Which services other than the proxy publish a port on the machine."""
        _code, out, _err = self._compose("ps", "--all", "--format", "json")
        text = out.strip()
        rows = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines() if line]
        services = {row.get("Service") for row in rows}
        problems = ["the setup has no `%s` service" % name for name in (PRODUCT_SERVICE, PROXY_SERVICE)
                    if name not in services]  # fmt: skip
        for row in rows:
            if row.get("Service") == PROXY_SERVICE:
                continue
            published = [p for p in row.get("Publishers") or [] if p.get("PublishedPort")]
            if published:
                problems.append(
                    "`%s` publishes %s" % (
                        row.get("Service"),
                        ", ".join("%s:%s->%s" % (p.get("URL"), p.get("PublishedPort"), p.get("TargetPort"))
                                  for p in published),
                    )
                )  # fmt: skip
        return problems

    def open_plain_address(self):
        self.plain_answer = self.plain_get(SIGN_IN_PATH)
        self.world.screen.request("GET", "http://%s%s" % (SITE_NAME, SIGN_IN_PATH), self.plain_answer.status, "")

    def sent_to_encrypted_problems(self):
        """Why the plain address does not send the visitor on to https://localhost/..."""
        answer = self.plain_answer
        if answer is None:
            return ["the plain address was not opened"]
        location = answer.headers.get("location", "")
        expected = "https://%s/" % SITE_NAME
        if answer.status not in REDIRECTS or not location.startswith(expected):
            return ["http://%s%s answered %d, location %r; expected a redirect to %s..."
                    % (SITE_NAME, SIGN_IN_PATH, answer.status, location or "(none)", expected)]  # fmt: skip
        return []
