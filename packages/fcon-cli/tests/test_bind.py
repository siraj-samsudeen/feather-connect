"""The port is bound before Uvicorn starts, so a port or address it cannot
use is said through the error helper."""

import errno
import socket

import pytest

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.server import bind, listen_problem


def bind_problem(host: str, port: int) -> problems.Problem:
    with pytest.raises(ProblemError) as raised:
        bind(host, port).close()
    return raised.value.problem


def test_a_port_another_program_listens_on_is_taken():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as other:
        # Uvicorn's own binding sets SO_REUSEADDR; Windows would let a second
        # program share a port bound like that, unless it asks for exclusive use.
        other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        other.bind(("127.0.0.1", 0))
        other.listen()
        port = other.getsockname()[1]

        assert bind_problem("127.0.0.1", port) == problems.port_taken("127.0.0.1", port)


def test_an_address_of_another_machine_is_not_here(free_port: int):
    assert bind_problem("192.0.2.1", free_port) == problems.host_not_here("192.0.2.1")  # TEST-NET-1


def test_a_host_name_nobody_knows_is_not_here(free_port: int):
    assert bind_problem("no-such-host.invalid", free_port) == problems.host_not_here("no-such-host.invalid")


# The codes this system uses for it: EACCES, and on Windows also WSAEACCES (10013).
@pytest.mark.parametrize("code", sorted({errno.EACCES, getattr(errno, "WSAEACCES", errno.EACCES)}))
def test_a_port_the_machine_refuses_is_not_allowed(code: int):
    problem = listen_problem(PermissionError(code, "permission denied"), "0.0.0.0", 80)  # noqa: S104

    assert problem == problems.port_not_allowed("0.0.0.0", 80)  # noqa: S104


def test_any_other_failure_to_listen_is_not_a_settings_mistake():
    assert listen_problem(OSError(errno.ENOBUFS, "no buffer space"), "127.0.0.1", 8080) is None


def test_a_free_port_is_bound(free_port: int):
    with bind("127.0.0.1", free_port) as sock:
        assert sock.getsockname()[1] == free_port
