"""SQLAlchemy adapter for reconciliation-owned persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ledger.domain.account import Account, AccountKind
from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.reconciliation.domain.errors import (
    DuplicateCompletedMembershipError,
    IneligibleAccountError,
)
from app.reconciliation.domain.reconciliation import (
    Reconciliation,
    ReconciliationCandidate,
    ReconciliationStatus,
)
from app.shared.models_control import ReconciliationEntryRecord, ReconciliationRecord
from app.shared.models_ledger import AccountRecord, EntryRecord, TransactionRecord


class SqlAlchemyReconciliationRepository:
    """Read canonical ledger effects and append completed memberships."""

    def __init__(self, session: object) -> None:
        if not isinstance(session, Session):
            raise TypeError("reconciliation repository requires an active SQLAlchemy session")
        self._session = session

    def get_account(self, space_id: str, account_id: str) -> Account:
        record = self._session.scalar(
            select(AccountRecord).where(
                AccountRecord.space_id == space_id,
                AccountRecord.id == account_id,
            )
        )
        if record is None:
            raise IneligibleAccountError("account was not found in the financial space")
        account = self._account(record)
        if (
            account.is_archived
            or not account.is_reconcilable
            or account.kind not in (AccountKind.ASSET, AccountKind.LIABILITY)
        ):
            raise IneligibleAccountError("account is not eligible for reconciliation")
        return account

    def list_candidates(
        self,
        space_id: str,
        account_id: str,
        cutoff_date: date,
    ) -> tuple[ReconciliationCandidate, ...]:
        self.get_account(space_id, account_id)
        eligibility_date = case(
            (
                (TransactionRecord.kind == TransactionKind.OPENING.value)
                | TransactionRecord.cash_date.is_(None),
                TransactionRecord.economic_date,
            ),
            else_=TransactionRecord.cash_date,
        )
        already_completed = (
            select(ReconciliationEntryRecord.entry_id)
            .where(
                ReconciliationEntryRecord.entry_id == EntryRecord.id,
                ReconciliationEntryRecord.is_completed.is_(True),
            )
            .exists()
        )
        rows = self._session.execute(
            select(EntryRecord, TransactionRecord, eligibility_date.label("eligibility_date"))
            .join(
                TransactionRecord,
                (TransactionRecord.space_id == EntryRecord.space_id)
                & (TransactionRecord.id == EntryRecord.transaction_id),
            )
            .where(
                EntryRecord.space_id == space_id,
                EntryRecord.account_id == account_id,
                TransactionRecord.state.in_(
                    (
                        TransactionStatus.POSTED.value,
                        TransactionStatus.RECONCILED.value,
                        TransactionStatus.VOIDED.value,
                    )
                ),
                eligibility_date <= cutoff_date,
                ~already_completed,
            )
            .order_by(eligibility_date, EntryRecord.id)
        )
        return tuple(
            ReconciliationCandidate(
                entry_id=entry.id,
                transaction_id=transaction.id,
                space_id=entry.space_id,
                account_id=account_id,
                eligibility_date=row_eligibility_date,
                signed_effect_cents=(
                    entry.amount_cents
                    if entry.side == EntrySide.DEBIT.value
                    else -entry.amount_cents
                ),
            )
            for entry, transaction, row_eligibility_date in rows
        )

    def prior_completed_cents(
        self,
        space_id: str,
        account_id: str,
        cutoff_date: date,
    ) -> int:
        self.get_account(space_id, account_id)
        signed_effect = case(
            (EntryRecord.side == EntrySide.DEBIT.value, EntryRecord.amount_cents),
            else_=-EntryRecord.amount_cents,
        )
        eligibility_date = case(
            (
                (TransactionRecord.kind == TransactionKind.OPENING.value)
                | TransactionRecord.cash_date.is_(None),
                TransactionRecord.economic_date,
            ),
            else_=TransactionRecord.cash_date,
        )
        value = self._session.scalar(
            select(func.coalesce(func.sum(signed_effect), 0))
            .select_from(ReconciliationEntryRecord)
            .join(
                ReconciliationRecord,
                (ReconciliationRecord.space_id == ReconciliationEntryRecord.space_id)
                & (ReconciliationRecord.id == ReconciliationEntryRecord.reconciliation_id),
            )
            .join(
                EntryRecord,
                (EntryRecord.space_id == ReconciliationEntryRecord.space_id)
                & (EntryRecord.id == ReconciliationEntryRecord.entry_id),
            )
            .join(
                TransactionRecord,
                (TransactionRecord.space_id == EntryRecord.space_id)
                & (TransactionRecord.id == EntryRecord.transaction_id),
            )
            .where(
                ReconciliationEntryRecord.space_id == space_id,
                ReconciliationEntryRecord.is_completed.is_(True),
                ReconciliationRecord.status == ReconciliationStatus.COMPLETED.value,
                EntryRecord.account_id == account_id,
                eligibility_date <= cutoff_date,
            )
        )
        return int(value or 0)

    def add_completed(self, reconciliation: Reconciliation, completed_at: datetime) -> None:
        if reconciliation.status is not ReconciliationStatus.COMPLETED:
            raise ValueError("only a completed reconciliation can be persisted")
        selected_ids = reconciliation.selection.entry_ids
        duplicate = self._session.scalar(
            select(ReconciliationEntryRecord.entry_id)
            .where(
                ReconciliationEntryRecord.entry_id.in_(selected_ids),
                ReconciliationEntryRecord.is_completed.is_(True),
            )
            .limit(1)
        )
        if duplicate is not None:
            raise DuplicateCompletedMembershipError(
                "entry already belongs to a completed reconciliation"
            )
        self._session.add(
            ReconciliationRecord(
                id=reconciliation.id,
                space_id=reconciliation.space_id,
                account_id=reconciliation.account_id,
                cutoff_date=reconciliation.cutoff_date,
                observed_balance_cents=reconciliation.observed_balance_cents,
                status=ReconciliationStatus.COMPLETED.value,
                completed_at=completed_at,
            )
        )
        self._session.flush()
        self._session.add_all(
            ReconciliationEntryRecord(
                reconciliation_id=reconciliation.id,
                entry_id=entry_id,
                space_id=reconciliation.space_id,
                is_completed=True,
            )
            for entry_id in selected_ids
        )
        try:
            self._session.flush()
        except IntegrityError as error:
            raise DuplicateCompletedMembershipError(
                "entry already belongs to a completed reconciliation"
            ) from error

    def transactions_for_entries(
        self,
        space_id: str,
        entry_ids: Sequence[str],
    ) -> tuple[Transaction, ...]:
        transaction_ids = tuple(
            self._session.scalars(
                select(EntryRecord.transaction_id)
                .where(
                    EntryRecord.space_id == space_id,
                    EntryRecord.id.in_(entry_ids),
                )
                .distinct()
                .order_by(EntryRecord.transaction_id)
            )
        )
        return tuple(
            self._transaction(space_id, transaction_id) for transaction_id in transaction_ids
        )

    def reconcilable_accounts(self, space_id: str) -> tuple[Account, ...]:
        records = self._session.scalars(
            select(AccountRecord)
            .where(
                AccountRecord.space_id == space_id,
                AccountRecord.is_archived.is_(False),
                AccountRecord.is_reconcilable.is_(True),
                AccountRecord.kind.in_((AccountKind.ASSET.value, AccountKind.LIABILITY.value)),
            )
            .order_by(AccountRecord.id)
        )
        return tuple(self._account(record) for record in records)

    def completed_entry_ids(self, space_id: str, transaction_id: str) -> frozenset[str]:
        return frozenset(
            self._session.scalars(
                select(ReconciliationEntryRecord.entry_id)
                .join(
                    EntryRecord,
                    (EntryRecord.space_id == ReconciliationEntryRecord.space_id)
                    & (EntryRecord.id == ReconciliationEntryRecord.entry_id),
                )
                .where(
                    ReconciliationEntryRecord.space_id == space_id,
                    ReconciliationEntryRecord.is_completed.is_(True),
                    EntryRecord.transaction_id == transaction_id,
                )
            )
        )

    def set_transaction_state(
        self,
        space_id: str,
        transaction_id: str,
        state: TransactionStatus,
    ) -> None:
        record = self._session.scalar(
            select(TransactionRecord).where(
                TransactionRecord.space_id == space_id,
                TransactionRecord.id == transaction_id,
            )
        )
        if record is None:
            raise RuntimeError("reconciled transaction was not found")
        if record.state != TransactionStatus.VOIDED.value:
            record.state = state.value
            self._session.flush()

    def _transaction(self, space_id: str, transaction_id: str) -> Transaction:
        record = self._session.scalar(
            select(TransactionRecord).where(
                TransactionRecord.space_id == space_id,
                TransactionRecord.id == transaction_id,
            )
        )
        if record is None:
            raise RuntimeError("candidate transaction was not found")
        entries = tuple(
            self._session.scalars(
                select(EntryRecord)
                .where(
                    EntryRecord.space_id == space_id,
                    EntryRecord.transaction_id == transaction_id,
                )
                .order_by(EntryRecord.id)
            )
        )
        return Transaction(
            id=record.id,
            space_id=record.space_id,
            kind=TransactionKind(record.kind),
            status=TransactionStatus(record.state),
            economic_date=record.economic_date,
            cash_date=record.cash_date,
            description=record.description,
            entries=tuple(self._entry(entry) for entry in entries),
        )

    @staticmethod
    def _account(record: AccountRecord) -> Account:
        return Account(
            id=record.id,
            space_id=record.space_id,
            name=record.name,
            kind=AccountKind(record.kind),
            is_archived=record.is_archived,
            is_reconcilable=record.is_reconcilable,
        )

    @staticmethod
    def _entry(record: EntryRecord) -> Entry:
        return Entry(
            id=record.id,
            space_id=record.space_id,
            side=EntrySide(record.side),
            amount_cents=record.amount_cents,
            account_id=record.account_id,
            category_id=record.category_id,
        )


__all__ = ("SqlAlchemyReconciliationRepository",)
