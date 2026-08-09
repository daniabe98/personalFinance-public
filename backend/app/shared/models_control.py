"""SQLAlchemy records for reconciliation, audit, and recovery controls."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database import Base


class ReconciliationRecord(Base):
    __tablename__ = "reconciliations"
    __table_args__ = (
        UniqueConstraint("space_id", "id"),
        ForeignKeyConstraint(
            ("space_id", "account_id"),
            ("accounts.space_id", "accounts.id"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'COMPLETED')",
            name="ck_reconciliations_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    observed_balance_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReconciliationEntryRecord(Base):
    __tablename__ = "reconciliation_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ("space_id", "reconciliation_id"),
            ("reconciliations.space_id", "reconciliations.id"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("space_id", "entry_id"),
            ("entries.space_id", "entries.id"),
            ondelete="RESTRICT",
        ),
        Index(
            "uq_completed_reconciliation_entry",
            "entry_id",
            unique=True,
            sqlite_where=text("is_completed = 1"),
        ),
    )

    reconciliation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), nullable=False)
    is_completed: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="0")


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str | None] = mapped_column(
        ForeignKey("spaces.id", ondelete="RESTRICT"),
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36))
    entity_type: Mapped[str | None] = mapped_column(String(120))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    correlation_id: Mapped[str] = mapped_column(String(120), nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text)


class BackupRunRecord(Base):
    __tablename__ = "backup_runs"
    __table_args__ = (
        UniqueConstraint("backup_date"),
        CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED')",
            name="ck_backup_runs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    backup_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    integrity_result: Mapped[str | None] = mapped_column(String(120))


__all__ = (
    "AuditEventRecord",
    "BackupRunRecord",
    "ReconciliationEntryRecord",
    "ReconciliationRecord",
)
