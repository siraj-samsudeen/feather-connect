"""Check the migrations against the base branch (design decision 6).

    uv run scripts/check_migrations.py            # against origin/main
    uv run scripts/check_migrations.py <base>     # against another ref

A migration on the base is never edited, renamed or removed; no two files
share a timestamp; each name is <UTC time>_<words>.sql. Files are compared
with their line endings made `\\n`, as the runner's checksum does, so a
Windows checkout agrees. Exit 1 with a line per mistake, else 0. CI runs it
in the checks job, with main fetched.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOLDER = "packages/fcon-server/src/fcon_server/store/migrations"
NAME = re.compile(r"^\d{8}T\d{4}Z_[a-z0-9_]+\.sql$")
EXAMPLE = "20261121T1530Z_first_tables.sql"


class GitError(Exception):
    pass


def _git(root: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)  # noqa: S603, S607
    if done.returncode != 0:
        raise GitError
    return done.stdout


def _normal(text: bytes) -> bytes:
    return text.replace(b"\r\n", b"\n")


def base_files(root: Path, base: str) -> dict[str, bytes]:
    """The migrations on `base`, by name, with their text; none when the
    base has no migrations folder yet."""
    _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    listed = _git(root, "ls-tree", "--name-only", base, "--", f"{FOLDER}/").decode().splitlines()
    return {path.rsplit("/", 1)[1]: _git(root, "show", f"{base}:{path}") for path in listed}


def mistakes(files: dict[str, bytes], on_base: dict[str, bytes], base: str) -> list[str]:
    found: list[str] = []
    for name, text in sorted(on_base.items()):
        if name not in files:
            found.append(f"{name} is on {base} and was removed or renamed. Restore it under its name.")
        elif _normal(files[name]) != _normal(text):
            found.append(
                f"{name} is on {base} and was edited. Restore it; never edit a migration that ran: add a new one."
            )
    stamps: dict[str, str] = {}
    for name in sorted(files):
        if not NAME.match(name):
            found.append(f"{name} is not named <UTC time>_<words>.sql, like {EXAMPLE}.")
            continue
        stamp = name.split("_", 1)[0]
        if stamp in stamps:
            found.append(f"{name} has the timestamp of {stamps[stamp]}. Give it the UTC time it was written.")
        stamps.setdefault(stamp, name)
    return found


def main(argv: Sequence[str], root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(prog="check_migrations.py", description="Check the migrations against a base.")
    parser.add_argument("base", nargs="?", default="origin/main", help="the ref to compare with (origin/main)")
    base = parser.parse_args(argv).base
    try:
        on_base = base_files(root, base)
    except GitError:
        print(f"error: cannot read {base} from git. Fetch it first: git fetch origin main", file=sys.stderr)
        return 1
    files = {path.name: path.read_bytes() for path in (root / FOLDER).iterdir() if path.name != "__init__.py"}
    found = mistakes(files, on_base, base)
    for line in found:
        print(f"error: {line}", file=sys.stderr)
    if found:
        return 1
    print(f"the migrations are fine: {len(files)} files, none on {base} changed.")
    return 0


if __name__ == "__main__":  # pragma: no cover - the command CI runs; main() is tested
    sys.exit(main(sys.argv[1:]))
