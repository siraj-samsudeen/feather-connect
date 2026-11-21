"""Where the server listens is logged, with a warning when other machines can reach it (R15.15)."""

import logging

import pytest

from fcon_cli import problems
from fcon_cli.server import announce


def messages(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(record.levelno, record.getMessage()) for record in caplog.records]


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_on_this_machine_it_only_says_where_it_listens(caplog: pytest.LogCaptureFixture, host: str):
    caplog.set_level(logging.INFO)

    announce(host, 8080)

    assert messages(caplog) == [(logging.INFO, f"listening on http://{host}:8080")]


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1"])  # noqa: S104
def test_beyond_this_machine_it_warns(caplog: pytest.LogCaptureFixture, host: str):
    caplog.set_level(logging.INFO)

    announce(host, 8080)

    assert messages(caplog)[1] == (logging.WARNING, problems.listening_beyond_machine(host, 8080).text())
