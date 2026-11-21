"""A developer's terminal: `fcon server` typed at a prompt, and what it
printed. The command, the settings it is given, and every message text the
start-up checks expect live here; the steps only ask questions.

The command runs from an empty directory of its own, with none of the
developer's FCON_* variables (nor PORT), so neither the developer's shell
nor the worktree's .env can fill in a setting the scenario leaves out.
"""

import html
import os
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request

from support import stack

START_TIMEOUT_S = 90  # `uv run` may first sync the environment
ANSWER_TIMEOUT_S = 1
SETTINGS_MISTAKE_EXIT = 2  # the error helper's exit code for a setting only a person can fix

# Issue 4, point 5: the error helper's texts, exactly.
DATABASE_URL_MISSING = (
    "error: FCON_DATABASE_URL is not set.",
    "  Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather",
    "  For development: copy .env.example to .env, then run: docker compose up -d",
)


def port_taken(port):
    return (
        "error: port %d on 127.0.0.1 is already in use." % port,
        "  Stop the program using it, or pick another port: FCON_PORT=%d (or --port %d)" % (port + 1, port + 1),
    )


TRACEBACK = "Traceback"

# What the command must not inherit: these are its settings, and the scenario sets them.
CLEARED_VARIABLES = ("PORT", "PYTHONPATH", "UV_ENV_FILE", "VIRTUAL_ENV")


class Result:
    def __init__(self, exit_code, output, timed_out):
        self.exit_code = exit_code
        self.output = output
        self.timed_out = timed_out

    def lines(self):
        return self.output.splitlines()

    def __repr__(self):
        return "exit %s%s, output:\n%s" % (
            self.exit_code,
            " (still running after %ds: stopped)" % START_TIMEOUT_S if self.timed_out else "",
            self.output or "(nothing)",
        )


class Terminal:
    def __init__(self, world):
        self.world = world
        self.env = {}  # the FCON_* settings the scenario gives the command
        self.port = None  # the port the server is told to listen on
        self.result = None
        self._held = None  # the other program's socket, while the scenario lasts

    # -- the situation ---------------------------------------------------

    def without_database_address(self):
        self.env.pop("FCON_DATABASE_URL", None)
        self.port = stack.free_port()

    def port_held_by_another_program(self):
        """A program of the scenario's own listens on a free port until the
        scenario ends, and the server is told to use that port."""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        holder.bind(("127.0.0.1", 0))
        holder.listen(1)
        self._held = holder
        self.port = holder.getsockname()[1]
        self.env["FCON_DATABASE_URL"] = stack.run_database_url()

    # -- the command -----------------------------------------------------

    def _environment(self):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("FCON_")}
        for name in CLEARED_VARIABLES:
            env.pop(name, None)
        env.update(self.env)
        if self.port is not None:
            env["FCON_PORT"] = str(self.port)
        return env

    def start_server(self):
        """`uv run fcon server`, from an empty directory, until it ends or the timeout."""
        if self.port is None:
            self.port = stack.free_port()
        command = [shutil.which("uv") or "uv", "run", "--project", str(stack.REPO_ROOT), "fcon", "server"]
        own_group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with tempfile.TemporaryDirectory(prefix="fcon-terminal-") as empty:
            process = subprocess.Popen(
                command,
                cwd=empty,
                env=self._environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **own_group,
            )
            stack.track(process, "terminal")
            timed_out = False
            try:
                output, _ = process.communicate(timeout=START_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                timed_out = True
                stack.stop(process)
                output, _ = process.communicate()
            stack.forget(process)
        text = output.decode("utf-8", errors="replace").replace("\r\n", "\n")
        self.result = Result(process.returncode, text, timed_out)
        self._show()

    def _show(self):
        """VIDEO=1 only: the terminal's output on a page of its own (about:blank,
        never the app), so a person watching the review video sees it."""
        from support import world as world_module

        if not world_module.VIDEO:
            return
        page = self.world.signed_out("the terminal")
        page.set_content(
            "<!doctype html><title>Terminal</title>"
            "<body bgcolor='#111827' text='#e5e7eb'><pre>&gt; uv run fcon server\n%s\n[exit code %s]</pre></body>"
            % (html.escape(self.result.output), self.result.exit_code)
        )

    def close(self):
        if self._held is not None:
            self._held.close()
            self._held = None

    # -- what happened ---------------------------------------------------

    def _result(self):
        if self.result is None:
            raise AssertionError("the server has not been started yet")
        return self.result

    def _something_answers(self):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/healthz" % self.port, timeout=ANSWER_TIMEOUT_S):
                return True
        except urllib.error.HTTPError:
            return True  # an HTTP answer, even an error, is a server
        except (urllib.error.URLError, OSError):
            return False

    def server_did_not_start(self):
        """(yes?, why): it stopped by itself, with the settings-mistake exit
        code, and no server answers on its port."""
        result = self._result()
        if result.timed_out or result.exit_code != SETTINGS_MISTAKE_EXIT:
            return False, "expected exit code %d; %r" % (SETTINGS_MISTAKE_EXIT, result)
        if self._something_answers():
            return False, "a server answers on port %d; %r" % (self.port, result)
        return True, result

    def _says(self, expected):
        result = self._result()
        lines = result.lines()
        missing = [line for line in expected if line not in lines]
        if missing:
            return False, "missing line(s) %r; %r" % (missing, result)
        if TRACEBACK in result.output:
            return False, "it printed a stack trace; %r" % result
        return True, result

    def says_database_address_missing(self):
        """(yes?, why): the address is named as missing, with how to set it, and no stack trace."""
        return self._says(DATABASE_URL_MISSING)

    def names_taken_port(self):
        """(yes?, why): the port is named as taken, with how to choose another, and no stack trace."""
        return self._says(port_taken(self.port))
