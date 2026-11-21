"""The one logger: text on a terminal, one JSON object per line elsewhere;
Uvicorn's lines go through it; successful health checks are left out."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from feather_cli.logs import configure_logging


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def access_line(path: str, status: int) -> None:
    """A request line as Uvicorn's access logger writes it."""
    logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:50000", "GET", path, "1.1", status)


def test_away_from_a_terminal_each_line_is_one_json_object():
    stream = io.StringIO()
    configure_logging("", stream)

    logging.getLogger("feather").info("listening on %s", "http://127.0.0.1:8080")

    line = json.loads(stream.getvalue())
    assert (line["level"], line["logger"], line["message"]) == ("info", "feather", "listening on http://127.0.0.1:8080")


def test_on_a_terminal_the_lines_are_text():
    stream = Terminal()
    configure_logging("", stream)

    logging.getLogger("feather").info("listening on %s", "http://127.0.0.1:8080")

    assert stream.getvalue().rstrip().endswith("INFO listening on http://127.0.0.1:8080")


def test_json_can_be_chosen_on_a_terminal():
    stream = Terminal()
    configure_logging("json", stream)

    logging.getLogger("feather").info("listening")

    assert json.loads(stream.getvalue())["message"] == "listening"


def test_text_can_be_chosen_away_from_a_terminal():
    stream = io.StringIO()
    configure_logging("text", stream)

    logging.getLogger("feather").info("listening")

    assert stream.getvalue().rstrip().endswith("INFO listening")


def test_a_failure_is_logged_with_its_traceback():
    stream = io.StringIO()
    configure_logging("", stream)

    try:
        raise RuntimeError("a bug")
    except RuntimeError:
        logging.getLogger("feather").exception("request failed")

    assert "RuntimeError: a bug" in json.loads(stream.getvalue())["exception"]


def test_uvicorns_lines_go_through_the_one_logger():
    stream = io.StringIO()
    configure_logging("", stream)

    access_line("/sign-in", 200)

    assert json.loads(stream.getvalue())["logger"] == "uvicorn.access"


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_a_successful_health_check_is_not_logged(path: str):
    stream = io.StringIO()
    configure_logging("", stream)

    access_line(path, 200)

    assert stream.getvalue() == ""


def test_a_failed_readiness_check_is_logged():
    stream = io.StringIO()
    configure_logging("", stream)

    access_line("/readyz", 503)

    assert '"GET /readyz HTTP/1.1" 503' in json.loads(stream.getvalue())["message"]
