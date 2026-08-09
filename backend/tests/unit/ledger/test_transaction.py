from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.errors import InvalidLifecycleError, OwnershipError
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from tests.support.ledger import ASSET_ID, CASH_DATE, ECONOMIC_DATE, INCOME_ID, SPACE_ID


def test_draft_has_no_entries_and_can_be_revised() -> None:
    draft = Transaction.draft(
        transaction_id="draft-1",
        space_id=SPACE_ID,
        kind=TransactionKind.INCOME,
        economic_date=ECONOMIC_DATE,
        description="Draft",
    )
    revised = draft.revise(economic_date=date(2026, 7, 3), description="Revised")

    assert draft.status is TransactionStatus.DRAFT
    assert draft.entries == ()
    assert revised.description == "Revised"
    assert revised.economic_date == date(2026, 7, 3)


def test_posted_requires_balanced_same_space_entries() -> None:
    entries = (
        Entry.for_account("e1", SPACE_ID, ASSET_ID, EntrySide.DEBIT, 100),
        Entry.for_category("e2", SPACE_ID, INCOME_ID, EntrySide.CREDIT, 100),
    )
    posted = Transaction.posted(
        transaction_id="tx-1",
        space_id=SPACE_ID,
        kind=TransactionKind.INCOME,
        economic_date=ECONOMIC_DATE,
        cash_date=CASH_DATE,
        description=None,
        entries=entries,
    )

    assert posted.status is TransactionStatus.POSTED
    assert sum(entry.signed_cents for entry in posted.entries) == 0
    with pytest.raises(FrozenInstanceError):
        posted.__setattr__("description", "changed")


def test_posted_rejects_cross_space_entry() -> None:
    entries = (
        Entry.for_account("e1", SPACE_ID, ASSET_ID, EntrySide.DEBIT, 100),
        Entry.for_category("e2", "other", INCOME_ID, EntrySide.CREDIT, 100),
    )
    with pytest.raises(OwnershipError):
        Transaction.posted(
            "tx-1",
            SPACE_ID,
            TransactionKind.INCOME,
            ECONOMIC_DATE,
            CASH_DATE,
            None,
            entries,
        )


def test_only_posted_can_reconcile_or_void() -> None:
    draft = Transaction.draft("draft-1", SPACE_ID, TransactionKind.EXPENSE, ECONOMIC_DATE, None)
    with pytest.raises(InvalidLifecycleError):
        draft.reconcile()
    with pytest.raises(InvalidLifecycleError):
        draft.void()
