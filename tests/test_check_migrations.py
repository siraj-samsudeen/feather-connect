"""`scripts/check_migrations.py [base]` (design decision 6): a migration on the
base branch is never edited, renamed or removed; each file has a timestamp of
its own and a name of the pattern. Each test makes a git repository of its own."""

import subprocess
from pathlib import Path

import pytest

import check_migrations

FIRST = "20261121T1530Z_first_tables.sql"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)  # noqa: S607


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose branch `base` holds one migration."""
    git(tmp_path, "init", "-q", "-b", "base")
    git(tmp_path, "config", "user.name", "test")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "core.autocrlf", "false")
    folder = tmp_path / check_migrations.FOLDER
    folder.mkdir(parents=True)
    (folder / FIRST).write_bytes(b"CREATE SCHEMA fcon;\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "first")
    return tmp_path


def migration(repo: Path, name: str) -> Path:
    return repo / check_migrations.FOLDER / name


def check(repo: Path, capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = check_migrations.main(list(argv or ["base"]), root=repo)
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_a_new_migration_beside_the_bases_passes(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, "20261122T0900Z_more.sql").write_bytes(b"CREATE TABLE fcon.more (n int);\n")

    assert check(repo, capsys) == (0, "the migrations are fine: 2 files, none on base changed.\n")


def test_an_edited_migration_of_the_base_fails(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, FIRST).write_bytes(b"CREATE SCHEMA fcon; -- edited\n")

    assert check(repo, capsys) == (
        1,
        f"error: {FIRST} is on base and was edited. Restore it; never edit a migration that ran: add a new one.\n",
    )


def test_a_migration_that_differs_only_in_line_endings_passes(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, FIRST).write_bytes(b"CREATE SCHEMA fcon;\r\n")

    assert check(repo, capsys)[0] == 0


def test_a_removed_migration_of_the_base_fails(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, FIRST).unlink()

    assert check(repo, capsys) == (
        1,
        f"error: {FIRST} is on base and was removed or renamed. Restore it under its name.\n",
    )


def test_a_renamed_migration_of_the_base_fails(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, FIRST).rename(migration(repo, "20261121T1530Z_renamed.sql"))

    assert check(repo, capsys)[0] == 1


def test_two_migrations_with_one_timestamp_fail(repo: Path, capsys: pytest.CaptureFixture[str]):
    migration(repo, "20261121T1530Z_twin.sql").write_bytes(b"SELECT 1;\n")

    assert check(repo, capsys) == (
        1,
        f"error: 20261121T1530Z_twin.sql has the timestamp of {FIRST}. Give it the UTC time it was written.\n",
    )


@pytest.mark.parametrize("name", ["20261122_more.sql", "20261122T0900Z_More.sql", "20261122T0900Z_more.SQL"])
def test_a_name_off_the_pattern_fails(repo: Path, capsys: pytest.CaptureFixture[str], name: str):
    migration(repo, name).write_bytes(b"SELECT 1;\n")

    assert check(repo, capsys) == (
        1,
        f"error: {name} is not named <UTC time>_<words>.sql, like 20261121T1530Z_first_tables.sql.\n",
    )


def test_a_base_git_cannot_read_fails_and_says_how_to_fetch_it(repo: Path, capsys: pytest.CaptureFixture[str]):
    assert check(repo, capsys, "nowhere") == (
        1,
        "error: cannot read nowhere from git. Fetch it first: git fetch origin main\n",
    )


def test_the_base_is_origin_main_unless_another_is_given(repo: Path, capsys: pytest.CaptureFixture[str]):
    code = check_migrations.main([], root=repo)

    assert (code, "cannot read origin/main" in capsys.readouterr().err) == (1, True)


def test_a_base_without_migrations_passes_every_new_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    git(tmp_path, "init", "-q", "-b", "base")
    git(
        tmp_path,
        "-c",
        "user.name=test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "0",
    )
    migration(tmp_path, "").mkdir(parents=True)
    migration(tmp_path, FIRST).write_bytes(b"CREATE SCHEMA fcon;\n")

    assert check(tmp_path, capsys) == (0, "the migrations are fine: 1 files, none on base changed.\n")
