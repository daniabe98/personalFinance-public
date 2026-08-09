"""Core-owned persistence and audit ports for reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import Protocol

from app.ledger.domain.account import Account
from app.ledger.domain.transaction import Transaction, TransactionStatus
from app.reconciliation.domain.reconciliation import (
    Reconciliation,
    ReconciliationCandidate,
)


class ReconciliationRepository(Protocol):
    def get_account(self, space_id: str, account_id: str) -> Account: ...

    def list_candidates(
        self,
        space_id: str,
        account_id: str,
        cutoff_date: date,
    ) -> Sequence[ReconciliationCandidate]: ...

    def prior_completed_cents(
        self,
        space_id: str,
        account_id: str,
        cutoff_date: date,
    ) -> int: ...

    def add_completed(self, reconciliation: Reconciliation, completed_at: datetime) -> None: ...

    def transactions_for_entries(
        self,
        space_id: str,
        entry_ids: Sequence[str],
    ) -> Sequence[Transaction]: ...

    def reconcilable_accounts(self, space_id: str) -> Sequence[Account]: ...

    def completed_entry_ids(self, space_id: str, transaction_id: str) -> frozenset[str]: ...

    def set_transaction_state(
        self,
        space_id: str,
        transaction_id: str,
        state: TransactionStatus,
    ) -> None: ...


class ReconciliationAuditWriter(Protocol):
    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        reconciliation_id: str | None,
        correlation_id: str,
    ) -> None: ...


RepositoryFactory = Callable[[object], ReconciliationRepository]


__all__ = (
    "ReconciliationAuditWriter",
    "ReconciliationRepository",
    "RepositoryFactory",
)
