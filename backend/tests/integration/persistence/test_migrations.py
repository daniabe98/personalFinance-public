from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from alembic import command
from tests.integration.persistence.conftest import alembic_config


def test_blank_database_upgrade_downgrade_upgrade(database_url: str) -> None:
    from app.shared.database import create_engine

    config = alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert {
        "users",
        "spaces",
        "sessions",
        "accounts",
        "categories",
        "transactions",
        "entries",
        "reversals",
        "idempotency_records",
        "reconciliations",
        "reconciliation_entries",
        "audit_events",
        "backup_runs",
    }.issubset(inspect(engine).get_table_names())
    engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(database_url)
    assert "transactions" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert "transactions" in inspect(engine).get_table_names()
    engine.dispose()


def test_foreign_keys_are_enabled_on_every_connection(migrated_engine) -> None:
    with migrated_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_migrate_cli_initializes_a_blank_file_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import cli
    from app.shared.database import create_engine

    database = tmp_path / "fresh.db"
    monkeypatch.setattr(cli, "_active_database", lambda *, must_exist: database)

    assert cli.app(["migrate"]) == 0
    engine = create_engine(f"sqlite:///{database}")
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()
