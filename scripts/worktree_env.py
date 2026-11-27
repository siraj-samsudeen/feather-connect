"""Set up a worktree for issue <n>: its .env and its own database, upgraded.

    uv run scripts/worktree_env.py <n>          # write .env, create feather_issue_<n>
    uv run scripts/worktree_env.py <n> --drop   # remove feather_issue_<n>

The ports come from the issue number: development 18000 + n, acceptance
19000 + n. The database lives in the shared development container of
compose.yaml (start it once: docker compose up -d). An existing .env keeps
every other line; the three keys are replaced in place, and each value that
changes is reported. A random FCON_SECRET_KEY is added when the file has none;
one already there is kept. Each run then upgrades the database, as `fcon db upgrade`
does. Works the same on Windows and Linux.
"""

import argparse
import secrets
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import psycopg
from psycopg import conninfo, sql

from fcon_server.store.clock import SystemClock
from fcon_server.store.migrate import upgrade

ROOT = Path(__file__).resolve().parent.parent
SERVER_URL = "postgresql://feather:feather@127.0.0.1:5442/feather"
DATABASE_URL = "postgresql://feather:feather@127.0.0.1:5442/{name}"
START_IT = "start the database: docker compose up -d"
LAST = 65535 - 19000
KEY_VARIABLE = "FCON_SECRET_KEY"


def new_secret_key() -> str:
    """A random secret key, as .env.example says to make one."""
    return secrets.token_urlsafe(32)


def database_name(number: int) -> str:
    """The name of the database of the worktree for issue `number`."""
    return f"feather_issue_{number}"


def env_values(number: int) -> dict[str, str]:
    """The ports and database address the worktree for issue `number` writes to its .env.

    Raises ValueError when `number` is below 1 or so high that a port would pass 65535.
    """
    if not 1 <= number <= LAST:
        raise ValueError(f"the issue number must be between 1 and {LAST}, not {number}")
    return {
        "FCON_PORT": str(18000 + number),
        "ACCEPTANCE_PORT": str(19000 + number),
        "FCON_DATABASE_URL": DATABASE_URL.format(name=database_name(number)),
    }


def merge_env(text: str, values: Mapping[str, str], defaults: Mapping[str, str] | None = None) -> tuple[str, list[str]]:
    """The .env text with `values` set and `defaults` added where their key is missing, with each change.

    The second item is a line for each value it replaced; every other line of `text` is kept.
    """
    lines = text.splitlines()
    changes: list[str] = []
    missing = dict(values)
    present = {line.partition("=")[0].strip() for line in lines if "=" in line}
    missing.update({key: value for key, value in (defaults or {}).items() if key not in present})
    for index, line in enumerate(lines):
        key, sep, old = line.partition("=")
        key = key.strip()
        if sep and key in missing:
            new = missing.pop(key)
            if old.strip() != new:
                changes.append(f"{key}: {old.strip()} -> {new}")
            lines[index] = f"{key}={new}"
    lines.extend(f"{key}={value}" for key, value in missing.items())
    return "".join(f"{line}\n" for line in lines), changes


def write_env(root: Path, values: Mapping[str, str], defaults: Mapping[str, str] | None = None) -> str:
    """Writes or updates `root`/.env with `values` and missing `defaults`, and says what it did to the file."""
    path = root / ".env"
    if not path.exists():
        path.write_text(merge_env("", values, defaults)[0], encoding="utf-8")
        return f"wrote {path}"
    old = path.read_text(encoding="utf-8")
    new, changes = merge_env(old, values, defaults)
    if new == old:
        return f"{path} already up to date"
    path.write_text(new, encoding="utf-8")
    said = "; ".join(changes) or "added missing keys"
    return f"updated {path} ({said}; other lines kept)"


def _exists(connection: psycopg.Connection[tuple[object, ...]], name: str) -> bool:
    """Whether the server `connection` is on has a database called `name`."""
    return connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None


def create_database(server_url: str, name: str) -> bool:
    """Create the database unless it exists; True when it was created."""
    with psycopg.connect(server_url, autocommit=True) as connection:
        if _exists(connection, name):
            return False
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        return True


def drop_database(server_url: str, name: str) -> bool:
    """Drop the database if it exists; True when it was dropped."""
    with psycopg.connect(server_url, autocommit=True) as connection:
        if not _exists(connection, name):
            return False
        connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        return True


def upgrade_database(server_url: str, name: str) -> str | None:
    """Applies the waiting upgrades to database `name` and says what it did.

    Gives back None, after printing why to stderr, when an upgrade that ran has changed; nothing is
    applied then.
    """
    result = upgrade(conninfo.make_conninfo(server_url, dbname=name), SystemClock())
    if result.changed:
        print(
            f"worktree_env.py: upgrade {result.changed[0]} has changed since it ran. "
            "Restore it; never edit a migration that ran.",
            file=sys.stderr,
        )
        return None
    if not result.applied:
        return f"database {name} is up to date"
    return f"upgraded database {name}: {len(result.applied)} applied"


def main(argv: Sequence[str], root: Path = ROOT, server_url: str = SERVER_URL) -> int:
    """Sets up, or with --drop removes, the worktree's .env and database; 0 when done, 2 on a problem it reports."""
    parser = argparse.ArgumentParser(prog="worktree_env.py", description="Set up a worktree's .env and database.")
    parser.add_argument("number", type=int, help="the issue number the worktree works on")
    parser.add_argument("--drop", action="store_true", help="remove the worktree's database")
    args = parser.parse_args(argv)
    try:
        values = env_values(args.number)
    except ValueError as err:
        print(f"worktree_env.py: {err}", file=sys.stderr)
        return 2
    name = database_name(args.number)
    try:
        if args.drop:
            done = drop_database(server_url, name)
            print(f"dropped database {name}" if done else f"database {name} did not exist")
            return 0
        print(write_env(root, values, {KEY_VARIABLE: new_secret_key()}))
        done = create_database(server_url, name)
        print(f"created database {name}" if done else f"database {name} already exists")
        upgraded = upgrade_database(server_url, name)
    except psycopg.OperationalError as err:
        first_line = str(err).splitlines()[0] if str(err) else type(err).__name__
        print(f"worktree_env.py: cannot reach the database server ({first_line}).\n{START_IT}", file=sys.stderr)
        return 2
    if upgraded is None:
        return 2
    print(upgraded)
    return 0


if __name__ == "__main__":  # pragma: no cover - the command a person runs; main() is tested
    sys.exit(main(sys.argv[1:]))
