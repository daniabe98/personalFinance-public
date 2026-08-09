"""Immutable command contracts for the closed ledger use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.transaction import TransactionKind


@dataclass(frozen=True, slots=True)
class CreateAccount:
    space_id: str
    name: str
    kind: AccountKind
    is_reconcilable: bool


@dataclass(frozen=True, slots=True)
class CreateCategory:
    space_id: str
    name: str
    kind: CategoryKind


@dataclass(frozen=True, slots=True)
class DraftCommand:
    space_id: str
    kind: TransactionKind
    economic_date: date
    description: str | None
    amount_cents: int
    account_id: str | None = None
    category_id: str | None = None
    destination_account_id: str | None = None
    cash_date: date | None = None


@dataclass(frozen=True, slots=True)
class PostDraft:
    space_id: str
    transaction_id: str
    idempotency_key: str
    cash_date: date | None = None


@dataclass(frozen=True, slots=True)
class OpeningCommand:
    space_id: str
    account_id: str
    amount_cents: int
    economic_date: date
    description: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class IncomeCommand:
    space_id: str
    account_id: str
    category_id: str
    amount_cents: int
    economic_date: date
    cash_date: date | None
    description: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ExpenseCommand:
    space_id: str
    account_id: str
    category_id: str
    amount_cents: int
    economic_date: date
    cash_date: date | None
    description: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class TransferCommand:
    space_id: str
    source_account_id: str
    destination_account_id: str
    amount_cents: int
    economic_date: date
    cash_date: date | None
    description: str | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ReverseCommand:
    space_id: str
    original_transaction_id: str
    economic_date: date | None
    cash_date: date | None
    description: str | None
    idempotency_key: str
    replacement: DraftCommand | None = None


@dataclass(frozen=True, slots=True)
class CommandResult:
    transaction_id: str
    status: str
    replayed: bool = False
    replacement_transaction_id: str | None = None

    def as_json(self) -> dict[str, str | bool | None]:
        return {
            "transaction_id": self.transaction_id,
            "status": self.status,
            "replayed": self.replayed,
            "replacement_transaction_id": self.replacement_transaction_id,
        }


__all__ = (
    "CommandResult",
    "CreateAccount",
    "CreateCategory",
    "DraftCommand",
    "ExpenseCommand",
    "IncomeCommand",
    "OpeningCommand",
    "PostDraft",
    "ReverseCommand",
    "TransferCommand",
)
