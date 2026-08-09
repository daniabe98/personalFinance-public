"""Daily consistent backup orchestration."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.recovery.application.ports import (
    BackupRunRepositoryFactory,
    BackupStore,
    Clock,
    RecoveryAuditSink,
    SqliteBackupPort,
)
from app.recovery.domain.models import BackupOutcome, BackupRunStatus
from app.shared.unit_of_work import UnitOfWorkFactory


class BackupOperationError(RuntimeError):
    """The backup attempt failed without declaring a valid result."""


class BackupService:
    def __init__(
        self,
        *,
        source_database: Path,
        backup_directory: Path,
        domestic_timezone: str,
        retention: int,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: BackupRunRepositoryFactory,
        sqlite_backup: SqliteBackupPort,
        store: BackupStore,
        audit: RecoveryAuditSink,
        clock: Clock,
    ) -> None:
        if retention < 1:
            raise ValueError("retention must be positive")
        self._source_database = source_database.resolve()
        self._backup_directory = backup_directory.resolve()
        self._domestic_timezone = ZoneInfo(domestic_timezone)
        self._retention = retention
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._sqlite_backup = sqlite_backup
        self._store = store
        self._audit = audit
        self._clock = clock

    def run_if_due(self, *, correlation_id: str) -> BackupOutcome:
        started_at = self._clock()
        if started_at.tzinfo is None:
            raise ValueError("backup clock must return a timezone-aware value")
        started_at = started_at.astimezone(UTC)
        backup_date = started_at.astimezone(self._domestic_timezone).date()
        destination = self._backup_directory / f"backup-{backup_date.isoformat()}.sqlite3"
        run_id = uuid4().hex

        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            run = repository.claim(
                backup_date,
                run_id=run_id,
                published_path=destination,
                started_at=started_at,
            )
            if run is None:
                existing = repository.find_by_date(backup_date)
                if existing is not None and existing.status is BackupRunStatus.COMPLETED:
                    return BackupOutcome.ALREADY_VALID
                raise BackupOperationError("a backup attempt is already in progress")
            unit_of_work.commit()

        temporary = self._store.temporary_for(destination)
        published = False
        try:
            self._sqlite_backup.copy(self._source_database, temporary)
            if not self._sqlite_backup.verify(temporary):
                raise BackupOperationError("backup integrity verification failed")
            self._store.publish(temporary, destination)
            published = True
            completed_at = self._utc_now()
            with self._unit_of_work_factory() as unit_of_work:
                repository = self._repository_factory(unit_of_work.session)
                repository.mark_completed(run_id, completed_at=completed_at)
                self._audit.record(
                    unit_of_work.session,
                    action="BACKUP",
                    result="SUCCESS",
                    correlation_id=correlation_id,
                    verification_status="verified",
                )
                unit_of_work.commit()
        except (OSError, RuntimeError) as error:
            self._cleanup_failed_artifacts(temporary, destination if published else None)
            self._record_failure(run_id, correlation_id)
            if isinstance(error, BackupOperationError):
                raise
            raise BackupOperationError("backup attempt failed") from error

        try:
            with self._unit_of_work_factory() as unit_of_work:
                verified = self._repository_factory(unit_of_work.session).verified_paths()
            self._store.prune_verified(verified, keep=self._retention)
        except (OSError, RuntimeError) as error:
            self._audit.record_durable(
                action="BACKUP",
                result="FAILURE",
                correlation_id=correlation_id,
                verification_status="verified",
            )
            raise BackupOperationError("backup retention failed after publication") from error
        return BackupOutcome.CREATED

    def _record_failure(self, run_id: str, correlation_id: str) -> None:
        completed_at = self._utc_now()
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            repository.mark_failed(run_id, completed_at=completed_at)
            self._audit.record(
                unit_of_work.session,
                action="BACKUP",
                result="FAILURE",
                correlation_id=correlation_id,
                verification_status="failed",
            )
            unit_of_work.commit()

    def _cleanup_failed_artifacts(
        self,
        temporary: Path,
        published: Path | None,
    ) -> None:
        self._store.cleanup(temporary)
        if published is not None:
            self._store.cleanup(published)

    def _utc_now(self):
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("backup clock must return a timezone-aware value")
        return value.astimezone(UTC)


__all__ = ("BackupOperationError", "BackupService")
