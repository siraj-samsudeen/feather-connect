"""The one logger: a single handler on the root logger, readable text on a
terminal and one JSON object per line elsewhere (FEATHER_LOG_FORMAT=text or
json overrides). Uvicorn's loggers are left unconfigured (log_config=None),
so their lines reach it too."""

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import TextIO

from feather_server.health import LIVENESS_PATH, READINESS_PATH

HEALTH_PATHS = {LIVENESS_PATH, READINESS_PATH}
TEXT_FORMAT = "%(asctime)s %(levelname)s %(message)s"


class JsonLines(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
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


def configure_logging(environ: Mapping[str, str], stream: TextIO) -> None:
    chosen = environ.get("FEATHER_LOG_FORMAT", "")
    as_json = chosen == "json" if chosen in ("text", "json") else not stream.isatty()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLines() if as_json else logging.Formatter(TEXT_FORMAT))
    handler.addFilter(lambda record: not is_successful_health_check(record))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
