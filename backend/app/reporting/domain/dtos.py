"""Immutable exact-cent reporting DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def _cents(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be integer cents")
    return value


@dataclass(frozen=True, slots=True)
class ReportInterval:
    space_id: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not self.space_id or self.space_id != self.space_id.strip():
            raise ValueError("space_id is required")
        if self.start_date > self.end_date:
            raise ValueError("report interval must be inclusive and ordered")


@dataclass(frozen=True, slots=True)
class ReportContribution:
    transaction_id: str
    amount_cents: int
    economic_date: date
    cash_date: date | None
    description: str | None
    account_id: str | None = None
    category_id: str | None = None
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if not self.transaction_id:
            raise ValueError("transaction_id is required")
        _cents(self.amount_cents, "amount_cents")
        if self.currency != "EUR":
            raise ValueError("only EUR is supported")


@dataclass(frozen=True, slots=True)
class EconomicReport:
    interval: ReportInterval
    income_cents: int
    expense_cents: int
    result_cents: int
    contributions: tuple[ReportContribution, ...]
    currency: str = "EUR"

    def __post_init__(self) -> None:
        _cents(self.income_cents, "income_cents")
        _cents(self.expense_cents, "expense_cents")
        _cents(self.result_cents, "result_cents")
        if self.result_cents != self.income_cents - self.expense_cents:
            raise ValueError("economic result must equal income minus expense")


@dataclass(frozen=True, slots=True)
class CashFlowReport:
    interval: ReportInterval
    receipts_cents: int
    payments_cents: int
    net_cash_flow_cents: int
    contributions: tuple[ReportContribution, ...]
    currency: str = "EUR"

    def __post_init__(self) -> None:
        _cents(self.receipts_cents, "receipts_cents")
        _cents(self.payments_cents, "payments_cents")
        _cents(self.net_cash_flow_cents, "net_cash_flow_cents")
        if self.net_cash_flow_cents != self.receipts_cents - self.payments_cents:
            raise ValueError("net cash flow must equal receipts minus payments")


@dataclass(frozen=True, slots=True)
class NetWorthReport:
    space_id: str
    as_of: date
    assets_cents: int
    liabilities_cents: int
    net_worth_cents: int
    contributions: tuple[ReportContribution, ...]
    currency: str = "EUR"

    def __post_init__(self) -> None:
        if not self.space_id:
            raise ValueError("space_id is required")
        _cents(self.assets_cents, "assets_cents")
        _cents(self.liabilities_cents, "liabilities_cents")
        _cents(self.net_worth_cents, "net_worth_cents")
        if self.net_worth_cents != self.assets_cents - self.liabilities_cents:
            raise ValueError("net worth must equal assets minus liabilities")


__all__ = (
    "CashFlowReport",
    "EconomicReport",
    "NetWorthReport",
    "ReportContribution",
    "ReportInterval",
)
