"""Validated process configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from the environment with fail-loud validation."""

    model_config = SettingsConfigDict(
        env_prefix="PF_",
        extra="forbid",
        hide_input_in_errors=True,
    )

    database_url: str
    secret_key: SecretStr = Field(min_length=32)
    busy_timeout_ms: int = Field(default=5_000, ge=1, le=60_000)
    backup_retention: int = Field(default=7, ge=1, le=365)
    backup_directory: Path = Path(r"C:\ProgramData\PersonalFinance\backups")
    domestic_timezone: str = "Europe/Madrid"
    transport_mode: Literal["https", "http_lan"] = "https"

    @field_validator("database_url")
    @classmethod
    def database_must_be_sqlite(cls, value: str) -> str:
        """Keep the V1 persistence boundary local and explicit."""
        if not value.startswith("sqlite:///"):
            raise ValueError("database_url must use SQLite")
        return value

    @field_validator("domestic_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        """Reject timezone typos at process startup."""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("domestic_timezone must be an IANA timezone") from error
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache validated process configuration."""
    return Settings()


__all__ = ("Settings", "get_settings")
