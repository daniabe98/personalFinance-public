"""Recovery application ports."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from app.recovery.domain.models import BackupRun


class Clock(Protocol):
    def __call__(self) -> datetime: ...


class BackupRunRepository(Protocol):
    def claim(
        self,
        backup_date: date,
        *,
        run_id: str,
        published_path: Path,
        started_at: datetime,
    ) -> BackupRun | None: ...

    def find_by_date(self, backup_date: date) -> BackupRun | None: ...

    def mark_completed(self, run_id: str, *, completed_at: datetime) -> BackupRun: ...

    def mark_failed(self, run_id: str, *, completed_at: datetime) -> BackupRun: ...

    def is_verified_source(self, source: Path) -> bool: ...

    def verified_paths(self) -> tuple[Path, ...]: ...


class BackupRunRepositoryFactory(Protocol):
    def __call__(self, session: object) -> BackupRunRepository: ...


class SqliteBackupPort(Protocol):
    def copy(self, source: Path, destination: Path) -> None: ...

    def verify(self, database: Path) -> bool: ...


class BackupStore(Protocol):
    def temporary_for(self, destination: Path) -> Path: ...

    def publish(self, temporary: Path, destination: Path) -> None: ...

    def cleanup(self, path: Path) -> None: ...

    def prune_verified(self, verified: tuple[Path, ...], *, keep: int) -> None: ...


class SchemaMigrator(Protocol):
    def migrate_and_verify(self, database: Path) -> None: ...


class RecoveryAuditSink(Protocol):
    def record(
        self,
        session: object,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None: ...

    def record_durable(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None: ...


__all__ = (
    "BackupRunRepository",
    "BackupRunRepositoryFactory",
    "BackupStore",
    "Clock",
    "RecoveryAuditSink",
    "SchemaMigrator",
    "SqliteBackupPort",
)
