"""SQLAlchemy adapter for ledger-owned records."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import Date, ForeignKeyConstraint, Integer, String, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.ledger.domain.account import Account, AccountKind, Category, CategoryKind
from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.errors import (
    DuplicateNameError,
    EntityNotFoundError,
    ImmutableLedgerError,
)
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.ledger.ports.repositories import DraftDetails
from app.shared.database import Base
from app.shared.models_ledger import (
    AccountRecord,
    CategoryRecord,
    EntryRecord,
    ReversalRecord,
    TransactionRecord,
)


class DraftDetailsRecord(Base):
    __tablename__ = "ledger_draft_details"
    __table_args__ = (
        ForeignKeyConstraint(
            ("space_id", "transaction_id"),
            ("transactions.space_id", "transactions.id"),
            ondelete="CASCADE",
        ),
    )

    transaction_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(36))
    category_id: Mapped[str | None] = mapped_column(String(36))
    destination_account_id: Mapped[str | None] = mapped_column(String(36))
    cash_date: Mapped[date | None] = mapped_column(Date)
    replacement_of_transaction_id: Mapped[str | None] = mapped_column(String(36))


class SqlAlchemyLedgerRepository:
    """Map ledger domain objects without owning a commit boundary."""

    def __init__(self, session: object) -> None:
        if not isinstance(session, Session):
            raise TypeError("ledger repository requires an active SQLAlchemy session")
        self._session = session

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
    def _category(record: CategoryRecord) -> Category:
        return Category(
            id=record.id,
            space_id=record.space_id,
            name=record.name,
            kind=CategoryKind(record.kind),
            is_archived=record.is_archived,
        )

    def add_account(self, account: Account) -> None:
        self._session.add(
            AccountRecord(
                id=account.id,
                space_id=account.space_id,
                name=account.name,
                kind=account.kind.value,
                is_archived=account.is_archived,
                is_reconcilable=account.is_reconcilable,
            )
        )
        self._flush_catalog()

    def get_account(self, space_id: str, account_id: str) -> Account:
        record = self._session.scalar(
            select(AccountRecord).where(
                AccountRecord.space_id == space_id,
                AccountRecord.id == account_id,
            )
        )
        if record is None:
            raise EntityNotFoundError("account was not found in the financial space")
        return self._account(record)

    def list_accounts(self, space_id: str, *, include_archived: bool) -> tuple[Account, ...]:
        statement = select(AccountRecord).where(
            AccountRecord.space_id == space_id,
            AccountRecord.kind != AccountKind.EQUITY.value,
        )
        if not include_archived:
            statement = statement.where(AccountRecord.is_archived.is_(False))
        records = self._session.scalars(statement.order_by(AccountRecord.name, AccountRecord.id))
        return tuple(self._account(record) for record in records)

    def update_account(self, account: Account) -> None:
        record = self._session.scalar(
            select(AccountRecord).where(
                AccountRecord.space_id == account.space_id,
                AccountRecord.id == account.id,
            )
        )
        if record is None:
            raise EntityNotFoundError("account was not found in the financial space")
        record.name = account.name
        record.is_archived = account.is_archived
        record.is_reconcilable = account.is_reconcilable
        self._flush_catalog()

    def add_category(self, category: Category) -> None:
        self._session.add(
            CategoryRecord(
                id=category.id,
                space_id=category.space_id,
                name=category.name,
                kind=category.kind.value,
                is_archived=category.is_archived,
            )
        )
        self._flush_catalog()

    def get_category(self, space_id: str, category_id: str) -> Category:
        record = self._session.scalar(
            select(CategoryRecord).where(
                CategoryRecord.space_id == space_id,
                CategoryRecord.id == category_id,
            )
        )
        if record is None:
            raise EntityNotFoundError("category was not found in the financial space")
        return self._category(record)

    def find_category_by_name(self, space_id: str, name: str) -> Category | None:
        record = self._session.scalar(
            select(CategoryRecord).where(
                CategoryRecord.space_id == space_id,
                CategoryRecord.name == name,
            )
        )
        return None if record is None else self._category(record)

    def list_categories(self, space_id: str, *, include_archived: bool) -> tuple[Category, ...]:
        statement = select(CategoryRecord).where(CategoryRecord.space_id == space_id)
        if not include_archived:
            statement = statement.where(CategoryRecord.is_archived.is_(False))
        records = self._session.scalars(statement.order_by(CategoryRecord.name, CategoryRecord.id))
        return tuple(self._category(record) for record in records)

    def update_category(self, category: Category) -> None:
        record = self._session.scalar(
            select(CategoryRecord).where(
                CategoryRecord.space_id == category.space_id,
                CategoryRecord.id == category.id,
            )
        )
        if record is None:
            raise EntityNotFoundError("category was not found in the financial space")
        record.name = category.name
        record.is_archived = category.is_archived
        self._flush_catalog()

    def _flush_catalog(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as error:
            raise DuplicateNameError("catalog name is already in use") from error

    def add_draft(self, transaction: Transaction, details: DraftDetails) -> None:
        self._session.add(self._transaction_record(transaction, state="DRAFT"))
        self._session.flush()
        self._session.add(
            DraftDetailsRecord(
                transaction_id=transaction.id,
                space_id=transaction.space_id,
                amount_cents=details.amount_cents,
                account_id=details.account_id,
                category_id=details.category_id,
                destination_account_id=details.destination_account_id,
                cash_date=details.cash_date,
                replacement_of_transaction_id=details.replacement_of_transaction_id,
            )
        )
        self._session.flush()

    def update_draft(self, transaction: Transaction, details: DraftDetails) -> None:
        record = self._transaction_record_for_update(transaction.space_id, transaction.id)
        if record.state != "DRAFT":
            raise ImmutableLedgerError("posted history cannot be edited")
        record.kind = transaction.kind.value
        record.economic_date = transaction.economic_date
        record.cash_date = transaction.cash_date
        record.description = transaction.description
        details_record = self._draft_details_record(transaction.space_id, transaction.id)
        details_record.amount_cents = details.amount_cents
        details_record.account_id = details.account_id
        details_record.category_id = details.category_id
        details_record.destination_account_id = details.destination_account_id
        details_record.cash_date = details.cash_date
        details_record.replacement_of_transaction_id = details.replacement_of_transaction_id
        self._session.flush()

    def discard_draft(self, space_id: str, transaction_id: str) -> None:
        record = self._transaction_record_for_update(space_id, transaction_id)
        if record.state != "DRAFT":
            raise ImmutableLedgerError("posted history cannot be deleted")
        self._session.delete(record)
        self._session.flush()

    def get_transaction(self, space_id: str, transaction_id: str) -> Transaction:
        record = self._session.scalar(
            select(TransactionRecord).where(
                TransactionRecord.space_id == space_id,
                TransactionRecord.id == transaction_id,
            )
        )
        if record is None:
            raise EntityNotFoundError("transaction was not found in the financial space")
        entries = self._entries(space_id, transaction_id)
        return self._transaction(record, entries)

    def get_draft_details(self, space_id: str, transaction_id: str) -> DraftDetails:
        record = self._draft_details_record(space_id, transaction_id)
        return DraftDetails(
            amount_cents=record.amount_cents,
            account_id=record.account_id,
            category_id=record.category_id,
            destination_account_id=record.destination_account_id,
            cash_date=record.cash_date,
            replacement_of_transaction_id=record.replacement_of_transaction_id,
        )

    def add_posted(self, transaction: Transaction) -> None:
        record = self._transaction_record(transaction, state="_POSTING")
        self._session.add(record)
        self._session.flush()
        self._add_entries(transaction)
        record.state = "POSTED"
        record.posted_at = datetime.now(UTC)
        self._session.flush()

    def post_existing_draft(self, transaction: Transaction) -> None:
        record = self._transaction_record_for_update(transaction.space_id, transaction.id)
        if record.state != "DRAFT":
            raise ImmutableLedgerError("only a draft can be posted")
        record.kind = transaction.kind.value
        record.economic_date = transaction.economic_date
        record.cash_date = transaction.cash_date
        record.description = transaction.description
        record.state = "_POSTING"
        self._session.flush()
        self._add_entries(transaction)
        record.state = "POSTED"
        record.posted_at = datetime.now(UTC)
        details_record = self._draft_details_record(transaction.space_id, transaction.id)
        self._session.delete(details_record)
        self._session.flush()

    def mark_voided(self, space_id: str, transaction_id: str) -> None:
        record = self._transaction_record_for_update(space_id, transaction_id)
        if record.state not in ("POSTED", "RECONCILED"):
            raise ImmutableLedgerError("only posted history can be voided")
        record.state = "VOIDED"
        self._session.flush()

    def add_reversal_link(
        self,
        *,
        space_id: str,
        original_transaction_id: str,
        reversal_transaction_id: str,
    ) -> None:
        self._session.add(
            ReversalRecord(
                id=uuid4().hex,
                space_id=space_id,
                original_transaction_id=original_transaction_id,
                reversal_transaction_id=reversal_transaction_id,
            )
        )
        self._session.flush()

    def list_transactions(
        self, space_id: str, *, limit: int, offset: int
    ) -> tuple[Transaction, ...]:
        records = self._session.scalars(
            select(TransactionRecord)
            .where(TransactionRecord.space_id == space_id)
            .order_by(
                TransactionRecord.economic_date.desc(),
                TransactionRecord.created_at.desc(),
                TransactionRecord.id,
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(
            self._transaction(record, self._entries(space_id, record.id)) for record in records
        )

    def account_balance_cents(self, space_id: str, account_id: str) -> int:
        signed = case(
            (EntryRecord.side == "DEBIT", EntryRecord.amount_cents),
            else_=-EntryRecord.amount_cents,
        )
        value = self._session.scalar(
            select(func.coalesce(func.sum(signed), 0))
            .join(TransactionRecord, TransactionRecord.id == EntryRecord.transaction_id)
            .where(
                EntryRecord.space_id == space_id,
                EntryRecord.account_id == account_id,
                TransactionRecord.state.in_(("POSTED", "RECONCILED", "VOIDED")),
            )
        )
        return int(value or 0)

    def reversal_links(self, space_id: str, transaction_id: str) -> tuple[str | None, str | None]:
        as_original = self._session.scalar(
            select(ReversalRecord).where(
                ReversalRecord.space_id == space_id,
                ReversalRecord.original_transaction_id == transaction_id,
            )
        )
        as_reversal = self._session.scalar(
            select(ReversalRecord).where(
                ReversalRecord.space_id == space_id,
                ReversalRecord.reversal_transaction_id == transaction_id,
            )
        )
        return (
            None if as_reversal is None else as_reversal.original_transaction_id,
            None if as_original is None else as_original.reversal_transaction_id,
        )

    def replacement_links(
        self, space_id: str, transaction_id: str
    ) -> tuple[str | None, str | None]:
        current = self._session.scalar(
            select(DraftDetailsRecord).where(
                DraftDetailsRecord.space_id == space_id,
                DraftDetailsRecord.transaction_id == transaction_id,
            )
        )
        replacement = self._session.scalar(
            select(DraftDetailsRecord).where(
                DraftDetailsRecord.space_id == space_id,
                DraftDetailsRecord.replacement_of_transaction_id == transaction_id,
            )
        )
        return (
            None if current is None else current.replacement_of_transaction_id,
            None if replacement is None else replacement.transaction_id,
        )

    def _transaction_record_for_update(
        self, space_id: str, transaction_id: str
    ) -> TransactionRecord:
        record = self._session.scalar(
            select(TransactionRecord).where(
                TransactionRecord.space_id == space_id,
                TransactionRecord.id == transaction_id,
            )
        )
        if record is None:
            raise EntityNotFoundError("transaction was not found in the financial space")
        return record

    def _draft_details_record(self, space_id: str, transaction_id: str) -> DraftDetailsRecord:
        record = self._session.scalar(
            select(DraftDetailsRecord).where(
                DraftDetailsRecord.space_id == space_id,
                DraftDetailsRecord.transaction_id == transaction_id,
            )
        )
        if record is None:
            raise EntityNotFoundError("draft details were not found in the financial space")
        return record

    @staticmethod
    def _transaction_record(transaction: Transaction, *, state: str) -> TransactionRecord:
        return TransactionRecord(
            id=transaction.id,
            space_id=transaction.space_id,
            kind=transaction.kind.value,
            state=state,
            economic_date=transaction.economic_date,
            cash_date=transaction.cash_date,
            description=transaction.description,
        )

    def _add_entries(self, transaction: Transaction) -> None:
        self._session.add_all(
            EntryRecord(
                id=entry.id,
                space_id=entry.space_id,
                transaction_id=transaction.id,
                account_id=entry.account_id,
                category_id=entry.category_id,
                side=entry.side.value,
                amount_cents=entry.amount_cents,
            )
            for entry in transaction.entries
        )
        self._session.flush()

    def _entries(self, space_id: str, transaction_id: str) -> tuple[Entry, ...]:
        records = self._session.scalars(
            select(EntryRecord)
            .where(
                EntryRecord.space_id == space_id,
                EntryRecord.transaction_id == transaction_id,
            )
            .order_by(EntryRecord.id)
        )
        return tuple(
            Entry(
                id=record.id,
                space_id=record.space_id,
                side=EntrySide(record.side),
                amount_cents=record.amount_cents,
                account_id=record.account_id,
                category_id=record.category_id,
            )
            for record in records
        )

    @staticmethod
    def _transaction(record: TransactionRecord, entries: tuple[Entry, ...]) -> Transaction:
        status = TransactionStatus(record.state)
        return Transaction(
            id=record.id,
            space_id=record.space_id,
            kind=TransactionKind(record.kind),
            status=status,
            economic_date=record.economic_date,
            cash_date=record.cash_date,
            description=record.description,
            entries=entries,
        )


__all__ = ("SqlAlchemyLedgerRepository",)
