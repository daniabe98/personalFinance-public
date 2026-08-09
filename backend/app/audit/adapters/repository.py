"""SQLAlchemy append-only audit repository."""

from __future__ import annotations

import json
from datetime import UTC

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.audit.domain.event import (
    AuditAction,
    AuditEvent,
    AuditMetadata,
    AuditResult,
    AuditScope,
)
from app.audit.ports.repository import AuditCursor, AuditSlice
from app.shared.models_control import AuditEventRecord


class AuditStoreError(RuntimeError):
    """Audit persistence returned malformed or unavailable data."""


class SqlAlchemyAuditRepository:
    """Append and page audit events without committing independently."""

    def __init__(self, session: object) -> None:
        if not isinstance(session, Session):
            raise TypeError("audit repository requires an active SQLAlchemy session")
        self._session = session

    def append(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventRecord(
                id=event.id,
                space_id=event.space_id,
                occurred_at=event.occurred_at,
                action=event.action.value,
                outcome=event.result.value,
                actor_id=event.actor_id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                correlation_id=event.correlation_id,
                details_json=self._encode_metadata(event.metadata),
            )
        )
        self._session.flush()

    def page_space(
        self,
        space_id: str,
        *,
        limit: int,
        cursor: AuditCursor | None,
    ) -> AuditSlice:
        statement = select(AuditEventRecord).where(AuditEventRecord.space_id == space_id)
        return self._page(statement, limit=limit, cursor=cursor)

    def page_system(
        self,
        *,
        limit: int,
        cursor: AuditCursor | None,
    ) -> AuditSlice:
        statement = select(AuditEventRecord).where(AuditEventRecord.space_id.is_(None))
        return self._page(statement, limit=limit, cursor=cursor)

    def _page(self, statement, *, limit: int, cursor: AuditCursor | None) -> AuditSlice:
        if cursor is not None:
            statement = statement.where(
                or_(
                    AuditEventRecord.occurred_at < cursor.occurred_at,
                    and_(
                        AuditEventRecord.occurred_at == cursor.occurred_at,
                        AuditEventRecord.id < cursor.event_id,
                    ),
                )
            )
        records = tuple(
            self._session.scalars(
                statement.order_by(
                    AuditEventRecord.occurred_at.desc(),
                    AuditEventRecord.id.desc(),
                ).limit(limit + 1)
            )
        )
        return AuditSlice(
            events=tuple(self._event(record) for record in records[:limit]),
            has_more=len(records) > limit,
        )

    @staticmethod
    def _event(record: AuditEventRecord) -> AuditEvent:
        occurred_at = record.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        else:
            occurred_at = occurred_at.astimezone(UTC)
        return AuditEvent(
            id=record.id,
            occurred_at=occurred_at,
            action=AuditAction(record.action),
            result=AuditResult(record.outcome),
            scope=AuditScope.SPACE if record.space_id is not None else AuditScope.SYSTEM,
            space_id=record.space_id,
            actor_id=record.actor_id,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            correlation_id=record.correlation_id,
            metadata=SqlAlchemyAuditRepository._decode_metadata(record.details_json),
        )

    @staticmethod
    def _encode_metadata(metadata: AuditMetadata) -> str | None:
        if not metadata:
            return None
        return json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _decode_metadata(details_json: str | None) -> AuditMetadata:
        if details_json is None:
            return ()
        try:
            decoded = json.loads(details_json)
        except json.JSONDecodeError as error:
            raise AuditStoreError("stored audit metadata is not valid JSON") from error
        if not isinstance(decoded, dict):
            raise AuditStoreError("stored audit metadata is not an object")
        metadata: list[tuple[str, str | int | bool | None]] = []
        for key, value in decoded.items():
            if not isinstance(key, str) or (
                value is not None and not isinstance(value, (str, int, bool))
            ):
                raise AuditStoreError("stored audit metadata is not scalar")
            metadata.append((key, value))
        return tuple(sorted(metadata))


__all__ = ("AuditStoreError", "SqlAlchemyAuditRepository")
