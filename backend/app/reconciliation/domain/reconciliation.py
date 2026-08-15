"""Pure reconciliation eligibility and exact balance model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum

from app.ledger.domain.account import Account, AccountKind
from app.ledger.domain.entry import Entry
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.reconciliation.domain.errors import (
    IneligibleAccountError,
    IneligibleEntryError,
    NonZeroDifferenceError,
)


def _exact_cents(value: int, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be integer cents")
    return value


class ReconciliationStatus(StrEnum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True, slots=True)
class ReconciliationCandidate:
    entry_id: str
    transaction_id: str
    space_id: str
    account_id: str
    description: str | None
    kind: TransactionKind
    eligibility_date: date
    signed_effect_cents: int

    def __post_init__(self) -> None:
        _exact_cents(self.signed_effect_cents, field_name="signed effect")

    @classmethod
    def from_ledger(
        cls,
        account: Account,
        transaction: Transaction,
        entry: Entry,
    ) -> ReconciliationCandidate:
        """Translate canonical ledger facts into one eligible account effect."""
        if (
            account.is_archived
            or not account.is_reconcilable
            or account.kind not in (AccountKind.ASSET, AccountKind.LIABILITY)
        ):
            raise IneligibleAccountError("account is not eligible for reconciliation")
        if (
            entry.account_id != account.id
            or entry.category_id is not None
            or entry.space_id != account.space_id
            or transaction.space_id != account.space_id
            or entry not in transaction.entries
            or transaction.status is TransactionStatus.DRAFT
        ):
            raise IneligibleEntryError("entry is not eligible for this account")
        eligibility_date = (
            transaction.economic_date
            if transaction.kind is TransactionKind.OPENING or transaction.cash_date is None
            else transaction.cash_date
        )
        return cls(
            entry_id=entry.id,
            transaction_id=transaction.id,
            space_id=entry.space_id,
            account_id=account.id,
            description=transaction.description,
            kind=transaction.kind,
            eligibility_date=eligibility_date,
            signed_effect_cents=entry.signed_cents,
        )

    def is_eligible(self, cutoff_date: date) -> bool:
        return self.eligibility_date <= cutoff_date


@dataclass(frozen=True, slots=True)
class ReconciliationSelection:
    entry_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.entry_ids:
            raise IneligibleEntryError("at least one entry must be selected")
        if len(set(self.entry_ids)) != len(self.entry_ids):
            raise IneligibleEntryError("selected entry identifiers must be unique")


@dataclass(frozen=True, slots=True)
class Reconciliation:
    id: str
    space_id: str
    account_id: str
    cutoff_date: date
    observed_balance_cents: int
    prior_completed_cents: int
    candidates: tuple[ReconciliationCandidate, ...]
    selection: ReconciliationSelection
    status: ReconciliationStatus = ReconciliationStatus.DRAFT

    def __post_init__(self) -> None:
        _exact_cents(self.observed_balance_cents, field_name="observed balance")
        _exact_cents(self.prior_completed_cents, field_name="prior completed balance")
        candidate_by_id = {candidate.entry_id: candidate for candidate in self.candidates}
        if len(candidate_by_id) != len(self.candidates):
            raise IneligibleEntryError("candidate entry identifiers must be unique")
        for entry_id in self.selection.entry_ids:
            candidate = candidate_by_id.get(entry_id)
            if (
                candidate is None
                or candidate.space_id != self.space_id
                or candidate.account_id != self.account_id
                or not candidate.is_eligible(self.cutoff_date)
            ):
                raise IneligibleEntryError("selected entry is outside this reconciliation")

    @classmethod
    def draft(
        cls,
        *,
        reconciliation_id: str,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        prior_completed_cents: int,
        candidates: tuple[ReconciliationCandidate, ...],
        selection: ReconciliationSelection,
    ) -> Reconciliation:
        return cls(
            id=reconciliation_id,
            space_id=space_id,
            account_id=account_id,
            cutoff_date=cutoff_date,
            observed_balance_cents=observed_balance_cents,
            prior_completed_cents=prior_completed_cents,
            candidates=candidates,
            selection=selection,
        )

    @property
    def selected_effect_cents(self) -> int:
        selected = set(self.selection.entry_ids)
        return sum(
            candidate.signed_effect_cents
            for candidate in self.candidates
            if candidate.entry_id in selected
        )

    @property
    def checked_balance_cents(self) -> int:
        return self.prior_completed_cents + self.selected_effect_cents

    @property
    def difference_cents(self) -> int:
        return self.observed_balance_cents - self.checked_balance_cents

    def complete(self) -> Reconciliation:
        if self.difference_cents != 0:
            raise NonZeroDifferenceError("observed and checked balances must match exactly")
        return replace(self, status=ReconciliationStatus.COMPLETED)


__all__ = (
    "Reconciliation",
    "ReconciliationCandidate",
    "ReconciliationSelection",
    "ReconciliationStatus",
)
