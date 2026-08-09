from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.ledger.domain.account import AccountKind
from app.ledger.domain.entry import EntrySide
from app.ledger.domain.posting_recipes import (
    expense_entries,
    income_entries,
    opening_entries,
    reversal_entries,
    transfer_entries,
)
from tests.support.ledger import (
    ASSET_ID,
    ASSET_TWO_ID,
    EQUITY_ID,
    EXPENSE_ID,
    INCOME_ID,
    LIABILITY_ID,
    SPACE_ID,
)


@given(st.integers(min_value=1, max_value=10**12))
def test_closed_recipes_are_balanced_for_every_positive_cent_amount(cents: int) -> None:
    recipes = (
        opening_entries(SPACE_ID, ASSET_ID, AccountKind.ASSET, EQUITY_ID, cents),
        opening_entries(SPACE_ID, LIABILITY_ID, AccountKind.LIABILITY, EQUITY_ID, cents),
        income_entries(SPACE_ID, ASSET_ID, INCOME_ID, cents),
        expense_entries(SPACE_ID, ASSET_ID, EXPENSE_ID, cents),
        transfer_entries(SPACE_ID, ASSET_ID, ASSET_TWO_ID, cents),
    )

    for entries in recipes:
        assert len(entries) == 2
        assert sum(entry.signed_cents for entry in entries) == 0
        assert {entry.space_id for entry in entries} == {SPACE_ID}


@given(st.integers(min_value=1, max_value=10**12))
def test_reversal_exactly_swaps_each_original_side(cents: int) -> None:
    original = income_entries(SPACE_ID, ASSET_ID, INCOME_ID, cents)
    reversed_entries = reversal_entries("reversal", original)

    assert [entry.amount_cents for entry in reversed_entries] == [cents, cents]
    assert [entry.side for entry in reversed_entries] == [EntrySide.CREDIT, EntrySide.DEBIT]
