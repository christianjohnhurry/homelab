from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KANANA_BANANA_")

    database_url: str = "sqlite:///kanana_banana.db"
    debug: bool = True


# Global settings instance
settings = Settings()
