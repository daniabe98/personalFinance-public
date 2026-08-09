"""Fail-closed action-specific audit metadata minimization."""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.audit.domain.event import AuditAction, AuditMetadata, AuditScalar


class AuditMetadataRejectedError(ValueError):
    """Metadata contained a disallowed key, type, or secret-like value."""


_ALLOWED_KEYS: dict[AuditAction, frozenset[str]] = {
    AuditAction.LOGIN: frozenset({"reason"}),
    AuditAction.LOGOUT: frozenset(),
    AuditAction.CREDENTIAL_RESET: frozenset(),
    AuditAction.POSTING: frozenset({"operation_kind"}),
    AuditAction.REVERSAL: frozenset({"operation_kind"}),
    AuditAction.RECONCILIATION: frozenset({"status"}),
    AuditAction.BACKUP: frozenset({"verification_status"}),
    AuditAction.RESTORE: frozenset({"verification_status"}),
}
_FORBIDDEN_KEY = re.compile(
    r"(password|passphrase|hash|token|cookie|csrf|secret|path|amount|entry|payload)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(bearer\s+[a-z0-9._~+/=-]+|__host-[^=\s]+=|password\s*=|cookie\s*=)",
    re.IGNORECASE,
)


def minimize_metadata(
    action: AuditAction, metadata: Mapping[str, object] | None = None
) -> AuditMetadata:
    if metadata is None:
        return ()
    allowed = _ALLOWED_KEYS[action]
    minimized: list[tuple[str, AuditScalar]] = []
    for key, value in metadata.items():
        if _FORBIDDEN_KEY.search(key) or key not in allowed:
            raise AuditMetadataRejectedError("audit metadata key is not allowlisted")
        if value is not None and (
            isinstance(value, (list, tuple, dict, set)) or not isinstance(value, (str, int, bool))
        ):
            raise AuditMetadataRejectedError("audit metadata must contain only scalars")
        if isinstance(value, str) and _SECRET_VALUE.search(value):
            raise AuditMetadataRejectedError("audit metadata contains secret-like material")
        minimized.append((key, value))
    return tuple(sorted(minimized))


__all__ = ("AuditMetadataRejectedError", "minimize_metadata")
