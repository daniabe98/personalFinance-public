from __future__ import annotations

import pytest

from app.ledger.domain.description import (
    legacy_description_label,
    normalize_required_description,
    reversal_description,
)
from app.ledger.domain.errors import InvalidLifecycleError


def test_normalize_required_description_trims_surrounding_whitespace() -> None:
    assert normalize_required_description("  Monthly salary  ") == "Monthly salary"


@pytest.mark.parametrize("description", [None, "", "   ", "x" * 501])
def test_normalize_required_description_rejects_invalid_text(
    description: str | None,
) -> None:
    with pytest.raises(InvalidLifecycleError, match="description"):
        normalize_required_description(description)


def test_normalize_required_description_accepts_exactly_500_characters() -> None:
    description = "x" * 500

    assert normalize_required_description(description) == description


@pytest.mark.parametrize("description", [None, "", "   "])
def test_legacy_description_label_uses_explicit_fallback(
    description: str | None,
) -> None:
    assert legacy_description_label(description) == "Sin descripción"


def test_legacy_description_label_trims_existing_text() -> None:
    assert legacy_description_label("  Historical salary  ") == "Historical salary"


def test_reversal_description_is_unambiguous_for_legacy_null_description() -> None:
    assert reversal_description(None) == "Reversión de: Sin descripción"


def test_reversal_description_truncates_the_total_to_500_characters() -> None:
    description = reversal_description("x" * 500)

    assert description.startswith("Reversión de: ")
    assert len(description) == 500
