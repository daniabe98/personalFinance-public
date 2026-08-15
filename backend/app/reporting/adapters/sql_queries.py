"""Parameterized SQLAlchemy reader over canonical ledger records."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.reporting.ports.ledger import ReportingEntry
from app.shared.models_ledger import (
    AccountRecord,
    CategoryRecord,
    EntryRecord,
    TransactionRecord,
)

_VISIBLE_STATES = ("POSTED", "RECONCILED", "VOIDED")


class SqlAlchemyReportingLedgerReader:
    def __init__(self, session: object) -> None:
        if not isinstance(session, Session):
            raise TypeError("reporting reader requires an active SQLAlchemy session")
        self._session = session

    def economic_entries(
        self, space_id: str, start_date: date, end_date: date
    ) -> tuple[ReportingEntry, ...]:
        statement = self._base_statement(space_id).where(
            TransactionRecord.economic_date >= start_date,
            TransactionRecord.economic_date <= end_date,
        )
        return self._read(statement, date_column=TransactionRecord.economic_date)

    def cash_entries(
        self, space_id: str, start_date: date, end_date: date
    ) -> tuple[ReportingEntry, ...]:
        statement = self._base_statement(space_id).where(
            TransactionRecord.cash_date.is_not(None),
            TransactionRecord.cash_date >= start_date,
            TransactionRecord.cash_date <= end_date,
        )
        return self._read(statement, date_column=TransactionRecord.cash_date)

    def net_worth_entries(self, space_id: str, as_of: date) -> tuple[ReportingEntry, ...]:
        statement = self._base_statement(space_id).where(TransactionRecord.economic_date <= as_of)
        return self._read(statement, date_column=TransactionRecord.economic_date)

    @staticmethod
    def _base_statement(space_id: str):
        return (
            select(EntryRecord, TransactionRecord, AccountRecord, CategoryRecord)
            .join(
                TransactionRecord,
                (TransactionRecord.id == EntryRecord.transaction_id)
                & (TransactionRecord.space_id == EntryRecord.space_id),
            )
            .outerjoin(
                AccountRecord,
                (AccountRecord.id == EntryRecord.account_id)
                & (AccountRecord.space_id == EntryRecord.space_id),
            )
            .outerjoin(
                CategoryRecord,
                (CategoryRecord.id == EntryRecord.category_id)
                & (CategoryRecord.space_id == EntryRecord.space_id),
            )
            .where(
                EntryRecord.space_id == space_id,
                TransactionRecord.space_id == space_id,
                TransactionRecord.state.in_(_VISIBLE_STATES),
            )
        )

    def _read(self, statement, *, date_column) -> tuple[ReportingEntry, ...]:
        rows = self._session.execute(
            statement.order_by(
                date_column,
                TransactionRecord.id,
                EntryRecord.id,
            )
        )
        return tuple(
            ReportingEntry(
                entry_id=entry.id,
                transaction_id=transaction.id,
                transaction_kind=transaction.kind,
                description=transaction.description,
                economic_date=transaction.economic_date,
                cash_date=transaction.cash_date,
                side=entry.side,
                amount_cents=entry.amount_cents,
                account_id=entry.account_id,
                account_kind=None if account is None else account.kind,
                category_id=entry.category_id,
                category_kind=None if category is None else category.kind,
            )
            for entry, transaction, account, category in rows
        )


__all__ = ("SqlAlchemyReportingLedgerReader",)
