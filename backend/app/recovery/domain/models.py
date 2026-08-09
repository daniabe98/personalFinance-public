"""Immutable recovery outcomes and durable backup-run values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum


class BackupRunStatus(StrEnum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BackupOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_VALID = "ALREADY_VALID"
    FAILED = "FAILED"


class RestoreOutcome(StrEnum):
    RESTORED = "RESTORED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class BackupRun:
    id: str
    backup_date: date
    status: BackupRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    integrity_result: str | None = None

    def __post_init__(self) -> None:
        if not self.id or self.id != self.id.strip():
            raise ValueError("backup run id must be an opaque identifier")
        if self.started_at.tzinfo is not UTC:
            raise ValueError("backup run timestamps must use UTC")
        if self.completed_at is not None and self.completed_at.tzinfo is not UTC:
            raise ValueError("backup completion timestamps must use UTC")
        if self.status is BackupRunStatus.COMPLETED:
            if self.completed_at is None or self.integrity_result != "ok":
                raise ValueError("completed backup runs require verified integrity")
        elif self.status is BackupRunStatus.FAILED:
            if self.completed_at is None or self.integrity_result != "failed":
                raise ValueError("failed backup runs require a terminal failure marker")
        elif self.completed_at is not None or self.integrity_result is not None:
            raise ValueError("started backup runs cannot carry a terminal result")


__all__ = (
    "BackupOutcome",
    "BackupRun",
    "BackupRunStatus",
    "RestoreOutcome",
)
