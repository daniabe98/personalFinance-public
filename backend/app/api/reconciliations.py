"""Authenticated reconciliation projection and commands."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Annotated, Protocol, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, StrictInt

from app.api.dependencies import (
    require_authenticated_principal,
    require_unsafe_request_protection,
)
from app.identity.application.service import AuthenticatedPrincipal
from app.reconciliation.application.service import ReconciliationResult
from app.reconciliation.domain.reconciliation import ReconciliationCandidate

router = APIRouter(tags=["reconciliation"])
ReadPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


def _require_write_principal(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_unsafe_request_protection)],
    csrf_token: Annotated[str, Header(alias="X-CSRF-Token")],
) -> AuthenticatedPrincipal:
    del csrf_token
    return principal


WritePrincipal = Annotated[AuthenticatedPrincipal, Depends(_require_write_principal)]


class ReconciliationPort(Protocol):
    def list_candidates(
        self, space_id: str, account_id: str, cutoff_date: date
    ) -> tuple[ReconciliationCandidate, ...]: ...
    def preview(
        self,
        *,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        entry_ids: Sequence[str],
    ) -> ReconciliationResult: ...
    def complete(
        self,
        *,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        entry_ids: Sequence[str],
        correlation_id: str,
    ) -> ReconciliationResult: ...


class ReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str
    cutoff_date: date
    actual_balance_cents: StrictInt
    selected_entry_ids: tuple[str, ...]


class CandidateResponse(BaseModel):
    entry_id: str
    transaction_id: str
    eligibility_date: date
    effect_cents: int
    currency: str = "EUR"


class ReconciliationResponse(BaseModel):
    reconciliation_id: str
    status: str
    account_id: str
    cutoff_date: date
    actual_balance_cents: int
    prior_completed_cents: int
    selected_effect_cents: int
    checked_balance_cents: int
    difference_cents: int
    selected_entry_ids: tuple[str, ...]
    currency: str = "EUR"


def _service(request: Request) -> ReconciliationPort:
    value = getattr(request.app.state, "reconciliation_service", None)
    if value is None:
        raise RuntimeError("reconciliation service is not configured")
    return cast(ReconciliationPort, value)


def _candidate(value: ReconciliationCandidate) -> CandidateResponse:
    return CandidateResponse(
        entry_id=str(value.entry_id),
        transaction_id=str(value.transaction_id),
        eligibility_date=value.eligibility_date,
        effect_cents=int(value.signed_effect_cents),
    )


def _result(value: ReconciliationResult) -> ReconciliationResponse:
    return ReconciliationResponse(
        reconciliation_id=str(value.reconciliation_id),
        status=str(value.status),
        account_id=str(value.account_id),
        cutoff_date=value.cutoff_date,
        actual_balance_cents=int(value.observed_balance_cents),
        prior_completed_cents=int(value.prior_completed_cents),
        selected_effect_cents=int(value.selected_effect_cents),
        checked_balance_cents=int(value.checked_balance_cents),
        difference_cents=int(value.difference_cents),
        selected_entry_ids=tuple(value.selected_entry_ids),
    )


@router.get("/reconciliations/candidates", response_model=list[CandidateResponse])
def list_candidates(
    request: Request,
    principal: ReadPrincipal,
    account_id: Annotated[str, Query(min_length=1)],
    cutoff_date: date,
) -> list[CandidateResponse]:
    return [
        _candidate(value)
        for value in _service(request).list_candidates(principal.space_id, account_id, cutoff_date)
    ]


@router.post("/reconciliations/preview", response_model=ReconciliationResponse)
def preview(
    payload: ReconciliationRequest, request: Request, principal: WritePrincipal
) -> ReconciliationResponse:
    return _result(
        _service(request).preview(
            space_id=principal.space_id,
            account_id=payload.account_id,
            cutoff_date=payload.cutoff_date,
            observed_balance_cents=payload.actual_balance_cents,
            entry_ids=payload.selected_entry_ids,
        )
    )


@router.post("/reconciliations", response_model=ReconciliationResponse)
def complete(
    payload: ReconciliationRequest, request: Request, principal: WritePrincipal
) -> ReconciliationResponse:
    correlation_id = request.headers.get("X-Request-ID") or str(uuid4())
    return _result(
        _service(request).complete(
            space_id=principal.space_id,
            account_id=payload.account_id,
            cutoff_date=payload.cutoff_date,
            observed_balance_cents=payload.actual_balance_cents,
            entry_ids=payload.selected_entry_ids,
            correlation_id=correlation_id,
        )
    )


__all__ = ("router",)
