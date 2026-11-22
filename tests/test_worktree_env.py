"""`scripts/worktree_env.py <n>`: a worktree's .env and its own database (issue 4, point 10)."""

import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import conninfo

import worktree_env
from fcon_server.store.migrate import MIGRATIONS

FILES = sorted(path.name for path in MIGRATIONS.glob("*.sql"))


def test_the_values_come_from_the_issue_number():
    assert worktree_env.env_values(4) == {
        "FCON_PORT": "18004",
        "ACCEPTANCE_PORT": "19004",
        "FCON_DATABASE_URL": "postgresql://feather:feather@127.0.0.1:5442/feather_issue_4",
    }


@pytest.mark.parametrize("number", [0, -1, 46536])
def test_a_number_that_gives_no_usable_port_is_refused(number: int):
    with pytest.raises(ValueError, match="between 1 and 46535"):
        worktree_env.env_values(number)


def test_an_empty_file_gets_the_three_lines():
    text, changes = worktree_env.merge_env("", {"FCON_PORT": "18004", "ACCEPTANCE_PORT": "19004"})

    assert text == "FCON_PORT=18004\nACCEPTANCE_PORT=19004\n"
    assert changes == []


def test_other_lines_are_kept_and_the_keys_are_replaced_in_place():
    existing = "# mine\nFCON_LOG_FORMAT=json\nFCON_PORT=8080\n\nOTHER=1"

    text, _ = worktree_env.merge_env(existing, {"FCON_PORT": "18004", "ACCEPTANCE_PORT": "19004"})

    assert text == "# mine\nFCON_LOG_FORMAT=json\nFCON_PORT=18004\n\nOTHER=1\nACCEPTANCE_PORT=19004\n"


def test_a_value_it_replaces_is_reported():
    _, changes = worktree_env.merge_env(
        "FCON_PORT=8080\nACCEPTANCE_PORT=19004\n", {"FCON_PORT": "18004", "ACCEPTANCE_PORT": "19004"}
    )

    assert changes == ["FCON_PORT: 8080 -> 18004"]


def test_a_default_is_added_when_its_key_is_missing():
    text, changes = worktree_env.merge_env("OTHER=1\n", {"FCON_PORT": "18004"}, {"FCON_SECRET_KEY": "new"})

    assert text == "OTHER=1\nFCON_PORT=18004\nFCON_SECRET_KEY=new\n"
    assert changes == []


def test_a_default_never_replaces_a_value_already_there():
    text, changes = worktree_env.merge_env("FCON_SECRET_KEY=mine\n", {}, {"FCON_SECRET_KEY": "new"})

    assert text == "FCON_SECRET_KEY=mine\n"
    assert changes == []


def test_a_new_secret_key_is_random_and_long_enough():
    first, second = worktree_env.new_secret_key(), worktree_env.new_secret_key()

    assert first != second
    assert len(first) >= 32


def test_a_new_env_file_is_written(tmp_path: Path):
    message = worktree_env.write_env(tmp_path, {"FCON_PORT": "18004"})

    assert (tmp_path / ".env").read_text(encoding="utf-8") == "FCON_PORT=18004\n"
    assert message == f"wrote {tmp_path / '.env'}"


def test_an_existing_env_file_says_what_it_changed(tmp_path: Path):
    (tmp_path / ".env").write_text("FCON_PORT=8080\n", encoding="utf-8")

    message = worktree_env.write_env(tmp_path, {"FCON_PORT": "18004"})

    assert message == f"updated {tmp_path / '.env'} (FCON_PORT: 8080 -> 18004; other lines kept)"


def test_an_env_file_already_right_is_left_alone(tmp_path: Path):
    (tmp_path / ".env").write_text("FCON_PORT=18004\n", encoding="utf-8")

    assert worktree_env.write_env(tmp_path, {"FCON_PORT": "18004"}) == f"{tmp_path / '.env'} already up to date"


def _secret_key(root: Path) -> str:
    lines = (root / ".env").read_text(encoding="utf-8").splitlines()
    keys = [line.partition("=")[2] for line in lines if line.startswith("FCON_SECRET_KEY=")]
    assert len(keys) == 1, lines
    return keys[0]


def _exists(server_url: str, name: str) -> bool:
    with psycopg.connect(server_url, autocommit=True) as connection:
        return connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None


@pytest.fixture
def worktree_db(database_url: str):
    name = f"feather_issue_test_{uuid.uuid4().hex[:8]}"
    yield name
    worktree_env.drop_database(database_url, name)


@pytest.mark.database
def test_the_database_is_created_once(database_url: str, worktree_db: str):
    assert worktree_env.create_database(database_url, worktree_db) is True
    assert worktree_env.create_database(database_url, worktree_db) is False
    assert _exists(database_url, worktree_db)


@pytest.mark.database
def test_drop_removes_the_database(database_url: str, worktree_db: str):
    worktree_env.create_database(database_url, worktree_db)

    assert worktree_env.drop_database(database_url, worktree_db) is True
    assert worktree_env.drop_database(database_url, worktree_db) is False
    assert not _exists(database_url, worktree_db)


@pytest.mark.database
def test_the_command_writes_the_env_file_and_creates_the_database(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    try:
        code = worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        assert code == 0
        assert f"FCON_PORT={18000 + number}\n" in (tmp_path / ".env").read_text(encoding="utf-8")
        assert _exists(database_url, f"feather_issue_{number}")
        assert f"created database feather_issue_{number}" in capsys.readouterr().out
    finally:
        worktree_env.drop_database(database_url, f"feather_issue_{number}")


@pytest.mark.database
def test_the_command_writes_a_secret_key_once_and_keeps_it(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    try:
        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)
        first = _secret_key(tmp_path)

        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        assert len(first) >= 32
        assert _secret_key(tmp_path) == first
        assert first not in capsys.readouterr().out
    finally:
        worktree_env.drop_database(database_url, f"feather_issue_{number}")


def _applied(url: str) -> list[str]:
    with psycopg.connect(url) as connection:
        return [str(name) for (name,) in connection.execute("SELECT name FROM fcon.migration ORDER BY name")]


@pytest.mark.database
def test_the_command_upgrades_the_database_it_creates(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    try:
        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        url = conninfo.make_conninfo(database_url, dbname=f"feather_issue_{number}")
        assert _applied(url) == FILES
        assert f"upgraded database feather_issue_{number}: {len(FILES)} applied" in capsys.readouterr().out
    finally:
        worktree_env.drop_database(database_url, f"feather_issue_{number}")


@pytest.mark.database
def test_the_command_run_again_finds_the_database_up_to_date(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    try:
        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        assert f"database feather_issue_{number} is up to date" in capsys.readouterr().out
    finally:
        worktree_env.drop_database(database_url, f"feather_issue_{number}")


@pytest.mark.database
def test_the_command_refuses_a_database_whose_upgrade_changed(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    try:
        worktree_env.main([str(number)], root=tmp_path, server_url=database_url)
        url = conninfo.make_conninfo(database_url, dbname=f"feather_issue_{number}")
        with psycopg.connect(url) as connection:
            connection.execute("UPDATE fcon.migration SET checksum = 'edited' WHERE name = %s", [FILES[0]])

        code = worktree_env.main([str(number)], root=tmp_path, server_url=database_url)

        assert code == 2
        assert f"upgrade {FILES[0]} has changed since it ran" in capsys.readouterr().err
    finally:
        worktree_env.drop_database(database_url, f"feather_issue_{number}")


@pytest.mark.database
def test_the_command_with_drop_removes_the_database(
    tmp_path: Path, database_url: str, capsys: pytest.CaptureFixture[str]
):
    number = 40000 + uuid.uuid4().int % 6000
    worktree_env.create_database(database_url, f"feather_issue_{number}")

    code = worktree_env.main([str(number), "--drop"], root=tmp_path, server_url=database_url)

    assert code == 0
    assert not _exists(database_url, f"feather_issue_{number}")
    assert not (tmp_path / ".env").exists()
    assert f"dropped database feather_issue_{number}" in capsys.readouterr().out


def test_the_command_says_how_to_start_an_unreachable_database(
    tmp_path: Path, free_port: int, capsys: pytest.CaptureFixture[str]
):
    unreachable = conninfo.make_conninfo(
        f"postgresql://feather:feather@127.0.0.1:{free_port}/feather", connect_timeout=2
    )

    code = worktree_env.main(["4"], root=tmp_path, server_url=unreachable)

    assert code == 2
    assert "start the database: docker compose up -d" in capsys.readouterr().err


def test_the_command_refuses_a_bad_number(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    code = worktree_env.main(["0"], root=tmp_path, server_url="postgresql://unused")

    assert code == 2
    assert "between 1 and 46535" in capsys.readouterr().err
    assert not (tmp_path / ".env").exists()


def test_an_existing_env_file_missing_the_keys_says_it_added_them(tmp_path: Path):
    (tmp_path / ".env").write_text("OTHER=1\n", encoding="utf-8")

    message = worktree_env.write_env(tmp_path, {"FCON_PORT": "18004"})

    assert message == f"updated {tmp_path / '.env'} (added missing keys; other lines kept)"
