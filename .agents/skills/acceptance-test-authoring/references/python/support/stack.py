"""Boots the app for the acceptance run and shuts it down after, on its OWN
database and port, so a run never touches the developer's database and never
collides with the dev server, another test suite, or another worktree's run.
Lines marked PROJECT: are the ones each project fills in.

Standard library only, so it also works before the app has any dependencies.
"""

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

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
        "command": ["uv", "run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        "env": {"DATABASE_URL": os.environ.get("ACCEPTANCE_DATABASE_URL")},
        "ready_url": BASE_URL + "/health",
        "port": (PORT, "ACCEPTANCE_PORT"),
    },
]

_children = []  # (service, process, log path)


def prepare():
    """Runs once, before the services start.

    PROJECT: give the run its own empty database here. For Postgres, create a
    scratch database, migrate it, set ACCEPTANCE_DATABASE_URL to it (and fill
    the service's "env" from that), and drop it in stop_all(). For SQLite, a
    file under reports/ deleted here is enough.
    """


def _port_taken(port):
    """Whether something already answers on this port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _start(service):
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / ("%s.log" % service["name"])
    env = dict(os.environ)
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


def stop_all():
    """Stops every service this run started, with its children. Safe to call twice."""
    while _children:
        _service, process, _log_path = _children.pop()
        if process.poll() is not None:
            continue
        try:
            if sys.platform == "win32":
                # The run's database is thrown away, so there is nothing to
                # save: take the whole tree at once.
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)], check=False, capture_output=True
                )
            else:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
        except (ProcessLookupError, PermissionError):
            pass  # already gone


atexit.register(stop_all)
