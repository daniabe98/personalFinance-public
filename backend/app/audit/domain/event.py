"""Immutable, minimized audit event values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

AuditScalar = str | int | bool | None
AuditMetadata = tuple[tuple[str, AuditScalar], ...]


class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CREDENTIAL_RESET = "CREDENTIAL_RESET"
    POSTING = "POSTING"
    REVERSAL = "REVERSAL"
    RECONCILIATION = "RECONCILIATION"
    BACKUP = "BACKUP"
    RESTORE = "RESTORE"


class AuditResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class AuditScope(StrEnum):
    SPACE = "SPACE"
    SYSTEM = "SYSTEM"


def _required_identifier(value: str, name: str, *, maximum: int = 120) -> str:
    if not value or value != value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty opaque identifier")
    return value


def _optional_identifier(value: str | None, name: str, *, maximum: int = 120) -> str | None:
    return None if value is None else _required_identifier(value, name, maximum=maximum)


@dataclass(frozen=True, slots=True)
class AuditEventDraft:
    occurred_at: datetime
    action: AuditAction
    result: AuditResult
    scope: AuditScope
    space_id: str | None
    actor_id: str | None
    entity_type: str | None
    entity_id: str | None
    correlation_id: str
    metadata: AuditMetadata = ()

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is not UTC:
            raise ValueError("audit timestamps must use UTC")
        _required_identifier(self.correlation_id, "correlation_id")
        _optional_identifier(self.space_id, "space_id")
        _optional_identifier(self.actor_id, "actor_id")
        _optional_identifier(self.entity_type, "entity_type")
        _optional_identifier(self.entity_id, "entity_id")
        if self.scope is AuditScope.SPACE and self.space_id is None:
            raise ValueError("space-scoped audit events require a space")
        if self.scope is AuditScope.SYSTEM and self.space_id is not None:
            raise ValueError("system-scoped audit events cannot carry a space")
        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("entity type and identifier must be supplied together")
        if tuple(sorted(self.metadata)) != self.metadata:
            raise ValueError("audit metadata must be deterministic and sorted")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    occurred_at: datetime
    action: AuditAction
    result: AuditResult
    scope: AuditScope
    space_id: str | None
    actor_id: str | None
    entity_type: str | None
    entity_id: str | None
    correlation_id: str
    metadata: AuditMetadata = ()

    def __post_init__(self) -> None:
        _required_identifier(self.id, "id")
        AuditEventDraft(
            occurred_at=self.occurred_at,
            action=self.action,
            result=self.result,
            scope=self.scope,
            space_id=self.space_id,
            actor_id=self.actor_id,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            correlation_id=self.correlation_id,
            metadata=self.metadata,
        )

    @classmethod
    def from_draft(cls, event_id: str, draft: AuditEventDraft) -> AuditEvent:
        return cls(
            id=event_id,
            occurred_at=draft.occurred_at,
            action=draft.action,
            result=draft.result,
            scope=draft.scope,
            space_id=draft.space_id,
            actor_id=draft.actor_id,
            entity_type=draft.entity_type,
            entity_id=draft.entity_id,
            correlation_id=draft.correlation_id,
            metadata=draft.metadata,
        )


__all__ = (
    "AuditAction",
    "AuditEvent",
    "AuditEventDraft",
    "AuditMetadata",
    "AuditResult",
    "AuditScalar",
    "AuditScope",
)
