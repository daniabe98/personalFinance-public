"""Durable append and authorized audit query services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.audit.domain.event import AuditEvent, AuditEventDraft
from app.audit.ports.repository import (
    AuditCursor,
    AuditRepositoryFactory,
)
from app.shared.unit_of_work import UnitOfWorkFactory


class AuthenticationAuditSink(Protocol):
    def record_authentication(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AuditPage:
    events: tuple[AuditEvent, ...]
    next_cursor: AuditCursor | None


class DurableAuditService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: AuditRepositoryFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory

    def append_in_transaction(self, session: object, draft: AuditEventDraft) -> AuditEvent:
        event = AuditEvent.from_draft(uuid4().hex, draft)
        self._repository_factory(session).append(event)
        return event

    def append_durable(self, draft: AuditEventDraft) -> AuditEvent:
        with self._unit_of_work_factory() as unit_of_work:
            event = self.append_in_transaction(unit_of_work.session, draft)
            unit_of_work.commit()
        return event


class AuditQueryService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: AuditRepositoryFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory

    def for_space(
        self,
        space_id: str,
        *,
        limit: int,
        cursor: AuditCursor | None = None,
    ) -> AuditPage:
        if not space_id:
            raise ValueError("space_id is required")
        self._validate_limit(limit)
        with self._unit_of_work_factory() as unit_of_work:
            page = self._repository_factory(unit_of_work.session).page_space(
                space_id, limit=limit, cursor=cursor
            )
        return self._page(page.events, page.has_more)

    def system(
        self,
        *,
        limit: int,
        cursor: AuditCursor | None = None,
    ) -> AuditPage:
        self._validate_limit(limit)
        with self._unit_of_work_factory() as unit_of_work:
            page = self._repository_factory(unit_of_work.session).page_system(
                limit=limit, cursor=cursor
            )
        return self._page(page.events, page.has_more)

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit < 1 or limit > 200:
            raise ValueError("audit page limit must be between 1 and 200")

    @staticmethod
    def _page(events: tuple[AuditEvent, ...], has_more: bool) -> AuditPage:
        next_cursor = None
        if has_more and events:
            last = events[-1]
            next_cursor = AuditCursor(last.occurred_at, last.id)
        return AuditPage(events, next_cursor)


__all__ = (
    "AuditPage",
    "AuditQueryService",
    "AuthenticationAuditSink",
    "DurableAuditService",
)
