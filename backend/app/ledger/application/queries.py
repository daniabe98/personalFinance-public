"""Immutable same-space projections over canonical ledger entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.ledger.domain.account import Account, AccountKind, Category, CategoryKind
from app.ledger.domain.entry import EntrySide
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.ledger.ports.repositories import DraftDetails, LedgerReadRepository, RepositoryFactory
from app.shared.unit_of_work import UnitOfWorkFactory

_STATUS_LABELS = {
    TransactionStatus.DRAFT: "Borrador",
    TransactionStatus.POSTED: "Contabilizado",
    TransactionStatus.RECONCILED: "Comprobado",
    TransactionStatus.VOIDED: "Anulado",
}


@dataclass(frozen=True, slots=True)
class AccountView:
    id: str
    name: str
    kind: AccountKind
    is_archived: bool
    is_reconcilable: bool
    balance_cents: int
    currency: str = "EUR"


@dataclass(frozen=True, slots=True)
class CategoryView:
    id: str
    name: str
    kind: CategoryKind
    is_archived: bool


@dataclass(frozen=True, slots=True)
class EntryView:
    id: str
    account_id: str | None
    category_id: str | None
    side: EntrySide
    amount_cents: int
    currency: str = "EUR"


@dataclass(frozen=True, slots=True)
class TransactionView:
    id: str
    kind: TransactionKind
    status: TransactionStatus
    status_label: str
    economic_date: date
    cash_date: date | None
    description: str | None
    entries: tuple[EntryView, ...]
    original_transaction_id: str | None
    reversal_transaction_id: str | None
    corrected_original_transaction_id: str | None
    replacement_transaction_id: str | None
    draft_details: DraftDetails | None


class LedgerQueryService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: RepositoryFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory

    def list_accounts(self, space_id: str, *, include_archived: bool) -> tuple[AccountView, ...]:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            accounts = repository.list_accounts(space_id, include_archived=include_archived)
            return tuple(self._account_view(repository, account) for account in accounts)

    def list_categories(self, space_id: str, *, include_archived: bool) -> tuple[CategoryView, ...]:
        with self._unit_of_work_factory() as unit_of_work:
            categories = self._repository_factory(unit_of_work.session).list_categories(
                space_id, include_archived=include_archived
            )
            return tuple(self._category_view(category) for category in categories)

    def get_transaction(self, space_id: str, transaction_id: str) -> TransactionView:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            transaction = repository.get_transaction(space_id, transaction_id)
            return self._transaction_view(repository, transaction)

    def list_transactions(
        self, space_id: str, *, limit: int, offset: int
    ) -> tuple[TransactionView, ...]:
        if limit < 1 or limit > 200 or offset < 0:
            raise ValueError("pagination is outside the accepted range")
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            transactions = repository.list_transactions(space_id, limit=limit, offset=offset)
            return tuple(
                self._transaction_view(repository, transaction) for transaction in transactions
            )

    @staticmethod
    def _account_view(repository: LedgerReadRepository, account: Account) -> AccountView:
        return AccountView(
            account.id,
            account.name,
            account.kind,
            account.is_archived,
            account.is_reconcilable,
            repository.account_balance_cents(account.space_id, account.id),
        )

    @staticmethod
    def _category_view(category: Category) -> CategoryView:
        return CategoryView(
            category.id,
            category.name,
            category.kind,
            category.is_archived,
        )

    @staticmethod
    def _transaction_view(
        repository: LedgerReadRepository, transaction: Transaction
    ) -> TransactionView:
        original_id, reversal_id = repository.reversal_links(transaction.space_id, transaction.id)
        corrected_original_id, replacement_id = repository.replacement_links(
            transaction.space_id, transaction.id
        )
        draft_details = (
            repository.get_draft_details(transaction.space_id, transaction.id)
            if transaction.status is TransactionStatus.DRAFT
            else None
        )
        return TransactionView(
            id=transaction.id,
            kind=transaction.kind,
            status=transaction.status,
            status_label=_STATUS_LABELS[transaction.status],
            economic_date=transaction.economic_date,
            cash_date=transaction.cash_date,
            description=transaction.description,
            entries=tuple(
                EntryView(
                    entry.id,
                    entry.account_id,
                    entry.category_id,
                    entry.side,
                    entry.amount_cents,
                )
                for entry in transaction.entries
            ),
            original_transaction_id=original_id,
            reversal_transaction_id=reversal_id,
            corrected_original_transaction_id=corrected_original_id,
            replacement_transaction_id=replacement_id,
            draft_details=draft_details,
        )


__all__ = (
    "AccountView",
    "CategoryView",
    "EntryView",
    "LedgerQueryService",
    "TransactionView",
)
