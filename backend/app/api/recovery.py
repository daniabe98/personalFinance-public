"""Authenticated read-only backup status route."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.dependencies import require_authenticated_principal
from app.identity.application.service import AuthenticatedPrincipal
from app.recovery.application.status import (
    BackupFailureDetail,
    BackupState,
    BackupStatus,
    VerificationResult,
)

router = APIRouter(tags=["recovery"])
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


class BackupQueryPort(Protocol):
    def get(self) -> BackupStatus: ...


class BackupStatusResponse(BaseModel):
    state: BackupState
    last_valid_backup_date: date | None
    last_verification_failure_date: date | None
    verification_result: VerificationResult
    failure_detail: BackupFailureDetail | None
    next_expected_execution_date: date
    retention_count: int


def _query(request: Request) -> BackupQueryPort:
    value = getattr(request.app.state, "backup_status_query", None)
    if value is None:
        raise RuntimeError("backup status reader is not configured")
    return cast(BackupQueryPort, value)


@router.get("/recovery/backup-status", response_model=BackupStatusResponse)
def backup_status(request: Request, principal: Principal) -> BackupStatusResponse:
    del principal
    value = _query(request).get()
    return BackupStatusResponse(
        state=value.state,
        last_valid_backup_date=value.last_valid_backup_date,
        last_verification_failure_date=value.last_verification_failure_date,
        verification_result=value.verification_result,
        failure_detail=value.failure_detail,
        next_expected_execution_date=value.next_expected_execution_date,
        retention_count=value.retention_count,
    )


__all__ = ("router",)
