"""What a monitor is told at /readyz."""

import socket

import pytest
from fastapi.testclient import TestClient

from feather_server.app import create_app
from feather_server.database import DatabaseAddress, DatabaseCheck, Problem
from feather_server.health import readiness

READY = {"status": "ready", "checks": {"database": "ok"}}
NOT_READY = {"status": "not ready", "checks": {"database": "unavailable"}}
ADDRESS = DatabaseAddress(host="db.internal", port="5432", dbname="feather", user="feather")


@pytest.mark.database
def test_readyz_says_ready_when_the_database_is_usable(database_url: str):
    response = TestClient(create_app(database_url)).get("/readyz")

    assert (response.status_code, response.json()) == (200, READY)


def test_readyz_says_not_ready_when_the_database_cannot_be_reached(free_port: int):
    app = create_app(f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")

    response = TestClient(app).get("/readyz")

    assert (response.status_code, response.json()) == (503, NOT_READY)


def test_readyz_never_probes_the_port_of_a_database_that_does_not_answer(
    silent_port: int, monkeypatch: pytest.MonkeyPatch
):
    """The probe only names the cause for the log, and takes seconds."""
    probes: list[object] = []

    def probe(address: object, *_args: object, **_kwargs: object) -> socket.socket:
        probes.append(address)
        raise ConnectionRefusedError

    monkeypatch.setattr(socket, "create_connection", probe)
    app = create_app(f"postgresql://feather:feather@127.0.0.1:{silent_port}/feather")

    TestClient(app).get("/readyz")

    assert probes == []


@pytest.mark.parametrize("problem", list(Problem), ids=[problem.name.lower() for problem in Problem])
def test_every_database_problem_is_answered_as_unavailable(problem: Problem):
    check = DatabaseCheck(address=ADDRESS, problem=problem, reason="timed out", version="16.4", detail="FATAL: x")

    assert readiness(check) == (503, NOT_READY)
