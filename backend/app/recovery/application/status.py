"""Minimized, read-only backup status application contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Protocol


class BackupState(StrEnum):
    NEVER_RUN = "NEVER_RUN"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class VerificationResult(StrEnum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class BackupFailureDetail(StrEnum):
    BACKUP_ATTEMPT_FAILED = "BACKUP_ATTEMPT_FAILED"


@dataclass(frozen=True, slots=True)
class BackupStatus:
    state: BackupState
    last_valid_backup_date: date | None
    last_verification_failure_date: date | None
    verification_result: VerificationResult
    failure_detail: BackupFailureDetail | None
    next_expected_execution_date: date
    retention_count: int

    def __post_init__(self) -> None:
        if self.retention_count < 1:
            raise ValueError("retention_count must be positive")
        if self.state is BackupState.NEVER_RUN and self.last_valid_backup_date is not None:
            raise ValueError("never-run status cannot claim a valid backup")
        if self.state is BackupState.VERIFIED and (
            self.last_valid_backup_date is None
            or self.verification_result is not VerificationResult.PASSED
        ):
            raise ValueError("verified status requires a passed valid backup")
        if self.state is BackupState.FAILED and (
            self.last_verification_failure_date is None
            or self.verification_result is not VerificationResult.FAILED
            or self.failure_detail is None
        ):
            raise ValueError("failed status requires a visible verification failure")
        if self.state is not BackupState.FAILED and self.failure_detail is not None:
            raise ValueError("only failed status can expose a failure detail")


class BackupStatusSnapshot(Protocol):
    @property
    def last_valid_date(self) -> date | None: ...

    @property
    def last_failure_date(self) -> date | None: ...

    @property
    def verification_status(self) -> str: ...

    @property
    def failure_detail(self) -> str | None: ...


class BackupStatusReader(Protocol):
    def read(self) -> BackupStatusSnapshot: ...


class BackupStatusQuery:
    def __init__(
        self,
        reader: BackupStatusReader,
        *,
        today: Callable[[], date],
        retention_count: int,
    ) -> None:
        if retention_count < 1:
            raise ValueError("retention_count must be positive")
        self._reader = reader
        self._today = today
        self._retention_count = retention_count

    def get(self) -> BackupStatus:
        snapshot = self._reader.read()
        domestic_date = self._today()
        state, verification = {
            "never": (BackupState.NEVER_RUN, VerificationResult.NOT_AVAILABLE),
            "pending": (BackupState.PENDING, VerificationResult.PENDING),
            "verified": (BackupState.VERIFIED, VerificationResult.PASSED),
            "failed": (BackupState.FAILED, VerificationResult.FAILED),
        }[snapshot.verification_status]
        return BackupStatus(
            state=state,
            last_valid_backup_date=snapshot.last_valid_date,
            last_verification_failure_date=snapshot.last_failure_date,
            verification_result=verification,
            failure_detail=(
                None
                if snapshot.failure_detail is None
                else BackupFailureDetail(snapshot.failure_detail)
            ),
            next_expected_execution_date=domestic_date + timedelta(days=1),
            retention_count=self._retention_count,
        )


__all__ = (
    "BackupFailureDetail",
    "BackupState",
    "BackupStatus",
    "BackupStatusQuery",
    "BackupStatusReader",
    "BackupStatusSnapshot",
    "VerificationResult",
)
