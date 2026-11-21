"""The settings of `feather server`: FEATHER_* environment variables only, and
in development a git-ignored .env file in the current directory, which fills
in only what the environment leaves unset. --host and --port win for one run."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
ENV_FILE = ".env"


class SettingsError(Exception):
    """A settings mistake only a person can fix: the command stops."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    database_url: str


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


def _port(variables: Mapping[str, str]) -> int:
    name = "FEATHER_PORT" if "FEATHER_PORT" in variables else "PORT"
    text = variables.get(name, str(DEFAULT_PORT))
    try:
        return int(text)
    except ValueError:
        raise SettingsError(f"{name} is not a number: {text!r}") from None


def load_settings(
    environ: Mapping[str, str], directory: Path, host: str | None = None, port: int | None = None
) -> Settings:
    variables = {**read_env_file(directory / ENV_FILE), **environ}
    database_url = variables.get("FEATHER_DATABASE_URL", "")
    if not database_url:
        raise SettingsError("FEATHER_DATABASE_URL is not set.")
    return Settings(
        host=host or variables.get("FEATHER_HOST", DEFAULT_HOST),
        port=port if port is not None else _port(variables),
        database_url=database_url,
    )
