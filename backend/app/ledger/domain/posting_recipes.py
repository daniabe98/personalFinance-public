"""Closed posting recipes; no arbitrary-entry command is exposed."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from app.ledger.domain.account import AccountKind
from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.errors import InvalidLifecycleError
from app.ledger.domain.money import Money


def _entry_id() -> str:
    return uuid4().hex


def opening_entries(
    space_id: str,
    account_id: str,
    account_kind: AccountKind,
    equity_account_id: str,
    amount_cents: int,
) -> tuple[Entry, Entry]:
    Money.positive(amount_cents)
    if account_kind is AccountKind.ASSET:
        return (
            Entry.for_account(_entry_id(), space_id, account_id, EntrySide.DEBIT, amount_cents),
            Entry.for_account(
                _entry_id(), space_id, equity_account_id, EntrySide.CREDIT, amount_cents
            ),
        )
    if account_kind is AccountKind.LIABILITY:
        return (
            Entry.for_account(
                _entry_id(), space_id, equity_account_id, EntrySide.DEBIT, amount_cents
            ),
            Entry.for_account(_entry_id(), space_id, account_id, EntrySide.CREDIT, amount_cents),
        )
    raise InvalidLifecycleError("opening is supported only for visible financial accounts")


def income_entries(
    space_id: str,
    account_id: str,
    category_id: str,
    amount_cents: int,
) -> tuple[Entry, Entry]:
    Money.positive(amount_cents)
    return (
        Entry.for_account(_entry_id(), space_id, account_id, EntrySide.DEBIT, amount_cents),
        Entry.for_category(_entry_id(), space_id, category_id, EntrySide.CREDIT, amount_cents),
    )


def expense_entries(
    space_id: str,
    account_id: str,
    category_id: str,
    amount_cents: int,
) -> tuple[Entry, Entry]:
    Money.positive(amount_cents)
    return (
        Entry.for_category(_entry_id(), space_id, category_id, EntrySide.DEBIT, amount_cents),
        Entry.for_account(_entry_id(), space_id, account_id, EntrySide.CREDIT, amount_cents),
    )


def transfer_entries(
    space_id: str,
    source_account_id: str,
    destination_account_id: str,
    amount_cents: int,
) -> tuple[Entry, Entry]:
    Money.positive(amount_cents)
    if source_account_id == destination_account_id:
        raise InvalidLifecycleError("transfer accounts must be different")
    return (
        Entry.for_account(
            _entry_id(), space_id, destination_account_id, EntrySide.DEBIT, amount_cents
        ),
        Entry.for_account(_entry_id(), space_id, source_account_id, EntrySide.CREDIT, amount_cents),
    )


def reversal_entries(prefix: str, original: Sequence[Entry]) -> tuple[Entry, ...]:
    if len(original) < 2:
        raise InvalidLifecycleError("a posted transaction must have at least two entries")
    return tuple(entry.reversed(f"{prefix}-{index}") for index, entry in enumerate(original))


__all__ = (
    "expense_entries",
    "income_entries",
    "opening_entries",
    "reversal_entries",
    "transfer_entries",
)
