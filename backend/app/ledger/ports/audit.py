"""Minimized ledger-owned audit outcome port."""

from __future__ import annotations

from typing import Protocol


class FinancialAuditSink(Protocol):
    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        transaction_id: str | None,
        correlation_id: str,
    ) -> None: ...


class NullFinancialAuditSink:
    """Explicit no-op binding used until the audit module supplies persistence."""

    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        transaction_id: str | None,
        correlation_id: str,
    ) -> None:
        del session, action, outcome, space_id, transaction_id, correlation_id


__all__ = ("FinancialAuditSink", "NullFinancialAuditSink")
