"""`feather server`, run as a person runs it: a process of its own."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from feather_cli.main import main
from feather_cli.server import bind

START_TIMEOUT_S = 30


@dataclass
class Running:
    process: subprocess.Popen[bytes]
    base_url: str
    log: Path

    def lines(self) -> list[dict[str, str]]:
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.startswith("{")]

    def stop(self) -> int:
        """Asks it to stop as a host or a person at a terminal does."""
        if sys.platform == "win32":
            self.process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            self.process.send_signal(signal.SIGTERM)
        return self.process.wait(timeout=30)


def _get(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - our own local server
        return response.status, response.read()


@pytest.fixture
def running(tmp_path: Path, free_port: int) -> Iterator[Running]:
    """`feather server` on a free port, its database address pointing nowhere
    (/healthz does not need it), in an empty directory (no .env)."""
    log = tmp_path / "server.log"
    env = {
        **os.environ,
        "FEATHER_DATABASE_URL": "postgresql://feather:feather@127.0.0.1:9/feather",
        "FEATHER_LOG_FORMAT": "json",
    }
    with log.open("wb") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "feather_cli", "server", "--host", "127.0.0.1", "--port", str(free_port)],
            cwd=tmp_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            # Its own process group, so the stop signal reaches it alone.
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            start_new_session=sys.platform != "win32",
        )
    server = Running(process, f"http://127.0.0.1:{free_port}", log)
    deadline = time.monotonic() + START_TIMEOUT_S
    while time.monotonic() < deadline and process.poll() is None:
        try:
            _get(server.base_url + "/healthz")
            break
        except urllib.error.URLError, OSError:
            time.sleep(0.2)
    yield server
    if process.poll() is None:
        server.stop()


def test_it_answers_health_checks_on_the_port_it_was_given(running: Running):
    assert _get(running.base_url + "/healthz") == (200, b'{"status":"alive"}')


def test_it_logs_where_it_listens(running: Running):
    _get(running.base_url + "/healthz")

    assert f"listening on {running.base_url}" in [line["message"] for line in running.lines()]


def test_it_stops_cleanly_when_asked(running: Running):
    assert running.stop() == 0


def test_a_settings_mistake_stops_it_with_exit_code_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.delenv("FEATHER_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    code = main(["server"])

    assert (code, capsys.readouterr().err.startswith("error: FEATHER_DATABASE_URL")) == (2, True)


def test_a_port_another_program_listens_on_cannot_be_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as other:
        # Uvicorn's own binding sets SO_REUSEADDR; Windows would let a second
        # program share a port bound like that, unless it asks for exclusive use.
        other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        other.bind(("127.0.0.1", 0))
        other.listen()

        with pytest.raises(OSError):
            bind("127.0.0.1", other.getsockname()[1])
