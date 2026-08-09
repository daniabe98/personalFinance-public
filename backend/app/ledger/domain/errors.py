"""Typed failures raised by the ledger domain and application boundary."""

from __future__ import annotations


class LedgerError(Exception):
    """Base class for expected ledger failures."""


class InvalidAmountError(LedgerError, ValueError):
    """Money was not expressed as exact EUR integer cents."""


class CurrencyMismatchError(LedgerError, ValueError):
    """Money values from different currencies were combined."""


class UnbalancedTransactionError(LedgerError, ValueError):
    """A posting did not contain at least two exactly balanced entries."""


class InvalidLifecycleError(LedgerError, ValueError):
    """A transaction lifecycle transition is not allowed."""


class OwnershipError(LedgerError, PermissionError):
    """An entity does not belong to the requested financial space."""


class ArchivedEntityError(LedgerError, ValueError):
    """An archived catalog entity was selected for a new operation."""


class EntityNotFoundError(LedgerError, LookupError):
    """A requested ledger entity does not exist in the financial space."""


class DuplicateNameError(LedgerError, ValueError):
    """A catalog name is already in use in the financial space."""


class ImmutableLedgerError(LedgerError):
    """Posted history was targeted by a forbidden mutation."""


__all__ = (
    "ArchivedEntityError",
    "CurrencyMismatchError",
    "DuplicateNameError",
    "EntityNotFoundError",
    "ImmutableLedgerError",
    "InvalidAmountError",
    "InvalidLifecycleError",
    "LedgerError",
    "OwnershipError",
    "UnbalancedTransactionError",
)
