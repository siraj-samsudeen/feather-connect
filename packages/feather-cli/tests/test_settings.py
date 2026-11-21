"""Where `feather server` gets its settings: FEATHER_* variables, .env in the
current directory for what they leave unset, and --host/--port for one run."""

from pathlib import Path

import pytest

from feather_cli.settings import Settings, SettingsError, load_settings

URL = "postgresql://feather:feather@127.0.0.1:5442/feather"


def test_it_listens_on_its_own_machine_at_8080_by_default(tmp_path: Path):
    settings = load_settings({"FEATHER_DATABASE_URL": URL}, tmp_path)

    assert settings == Settings(host="127.0.0.1", port=8080, database_url=URL)


def test_the_hosts_port_is_used_when_feather_port_is_not_set(tmp_path: Path):
    settings = load_settings({"FEATHER_DATABASE_URL": URL, "PORT": "9000"}, tmp_path)

    assert settings.port == 9000


def test_feather_port_wins_over_the_hosts_port(tmp_path: Path):
    settings = load_settings({"FEATHER_DATABASE_URL": URL, "PORT": "9000", "FEATHER_PORT": "9100"}, tmp_path)

    assert settings.port == 9100


def test_feather_host_sets_where_it_listens(tmp_path: Path):
    settings = load_settings({"FEATHER_DATABASE_URL": URL, "FEATHER_HOST": "0.0.0.0"}, tmp_path)  # noqa: S104

    assert settings.host == "0.0.0.0"  # noqa: S104


def test_the_options_win_over_the_variables_for_one_run(tmp_path: Path):
    environ = {"FEATHER_DATABASE_URL": URL, "FEATHER_HOST": "0.0.0.0", "FEATHER_PORT": "9100"}  # noqa: S104

    settings = load_settings(environ, tmp_path, host="127.0.0.2", port=9200)

    assert (settings.host, settings.port) == ("127.0.0.2", 9200)


def test_env_file_fills_in_only_what_the_environment_leaves_unset(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "# the worktree's settings\n\nFEATHER_PORT=18004\nFEATHER_DATABASE_URL=postgresql://x@h/from_file\n",
        encoding="utf-8",
    )

    settings = load_settings({"FEATHER_DATABASE_URL": URL}, tmp_path)

    assert (settings.port, settings.database_url) == (18004, URL)


def test_a_missing_database_address_is_a_settings_mistake(tmp_path: Path):
    with pytest.raises(SettingsError, match="FEATHER_DATABASE_URL"):
        load_settings({}, tmp_path)


def test_a_port_that_is_not_a_number_is_a_settings_mistake(tmp_path: Path):
    with pytest.raises(SettingsError, match="FEATHER_PORT"):
        load_settings({"FEATHER_DATABASE_URL": URL, "FEATHER_PORT": "eighty"}, tmp_path)
