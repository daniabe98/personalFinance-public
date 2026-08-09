"""Authenticated exact-cent report queries."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.dependencies import require_authenticated_principal
from app.identity.application.service import AuthenticatedPrincipal
from app.reporting.domain.dtos import (
    CashFlowReport,
    EconomicReport,
    NetWorthReport,
    ReportInterval,
)

router = APIRouter(tags=["reports"])
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


class ReportsPort(Protocol):
    def economic(self, interval: ReportInterval) -> EconomicReport: ...
    def cash_flow(self, interval: ReportInterval) -> CashFlowReport: ...
    def net_worth(self, space_id: str, as_of: date) -> NetWorthReport: ...


class ContributionResponse(BaseModel):
    transaction_id: str
    amount_cents: int
    economic_date: date
    cash_date: date | None
    account_id: str | None = None
    category_id: str | None = None
    currency: str = "EUR"


class EconomicReportResponse(BaseModel):
    start_date: date
    end_date: date
    income_cents: int
    expense_cents: int
    result_cents: int
    contributions: tuple[ContributionResponse, ...]
    currency: str = "EUR"


class CashFlowReportResponse(BaseModel):
    start_date: date
    end_date: date
    receipts_cents: int
    payments_cents: int
    net_cash_flow_cents: int
    contributions: tuple[ContributionResponse, ...]
    currency: str = "EUR"


class NetWorthResponse(BaseModel):
    as_of: date
    assets_cents: int
    liabilities_cents: int
    net_worth_cents: int
    contributions: tuple[ContributionResponse, ...]
    currency: str = "EUR"


def _service(request: Request) -> ReportsPort:
    value = getattr(request.app.state, "report_query_service", None)
    if value is None:
        raise RuntimeError("report query service is not configured")
    return cast(ReportsPort, value)


def _contributions(
    value: EconomicReport | CashFlowReport | NetWorthReport,
) -> tuple[ContributionResponse, ...]:
    return tuple(
        ContributionResponse(
            transaction_id=item.transaction_id,
            amount_cents=item.amount_cents,
            economic_date=item.economic_date,
            cash_date=item.cash_date,
            account_id=item.account_id,
            category_id=item.category_id,
        )
        for item in value.contributions
    )


def _economic(value: EconomicReport) -> EconomicReportResponse:
    interval = value.interval
    return EconomicReportResponse(
        start_date=interval.start_date,
        end_date=interval.end_date,
        income_cents=value.income_cents,
        expense_cents=value.expense_cents,
        result_cents=value.result_cents,
        contributions=_contributions(value),
    )


def _cash_flow(value: CashFlowReport) -> CashFlowReportResponse:
    interval = value.interval
    return CashFlowReportResponse(
        start_date=interval.start_date,
        end_date=interval.end_date,
        receipts_cents=value.receipts_cents,
        payments_cents=value.payments_cents,
        net_cash_flow_cents=value.net_cash_flow_cents,
        contributions=_contributions(value),
    )


@router.get("/reports/economic", response_model=EconomicReportResponse)
def economic_report(
    request: Request,
    principal: Principal,
    start_date: date,
    end_date: date,
) -> EconomicReportResponse:
    return _economic(
        _service(request).economic(ReportInterval(principal.space_id, start_date, end_date))
    )


@router.get("/reports/cash-flow", response_model=CashFlowReportResponse)
def cash_flow_report(
    request: Request,
    principal: Principal,
    start_date: date,
    end_date: date,
) -> CashFlowReportResponse:
    return _cash_flow(
        _service(request).cash_flow(ReportInterval(principal.space_id, start_date, end_date))
    )


@router.get("/reports/net-worth", response_model=NetWorthResponse)
def net_worth_report(
    request: Request,
    principal: Principal,
    as_of: Annotated[date, Query()],
) -> NetWorthResponse:
    value = _service(request).net_worth(principal.space_id, as_of)
    return NetWorthResponse(
        as_of=value.as_of,
        assets_cents=value.assets_cents,
        liabilities_cents=value.liabilities_cents,
        net_worth_cents=value.net_worth_cents,
        contributions=_contributions(value),
    )


__all__ = ("router",)
