"""Guarded restore into a new isolated destination."""

from __future__ import annotations

from pathlib import Path

from app.recovery.application.ports import (
    BackupRunRepositoryFactory,
    BackupStore,
    RecoveryAuditSink,
    SchemaMigrator,
    SqliteBackupPort,
)
from app.recovery.domain.models import RestoreOutcome
from app.shared.unit_of_work import UnitOfWorkFactory


class RestoreRejectedError(RuntimeError):
    """Restore was rejected or rolled back before a destination became valid."""


class RestoreService:
    def __init__(
        self,
        *,
        active_database: Path,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: BackupRunRepositoryFactory,
        sqlite_backup: SqliteBackupPort,
        store: BackupStore,
        migrator: SchemaMigrator,
        audit: RecoveryAuditSink,
    ) -> None:
        self._active_database = active_database.resolve(strict=True)
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._sqlite_backup = sqlite_backup
        self._store = store
        self._migrator = migrator
        self._audit = audit

    def restore_isolated(
        self,
        *,
        source: Path,
        destination: Path,
        correlation_id: str,
    ) -> RestoreOutcome:
        temporary: Path | None = None
        published = False
        try:
            verified_source, isolated_destination = self._validated_paths(source, destination)
            temporary = self._store.temporary_for(isolated_destination)
            self._sqlite_backup.copy(verified_source, temporary)
            if not self._sqlite_backup.verify(temporary):
                raise RestoreRejectedError("restore staging failed integrity verification")
            self._migrator.migrate_and_verify(temporary)
            if not self._sqlite_backup.verify(temporary):
                raise RestoreRejectedError("migrated restore failed integrity verification")
            self._store.publish(temporary, isolated_destination)
            published = True
            self._audit.record_durable(
                action="RESTORE",
                result="SUCCESS",
                correlation_id=correlation_id,
                verification_status="verified",
            )
        except (OSError, RuntimeError) as error:
            if temporary is not None:
                self._store.cleanup(temporary)
            if published:
                self._store.cleanup(destination.resolve(strict=False))
            self._audit.record_durable(
                action="RESTORE",
                result="FAILURE",
                correlation_id=correlation_id,
                verification_status="failed",
            )
            if isinstance(error, RestoreRejectedError):
                raise
            raise RestoreRejectedError("isolated restore failed") from error
        return RestoreOutcome.RESTORED

    def _validated_paths(self, source: Path, destination: Path) -> tuple[Path, Path]:
        try:
            verified_source = source.resolve(strict=True)
        except OSError as error:
            raise RestoreRejectedError("restore source is unavailable") from error
        if not verified_source.is_file():
            raise RestoreRejectedError("restore source is unavailable")
        if destination.exists() or destination.is_symlink():
            raise RestoreRejectedError("restore destination must not exist")
        isolated_destination = destination.resolve(strict=False)
        if isolated_destination == self._active_database:
            raise RestoreRejectedError("active database cannot be a restore destination")
        if verified_source == self._active_database:
            raise RestoreRejectedError("active database is not a catalogued backup")
        with self._unit_of_work_factory() as unit_of_work:
            verified = self._repository_factory(unit_of_work.session).is_verified_source(
                verified_source
            )
        if not verified:
            raise RestoreRejectedError("restore source is not a verified catalogued backup")
        return verified_source, isolated_destination


__all__ = ("RestoreRejectedError", "RestoreService")
