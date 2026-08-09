"""Acceptance proof for guarded, isolated restoration."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alembic import command
from app.cli import EXIT_SUCCESS, app
from app.recovery.adapters.alembic_migration import AlembicSchemaMigrator
from app.recovery.adapters.filesystem import AtomicBackupStore
from app.recovery.adapters.run_repository import SqlAlchemyBackupRunRepository
from app.recovery.adapters.sqlite_backup import SqliteOnlineBackup
from app.recovery.application.backup import BackupService
from app.recovery.application.restore import RestoreRejectedError, RestoreService
from app.recovery.domain.models import BackupOutcome, RestoreOutcome
from app.shared.config import get_settings
from app.shared.database import create_engine, create_session_factory
from app.shared.unit_of_work import UnitOfWorkFactory
from tests.fixtures.known_finances import financial_fingerprint, seed_known_finances
from tests.integration.persistence.conftest import alembic_config
from tests.integration.recovery.test_backup import MutableClock, RecordingAudit


@dataclass
class RestoreHarness:
    active: Path
    backup: Path
    unit_of_work_factory: UnitOfWorkFactory
    audit: RecordingAudit

    def service(
        self,
        *,
        migrator: AlembicSchemaMigrator | None = None,
        sqlite_backup: SqliteOnlineBackup | None = None,
    ) -> RestoreService:
        return RestoreService(
            active_database=self.active,
            unit_of_work_factory=self.unit_of_work_factory,
            repository_factory=SqlAlchemyBackupRunRepository,
            sqlite_backup=sqlite_backup or SqliteOnlineBackup(),
            store=AtomicBackupStore(),
            migrator=migrator or AlembicSchemaMigrator(),
            audit=self.audit,
        )


@pytest.fixture
def restore_harness(tmp_path: Path) -> Iterator[RestoreHarness]:
    active = tmp_path / "active.sqlite3"
    database_url = f"sqlite+pysqlite:///{active.as_posix()}"
    command.upgrade(alembic_config(database_url), "head")
    expected = seed_known_finances(active)
    assert expected.asset_balance_cents == 137_500
    engine = create_engine(database_url)
    unit_of_work_factory = UnitOfWorkFactory(create_session_factory(engine))
    audit = RecordingAudit()
    backup_service = BackupService(
        source_database=active,
        backup_directory=tmp_path / "backups",
        domestic_timezone="Europe/Madrid",
        retention=3,
        unit_of_work_factory=unit_of_work_factory,
        repository_factory=SqlAlchemyBackupRunRepository,
        sqlite_backup=SqliteOnlineBackup(),
        store=AtomicBackupStore(),
        audit=audit,
        clock=MutableClock(datetime(2026, 7, 23, 10, tzinfo=UTC)),
    )
    assert backup_service.run_if_due(correlation_id="restore-fixture") is BackupOutcome.CREATED
    backup = next((tmp_path / "backups").glob("*.sqlite3"))
    audit.calls.clear()
    try:
        yield RestoreHarness(active, backup, unit_of_work_factory, audit)
    finally:
        engine.dispose()


def test_restore_publishes_isolated_database_with_schema_entities_and_known_balances(
    restore_harness: RestoreHarness,
    tmp_path: Path,
) -> None:
    before = financial_fingerprint(restore_harness.active)
    destination = tmp_path / "isolated" / "restored.sqlite3"

    outcome = restore_harness.service().restore_isolated(
        source=restore_harness.backup,
        destination=destination,
        correlation_id="restore-success",
    )

    assert outcome is RestoreOutcome.RESTORED
    assert SqliteOnlineBackup().verify(destination)
    assert financial_fingerprint(destination) == before
    assert financial_fingerprint(restore_harness.active) == before
    with closing(sqlite3.connect(destination)) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "0002_ledger_immutability",
        )
    assert restore_harness.audit.calls[0].action == "RESTORE"
    assert restore_harness.audit.calls[0].result == "SUCCESS"
    assert "path" not in repr(restore_harness.audit.calls)


@pytest.mark.parametrize("case", ["active", "existing", "unverified"])
def test_restore_rejects_unsafe_source_or_destination_without_partial_publication(
    restore_harness: RestoreHarness,
    tmp_path: Path,
    case: str,
) -> None:
    source = restore_harness.backup
    destination = tmp_path / "isolated.sqlite3"
    if case == "active":
        destination = restore_harness.active
    elif case == "existing":
        destination.touch()
    else:
        source = tmp_path / "uncatalogued.sqlite3"
        SqliteOnlineBackup().copy(restore_harness.active, source)

    with pytest.raises(RestoreRejectedError):
        restore_harness.service().restore_isolated(
            source=source,
            destination=destination,
            correlation_id=f"restore-{case}",
        )

    if case != "existing" and destination != restore_harness.active:
        assert not destination.exists()
    assert financial_fingerprint(restore_harness.active).asset_balance_cents == 137_500


class FailingMigrator(AlembicSchemaMigrator):
    def migrate_and_verify(self, database: Path) -> None:
        del database
        raise RuntimeError("injected migration failure")


def test_restore_rolls_back_staging_on_migration_failure_and_audits_failure(
    restore_harness: RestoreHarness,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "failed" / "restored.sqlite3"

    with pytest.raises(RestoreRejectedError):
        restore_harness.service(migrator=FailingMigrator()).restore_isolated(
            source=restore_harness.backup,
            destination=destination,
            correlation_id="restore-failure",
        )

    assert not destination.exists()
    assert not tuple(destination.parent.glob("*.tmp"))
    assert financial_fingerprint(restore_harness.active).asset_balance_cents == 137_500
    assert restore_harness.audit.calls[-1].result == "FAILURE"
    assert restore_harness.audit.calls[-1].verification_status == "failed"


def test_restore_cli_is_local_only_and_uses_guarded_service(
    restore_harness: RestoreHarness,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "cli-restore" / "restored.sqlite3"
    output: list[str] = []
    monkeypatch.setenv(
        "PF_DATABASE_URL",
        f"sqlite:///{restore_harness.active.as_posix()}",
    )
    monkeypatch.setenv("PF_SECRET_KEY", "x" * 32)
    get_settings.cache_clear()

    def unexpected_password_prompt(prompt: str) -> str:
        raise AssertionError(f"unexpected password prompt: {prompt}")

    try:
        assert (
            app(
                [
                    "restore",
                    "--source",
                    str(restore_harness.backup),
                    "--destination",
                    str(destination),
                ],
                password_prompt=unexpected_password_prompt,
                stdout=output.append,
            )
            == EXIT_SUCCESS
        )
    finally:
        get_settings.cache_clear()
    assert output == ["Backup restored to an isolated destination and verified."]
    assert financial_fingerprint(destination).asset_balance_cents == 137_500
