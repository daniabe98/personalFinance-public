"""Ledger-derived economic, cash-flow and net-worth reports."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.reporting.domain.dtos import (
    CashFlowReport,
    EconomicReport,
    NetWorthReport,
    ReportContribution,
    ReportInterval,
)
from app.reporting.ports.ledger import (
    ReportingEntry,
    ReportingLedgerReaderFactory,
)
from app.shared.unit_of_work import UnitOfWorkFactory


class ReportQueryService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        reader_factory: ReportingLedgerReaderFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._reader_factory = reader_factory

    def economic(self, interval: ReportInterval) -> EconomicReport:
        with self._unit_of_work_factory() as unit_of_work:
            entries = self._reader_factory(unit_of_work.session).economic_entries(
                interval.space_id, interval.start_date, interval.end_date
            )
        income = 0
        expense = 0
        contributions: list[ReportContribution] = []
        for entry in entries:
            amount = 0
            if entry.category_kind == "INCOME":
                amount = -entry.signed_cents
                income += amount
            elif entry.category_kind == "EXPENSE":
                amount = entry.signed_cents
                expense += amount
            else:
                continue
            contributions.append(self._contribution(entry, amount))
        return EconomicReport(
            interval=interval,
            income_cents=income,
            expense_cents=expense,
            result_cents=income - expense,
            contributions=tuple(contributions),
        )

    def cash_flow(self, interval: ReportInterval) -> CashFlowReport:
        with self._unit_of_work_factory() as unit_of_work:
            entries = self._reader_factory(unit_of_work.session).cash_entries(
                interval.space_id, interval.start_date, interval.end_date
            )
        by_transaction: dict[str, list[ReportingEntry]] = defaultdict(list)
        for entry in entries:
            by_transaction[entry.transaction_id].append(entry)
        receipts = 0
        payments = 0
        contributions: list[ReportContribution] = []
        for transaction_id in sorted(by_transaction):
            transaction_entries = by_transaction[transaction_id]
            category_kind = next(
                (
                    entry.category_kind
                    for entry in transaction_entries
                    if entry.category_kind is not None
                ),
                None,
            )
            account_entry = next(
                (entry for entry in transaction_entries if entry.account_id is not None),
                None,
            )
            if account_entry is None:
                continue
            if category_kind == "INCOME":
                amount = account_entry.signed_cents
                receipts += amount
            elif category_kind == "EXPENSE":
                amount = -account_entry.signed_cents
                payments += amount
            else:
                continue
            contributions.append(self._contribution(account_entry, amount))
        return CashFlowReport(
            interval=interval,
            receipts_cents=receipts,
            payments_cents=payments,
            net_cash_flow_cents=receipts - payments,
            contributions=tuple(contributions),
        )

    def net_worth(self, space_id: str, as_of: date) -> NetWorthReport:
        if not space_id:
            raise ValueError("space_id is required")
        with self._unit_of_work_factory() as unit_of_work:
            entries = self._reader_factory(unit_of_work.session).net_worth_entries(space_id, as_of)
        assets = 0
        liabilities = 0
        contributions: list[ReportContribution] = []
        for entry in entries:
            if entry.account_kind == "ASSET":
                amount = entry.signed_cents
                assets += amount
            elif entry.account_kind == "LIABILITY":
                amount = -entry.signed_cents
                liabilities += amount
            else:
                continue
            contributions.append(self._contribution(entry, amount))
        return NetWorthReport(
            space_id=space_id,
            as_of=as_of,
            assets_cents=assets,
            liabilities_cents=liabilities,
            net_worth_cents=assets - liabilities,
            contributions=tuple(contributions),
        )

    @staticmethod
    def _contribution(entry: ReportingEntry, amount_cents: int) -> ReportContribution:
        return ReportContribution(
            transaction_id=entry.transaction_id,
            amount_cents=amount_cents,
            economic_date=entry.economic_date,
            cash_date=entry.cash_date,
            description=entry.description,
            account_id=entry.account_id,
            category_id=entry.category_id,
        )


__all__ = ("ReportQueryService",)
