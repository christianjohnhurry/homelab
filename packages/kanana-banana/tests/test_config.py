from pathlib import Path

import pytest

from kanana_banana import config
from kanana_banana.database import ensure_database_dir


class TestDatabaseLocation:
    def test_default_under_local_share(self, monkeypatch, tmp_path):
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        expected = tmp_path / ".local" / "share" / "kanana-banana" / "kanana_banana.db"
        assert config.default_database_url() == f"sqlite:///{expected}"

    def test_respects_xdg_data_home(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        expected = tmp_path / "data" / "kanana-banana" / "kanana_banana.db"
        assert config.default_database_url() == f"sqlite:///{expected}"

    def test_independent_of_working_directory(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        first = config.default_database_url()
        monkeypatch.chdir("/")
        assert config.default_database_url() == first
        assert Path(first.removeprefix("sqlite:///")).is_absolute()

    def test_env_var_overrides(self, monkeypatch):
        monkeypatch.setenv("KANANA_BANANA_DATABASE_URL", "sqlite:////somewhere/else.db")
        assert config.Settings().database_url == "sqlite:////somewhere/else.db"

    def test_settings_default(self, monkeypatch):
        monkeypatch.delenv("KANANA_BANANA_DATABASE_URL")
        assert config.Settings().database_url == config.default_database_url()


class TestEnsureDatabaseDir:
    def test_creates_parent(self, tmp_path):
        db = tmp_path / "a" / "b" / "kb.db"
        ensure_database_dir(f"sqlite:///{db}")
        assert db.parent.is_dir()
        assert not db.exists()

    def test_existing_parent(self, tmp_path):
        ensure_database_dir(f"sqlite:///{tmp_path / 'kb.db'}")
        assert tmp_path.is_dir()

    @pytest.mark.parametrize("url", ["sqlite://", "postgresql://u@localhost/db"])
    def test_ignores_non_file_databases(self, url, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ensure_database_dir(url)
        assert list(tmp_path.iterdir()) == []
