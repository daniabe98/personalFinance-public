"""Immutable signed ledger entries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.ledger.domain.money import Money


class EntrySide(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


@dataclass(frozen=True, slots=True)
class Entry:
    id: str
    space_id: str
    side: EntrySide
    amount_cents: int
    account_id: str | None = None
    category_id: str | None = None

    def __post_init__(self) -> None:
        Money.positive(self.amount_cents)
        if (self.account_id is None) == (self.category_id is None):
            raise ValueError("an entry must target exactly one account or category")

    @classmethod
    def for_account(
        cls,
        entry_id: str,
        space_id: str,
        account_id: str,
        side: EntrySide,
        amount_cents: int,
    ) -> Entry:
        return cls(entry_id, space_id, side, amount_cents, account_id=account_id)

    @classmethod
    def for_category(
        cls,
        entry_id: str,
        space_id: str,
        category_id: str,
        side: EntrySide,
        amount_cents: int,
    ) -> Entry:
        return cls(entry_id, space_id, side, amount_cents, category_id=category_id)

    @property
    def signed_cents(self) -> int:
        return self.amount_cents if self.side is EntrySide.DEBIT else -self.amount_cents

    def reversed(self, entry_id: str) -> Entry:
        side = EntrySide.CREDIT if self.side is EntrySide.DEBIT else EntrySide.DEBIT
        return Entry(
            id=entry_id,
            space_id=self.space_id,
            side=side,
            amount_cents=self.amount_cents,
            account_id=self.account_id,
            category_id=self.category_id,
        )


__all__ = ("Entry", "EntrySide")
