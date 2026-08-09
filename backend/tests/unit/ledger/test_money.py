from __future__ import annotations

from typing import cast

import pytest

from app.ledger.domain.errors import InvalidAmountError
from app.ledger.domain.money import Money


def test_money_keeps_exact_integer_eur_cents() -> None:
    value = Money(125)

    assert value.cents == 125
    assert value.currency == "EUR"
    assert value + Money(75) == Money(200)
    assert value - Money(25) == Money(100)
    assert -value == Money(-125)


@pytest.mark.parametrize("value", [True, False, 1.0, "100", None])
def test_money_rejects_non_integer_cents(value: object) -> None:
    with pytest.raises(InvalidAmountError):
        Money(cast(int, value))


def test_money_rejects_other_currency_and_mismatch() -> None:
    with pytest.raises(InvalidAmountError):
        Money(100, "USD")


@pytest.mark.parametrize("value", [0, -1])
def test_positive_rejects_non_positive_command_amount(value: int) -> None:
    with pytest.raises(InvalidAmountError):
        Money.positive(value)


def test_money_is_immutable() -> None:
    value = Money(100)
    with pytest.raises((AttributeError, TypeError)):
        value.__setattr__("cents", 200)
