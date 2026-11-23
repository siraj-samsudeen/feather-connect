"""The settings of the commands: FCON_* environment variables only, and
in development a git-ignored .env file in the current directory, which fills
in only what the environment leaves unset. --host and --port win for one run
of `fcon server`. A mistake raises SettingsError, with the error helper's
words for it."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

import psycopg
from psycopg import conninfo

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_server.proxies import NotAProxyError, TrustedProxies, trusted_proxies
from fcon_server.users.rules import normal_name, user_name_problem

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
ENV_FILE = ".env"
LOG_FORMATS = ("text", "json")  # unset: text on a terminal, json elsewhere
DEFAULT_POOL_SIZE = 5
PREPARE = {"on": True, "off": False}  # off: for a connection pooler in front of Postgres
SHORTEST_SECRET_KEY = 32  # characters
DEFAULT_ENVIRONMENT = "development"


class SettingsError(ProblemError):
    """A settings mistake only a person can fix: the command stops."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str = field(repr=False)  # may hold a password
    secret_key: str = field(repr=False)
    log_format: str = ""
    pool_size: int = DEFAULT_POOL_SIZE
    prepare: bool = True
    previous_secret_key: str | None = field(default=None, repr=False)
    environment: str = DEFAULT_ENVIRONMENT
    first_admin: str | None = None
    trusted_proxies: TrustedProxies | None = None


@dataclass(frozen=True)
class DatabaseSettings:
    """`fcon db`: the app's address, and the owner's for upgrades
    (FCON_MIGRATION_DATABASE_URL, else the app's)."""

    database_url: str = field(repr=False)  # may hold a password
    migration_database_url: str = field(repr=False)


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
    name = "FCON_PORT" if "FCON_PORT" in variables else "PORT"
    return _checked_port(name, variables.get(name, str(DEFAULT_PORT)))


def _checked_database_url(name: str, url: str) -> str:
    """An address psycopg reads, as it takes it: a postgresql:// or postgres://
    URL, or libpq's key=value form. Never repeated: it may hold a password."""
    try:
        port = str(conninfo.conninfo_to_dict(url).get("port") or "5432")
    except psycopg.ProgrammingError:
        port = ""
    if not port.isdigit():
        raise SettingsError(problems.database_url_not_postgres(name))
    return url


def _database_url(variables: Mapping[str, str]) -> str:
    url = variables.get("FCON_DATABASE_URL", "")
    if not url:
        raise SettingsError(problems.database_url_missing())
    return _checked_database_url("FCON_DATABASE_URL", url)


def _log_format(variables: Mapping[str, str]) -> str:
    chosen = variables.get("FCON_LOG_FORMAT", "")
    if chosen and chosen not in LOG_FORMATS:
        raise SettingsError(problems.log_format_unknown(chosen))
    return chosen


def _pool_size(variables: Mapping[str, str]) -> int:
    text = variables.get("FCON_DATABASE_POOL_SIZE", "")
    if not text:
        return DEFAULT_POOL_SIZE
    if not text.isdigit() or int(text) < 1:
        raise SettingsError(problems.pool_size_not_a_number(text))
    return int(text)


def _prepare(variables: Mapping[str, str]) -> bool:
    text = variables.get("FCON_DATABASE_PREPARE", "") or "on"
    if text not in PREPARE:
        raise SettingsError(problems.prepare_unknown(text))
    return PREPARE[text]


def _secret_key(variables: Mapping[str, str], name: str) -> str | None:
    """At least SHORTEST_SECRET_KEY characters, when set. Never repeated: it is a secret."""
    key = variables.get(name, "")
    if key and len(key) < SHORTEST_SECRET_KEY:
        raise SettingsError(problems.secret_key_too_short(name))
    return key or None


def _first_admin(variables: Mapping[str, str]) -> str | None:
    """The user name, as it is stored, of the administrator to make on a start with no users."""
    typed = variables.get("FCON_FIRST_ADMIN", "")
    if not typed.strip():
        return None
    if user_name_problem(name := normal_name(typed)) is not None:
        raise SettingsError(problems.first_admin_not_allowed(typed.strip()))
    return name


def _trusted_proxies(variables: Mapping[str, str]) -> TrustedProxies | None:
    try:
        return trusted_proxies(variables.get("FCON_TRUSTED_PROXIES", ""))
    except NotAProxyError as err:
        raise SettingsError(problems.trusted_proxies_not_addresses(err.item)) from None


def _no_secret_key() -> NoReturn:
    raise SettingsError(problems.secret_key_missing())


def load_settings(
    environ: Mapping[str, str], directory: Path, host: str | None = None, port: int | None = None
) -> Settings:
    variables = {**read_env_file(directory / ENV_FILE), **environ}
    return Settings(
        database_url=_database_url(variables),
        host=host or variables.get("FCON_HOST", DEFAULT_HOST),
        port=_port(variables, port),
        log_format=_log_format(variables),
        pool_size=_pool_size(variables),
        prepare=_prepare(variables),
        secret_key=_secret_key(variables, "FCON_SECRET_KEY") or _no_secret_key(),
        previous_secret_key=_secret_key(variables, "FCON_SECRET_KEY_PREVIOUS"),
        environment=variables.get("FCON_ENVIRONMENT", "").strip() or DEFAULT_ENVIRONMENT,
        first_admin=_first_admin(variables),
        trusted_proxies=_trusted_proxies(variables),
    )


def load_database_settings(environ: Mapping[str, str], directory: Path) -> DatabaseSettings:
    variables = {**read_env_file(directory / ENV_FILE), **environ}
    database_url = _database_url(variables)
    owner_url = variables.get("FCON_MIGRATION_DATABASE_URL", "")
    return DatabaseSettings(
        database_url=database_url,
        migration_database_url=_checked_database_url("FCON_MIGRATION_DATABASE_URL", owner_url)
        if owner_url
        else database_url,
    )
