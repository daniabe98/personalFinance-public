"""Authenticated, minimized audit event query."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.dependencies import require_authenticated_principal
from app.audit.application.service import AuditPage
from app.audit.ports.repository import AuditCursor
from app.identity.application.service import AuthenticatedPrincipal

router = APIRouter(tags=["audit"])
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


class AuditPort(Protocol):
    def for_space(
        self, space_id: str, *, limit: int, cursor: AuditCursor | None = None
    ) -> AuditPage: ...


class AuditEventResponse(BaseModel):
    id: str
    occurred_at: datetime
    action: str
    result: str
    actor_id: str | None
    entity_type: str | None
    entity_id: str | None
    correlation_id: str
    metadata: dict[str, str | int | bool | None]


class AuditPageResponse(BaseModel):
    events: tuple[AuditEventResponse, ...]
    next_cursor: str | None


def _service(request: Request) -> AuditPort:
    value = getattr(request.app.state, "audit_query_service", None)
    if value is None:
        raise RuntimeError("audit query service is not configured")
    return cast(AuditPort, value)


def _decode_cursor(value: str | None) -> AuditCursor | None:
    if value is None:
        return None
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        timestamp, event_id = decoded.split("|", 1)
        return AuditCursor(datetime.fromisoformat(timestamp), event_id)
    except (ValueError, UnicodeError) as error:
        raise ValueError("invalid audit cursor") from error


def _encode_cursor(value: AuditCursor | None) -> str | None:
    if value is None:
        return None
    raw = f"{value.occurred_at.isoformat()}|{value.event_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


@router.get("/audit/events", response_model=AuditPageResponse)
def audit_events(
    request: Request,
    principal: Principal,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: str | None = None,
) -> AuditPageResponse:
    page = _service(request).for_space(
        principal.space_id, limit=limit, cursor=_decode_cursor(cursor)
    )
    return AuditPageResponse(
        events=tuple(
            AuditEventResponse(
                id=event.id,
                occurred_at=event.occurred_at,
                action=str(event.action),
                result=str(event.result),
                actor_id=event.actor_id,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                correlation_id=event.correlation_id,
                metadata=dict(event.metadata),
            )
            for event in page.events
        ),
        next_cursor=_encode_cursor(page.next_cursor),
    )


__all__ = ("router",)
