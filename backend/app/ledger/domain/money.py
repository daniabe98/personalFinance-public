"""Exact EUR money represented only as integer cents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.ledger.domain.errors import CurrencyMismatchError, InvalidAmountError


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable exact amount of EUR cents."""

    cents: int
    currency: str = "EUR"

    EUR: ClassVar[str] = "EUR"

    def __post_init__(self) -> None:
        if isinstance(self.cents, bool) or not isinstance(self.cents, int):
            raise InvalidAmountError("money cents must be an integer")
        if self.currency != self.EUR:
            raise InvalidAmountError("only EUR is supported")

    @classmethod
    def positive(cls, cents: int) -> Money:
        value = cls(cents)
        if value.cents <= 0:
            raise InvalidAmountError("command amount must be positive")
        return value

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError("money currencies must match")

    def __add__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._require_same_currency(other)
        return Money(self.cents - other.cents, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.cents, self.currency)


__all__ = ("Money",)
