"""Pure ledger transaction state derived from completed entry memberships."""

from __future__ import annotations

from collections.abc import Collection

from app.ledger.domain.account import Account, AccountKind
from app.ledger.domain.transaction import Transaction, TransactionStatus


def project_transaction_state(
    transaction: Transaction,
    accounts: Collection[Account],
    completed_entry_ids: Collection[str],
) -> TransactionStatus:
    """Project RECONCILED only when every reconcilable account entry is complete."""
    if transaction.status in (TransactionStatus.DRAFT, TransactionStatus.VOIDED):
        return transaction.status
    eligible_account_ids = {
        account.id
        for account in accounts
        if account.space_id == transaction.space_id
        and not account.is_archived
        and account.is_reconcilable
        and account.kind in (AccountKind.ASSET, AccountKind.LIABILITY)
    }
    reconcilable_entry_ids = {
        entry.id for entry in transaction.entries if entry.account_id in eligible_account_ids
    }
    if not reconcilable_entry_ids:
        return transaction.status
    if reconcilable_entry_ids.issubset(completed_entry_ids):
        return TransactionStatus.RECONCILED
    return TransactionStatus.POSTED


__all__ = ("project_transaction_state",)
