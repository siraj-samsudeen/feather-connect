"""The suite's Docker: the product's image, built once per run from the
checkout, and the containers and networks a scenario starts, all through the
`docker` command (design, decision 3: no new dependency). Nothing here knows
the product: its settings, commands and ports are in pages/container_host.py.

- Every name carries the run's port and a random part (RUN_NAME), so
  worktrees run side by side; every container and network has the label
  LABEL=RUN_NAME, so stop_all() finds what a scenario left behind.
- A scenario's containers live on a network of their own; its Postgres is a
  container of its own there, never the shared development container.
- Everything is removed at the end: a scenario's containers, their volumes
  and its network when it ends (Scenario.close), the image when the run ends.
- Without Docker, the first scenario that needs it fails, saying to start
  Docker. It never skips.
"""

import atexit
import json
import secrets
import shutil
import subprocess
import time

from support import stack

LOGS = stack.LOGS
RUN_NAME = "fcon-acceptance-%d-%s" % (stack.PORT, secrets.token_hex(4))
LABEL = "fcon.acceptance.run"
IMAGE = "fcon-acceptance:%d-%s" % (stack.PORT, RUN_NAME.rsplit("-", 1)[1])
POSTGRES_IMAGE = "postgres:18"

COMMAND_TIMEOUT_S = 120
BUILD_TIMEOUT_S = 1200  # the first build downloads the base images and every wheel
LOG_TAIL = 60

START_DOCKER = (
    "Docker is not running, or the docker command cannot reach it (%s).\n"
    "Start Docker (Docker Desktop, or the docker service), then run the suite again:"
    " the deployment scenarios run the product's image."
)

_image_built = False
_build_failure = None  # the first build's failure: the run does not build twice


class DockerError(RuntimeError):
    pass


def _text(data):
    return (data or b"").decode("utf-8", errors="replace").replace("\r\n", "\n")


def _tail(text, lines=LOG_TAIL):
    return "\n".join(text.splitlines()[-lines:]) or "(nothing)"


def docker(*arguments, timeout=COMMAND_TIMEOUT_S, check=True):
    """`docker <arguments>`. Returns (exit code, stdout, stderr); with
    check, anything but 0 raises, with what docker said."""
    command = [shutil.which("docker") or "docker", *arguments]
    try:
        done = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False)
    except FileNotFoundError:
        raise DockerError(START_DOCKER % "no docker command on the PATH") from None
    except subprocess.TimeoutExpired:
        raise DockerError("`docker %s` did not finish within %d s" % (" ".join(arguments), timeout)) from None
    out, err = _text(done.stdout), _text(done.stderr)
    if check and done.returncode != 0:
        raise DockerError("`docker %s` failed (exit %d):\n%s" % (" ".join(arguments), done.returncode, _tail(out + err)))
    return done.returncode, out, err


def require_docker():
    """Fails, saying to start Docker, when Docker cannot be reached."""
    code, out, err = docker("info", "--format", "{{.ServerVersion}}", timeout=30, check=False)
    if code != 0 or not out.strip():
        raise DockerError(START_DOCKER % (_tail(err or out, 3).strip() or "docker info failed"))


def image():
    """The product's image, built from the checkout the first time a scenario
    asks for it, and only once per run. Its build log is in reports/logs/."""
    global _image_built, _build_failure
    if _image_built:
        return IMAGE
    if _build_failure is not None:
        raise DockerError(_build_failure)
    require_docker()
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / "image-build.log"
    code, out, err = docker(
        "build", "--tag", IMAGE, "--label", "%s=%s" % (LABEL, RUN_NAME), str(stack.REPO_ROOT),
        timeout=BUILD_TIMEOUT_S, check=False,
    )  # fmt: skip
    log.write_text(out + err, encoding="utf-8")
    if code != 0:
        _build_failure = "the product's image did not build (`docker build %s`, exit %d; log: %s):\n%s" % (
            stack.REPO_ROOT, code, log, _tail(out + err, 30),
        )  # fmt: skip
        raise DockerError(_build_failure)
    _image_built = True
    return IMAGE


class Container:
    """One container a scenario started, by name."""

    def __init__(self, name):
        self.name = name

    def state(self):
        """The container's State, as `docker inspect` gives it."""
        _code, out, _err = docker("inspect", "--format", "{{json .State}}", self.name)
        return json.loads(out)

    def running(self):
        return bool(self.state().get("Running"))

    def health(self):
        """(status, the last check's output): status is "starting", "healthy"
        or "unhealthy", or None when the image has no health check."""
        health = self.state().get("Health")
        if not health:
            return None, ""
        log = health.get("Log") or []
        return health.get("Status"), (log[-1].get("Output", "").strip() if log else "")

    def published(self, container_port):
        """The host's address ("127.0.0.1", port) the container's port is published on."""
        _code, out, _err = docker("port", self.name, "%d/tcp" % container_port)
        first = out.strip().splitlines()[0]
        host, _, port = first.rpartition(":")
        return host.strip("[]"), int(port)

    def logs(self):
        code, out, err = docker("logs", self.name, check=False)
        return (out + err) if code == 0 else "(no log: %s)" % _tail(err, 3)

    def log_tail(self, lines=LOG_TAIL):
        return _tail(self.logs(), lines)

    def save_log(self):
        """Keeps the container's log in reports/logs/<name>.log."""
        LOGS.mkdir(parents=True, exist_ok=True)
        path = LOGS / ("%s.log" % self.name)
        path.write_text(self.logs(), encoding="utf-8")
        return path


class Scenario:
    """A scenario's network and containers, removed when it ends."""

    def __init__(self):
        require_docker()
        self.name = "%s-%s" % (RUN_NAME, secrets.token_hex(3))
        self.network = self.name
        self.containers = []
        docker("network", "create", "--label", "%s=%s" % (LABEL, RUN_NAME), self.network)

    def _label(self):
        return ["--label", "%s=%s" % (LABEL, RUN_NAME)]

    def _env(self, settings):
        return [part for name, value in settings.items() for part in ("--env", "%s=%s" % (name, value))]

    def start(self, role, image_name, settings, publish=(), options=(), arguments=()):
        """Starts a container in the background on the scenario's network:
        `docker run -d`, its settings as --env, each port of `publish`
        published on a free port of 127.0.0.1. Returns the Container."""
        container = Container("%s-%s" % (self.name, role))
        ports = [part for port in publish for part in ("--publish", "127.0.0.1::%d" % port)]
        docker(
            "run", "--detach", "--name", container.name, "--network", self.network, *self._label(),
            *self._env(settings), *ports, *options, image_name, *arguments,
        )  # fmt: skip
        self.containers.append(container)
        return container

    def run(self, role, image_name, settings, arguments=(), timeout=COMMAND_TIMEOUT_S):
        """Runs a container to its end on the scenario's network, as a
        one-shot command. Returns (exit code, stdout, stderr)."""
        name = "%s-%s" % (self.name, role)
        code, out, err = docker(
            "run", "--rm", "--name", name, "--network", self.network, *self._label(), *self._env(settings),
            image_name, *arguments, timeout=timeout, check=False,
        )  # fmt: skip
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / ("%s.log" % name)).write_text(out + err, encoding="utf-8")
        return code, out, err

    def exec(self, container, *command, check=True):
        return docker("exec", container.name, *command, check=check)

    def close(self):
        """Removes the scenario's containers, with their volumes, and its
        network; their logs stay in reports/logs/."""
        while self.containers:
            container = self.containers.pop()
            try:
                container.save_log()
            except (DockerError, OSError):
                pass  # a container that is gone has no log to keep
            docker("rm", "--force", "--volumes", container.name, check=False)
        docker("network", "rm", self.network, check=False)


def wait_until(condition, timeout_s, poll_s=0.5):
    """Asks `condition()` until it is true or the time is up; returns its last answer."""
    deadline = time.monotonic() + timeout_s
    while True:
        answer = condition()
        if answer or time.monotonic() >= deadline:
            return answer
        time.sleep(poll_s)


def stop_all():
    """Removes whatever of this run's is left: containers, networks, the
    image. Safe to call twice, and without Docker."""
    global _image_built
    if shutil.which("docker") is None:
        return
    try:
        _code, out, _err = docker("ps", "--all", "--quiet", "--filter", "label=%s=%s" % (LABEL, RUN_NAME), check=False)
        ids = out.split()
        if ids:
            docker("rm", "--force", "--volumes", *ids, check=False)
        _code, out, _err = docker("network", "ls", "--quiet", "--filter", "label=%s=%s" % (LABEL, RUN_NAME), check=False)
        ids = out.split()
        if ids:
            docker("network", "rm", *ids, check=False)
        if _image_built:
            docker("image", "rm", IMAGE, check=False)
            _image_built = False
    except DockerError:
        pass  # Docker went away: nothing of ours runs there any more


atexit.register(stop_all)
