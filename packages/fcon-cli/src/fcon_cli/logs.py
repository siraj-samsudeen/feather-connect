"""The one logger: a single handler on the root logger, readable text on a
terminal and one JSON object per line elsewhere (FCON_LOG_FORMAT=text or
json overrides). Uvicorn's loggers are left unconfigured (log_config=None),
so their lines reach it too."""

import json
import logging
from datetime import UTC, datetime
from typing import TextIO

from fcon_cli.problems import Level, Problem
from fcon_server.health import LIVENESS_PATH, READINESS_PATH

HEALTH_PATHS = {LIVENESS_PATH, READINESS_PATH}
TEXT_FORMAT = "%(asctime)s %(levelname)s %(message)s"
_LEVELS = {Level.ERROR: logging.ERROR, Level.WARNING: logging.WARNING}
_PROBLEM = "problem"  # the record's mark: its message is the error helper's text


def log_problem(logger: logging.Logger, problem: Problem, exc_info: bool = False) -> None:
    """The error helper's whole text, as one record at its level; with
    exc_info, the exception being handled (a bug) goes with it."""
    logger.log(_LEVELS[problem.level], problem.text(), exc_info=exc_info, extra={_PROBLEM: True})


def time_of(record: logging.LogRecord) -> str:
    """UTC, ISO 8601, to the millisecond, with its offset: the same in both formats."""
    return datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")


class Text(logging.Formatter):
    """A problem's text starts with its own level ("warning: ..."), so its
    line leaves out the level name."""

    def __init__(self) -> None:
        super().__init__(TEXT_FORMAT)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return time_of(record)

    def formatMessage(self, record: logging.LogRecord) -> str:
        if getattr(record, _PROBLEM, False):
            return f"{record.asctime} {record.message}"
        return super().formatMessage(record)


class JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": time_of(record),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False)


def is_successful_health_check(record: logging.LogRecord) -> bool:
    """Uvicorn's access line for a 2xx answer at /healthz or /readyz: a
    monitor asks every few seconds, and a success says nothing new."""
    if record.name != "uvicorn.access" or not isinstance(record.args, tuple) or len(record.args) != 5:
        return False
    _client, _method, path, _version, status = record.args
    return str(path).split("?")[0] in HEALTH_PATHS and isinstance(status, int) and 200 <= status < 300


def configure_logging(log_format: str, stream: TextIO) -> None:
    """log_format: "text", "json", or "" for text on a terminal, json elsewhere."""
    as_json = log_format == "json" if log_format else not stream.isatty()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLines() if as_json else Text())
    handler.addFilter(lambda record: not is_successful_health_check(record))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
