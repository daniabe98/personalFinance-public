"""Specific reconciliation invariant failures."""


class ReconciliationError(RuntimeError):
    """Base error for reconciliation use cases."""


class IneligibleAccountError(ReconciliationError):
    """The account cannot participate in reconciliation."""


class IneligibleEntryError(ReconciliationError):
    """The ledger entry cannot participate in the requested reconciliation."""


class DuplicateCompletedMembershipError(ReconciliationError):
    """An entry already belongs to a completed reconciliation."""


class NonZeroDifferenceError(ReconciliationError):
    """A reconciliation cannot complete while its difference is non-zero."""


__all__ = (
    "DuplicateCompletedMembershipError",
    "IneligibleAccountError",
    "IneligibleEntryError",
    "NonZeroDifferenceError",
    "ReconciliationError",
)
