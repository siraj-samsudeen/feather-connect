"""The host an operator runs the product's image on, as a container runtime
(Docker) sees it: a Postgres 18 server run outside the product, with the
database an administrator made for it, the image run once to upgrade that
database, then started to serve. Every setting name, command, port and user
the deployment scenarios rely on lives here; the steps only ask questions.
The Docker mechanics are in support/docker.py.

The stand-in for the administrator's Postgres is a `postgres:18` container on
the scenario's own network; the product's containers reach it by its
container name. As the guide's one-time SQL does, its superuser makes the
owner user `fcon` (for upgrades), the app user `fcon_app` (for the server)
and the database `fcon`, owned by `fcon`.
"""

import secrets
import time
import urllib.error
import urllib.request

from support import docker, stack

POSTGRES_PORT = 5432
DATABASE = "fcon"
OWNER_USER = "fcon"
APP_USER = "fcon_app"

# The image's own default port, when the host gives none (FCON_PORT, else PORT, else 8080).
DEFAULT_PORT = 8080
HOST_PORT_SETTING = "PORT"  # what a cloud host that runs containers sets
DATABASE_SETTING = "FCON_DATABASE_URL"
MIGRATION_DATABASE_SETTING = "FCON_MIGRATION_DATABASE_URL"
UPGRADE = ("db", "upgrade")  # the image's command is `fcon`: these are its arguments
# The image starts the server by itself (its CMD): the operator gives no command.

LIVENESS_PATH = "/healthz"
POSTGRES_READY_S = 90
ANSWER_S = 60  # the server answers within seconds of its container starting
HEALTHY_S = 60  # the image's health check: every 10 s (every 1 s while starting), 3 misses
UPGRADE_TIMEOUT_S = 180

ALREADY_UP_TO_DATE = "the database was already up to date."
UP_TO_DATE_PREFIX = "the database is up to date: "


def _address(host, user, password):
    return "postgresql://%s:%s@%s:%d/%s" % (user, password, host, POSTGRES_PORT, DATABASE)


class ContainerHost:
    def __init__(self, world):
        self.world = world
        self._scenario = None
        self.postgres = None
        self.owner_address = None
        self.app_address = None
        self.host_port = None  # the port the host gives the product, if any
        self.product = None  # the product's container, once started
        self.container_port = None
        self.upgrade_result = None

    # --- the scenario's containers ----------------------------------------

    def _containers(self):
        if self._scenario is None:
            self._scenario = docker.Scenario()
        return self._scenario

    def network(self):
        """The scenario's own network, where its Postgres is reached by its container name."""
        return self._containers().network

    def close(self):
        """Removes the scenario's containers and network (environment.py, after the scenario)."""
        if self._scenario is not None:
            self._scenario.close()
            self._scenario = None

    # --- the database server, outside the product -------------------------

    def new_postgres_database(self):
        """A Postgres 18 server of the scenario's own, with a new, empty
        database `fcon` and its two users, as an administrator makes them."""
        containers = self._containers()
        superuser_password = secrets.token_hex(12)
        owner_password = secrets.token_hex(12)
        app_password = secrets.token_hex(12)
        self.postgres = containers.start(
            "postgres",
            docker.POSTGRES_IMAGE,
            {"POSTGRES_PASSWORD": superuser_password},
            options=("--tmpfs", "/var/lib/postgresql"),
        )
        # Over TCP: while the image makes its data folder, its server takes
        # connections on its socket only, then restarts.
        ready = docker.wait_until(
            lambda: containers.exec(self.postgres, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", check=False)[0] == 0,
            POSTGRES_READY_S,
        )
        if not ready:
            raise AssertionError(
                "the stand-in Postgres 18 did not start within %d s; its log:\n%s"
                % (POSTGRES_READY_S, self.postgres.log_tail())
            )
        for statement in (
            "CREATE USER %s PASSWORD '%s'" % (OWNER_USER, owner_password),
            "CREATE USER %s PASSWORD '%s'" % (APP_USER, app_password),
            "CREATE DATABASE %s OWNER %s" % (DATABASE, OWNER_USER),
        ):
            containers.exec(self.postgres, "psql", "-h", "127.0.0.1", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                            "-c", statement)  # fmt: skip
        self.owner_address = _address(self.postgres.name, OWNER_USER, owner_password)
        self.app_address = _address(self.postgres.name, APP_USER, app_password)
        self.world.database = {
            "host": self.postgres.name,
            "port": str(POSTGRES_PORT),
            "user": APP_USER,
            "password": app_password,
            "dbname": DATABASE,
        }
        self.world.screen.note("a new, empty Postgres 18 database `fcon`, with its owner and app users")

    def _require_database(self):
        if self.app_address is None:
            raise RuntimeError("the scenario has no Postgres database yet: its first Given makes one")

    # --- the host ------------------------------------------------------------

    def gives_port(self, port):
        """The host gives the product this port, as a cloud host does with PORT."""
        self.host_port = int(port)

    # --- the product's image ----------------------------------------------

    def upgrade_database(self):
        """`fcon db upgrade` from the image, run once to its end, with both
        addresses: the owner's to upgrade, the app's to grant its rights."""
        self._require_database()
        image = docker.image()
        self.world.screen.note("$ docker run --rm <image> db upgrade")
        code, out, err = self._containers().run(
            "migrate",
            image,
            {MIGRATION_DATABASE_SETTING: self.owner_address, DATABASE_SETTING: self.app_address},
            UPGRADE,
            timeout=UPGRADE_TIMEOUT_S,
        )
        self.upgrade_result = (code, out, err)
        self.world.screen.command("fcon db upgrade", out + err, code)

    def upgrade_problems(self):
        """Why the upgrade did not end well: its exit code and what it said."""
        if self.upgrade_result is None:
            return ["the database was not upgraded with the image"]
        code, out, err = self.upgrade_result
        said = out + err
        if code == 0 and (ALREADY_UP_TO_DATE in said or UP_TO_DATE_PREFIX in said):
            return []
        return ["`fcon db upgrade` from the image exited %s, saying:\n%s" % (code, said or "(nothing)")]

    def start_product(self):
        """The image started in the background with only the app's database
        address (and the host's port, when it gives one), its port published
        on a free one of 127.0.0.1; the scenario then talks to it, once it
        answers there."""
        self._require_database()
        image = docker.image()
        settings = {DATABASE_SETTING: self.app_address, stack.SECRET_KEY_SETTING: stack.SECRET_KEY}
        self.container_port = DEFAULT_PORT
        if self.host_port is not None:
            settings[HOST_PORT_SETTING] = str(self.host_port)
            self.container_port = self.host_port
        self.world.screen.note("$ docker run -d -e %s=... <image>" % " -e ".join(sorted(settings)))
        self.product = self._containers().start("server", image, settings, publish=(self.container_port,))
        host, port = self.product.published(self.container_port)
        base_url = "http://%s:%d" % (host, port)
        if not self._answers(base_url):
            raise AssertionError(
                "the product's container did not answer on its port %d within %d s (%s); its log:\n%s"
                % (self.container_port, ANSWER_S, self._state(), self.product.log_tail())
            )
        self.world.use_product_at(base_url)

    def _answers(self, base_url):
        """Whether the product answers at base_url, waiting until it does or its container stops."""

        def answer():
            try:
                with urllib.request.urlopen(base_url + LIVENESS_PATH, timeout=2):
                    return True
            except urllib.error.HTTPError:
                return True  # an answer, whatever it says
            except (urllib.error.URLError, OSError):
                return False

        docker.wait_until(lambda: answer() or not self.product.running(), ANSWER_S)
        return answer()

    def _state(self):
        state = self.product.state()
        if state.get("Running"):
            return "still running"
        return "stopped, exit code %s" % state.get("ExitCode")

    # --- what the host sees -------------------------------------------------

    def product_port(self):
        """The port inside the container the scenario reaches the product on."""
        if self.product is None:
            raise AssertionError("the product's image was not started")
        return self.container_port

    def becomes_healthy(self, timeout_s=HEALTHY_S):
        """(yes?, why not): the container runtime reports the product as
        healthy, by the image's own health check, within the time."""
        if self.product is None:
            return False, "the product's image was not started"
        deadline = time.monotonic() + timeout_s
        while True:
            status, last = self.product.health()
            if status is None:
                return False, "the image has no health check: Docker reports no health for its container"
            if status == "healthy":
                return True, ""
            if time.monotonic() >= deadline or not self.product.running():
                return False, "Docker reports it %s after %d s (last check said: %s); its log:\n%s" % (
                    status, timeout_s, last or "nothing", self.product.log_tail(),
                )  # fmt: skip
            time.sleep(1)
