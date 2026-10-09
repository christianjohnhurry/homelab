import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def data_dir() -> Path:
    """Where the database lives: $XDG_DATA_HOME/kanana-banana, else ~/.local/share/kanana-banana."""
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "kanana-banana"


def default_database_url() -> str:
    # A fixed location, so the board is the same whichever directory the server starts in
    return f"sqlite:///{data_dir() / 'kanana_banana.db'}"


def config_dir() -> Path:
    """Secrets live here: $KANANA_BANANA_CONFIG_DIR, else ~/.config/kanana-banana."""
    override = os.environ.get("KANANA_BANANA_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".config" / "kanana-banana"


def secrets_path() -> Path:
    return config_dir() / "secrets.env"


def read_secret(name: str) -> str:
    """A value from secrets.env (KEY=value lines, values literal), or "" if absent."""
    path = secrets_path()
    if not path.exists():
        return ""
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value
    return ""


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KANANA_BANANA_")

    database_url: str = Field(default_factory=default_database_url)
    debug: bool = True


# Global settings instance
settings = Settings()
