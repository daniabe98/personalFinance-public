"""SQLAlchemy records for the canonical ledger."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class AccountRecord(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("space_id", "id"),
        UniqueConstraint("space_id", "name"),
        CheckConstraint("kind IN ('ASSET', 'LIABILITY', 'EQUITY')", name="ck_accounts_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    is_archived: Mapped[bool] = mapped_column(default=False, server_default="0")
    is_reconcilable: Mapped[bool] = mapped_column(default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )


class CategoryRecord(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("space_id", "id"),
        UniqueConstraint("space_id", "name"),
        CheckConstraint("kind IN ('INCOME', 'EXPENSE')", name="ck_categories_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    is_archived: Mapped[bool] = mapped_column(default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )


class TransactionRecord(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("space_id", "id"),
        CheckConstraint(
            "kind IN ('OPENING', 'INCOME', 'EXPENSE', 'TRANSFER', 'REVERSAL')",
            name="ck_transactions_kind",
        ),
        CheckConstraint(
            "state IN ('DRAFT', '_POSTING', 'POSTED', 'RECONCILED', 'VOIDED')",
            name="ck_transactions_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    economic_date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EntryRecord(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("space_id", "id"),
        ForeignKeyConstraint(
            ("space_id", "transaction_id"),
            ("transactions.space_id", "transactions.id"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("space_id", "account_id"),
            ("accounts.space_id", "accounts.id"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("space_id", "category_id"),
            ("categories.space_id", "categories.id"),
            ondelete="RESTRICT",
        ),
        CheckConstraint("side IN ('DEBIT', 'CREDIT')", name="ck_entries_side"),
        CheckConstraint("amount_cents > 0", name="ck_entries_positive_amount"),
        CheckConstraint(
            "(account_id IS NULL) <> (category_id IS NULL)",
            name="ck_entries_single_target",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str | None] = mapped_column(String(36))
    category_id: Mapped[str | None] = mapped_column(String(36))
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class ReversalRecord(Base):
    __tablename__ = "reversals"
    __table_args__ = (
        ForeignKeyConstraint(
            ("space_id", "original_transaction_id"),
            ("transactions.space_id", "transactions.id"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("space_id", "reversal_transaction_id"),
            ("transactions.space_id", "transactions.id"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint("original_transaction_id"),
        UniqueConstraint("reversal_transaction_id"),
        CheckConstraint(
            "original_transaction_id <> reversal_transaction_id",
            name="ck_reversals_distinct",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), nullable=False)
    original_transaction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reversal_transaction_id: Mapped[str] = mapped_column(String(36), nullable=False)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("space_id", "idempotency_key"),
        CheckConstraint("length(payload_hash) = 64", name="ck_idempotency_payload_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    command_name: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = (
    "AccountRecord",
    "CategoryRecord",
    "EntryRecord",
    "IdempotencyRecord",
    "ReversalRecord",
    "TransactionRecord",
)
