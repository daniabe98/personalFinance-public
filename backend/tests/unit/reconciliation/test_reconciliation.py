from __future__ import annotations

from datetime import date

import pytest

from app.ledger.application.state_projection import project_transaction_state
from app.ledger.domain.account import Account, AccountKind
from app.ledger.domain.entry import Entry, EntrySide
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.reconciliation.domain.errors import (
    IneligibleAccountError,
    IneligibleEntryError,
    NonZeroDifferenceError,
)
from app.reconciliation.domain.reconciliation import (
    Reconciliation,
    ReconciliationCandidate,
    ReconciliationSelection,
    ReconciliationStatus,
)

SPACE_ID = "space-1"
ACCOUNT_ID = "account-1"
CUTOFF = date(2026, 7, 31)


def _account(
    account_id: str = ACCOUNT_ID,
    *,
    kind: AccountKind = AccountKind.ASSET,
    archived: bool = False,
    reconcilable: bool = True,
) -> Account:
    return Account(
        id=account_id,
        space_id=SPACE_ID,
        name=account_id,
        kind=kind,
        is_archived=archived,
        is_reconcilable=reconcilable,
    )


def _posted_transaction(
    transaction_id: str,
    *,
    kind: TransactionKind,
    economic_date: date,
    cash_date: date | None,
    account_id: str = ACCOUNT_ID,
    side: EntrySide = EntrySide.DEBIT,
    entry_id: str | None = None,
    description: str | None = "Test movement",
) -> tuple[Transaction, Entry]:
    financial = Entry.for_account(
        entry_id or f"{transaction_id}-financial",
        SPACE_ID,
        account_id,
        side,
        100_000,
    )
    balancing = Entry.for_category(
        f"{transaction_id}-category",
        SPACE_ID,
        "category-1",
        EntrySide.CREDIT if side is EntrySide.DEBIT else EntrySide.DEBIT,
        100_000,
    )
    transaction = Transaction.posted(
        transaction_id,
        SPACE_ID,
        kind,
        economic_date,
        cash_date,
        description,
        (financial, balancing),
    )
    return transaction, financial


@pytest.mark.parametrize("kind", [AccountKind.ASSET, AccountKind.LIABILITY])
def test_candidate_accepts_visible_reconcilable_financial_accounts(
    kind: AccountKind,
) -> None:
    transaction, entry = _posted_transaction(
        "income",
        kind=TransactionKind.INCOME,
        economic_date=date(2026, 7, 2),
        cash_date=date(2026, 7, 3),
    )

    candidate = ReconciliationCandidate.from_ledger(_account(kind=kind), transaction, entry)

    assert candidate.entry_id == entry.id
    assert candidate.eligibility_date == date(2026, 7, 3)
    assert candidate.signed_effect_cents == 100_000
    assert candidate.description == "Test movement"
    assert candidate.kind is TransactionKind.INCOME


@pytest.mark.parametrize(
    "account",
    [
        _account(archived=True),
        _account(reconcilable=False),
        _account(kind=AccountKind.EQUITY, reconcilable=False),
    ],
)
def test_candidate_rejects_hidden_internal_or_non_reconcilable_account(
    account: Account,
) -> None:
    transaction, entry = _posted_transaction(
        "income",
        kind=TransactionKind.INCOME,
        economic_date=date(2026, 7, 2),
        cash_date=date(2026, 7, 3),
    )

    with pytest.raises(IneligibleAccountError):
        ReconciliationCandidate.from_ledger(account, transaction, entry)


def test_candidate_rejects_category_entry() -> None:
    transaction, _ = _posted_transaction(
        "expense",
        kind=TransactionKind.EXPENSE,
        economic_date=date(2026, 7, 2),
        cash_date=date(2026, 7, 3),
    )
    category_entry = transaction.entries[1]

    with pytest.raises(IneligibleEntryError):
        ReconciliationCandidate.from_ledger(_account(), transaction, category_entry)


def test_opening_uses_economic_date_for_cutoff() -> None:
    transaction, entry = _posted_transaction(
        "opening",
        kind=TransactionKind.OPENING,
        economic_date=CUTOFF,
        cash_date=None,
        description=None,
    )

    candidate = ReconciliationCandidate.from_ledger(_account(), transaction, entry)

    assert candidate.eligibility_date == CUTOFF
    assert candidate.description is None
    assert candidate.kind is TransactionKind.OPENING
    assert candidate.is_eligible(CUTOFF)
    assert not candidate.is_eligible(date(2026, 7, 30))


def test_ordinary_entry_uses_cash_date_for_cutoff() -> None:
    transaction, entry = _posted_transaction(
        "income",
        kind=TransactionKind.INCOME,
        economic_date=date(2026, 7, 1),
        cash_date=date(2026, 8, 1),
    )

    candidate = ReconciliationCandidate.from_ledger(_account(), transaction, entry)

    assert not candidate.is_eligible(CUTOFF)
    assert candidate.is_eligible(date(2026, 8, 1))


def test_reconciliation_calculates_prior_plus_selection_and_exact_difference() -> None:
    first_transaction, first_entry = _posted_transaction(
        "first",
        kind=TransactionKind.INCOME,
        economic_date=date(2026, 7, 1),
        cash_date=date(2026, 7, 1),
        entry_id="first-entry",
    )
    second_transaction, second_entry = _posted_transaction(
        "second",
        kind=TransactionKind.EXPENSE,
        economic_date=date(2026, 7, 2),
        cash_date=date(2026, 7, 2),
        side=EntrySide.CREDIT,
        entry_id="second-entry",
    )
    candidates = (
        ReconciliationCandidate.from_ledger(_account(), first_transaction, first_entry),
        ReconciliationCandidate.from_ledger(_account(), second_transaction, second_entry),
    )

    reconciliation = Reconciliation.draft(
        reconciliation_id="reconciliation-1",
        space_id=SPACE_ID,
        account_id=ACCOUNT_ID,
        cutoff_date=CUTOFF,
        observed_balance_cents=125_000,
        prior_completed_cents=75_000,
        candidates=candidates,
        selection=ReconciliationSelection(("first-entry", "second-entry")),
    )

    assert reconciliation.selected_effect_cents == 0
    assert reconciliation.checked_balance_cents == 75_000
    assert reconciliation.difference_cents == 50_000


def test_completion_requires_exact_zero_difference() -> None:
    transaction, entry = _posted_transaction(
        "opening",
        kind=TransactionKind.OPENING,
        economic_date=CUTOFF,
        cash_date=None,
    )
    candidate = ReconciliationCandidate.from_ledger(_account(), transaction, entry)
    reconciliation = Reconciliation.draft(
        reconciliation_id="reconciliation-1",
        space_id=SPACE_ID,
        account_id=ACCOUNT_ID,
        cutoff_date=CUTOFF,
        observed_balance_cents=99_999,
        prior_completed_cents=0,
        candidates=(candidate,),
        selection=ReconciliationSelection((entry.id,)),
    )

    with pytest.raises(NonZeroDifferenceError):
        reconciliation.complete()

    exact = Reconciliation.draft(
        reconciliation_id="reconciliation-2",
        space_id=SPACE_ID,
        account_id=ACCOUNT_ID,
        cutoff_date=CUTOFF,
        observed_balance_cents=100_000,
        prior_completed_cents=0,
        candidates=(candidate,),
        selection=ReconciliationSelection((entry.id,)),
    ).complete()
    assert exact.status is ReconciliationStatus.COMPLETED


def test_transfer_sides_are_reconciled_independently() -> None:
    source = _account("source")
    destination = _account("destination")
    source_entry = Entry.for_account(
        "source-entry",
        SPACE_ID,
        source.id,
        EntrySide.CREDIT,
        50_000,
    )
    destination_entry = Entry.for_account(
        "destination-entry",
        SPACE_ID,
        destination.id,
        EntrySide.DEBIT,
        50_000,
    )
    transaction = Transaction.posted(
        "transfer",
        SPACE_ID,
        TransactionKind.TRANSFER,
        CUTOFF,
        CUTOFF,
        None,
        (source_entry, destination_entry),
    )

    assert (
        project_transaction_state(transaction, (source, destination), {"source-entry"})
        is TransactionStatus.POSTED
    )
    assert (
        project_transaction_state(
            transaction,
            (source, destination),
            {"source-entry", "destination-entry"},
        )
        is TransactionStatus.RECONCILED
    )


def test_expense_category_entry_is_excluded_from_state_projection() -> None:
    transaction, financial_entry = _posted_transaction(
        "expense",
        kind=TransactionKind.EXPENSE,
        economic_date=CUTOFF,
        cash_date=CUTOFF,
        side=EntrySide.CREDIT,
    )

    state = project_transaction_state(transaction, (_account(),), {financial_entry.id})

    assert state is TransactionStatus.RECONCILED


def test_original_and_reversal_entries_project_independently() -> None:
    original, original_entry = _posted_transaction(
        "original",
        kind=TransactionKind.EXPENSE,
        economic_date=date(2026, 6, 1),
        cash_date=date(2026, 6, 1),
        side=EntrySide.CREDIT,
    )
    reversal_entries = tuple(entry.reversed(f"reversal-{entry.id}") for entry in original.entries)
    reversal = Transaction.posted(
        "reversal",
        SPACE_ID,
        TransactionKind.REVERSAL,
        CUTOFF,
        CUTOFF,
        None,
        reversal_entries,
    )

    assert (
        project_transaction_state(original, (_account(),), {original_entry.id})
        is TransactionStatus.RECONCILED
    )
    assert (
        project_transaction_state(reversal, (_account(),), {original_entry.id})
        is TransactionStatus.POSTED
    )
    assert (
        project_transaction_state(reversal, (_account(),), {"reversal-original-financial"})
        is TransactionStatus.RECONCILED
    )
