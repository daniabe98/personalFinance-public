"""Recovery integration contract over real SQLite files."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alembic import command
from app.cli import EXIT_BACKUP_ALREADY_VALID, EXIT_SUCCESS, app
from app.recovery.adapters.filesystem import AtomicBackupStore, BackupStoreError
from app.recovery.adapters.run_repository import (
    BackupRunStoreError,
    BackupStatusSnapshot,
    SqlAlchemyBackupRunRepository,
    SqlAlchemyBackupStatusReader,
    new_run_id,
)
from app.recovery.adapters.sqlite_backup import SqliteBackupError, SqliteOnlineBackup
from app.recovery.application.backup import BackupOperationError, BackupService
from app.recovery.domain.models import BackupOutcome, BackupRun, BackupRunStatus
from app.shared.config import get_settings
from app.shared.database import create_engine, create_session_factory
from app.shared.unit_of_work import UnitOfWorkFactory
from tests.integration.persistence.conftest import alembic_config


@dataclass
class MutableClock:
    value: datetime

    def __call__(self) -> datetime:
        return self.value


@dataclass
class AuditCall:
    action: str
    result: str
    correlation_id: str
    verification_status: str


@dataclass
class RecordingAudit:
    calls: list[AuditCall] = field(default_factory=list)

    def record(
        self,
        session: object,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None:
        del session
        self.calls.append(AuditCall(action, result, correlation_id, verification_status))

    def record_durable(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None:
        self.calls.append(AuditCall(action, result, correlation_id, verification_status))


@dataclass
class RecoveryHarness:
    source: Path
    backup_directory: Path
    unit_of_work_factory: UnitOfWorkFactory
    clock: MutableClock
    audit: RecordingAudit

    def service(
        self,
        *,
        retention: int = 3,
        backup: SqliteOnlineBackup | None = None,
        store: AtomicBackupStore | None = None,
    ) -> BackupService:
        return BackupService(
            source_database=self.source,
            backup_directory=self.backup_directory,
            domestic_timezone="Europe/Madrid",
            retention=retention,
            unit_of_work_factory=self.unit_of_work_factory,
            repository_factory=SqlAlchemyBackupRunRepository,
            sqlite_backup=backup or SqliteOnlineBackup(),
            store=store or AtomicBackupStore(),
            audit=self.audit,
            clock=self.clock,
        )


@pytest.fixture
def recovery_harness(tmp_path: Path) -> Iterator[RecoveryHarness]:
    source = tmp_path / "finance.sqlite3"
    database_url = f"sqlite+pysqlite:///{source.as_posix()}"
    command.upgrade(alembic_config(database_url), "head")
    with closing(sqlite3.connect(source)) as connection, connection:
        connection.execute("CREATE TABLE backup_probe (value INTEGER NOT NULL)")
        connection.executemany(
            "INSERT INTO backup_probe(value) VALUES (?)",
            ((index,) for index in range(20)),
        )
    engine = create_engine(database_url)
    unit_of_work_factory = UnitOfWorkFactory(create_session_factory(engine))
    try:
        yield RecoveryHarness(
            source=source,
            backup_directory=tmp_path / "backups",
            unit_of_work_factory=unit_of_work_factory,
            clock=MutableClock(datetime(2026, 3, 29, 0, 30, tzinfo=UTC)),
            audit=RecordingAudit(),
        )
    finally:
        engine.dispose()


def test_backup_is_consistent_verified_and_idempotent_for_domestic_date(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service()

    assert service.run_if_due(correlation_id="backup-first") is BackupOutcome.CREATED
    assert service.run_if_due(correlation_id="backup-repeat") is BackupOutcome.ALREADY_VALID

    backups = tuple(recovery_harness.backup_directory.glob("*.sqlite3"))
    assert len(backups) == 1
    assert SqliteOnlineBackup().verify(backups[0])
    with closing(sqlite3.connect(backups[0])) as connection:
        assert connection.execute("SELECT count(*) FROM backup_probe").fetchone() == (20,)
    assert not tuple(recovery_harness.backup_directory.glob("*.tmp"))
    assert recovery_harness.audit.calls == [
        AuditCall("BACKUP", "SUCCESS", "backup-first", "verified")
    ]


def test_backup_date_is_derived_once_with_iana_midnight_and_dst(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service()
    assert service.run_if_due(correlation_id="before-dst") is BackupOutcome.CREATED

    recovery_harness.clock.value = datetime(2026, 3, 29, 22, 30, tzinfo=UTC)
    assert service.run_if_due(correlation_id="next-domestic-day") is BackupOutcome.CREATED

    reader = SqlAlchemyBackupStatusReader(recovery_harness.unit_of_work_factory)
    status = reader.read()
    assert status.last_valid_date == date(2026, 3, 30)
    assert status.last_attempt_status is BackupRunStatus.COMPLETED


class RejectingVerifier(SqliteOnlineBackup):
    def verify(self, database: Path) -> bool:
        del database
        return False


def test_failed_verification_is_durable_without_false_success_or_path_in_audit(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service(backup=RejectingVerifier())

    with pytest.raises(BackupOperationError):
        service.run_if_due(correlation_id="backup-failure")

    assert not tuple(recovery_harness.backup_directory.glob("*.sqlite3"))
    status = SqlAlchemyBackupStatusReader(recovery_harness.unit_of_work_factory).read()
    assert status == BackupStatusSnapshot(
        last_valid_date=None,
        last_failure_date=date(2026, 3, 29),
        last_attempt_date=date(2026, 3, 29),
        last_attempt_status=BackupRunStatus.FAILED,
        verification_status="failed",
    )
    assert recovery_harness.audit.calls == [
        AuditCall("BACKUP", "FAILURE", "backup-failure", "failed")
    ]
    assert "path" not in repr(recovery_harness.audit.calls)


def test_retention_keeps_only_three_newest_verified_publications(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service(retention=3)
    for day in range(1, 5):
        recovery_harness.clock.value = datetime(2026, 4, day, 10, tzinfo=UTC)
        assert service.run_if_due(correlation_id=f"backup-{day}") is BackupOutcome.CREATED

    assert tuple(
        path.name for path in sorted(recovery_harness.backup_directory.glob("*.sqlite3"))
    ) == (
        "backup-2026-04-02.sqlite3",
        "backup-2026-04-03.sqlite3",
        "backup-2026-04-04.sqlite3",
    )


class FailingPruneStore(AtomicBackupStore):
    def prune_verified(self, verified: tuple[Path, ...], *, keep: int) -> None:
        del verified, keep
        raise OSError("injected retention failure")


def test_prune_failure_never_deletes_or_declassifies_new_valid_backup(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service(store=FailingPruneStore())

    with pytest.raises(BackupOperationError):
        service.run_if_due(correlation_id="prune-failure")

    status = SqlAlchemyBackupStatusReader(recovery_harness.unit_of_work_factory).read()
    assert status.last_valid_date == date(2026, 3, 29)
    assert status.last_attempt_status is BackupRunStatus.COMPLETED
    assert len(tuple(recovery_harness.backup_directory.glob("*.sqlite3"))) == 1


def test_backup_cli_uses_local_service_without_reading_credentials(
    recovery_harness: RecoveryHarness,
) -> None:
    service = recovery_harness.service()
    output: list[str] = []

    def unexpected_prompt(prompt: str) -> str:
        raise AssertionError(f"recovery CLI requested a credential: {prompt}")

    assert (
        app(
            ["backup", "--if-due"],
            backup_service=service,
            password_prompt=unexpected_prompt,
            stdout=output.append,
        )
        == EXIT_SUCCESS
    )
    assert (
        app(
            ["backup", "--if-due"],
            backup_service=service,
            password_prompt=unexpected_prompt,
            stdout=output.append,
        )
        == EXIT_BACKUP_ALREADY_VALID
    )
    assert output == ["Backup created and verified.", "A verified backup already exists today."]


def test_backup_cli_builds_default_durable_composition(
    recovery_harness: RecoveryHarness,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured_backups = tmp_path / "authorized-backups"
    monkeypatch.setenv(
        "PF_DATABASE_URL",
        f"sqlite:///{recovery_harness.source.as_posix()}",
    )
    monkeypatch.setenv("PF_SECRET_KEY", "x" * 32)
    monkeypatch.setenv("PF_BACKUP_DIRECTORY", str(configured_backups))
    get_settings.cache_clear()
    output: list[str] = []
    try:
        assert app(["backup", "--if-due"], stdout=output.append) == EXIT_SUCCESS
    finally:
        get_settings.cache_clear()
    assert output == ["Backup created and verified."]
    assert len(tuple(configured_backups.glob("*.sqlite3"))) == 1
    assert not (recovery_harness.source.parent / "backups").exists()


def test_recovery_values_and_adapters_fail_closed(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        BackupRun("", date(2026, 1, 1), BackupRunStatus.STARTED, now)
    with pytest.raises(ValueError):
        BackupRun("run", date(2026, 1, 1), BackupRunStatus.STARTED, datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        BackupRun("run", date(2026, 1, 1), BackupRunStatus.COMPLETED, now)
    with pytest.raises(ValueError):
        BackupRun("run", date(2026, 1, 1), BackupRunStatus.FAILED, now, now)
    with pytest.raises(ValueError):
        BackupRun("run", date(2026, 1, 1), BackupRunStatus.STARTED, now, now)

    adapter = SqliteOnlineBackup()
    with pytest.raises(SqliteBackupError):
        adapter.copy(tmp_path / "missing.sqlite3", tmp_path / "copy.sqlite3")
    assert not adapter.verify(tmp_path / "missing.sqlite3")
    malformed = tmp_path / "malformed.sqlite3"
    malformed.write_text("not sqlite", encoding="utf-8")
    assert not adapter.verify(malformed)

    store = AtomicBackupStore()
    with pytest.raises(ValueError):
        store.prune_verified((), keep=0)
    with pytest.raises(BackupStoreError):
        store.publish(tmp_path / "one" / "temp", tmp_path / "two" / "final")
    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(BackupStoreError):
        store.cleanup(directory)
    with pytest.raises(TypeError):
        SqlAlchemyBackupRunRepository(object())
    assert len(new_run_id()) == 32
    assert issubclass(BackupRunStoreError, RuntimeError)
