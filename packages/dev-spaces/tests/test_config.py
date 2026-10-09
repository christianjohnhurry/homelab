import stat
import tomllib

import pytest

from dev_spaces import config
from dev_spaces.config import ConfigError


def mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


class TestInit:
    def test_creates_everything(self, config_dir):
        results = config.init()
        assert all(created for _, created in results)
        assert {p.name for p, _ in results} == {"config.toml", "secrets.env", ".zshrc", ".devrc"}
        for path, _ in results:
            assert path.exists()

    def test_permissions(self, config_dir):
        config.init()
        assert mode(config_dir) == 0o700
        assert mode(config.dotfiles_dir()) == 0o700
        assert mode(config.secrets_path()) == 0o600

    def test_never_overwrites(self, config_dir):
        config.init()
        config.secrets_path().write_text("GH_TOKEN=mine\n")
        (config.dotfiles_dir() / ".zshrc").write_text("# edited\n")

        results = config.init()

        assert not any(created for _, created in results)
        assert config.secrets_path().read_text() == "GH_TOKEN=mine\n"
        assert (config.dotfiles_dir() / ".zshrc").read_text() == "# edited\n"

    def test_prefills_git_identity(self, config_dir):
        config.init()
        cfg = config.load()
        assert (cfg.git_name, cfg.git_email) == ("Test User", "test@example.com")

    @pytest.mark.parametrize("name", ['A "Quoted" Name', "Back\\slash", "Ünïcödé", ""])
    def test_awkward_git_names_stay_valid_toml(self, config_dir, monkeypatch, name):
        monkeypatch.setattr(config, "_git_global", lambda key: name if key == "user.name" else "")
        config.init()
        assert tomllib.loads(config.config_path().read_text())["git"]["name"] == name


class TestLoad:
    def test_round_trips_template(self, config_dir):
        config.init()
        assert config.load() == config.Config(git_name="Test User", git_email="test@example.com")

    def test_missing_keys_use_defaults(self, config_dir):
        config_dir.mkdir()
        config.config_path().write_text('[ports]\ncontainer = [9000]\n')
        cfg = config.load()
        assert cfg.ports == [9000]
        assert cfg.image_name == "dev-spaces-base"
        assert cfg.git_name == ""

    def test_missing_file(self, config_dir):
        with pytest.raises(ConfigError, match="dev-spaces init"):
            config.load()


class TestSecrets:
    def write(self, text):
        config.config_dir().mkdir(exist_ok=True)
        config.secrets_path().write_text(text)

    def test_parses_like_env_file(self, config_dir):
        self.write("# comment\n\nGH_TOKEN=abc\n  # indented comment\nOTHER=x\n")
        assert config.read_secrets() == {"GH_TOKEN": "abc", "OTHER": "x"}

    def test_value_with_equals(self, config_dir):
        self.write("KEY=a=b==\n")
        assert config.read_secrets()["KEY"] == "a=b=="

    def test_quotes_kept_literally(self, config_dir):
        # docker --env-file does not strip quotes, so neither do we
        self.write('GH_TOKEN="abc"\n')
        assert config.read_secrets()["GH_TOKEN"] == '"abc"'

    def test_missing_file(self, config_dir):
        with pytest.raises(ConfigError, match="dev-spaces init"):
            config.read_secrets()

    def test_github_token(self, config_dir):
        self.write("GH_TOKEN=abc\n")
        assert config.github_token() == "abc"

    @pytest.mark.parametrize("text", ["GH_TOKEN=\n", "OTHER=x\n"])
    def test_github_token_empty(self, config_dir, text):
        self.write(text)
        with pytest.raises(ConfigError, match="GH_TOKEN is empty"):
            config.github_token()


class TestSecretsPermissions:
    def test_silent_at_600(self, config_dir):
        config.init()
        assert config.check_secrets_permissions() is None

    @pytest.mark.parametrize("bad_mode", [0o644, 0o640, 0o604])
    def test_warns_when_others_can_read(self, config_dir, bad_mode):
        config.init()
        config.secrets_path().chmod(bad_mode)
        assert "chmod 600" in config.check_secrets_permissions()

    def test_silent_when_missing(self, config_dir):
        assert config.check_secrets_permissions() is None
