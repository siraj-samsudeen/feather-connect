"""Boots the app for the acceptance run and shuts it down after, on its OWN
database and port, so a run never touches the developer's database and never
collides with the dev server, another test suite, or another worktree's run.
Lines marked PROJECT: are the ones each project fills in.

The standard library, plus psycopg to make the run's own database.
"""

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg
from psycopg import conninfo, sql

ACCEPTANCE = Path(__file__).resolve().parents[1]
REPO_ROOT = ACCEPTANCE.parent
LOGS = ACCEPTANCE / "reports" / "logs"

PORT = int(os.environ.get("ACCEPTANCE_PORT", "8030"))
# 127.0.0.1, not localhost: on Windows localhost is tried as ::1 first, and a
# server bound to 127.0.0.1 then answers slowly or not at all.
BASE_URL = "http://127.0.0.1:%d" % PORT
BOOT_TIMEOUT_S = 240

# PROJECT: the command that starts the app on this port and on its own,
# freshly reset database, and a URL that answers 2xx once it is up.
# A server-rendered app is one service: the server renders the pages itself.
# If a separate client is added later (a React dev server), add a second
# entry with its own port and variable, and point BASE_URL at it.
SERVICES = [
    {
        "name": "server",
        "command": ["uv", "run", "fcon", "server", "--host", "127.0.0.1", "--port", str(PORT)],
        "env": {},  # FCON_DATABASE_URL: the run's own database, set by prepare()
        "ready_url": BASE_URL + "/readyz",
        "port": (PORT, "ACCEPTANCE_PORT"),
    },
]

# The Postgres server the run makes its throwaway database on: the shared
# development container by default, the CI job's service container there.
ADMIN_DATABASE_URL = os.environ.get(
    "ACCEPTANCE_ADMIN_DATABASE_URL", "postgresql://feather:feather@127.0.0.1:5442/postgres"
)
RUN_DATABASE = "feather_acceptance_%d_%s" % (PORT, uuid.uuid4().hex[:8])

_children = []  # (service, process, log path)
_database_created = False


def run_database_url():
    """The address of this run's own database."""
    return str(conninfo.make_conninfo(ADMIN_DATABASE_URL, dbname=RUN_DATABASE))


def _admin():
    try:
        return psycopg.connect(ADMIN_DATABASE_URL, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as err:
        raise RuntimeError(
            "cannot reach the test database server (%s).\n"
            "Start the database: docker compose up -d" % str(err).splitlines()[0]
        ) from None


def prepare():
    """Runs once, before the services start: the run's own database, upgraded
    with `fcon db upgrade` as an operator would before starting the product,
    and dropped again in stop_all(). The shared database is never stopped."""
    global _database_created
    with _admin() as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(RUN_DATABASE)))
    _database_created = True
    upgrade_database(run_database_url())
    for service in SERVICES:
        service["env"]["FCON_DATABASE_URL"] = run_database_url()


# -- a scenario's own database ------------------------------------------------

COMMAND_TIMEOUT_S = 120  # `uv run` may first sync the environment

# What a command must not inherit: its settings are the ones it is given.
CLEARED_VARIABLES = ("PORT", "PYTHONPATH", "UV_ENV_FILE", "VIRTUAL_ENV")


def create_database():
    """A new, empty database of a scenario's own, on the same server as the
    run's. Returns its address; give it to drop_database() at the end."""
    name = "feather_acceptance_%d_s_%s" % (PORT, uuid.uuid4().hex[:8])
    with _admin() as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return str(conninfo.make_conninfo(ADMIN_DATABASE_URL, dbname=name))


def drop_database(database_url):
    name = conninfo.conninfo_to_dict(database_url)["dbname"]
    with _admin() as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def fcon_environment(settings):
    """The environment of an `fcon` command: none of the developer's FCON_*
    variables, only the settings given."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("FCON_")}
    for name in CLEARED_VARIABLES:
        env.pop(name, None)
    env.update(settings)
    return env


def start_fcon(arguments, settings):
    """`uv run fcon <arguments>`, from an empty directory of its own (so no
    .env fills in a setting), with only the given FCON_* settings. Returns the
    running process, its stdout and stderr piped; finish it with finish_fcon()."""
    command = [shutil.which("uv") or "uv", "run", "--project", str(REPO_ROOT), "fcon", *arguments]
    own_group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    empty = tempfile.mkdtemp(prefix="fcon-command-")
    process = subprocess.Popen(
        command,
        cwd=empty,
        env=fcon_environment(settings),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **own_group,
    )
    process.empty_directory = empty
    track(process, "fcon " + " ".join(arguments))
    return process


def finish_fcon(process):
    """Waits for a command from start_fcon(). Returns (exit code, stdout,
    stderr, timed out?), the texts with Unix line endings."""
    timed_out = False
    try:
        out, err = process.communicate(timeout=COMMAND_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop(process)
        out, err = process.communicate()
    forget(process)
    shutil.rmtree(process.empty_directory, ignore_errors=True)

    def text(data):
        return data.decode("utf-8", errors="replace").replace("\r\n", "\n")

    return process.returncode, text(out), text(err), timed_out


def upgrade_database(database_url):
    """`fcon db upgrade` on that database, as setup: anything but success
    stops the run, with what the command said."""
    code, out, err, timed_out = finish_fcon(start_fcon(["db", "upgrade"], {"FCON_DATABASE_URL": database_url}))
    if code != 0 or timed_out:
        raise RuntimeError(
            "`fcon db upgrade` did not upgrade the test database (exit %s%s).\n--- output ---\n%s%s"
            % (code, ", timed out" if timed_out else "", out, err)
        )


def _drop_database():
    global _database_created
    if not _database_created:
        return
    with _admin() as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(RUN_DATABASE)))
    _database_created = False


def _port_taken(port):
    """Whether something already answers on this port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _start(service):
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / ("%s.log" % service["name"])
    env = dict(os.environ)
    # The suite's own import path (run_acceptance.py) is not the app's: with
    # it, the suite's `support` or `pages` could hide a module of the app.
    kept = [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and Path(p).resolve() != ACCEPTANCE]
    env.pop("PYTHONPATH", None)
    if kept:
        env["PYTHONPATH"] = os.pathsep.join(kept)
    env.update({k: v for k, v in service["env"].items() if v is not None})
    command = list(service["command"])
    # Finds .cmd and .exe launchers on Windows (npm is npm.cmd there).
    command[0] = shutil.which(command[0]) or command[0]
    # Its own process group, so shutdown takes its children with it: `uv run`
    # and a reloading server both start the real server as a child.
    own_group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            command, cwd=str(REPO_ROOT), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **own_group
        )
    _children.append((service, process, log_path))
    return process, log_path


def _last_output(log_path, lines=60):
    try:
        return "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no output)"


def _wait_for(service, process, log_path):
    deadline = time.monotonic() + BOOT_TIMEOUT_S
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with urllib.request.urlopen(service["ready_url"], timeout=2) as response:
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, OSError):
            pass  # not up yet
        time.sleep(0.5)
    raise RuntimeError(
        "%s did not come up at %s.\n--- last output (%s) ---\n%s"
        % (service["name"], service["ready_url"], log_path, _last_output(log_path))
    )


def start_all():
    """Starts every service and waits until each answers."""
    # A second run started while one is going would answer its boot checks from
    # the first run's server, reset the database under it, and then lose it
    # when the first run ends: both fail in ways that point nowhere near the
    # cause. So refuse, and say which port and which variable moves it.
    for service in SERVICES:
        port, variable = service["port"]
        if _port_taken(port):
            raise RuntimeError(
                "port %d is already in use, most likely by another acceptance run. "
                "Wait for it to finish, or run on another port (%s)." % (port, variable)
            )
    prepare()
    started = [(service,) + _start(service) for service in SERVICES]
    for service, process, log_path in started:
        _wait_for(service, process, log_path)


def free_port():
    """A port nothing listens on right now, chosen by the operating system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_server(name, database_url, ready_path="/healthz"):
    """A second `fcon server` for one scenario, on a free port and the given
    database address, waited on at `ready_path`. Returns (base URL, process);
    give the process to stop() at the scenario's end (stop_all() takes any
    that are left)."""
    port = free_port()
    base_url = "http://127.0.0.1:%d" % port
    service = {
        "name": name,
        "command": ["uv", "run", "fcon", "server", "--host", "127.0.0.1", "--port", str(port)],
        "env": {"FCON_DATABASE_URL": database_url},
        "ready_url": base_url + ready_path,
    }
    process, log_path = _start(service)
    try:
        _wait_for(service, process, log_path)
    except Exception:
        stop(process)
        raise
    return base_url, process


def _stop(process):
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            # The run's database is thrown away, so there is nothing to
            # save: take the whole tree at once, by its PID.
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], check=False, capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)  # the group, as above: not only its leader
    except (ProcessLookupError, PermissionError):
        pass  # already gone


def log_path(process):
    """Where a service started by this run writes its output."""
    for _service, child, path in _children:
        if child is process:
            return path
    raise RuntimeError("that process is not a service of this run")


def track(process, name):
    """A process a page object started itself (pages/terminal.py): stop_all()
    takes it if the run ends while it is still going."""
    _children.append(({"name": name}, process, None))


def forget(process):
    """That process has ended: nothing left to stop."""
    for child in list(_children):
        if child[1] is process:
            _children.remove(child)


def stop(process):
    """Stops one process this run started, with its children."""
    for child in list(_children):
        if child[1] is process:
            _children.remove(child)
    _stop(process)


def stop_all():
    """Stops every service this run started, with its children. Safe to call twice."""
    while _children:
        _service, process, _log_path = _children.pop()
        _stop(process)
    _drop_database()


atexit.register(stop_all)
