"""The one logger: text on a terminal, one JSON object per line elsewhere;
Uvicorn's lines go through it; successful health checks are left out."""

import io
import json
import logging

import pytest

from fcon_cli.logs import JsonLines, Text, configure_logging, log_problem
from fcon_cli.problems import Level, Problem
from fcon_server.store.context import Context, bind


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


PROBLEM = Problem(Level.WARNING, "something is wrong.", ("Do this.", "Or that."))


def access_line(path: str, status: int) -> None:
    """A request line as Uvicorn's access logger writes it."""
    logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:50000", "GET", path, "1.1", status)


def test_away_from_a_terminal_each_line_is_one_json_object():
    stream = io.StringIO()
    configure_logging("", stream)

    logging.getLogger("fcon").info("listening on %s", "http://127.0.0.1:8080")

    line = json.loads(stream.getvalue())
    assert (line["level"], line["logger"], line["message"]) == ("info", "fcon", "listening on http://127.0.0.1:8080")


def test_on_a_terminal_the_lines_are_text():
    stream = Terminal()
    configure_logging("", stream)

    logging.getLogger("fcon").info("listening on %s", "http://127.0.0.1:8080")

    assert stream.getvalue().rstrip().endswith("INFO listening on http://127.0.0.1:8080")


def test_json_can_be_chosen_on_a_terminal():
    stream = Terminal()
    configure_logging("json", stream)

    logging.getLogger("fcon").info("listening")

    assert json.loads(stream.getvalue())["message"] == "listening"


def test_text_can_be_chosen_away_from_a_terminal():
    stream = io.StringIO()
    configure_logging("text", stream)

    logging.getLogger("fcon").info("listening")

    assert stream.getvalue().rstrip().endswith("INFO listening")


def test_a_failure_is_logged_with_its_traceback():
    stream = io.StringIO()
    configure_logging("", stream)

    try:
        raise RuntimeError("a bug")
    except RuntimeError:
        logging.getLogger("fcon").exception("request failed")

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


def test_away_from_a_terminal_a_problem_is_one_json_object():
    stream = io.StringIO()
    configure_logging("", stream)

    log_problem(logging.getLogger("fcon"), PROBLEM)

    line = json.loads(stream.getvalue())
    assert (line["level"], line["message"]) == ("warning", PROBLEM.text())


def test_an_error_is_logged_at_the_error_level():
    stream = io.StringIO()
    configure_logging("", stream)

    log_problem(logging.getLogger("fcon"), Problem(Level.ERROR, "broken."))

    assert json.loads(stream.getvalue())["level"] == "error"


def test_on_a_terminal_a_problem_reads_as_its_own_text_after_the_time():
    stream = Terminal()
    configure_logging("", stream)

    log_problem(logging.getLogger("fcon"), PROBLEM)

    first, *rest = stream.getvalue().splitlines()
    assert (first.split(" ", 1)[1], rest) == ("warning: something is wrong.", ["  Do this.", "  Or that."])


def test_a_text_line_carries_the_same_time_as_its_json_line():
    record = logging.LogRecord("fcon", logging.INFO, __file__, 1, "listening", None, None)

    assert Text().format(record).split(" ")[0] == json.loads(JsonLines().format(record))["time"]


def test_a_note_is_logged_at_the_info_level():
    stream = io.StringIO()
    configure_logging("", stream)

    log_problem(logging.getLogger("fcon"), Problem(Level.INFO, "worth knowing."))

    assert json.loads(stream.getvalue())["level"] == "info"


# -- the context of a request or job (design decision 5) -----------------

CONTEXT = Context(tenant_id="acme-test", actor="system:test", request_id="req-1")


def test_a_json_line_carries_the_tenant_of_the_bound_context():
    stream = io.StringIO()
    configure_logging("json", stream)

    with bind(CONTEXT):
        logging.getLogger("fcon").info("saved")

    line = json.loads(stream.getvalue())
    assert (line["tenant"], line["request_id"]) == ("acme-test", "req-1")


def test_a_text_line_carries_the_tenant_of_the_bound_context_before_its_message():
    stream = io.StringIO()
    configure_logging("text", stream)

    with bind(CONTEXT):
        logging.getLogger("fcon").info("saved")

    assert stream.getvalue().rstrip().endswith("INFO tenant=acme-test request_id=req-1 saved")


def test_a_request_id_with_a_line_break_stays_on_its_text_line():
    stream = io.StringIO()
    configure_logging("text", stream)

    with bind(Context(tenant_id="acme-test", actor="system:test", request_id="req-1\nINFO forged\t\x1b[2J")):
        logging.getLogger("fcon").info("saved")

    assert stream.getvalue().rstrip().endswith(r"INFO tenant=acme-test request_id=req-1\nINFO forged\t\u001b[2J saved")


def test_a_problem_on_a_terminal_carries_the_tenant_of_the_bound_context():
    stream = Terminal()
    configure_logging("", stream)

    with bind(CONTEXT):
        log_problem(logging.getLogger("fcon"), PROBLEM)

    first = stream.getvalue().splitlines()[0]
    assert first.split(" ", 1)[1] == "tenant=acme-test request_id=req-1 warning: something is wrong."


def test_uvicorns_lines_carry_the_tenant_of_the_bound_context():
    stream = io.StringIO()
    configure_logging("json", stream)

    with bind(CONTEXT):
        access_line("/sign-in", 200)

    assert json.loads(stream.getvalue())["tenant"] == "acme-test"


def test_a_line_after_the_context_ends_carries_no_tenant():
    stream = io.StringIO()
    configure_logging("json", stream)

    with bind(CONTEXT):
        pass
    logging.getLogger("fcon").info("idle")

    assert "tenant" not in json.loads(stream.getvalue())
