"""Persistence ports owned by the ledger bounded context."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.ledger.domain.account import Account, Category
from app.ledger.domain.transaction import Transaction


@dataclass(frozen=True, slots=True)
class DraftDetails:
    amount_cents: int
    account_id: str | None
    category_id: str | None
    destination_account_id: str | None
    cash_date: date | None
    replacement_of_transaction_id: str | None = None


class CatalogRepository(Protocol):
    def add_account(self, account: Account) -> None: ...

    def get_account(self, space_id: str, account_id: str) -> Account: ...

    def list_accounts(self, space_id: str, *, include_archived: bool) -> Sequence[Account]: ...

    def update_account(self, account: Account) -> None: ...

    def add_category(self, category: Category) -> None: ...

    def get_category(self, space_id: str, category_id: str) -> Category: ...

    def find_category_by_name(self, space_id: str, name: str) -> Category | None: ...

    def list_categories(self, space_id: str, *, include_archived: bool) -> Sequence[Category]: ...

    def update_category(self, category: Category) -> None: ...


class TransactionRepository(CatalogRepository, Protocol):
    def add_draft(self, transaction: Transaction, details: DraftDetails) -> None: ...

    def update_draft(self, transaction: Transaction, details: DraftDetails) -> None: ...

    def discard_draft(self, space_id: str, transaction_id: str) -> None: ...

    def get_transaction(self, space_id: str, transaction_id: str) -> Transaction: ...

    def get_draft_details(self, space_id: str, transaction_id: str) -> DraftDetails: ...

    def add_posted(self, transaction: Transaction) -> None: ...

    def post_existing_draft(self, transaction: Transaction) -> None: ...

    def mark_voided(self, space_id: str, transaction_id: str) -> None: ...

    def add_reversal_link(
        self,
        *,
        space_id: str,
        original_transaction_id: str,
        reversal_transaction_id: str,
    ) -> None: ...

    def list_transactions(
        self, space_id: str, *, limit: int, offset: int
    ) -> Sequence[Transaction]: ...

    def reversal_links(
        self, space_id: str, transaction_id: str
    ) -> tuple[str | None, str | None]: ...

    def replacement_links(
        self, space_id: str, transaction_id: str
    ) -> tuple[str | None, str | None]: ...


class LedgerReadRepository(TransactionRepository, Protocol):
    def account_balance_cents(self, space_id: str, account_id: str) -> int: ...


RepositoryFactory = Callable[[object], LedgerReadRepository]


__all__ = (
    "CatalogRepository",
    "DraftDetails",
    "LedgerReadRepository",
    "RepositoryFactory",
    "TransactionRepository",
)
