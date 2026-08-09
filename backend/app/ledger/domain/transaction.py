"""Immutable ledger transaction lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import Self

from app.ledger.domain.entry import Entry
from app.ledger.domain.errors import (
    InvalidLifecycleError,
    OwnershipError,
    UnbalancedTransactionError,
)


class TransactionKind(StrEnum):
    OPENING = "OPENING"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    REVERSAL = "REVERSAL"


class TransactionStatus(StrEnum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    RECONCILED = "RECONCILED"
    VOIDED = "VOIDED"


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    space_id: str
    kind: TransactionKind
    status: TransactionStatus
    economic_date: date
    cash_date: date | None
    description: str | None
    entries: tuple[Entry, ...] = ()

    @classmethod
    def draft(
        cls,
        transaction_id: str,
        space_id: str,
        kind: TransactionKind,
        economic_date: date,
        description: str | None,
    ) -> Transaction:
        return cls(
            transaction_id,
            space_id,
            kind,
            TransactionStatus.DRAFT,
            economic_date,
            None,
            description,
        )

    @classmethod
    def posted(
        cls,
        transaction_id: str,
        space_id: str,
        kind: TransactionKind,
        economic_date: date,
        cash_date: date | None,
        description: str | None,
        entries: tuple[Entry, ...],
    ) -> Transaction:
        cls._validate_posting(space_id, entries)
        if kind is TransactionKind.OPENING and cash_date is not None:
            raise InvalidLifecycleError("opening transactions do not have a cash date")
        if kind not in (TransactionKind.OPENING, TransactionKind.REVERSAL) and cash_date is None:
            raise InvalidLifecycleError("cash-moving transactions require a cash date")
        return cls(
            transaction_id,
            space_id,
            kind,
            TransactionStatus.POSTED,
            economic_date,
            cash_date,
            description,
            entries,
        )

    @staticmethod
    def _validate_posting(space_id: str, entries: tuple[Entry, ...]) -> None:
        if len(entries) < 2 or sum(entry.signed_cents for entry in entries) != 0:
            raise UnbalancedTransactionError("posted entries must balance exactly")
        if any(entry.space_id != space_id for entry in entries):
            raise OwnershipError("all entries must belong to the transaction space")

    def revise(self, *, economic_date: date, description: str | None) -> Transaction:
        if self.status is not TransactionStatus.DRAFT:
            raise InvalidLifecycleError("only a draft can be revised")
        return replace(self, economic_date=economic_date, description=description)

    def reconcile(self) -> Transaction:
        if self.status is not TransactionStatus.POSTED:
            raise InvalidLifecycleError("only a posted transaction can be reconciled")
        return replace(self, status=TransactionStatus.RECONCILED)

    def void(self) -> Self:
        if self.status not in (TransactionStatus.POSTED, TransactionStatus.RECONCILED):
            raise InvalidLifecycleError("only posted history can be voided")
        return replace(self, status=TransactionStatus.VOIDED)


__all__ = ("Transaction", "TransactionKind", "TransactionStatus")
