from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.shared.config import Settings


def test_required_data_and_security_settings_fail_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PF_DATABASE_URL", raising=False)
    monkeypatch.delenv("PF_SECRET_KEY", raising=False)

    with pytest.raises(ValidationError) as error:
        Settings()

    message = str(error.value)
    assert "database_url" in message
    assert "secret_key" in message


def test_settings_have_safe_typed_defaults() -> None:
    settings = Settings(
        database_url="sqlite:///C:/ProgramData/PersonalFinance/data/personal-finance.db",
        secret_key="a" * 32,
    )

    assert settings.database_url.startswith("sqlite:///")
    assert settings.busy_timeout_ms == 5_000
    assert settings.backup_retention == 7
    assert settings.backup_directory == Path(r"C:\ProgramData\PersonalFinance\backups")
    assert settings.domestic_timezone == "Europe/Madrid"
    assert settings.transport_mode == "https"


def test_transport_mode_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PF_DATABASE_URL", "sqlite:///finance.db")
    monkeypatch.setenv("PF_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("PF_TRANSPORT_MODE", "plain_http")

    with pytest.raises(ValidationError) as error:
        Settings()

    assert "transport_mode" in str(error.value)


def test_backup_directory_can_be_configured_from_the_single_environment_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "authorized-backups"
    monkeypatch.setenv("PF_DATABASE_URL", "sqlite:///finance.db")
    monkeypatch.setenv("PF_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("PF_BACKUP_DIRECTORY", str(configured))

    assert Settings().backup_directory == configured


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("database_url", "postgresql://not-approved"),
        ("secret_key", "too-short"),
        ("busy_timeout_ms", 0),
        ("backup_retention", 0),
    ],
)
def test_invalid_configuration_is_rejected_without_echoing_secrets(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError) as error:
        if field == "database_url":
            Settings(
                database_url=cast(str, value),
                secret_key="valid-secret-value-that-is-long-enough",
            )
        elif field == "secret_key":
            Settings(database_url="sqlite:///finance.db", secret_key=cast(str, value))
        elif field == "busy_timeout_ms":
            Settings(
                database_url="sqlite:///finance.db",
                secret_key="valid-secret-value-that-is-long-enough",
                busy_timeout_ms=cast(int, value),
            )
        else:
            Settings(
                database_url="sqlite:///finance.db",
                secret_key="valid-secret-value-that-is-long-enough",
                backup_retention=cast(int, value),
            )

    assert str(value) not in str(error.value) if field == "secret_key" else True
