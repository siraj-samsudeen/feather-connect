"""The settings of `feather server`: FEATHER_* environment variables only, and
in development a git-ignored .env file in the current directory, which fills
in only what the environment leaves unset. --host and --port win for one run.
A mistake raises SettingsError, with the error helper's words for it."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import conninfo

from feather_cli import problems
from feather_cli.problems import ProblemError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
ENV_FILE = ".env"
LOG_FORMATS = ("text", "json")  # unset: text on a terminal, json elsewhere


class SettingsError(ProblemError):
    """A settings mistake only a person can fix: the command stops."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str
    log_format: str = ""


def read_env_file(path: Path) -> dict[str, str]:
    """NAME=value lines; blank lines and # comments are skipped."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, equals, value = line.strip().partition("=")
        if equals and not name.startswith("#"):
            values[name.strip()] = value.strip()
    return values


def _checked_port(name: str, text: str) -> int:
    port = int(text) if text.isdigit() else 0
    if not 1 <= port <= 65535:
        raise SettingsError(problems.port_not_a_number(name, text))
    return port


def _port(variables: Mapping[str, str], option: int | None) -> int:
    if option is not None:
        return _checked_port("--port", str(option))
    name = "FEATHER_PORT" if "FEATHER_PORT" in variables else "PORT"
    return _checked_port(name, variables.get(name, str(DEFAULT_PORT)))


def _database_url(variables: Mapping[str, str]) -> str:
    """An address psycopg reads, as it takes it: a postgresql:// or postgres://
    URL, or libpq's key=value form. Never repeated: it may hold a password."""
    url = variables.get("FEATHER_DATABASE_URL", "")
    if not url:
        raise SettingsError(problems.database_url_missing())
    try:
        port = str(conninfo.conninfo_to_dict(url).get("port") or "5432")
    except psycopg.ProgrammingError:
        port = ""
    if not port.isdigit():
        raise SettingsError(problems.database_url_not_postgres())
    return url


def _log_format(variables: Mapping[str, str]) -> str:
    chosen = variables.get("FEATHER_LOG_FORMAT", "")
    if chosen and chosen not in LOG_FORMATS:
        raise SettingsError(problems.log_format_unknown(chosen))
    return chosen


def load_settings(
    environ: Mapping[str, str], directory: Path, host: str | None = None, port: int | None = None
) -> Settings:
    variables = {**read_env_file(directory / ENV_FILE), **environ}
    return Settings(
        database_url=_database_url(variables),
        host=host or variables.get("FEATHER_HOST", DEFAULT_HOST),
        port=_port(variables, port),
        log_format=_log_format(variables),
    )
