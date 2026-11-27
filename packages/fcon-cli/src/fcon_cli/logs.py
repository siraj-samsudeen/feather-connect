"""The one logger: a single handler on the root logger.

Readable text on a terminal and one JSON object per line elsewhere (FCON_LOG_FORMAT=text or json overrides).
Uvicorn's loggers are left unconfigured (log_config=None), so their lines reach it too.
"""

import json
import logging
from datetime import UTC, datetime
from typing import TextIO

from fcon_cli.problems import Level, Problem
from fcon_server.health import LIVENESS_PATH, READINESS_PATH
from fcon_server.store.context import bound

HEALTH_PATHS = {LIVENESS_PATH, READINESS_PATH}
TEXT_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_LEVELS = {Level.ERROR: logging.ERROR, Level.WARNING: logging.WARNING, Level.INFO: logging.INFO}
_PROBLEM = "problem"  # the record's mark: its message is the error helper's text


def log_problem(logger: logging.Logger, problem: Problem, exc_info: bool = False) -> None:
    """Log the error helper's whole text as one record at the problem's level.

    With exc_info, the exception being handled (a bug) goes with it.
    """
    logger.log(_LEVELS[problem.level], problem.text(), exc_info=exc_info, extra={_PROBLEM: True})


def _context_fields() -> dict[str, str]:
    """The tenant and request id of the request or job being served, if any (design decision 5).

    They go on every line, Uvicorn's included.
    """
    context = bound()
    return {} if context is None else {"tenant": context.tenant_id, "request_id": context.request_id}


def time_of(record: logging.LogRecord) -> str:
    """The record's time in UTC as ISO 8601, to the millisecond, with its offset: the same in both formats."""
    return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")


def _one_line(value: str) -> str:
    """The value with its line breaks and control characters escaped as JSON writes them.

    That way a request id sent by a client cannot start a line of its own.
    """
    return json.dumps(value, ensure_ascii=False)[1:-1]


class Text(logging.Formatter):
    """The text format: the time, the level, the request's context fields, then the message.

    A problem's text starts with its own level ("warning: ..."), so its line leaves out the level name.
    """

    def __init__(self) -> None:
        super().__init__(TEXT_FORMAT)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """The record's time as time_of gives it; datefmt is not used."""
        return time_of(record)

    def formatMessage(self, record: logging.LogRecord) -> str:
        """The record's line, with the context fields and, unless it is a problem, the level name."""
        fields = "".join(f"{name}={_one_line(value)} " for name, value in _context_fields().items())
        if getattr(record, _PROBLEM, False):
            return f"{record.asctime} {fields}{record.message}"
        return f"{record.asctime} {record.levelname} {fields}{record.message}"


class JsonLines(logging.Formatter):
    """One JSON object per record: time, level, logger, context fields, message, and the exception if any."""

    def format(self, record: logging.LogRecord) -> str:
        """The record as one line of JSON."""
        line = {
            "time": time_of(record),
            "level": record.levelname.lower(),
            "logger": record.name,
            **_context_fields(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def is_successful_health_check(record: logging.LogRecord) -> bool:
    """Whether the record is Uvicorn's access line for a 2xx answer at /healthz or /readyz.

    A monitor asks every few seconds, and a success says nothing new, so these lines are left out.
    """
    if record.name != "uvicorn.access" or not isinstance(record.args, tuple) or len(record.args) != 5:
        return False
    _client, _method, path, _version, status = record.args
    return str(path).split("?")[0] in HEALTH_PATHS and isinstance(status, int) and 200 <= status < 300


def configure_logging(log_format: str, stream: TextIO) -> None:
    """Send every log record to `stream` as text or JSON, leaving out successful health checks.

    log_format: "text", "json", or "" for text on a terminal, json elsewhere. Replaces the root logger's handlers and
    sets its level to INFO.
    """
    as_json = log_format == "json" if log_format else not stream.isatty()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLines() if as_json else Text())
    handler.addFilter(lambda record: not is_successful_health_check(record))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
