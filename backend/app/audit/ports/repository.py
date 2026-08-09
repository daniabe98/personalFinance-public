"""Append-only audit persistence contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.audit.domain.event import AuditEvent


@dataclass(frozen=True, slots=True)
class AuditCursor:
    occurred_at: datetime
    event_id: str


@dataclass(frozen=True, slots=True)
class AuditSlice:
    events: tuple[AuditEvent, ...]
    has_more: bool


class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> None: ...

    def page_space(
        self,
        space_id: str,
        *,
        limit: int,
        cursor: AuditCursor | None,
    ) -> AuditSlice: ...

    def page_system(
        self,
        *,
        limit: int,
        cursor: AuditCursor | None,
    ) -> AuditSlice: ...


AuditRepositoryFactory = Callable[[object], AuditRepository]


__all__ = (
    "AuditCursor",
    "AuditRepository",
    "AuditRepositoryFactory",
    "AuditSlice",
)
