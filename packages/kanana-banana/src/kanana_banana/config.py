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


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KANANA_BANANA_")

    database_url: str = Field(default_factory=default_database_url)
    debug: bool = True


# Global settings instance
settings = Settings()
