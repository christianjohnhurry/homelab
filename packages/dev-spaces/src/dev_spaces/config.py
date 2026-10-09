"""User configuration in ~/.config/dev-spaces/."""

import json
import os
import stat
import subprocess
import tomllib
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path

TEMPLATES = files("dev_spaces") / "templates"


def config_dir() -> Path:
    """Config directory, overridable with DEV_SPACES_CONFIG_DIR."""
    override = os.environ.get("DEV_SPACES_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".config" / "dev-spaces"


def config_path() -> Path:
    return config_dir() / "config.toml"


def secrets_path() -> Path:
    return config_dir() / "secrets.env"


def dotfiles_dir() -> Path:
    return config_dir() / "dotfiles"


@dataclass
class Config:
    git_name: str = ""
    git_email: str = ""
    image_name: str = "dev-spaces-base"
    ports: list[int] = field(default_factory=lambda: [8000, 8080, 5173, 3000])


class ConfigError(Exception):
    pass


def load() -> Config:
    """Load config.toml, falling back to defaults for missing keys."""
    path = config_path()
    if not path.exists():
        raise ConfigError(f"{path} not found. Run `dev-spaces init` first.")
    data = tomllib.loads(path.read_text())
    defaults = Config()
    return Config(
        git_name=data.get("git", {}).get("name", defaults.git_name),
        git_email=data.get("git", {}).get("email", defaults.git_email),
        image_name=data.get("image", {}).get("name", defaults.image_name),
        ports=data.get("ports", {}).get("container", defaults.ports),
    )


def read_secrets() -> dict[str, str]:
    """Parse secrets.env as docker --env-file does: KEY=value, values literal."""
    path = secrets_path()
    if not path.exists():
        raise ConfigError(f"{path} not found. Run `dev-spaces init` first.")
    secrets = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            secrets[key.strip()] = value
    return secrets


def github_token() -> str:
    token = read_secrets().get("GH_TOKEN", "")
    if not token:
        raise ConfigError(f"GH_TOKEN is empty in {secrets_path()}.")
    return token


def check_secrets_permissions() -> str | None:
    """Return a warning if secrets.env is readable by anyone but the owner."""
    path = secrets_path()
    if path.exists() and path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        return f"{path} is readable by other users. Fix with: chmod 600 {path}"
    return None


def _git_global(key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--global", key], capture_output=True, text=True
    )
    return result.stdout.strip()


def init() -> list[tuple[Path, bool]]:
    """
    Create the config directory and starter files.

    Never overwrites existing files. Returns (path, created) for each file.
    """
    root = config_dir()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    dotfiles_dir().mkdir(mode=0o700, exist_ok=True)

    config_text = (TEMPLATES / "config.toml").read_text().format(
        # JSON string escaping is valid TOML basic-string escaping
        git_name=json.dumps(_git_global("user.name")),
        git_email=json.dumps(_git_global("user.email")),
    )
    planned = [
        (config_path(), config_text, 0o644),
        (secrets_path(), (TEMPLATES / "secrets.env").read_text(), 0o600),
    ]
    for dotfile in (TEMPLATES / "dotfiles").iterdir():
        planned.append((dotfiles_dir() / dotfile.name, dotfile.read_text(), 0o644))

    results = []
    for path, text, mode in planned:
        if path.exists():
            results.append((path, False))
            continue
        # Create with final permissions so secrets are never briefly world-readable
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        results.append((path, True))
    return results
