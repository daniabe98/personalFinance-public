"""Narrow canonical ledger-read port for reporting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ReportingEntry:
    entry_id: str
    transaction_id: str
    transaction_kind: str
    economic_date: date
    cash_date: date | None
    side: str
    amount_cents: int
    account_id: str | None
    account_kind: str | None
    category_id: str | None
    category_kind: str | None

    @property
    def signed_cents(self) -> int:
        return self.amount_cents if self.side == "DEBIT" else -self.amount_cents


class ReportingLedgerReader(Protocol):
    def economic_entries(
        self, space_id: str, start_date: date, end_date: date
    ) -> tuple[ReportingEntry, ...]: ...

    def cash_entries(
        self, space_id: str, start_date: date, end_date: date
    ) -> tuple[ReportingEntry, ...]: ...

    def net_worth_entries(self, space_id: str, as_of: date) -> tuple[ReportingEntry, ...]: ...


ReportingLedgerReaderFactory = Callable[[object], ReportingLedgerReader]


__all__ = (
    "ReportingEntry",
    "ReportingLedgerReader",
    "ReportingLedgerReaderFactory",
)
