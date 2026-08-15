"""Canonical descriptions for new writes and nullable historical records."""

from __future__ import annotations

from app.ledger.domain.errors import InvalidLifecycleError

_MAX_DESCRIPTION_LENGTH = 500
_LEGACY_DESCRIPTION_FALLBACK = "Sin descripción"
_REVERSAL_PREFIX = "Reversión de: "


def normalize_required_description(description: str | None) -> str:
    """Return trimmed write text or fail when no bounded description exists."""
    if not isinstance(description, str):
        raise InvalidLifecycleError("description is required")
    normalized = description.strip()
    if not normalized:
        raise InvalidLifecycleError("description cannot be blank")
    if len(normalized) > _MAX_DESCRIPTION_LENGTH:
        raise InvalidLifecycleError("description cannot exceed 500 characters")
    return normalized


def legacy_description_label(description: str | None) -> str:
    """Expose nullable or blank historical text without inventing financial meaning."""
    if not isinstance(description, str):
        return _LEGACY_DESCRIPTION_FALLBACK
    normalized = description.strip()
    return normalized or _LEGACY_DESCRIPTION_FALLBACK


def reversal_description(original_description: str | None) -> str:
    """Derive an unambiguous bounded description from the original event."""
    label = legacy_description_label(original_description)
    return f"{_REVERSAL_PREFIX}{label}"[:_MAX_DESCRIPTION_LENGTH]


__all__ = (
    "legacy_description_label",
    "normalize_required_description",
    "reversal_description",
)
