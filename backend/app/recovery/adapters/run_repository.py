"""Durable backup-run catalog and minimized status projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.recovery.domain.models import BackupRun, BackupRunStatus
from app.shared.models_control import BackupRunRecord
from app.shared.unit_of_work import UnitOfWorkFactory


class BackupRunStoreError(RuntimeError):
    """The durable run catalog rejected an invalid transition."""


@dataclass(frozen=True, slots=True)
class BackupStatusSnapshot:
    last_valid_date: date | None
    last_failure_date: date | None
    last_attempt_date: date | None
    last_attempt_status: BackupRunStatus | None
    verification_status: str
    failure_detail: str | None


class SqlAlchemyBackupRunRepository:
    def __init__(self, session: object) -> None:
        if not isinstance(session, Session):
            raise TypeError("backup repository requires an active SQLAlchemy session")
        self._session = session

    def claim(
        self,
        backup_date: date,
        *,
        run_id: str,
        published_path: Path,
        started_at: datetime,
    ) -> BackupRun | None:
        if started_at.tzinfo is not UTC:
            raise ValueError("claim timestamp must use UTC")
        statement = (
            sqlite_insert(BackupRunRecord)
            .values(
                id=run_id,
                backup_date=backup_date,
                status=BackupRunStatus.STARTED.value,
                path=str(published_path),
                started_at=started_at,
                completed_at=None,
                integrity_result=None,
            )
            .on_conflict_do_nothing(index_elements=[BackupRunRecord.backup_date])
        )
        inserted_id = self._session.scalar(statement.returning(BackupRunRecord.id))
        if inserted_id is not None:
            return BackupRun(run_id, backup_date, BackupRunStatus.STARTED, started_at)

        record = self._record_for_date(backup_date)
        if record is None or record.status != BackupRunStatus.FAILED.value:
            return None
        record.id = run_id
        record.path = str(published_path)
        record.status = BackupRunStatus.STARTED.value
        record.started_at = started_at
        record.completed_at = None
        record.integrity_result = None
        self._session.flush()
        return BackupRun(run_id, backup_date, BackupRunStatus.STARTED, started_at)

    def find_by_date(self, backup_date: date) -> BackupRun | None:
        record = self._record_for_date(backup_date)
        return None if record is None else self._run(record)

    def mark_completed(self, run_id: str, *, completed_at: datetime) -> BackupRun:
        record = self._started(run_id)
        record.status = BackupRunStatus.COMPLETED.value
        record.completed_at = completed_at
        record.integrity_result = "ok"
        self._session.flush()
        return self._run(record)

    def mark_failed(self, run_id: str, *, completed_at: datetime) -> BackupRun:
        record = self._started(run_id)
        record.status = BackupRunStatus.FAILED.value
        record.completed_at = completed_at
        record.integrity_result = "failed"
        self._session.flush()
        return self._run(record)

    def is_verified_source(self, source: Path) -> bool:
        statement = select(BackupRunRecord.id).where(
            BackupRunRecord.path == str(source),
            BackupRunRecord.status == BackupRunStatus.COMPLETED.value,
            BackupRunRecord.integrity_result == "ok",
        )
        return self._session.scalar(statement) is not None

    def verified_paths(self) -> tuple[Path, ...]:
        statement = (
            select(BackupRunRecord.path)
            .where(
                BackupRunRecord.status == BackupRunStatus.COMPLETED.value,
                BackupRunRecord.integrity_result == "ok",
            )
            .order_by(BackupRunRecord.backup_date.desc(), BackupRunRecord.id.desc())
        )
        return tuple(Path(path) for path in self._session.scalars(statement))

    def _record_for_date(self, backup_date: date) -> BackupRunRecord | None:
        return self._session.scalar(
            select(BackupRunRecord).where(BackupRunRecord.backup_date == backup_date)
        )

    def _started(self, run_id: str) -> BackupRunRecord:
        record = self._session.get(BackupRunRecord, run_id)
        if record is None or record.status != BackupRunStatus.STARTED.value:
            raise BackupRunStoreError("backup run is not in the started state")
        return record

    @staticmethod
    def _run(record: BackupRunRecord) -> BackupRun:
        return BackupRun(
            id=record.id,
            backup_date=record.backup_date,
            status=BackupRunStatus(record.status),
            started_at=_utc(record.started_at),
            completed_at=None if record.completed_at is None else _utc(record.completed_at),
            integrity_result=record.integrity_result,
        )


class SqlAlchemyBackupStatusReader:
    """Structural reader for sub-006's forthcoming status port."""

    def __init__(self, unit_of_work_factory: UnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def read(self) -> BackupStatusSnapshot:
        with self._unit_of_work_factory() as unit_of_work:
            session = unit_of_work.session
            valid = session.scalar(
                select(BackupRunRecord)
                .where(BackupRunRecord.status == BackupRunStatus.COMPLETED.value)
                .order_by(BackupRunRecord.backup_date.desc(), BackupRunRecord.id.desc())
                .limit(1)
            )
            failure = session.scalar(
                select(BackupRunRecord)
                .where(BackupRunRecord.status == BackupRunStatus.FAILED.value)
                .order_by(BackupRunRecord.backup_date.desc(), BackupRunRecord.id.desc())
                .limit(1)
            )
            attempt = session.scalar(
                select(BackupRunRecord)
                .order_by(BackupRunRecord.started_at.desc(), BackupRunRecord.id.desc())
                .limit(1)
            )
            attempt_status = None if attempt is None else BackupRunStatus(attempt.status)
            verification = (
                "never"
                if attempt_status is None
                else {
                    BackupRunStatus.STARTED: "pending",
                    BackupRunStatus.COMPLETED: "verified",
                    BackupRunStatus.FAILED: "failed",
                }[attempt_status]
            )
            return BackupStatusSnapshot(
                last_valid_date=None if valid is None else valid.backup_date,
                last_failure_date=None if failure is None else failure.backup_date,
                last_attempt_date=None if attempt is None else attempt.backup_date,
                last_attempt_status=attempt_status,
                verification_status=verification,
                failure_detail=(
                    "BACKUP_ATTEMPT_FAILED" if attempt_status is BackupRunStatus.FAILED else None
                ),
            )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def new_run_id() -> str:
    return uuid4().hex


__all__ = (
    "BackupRunStoreError",
    "BackupStatusSnapshot",
    "SqlAlchemyBackupRunRepository",
    "SqlAlchemyBackupStatusReader",
    "new_run_id",
)
