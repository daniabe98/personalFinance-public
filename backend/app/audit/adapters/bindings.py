"""Narrow bindings from producer-owned audit ports to durable audit."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from app.audit.adapters.redaction import minimize_metadata
from app.audit.application.service import DurableAuditService
from app.audit.domain.event import (
    AuditAction,
    AuditEvent,
    AuditEventDraft,
    AuditResult,
    AuditScope,
)

Clock = Callable[[], datetime]

_LEDGER_ACTIONS: dict[str, tuple[AuditAction, str]] = {
    "create_opening": (AuditAction.POSTING, "OPENING"),
    "create_income": (AuditAction.POSTING, "INCOME"),
    "create_expense": (AuditAction.POSTING, "EXPENSE"),
    "create_transfer": (AuditAction.POSTING, "TRANSFER"),
    "post_draft": (AuditAction.POSTING, "DRAFT"),
    "reverse_transaction": (AuditAction.REVERSAL, "REVERSAL"),
}


class AuthenticationAuditBinding:
    """Structurally satisfy identity's AuthenticationAuditSink."""

    def __init__(self, service: DurableAuditService, *, clock: Clock) -> None:
        self._service = service
        self._clock = clock

    def record_authentication(
        self,
        *,
        action: str,
        result: str,
        actor_id: str | None,
        space_id: str | None,
        correlation_id: str,
    ) -> None:
        audit_action = AuditAction(action)
        audit_result = AuditResult(result)
        metadata = (
            minimize_metadata(audit_action, {"reason": "invalid_credentials"})
            if audit_action is AuditAction.LOGIN and audit_result is AuditResult.FAILURE
            else ()
        )
        self._service.append_durable(
            AuditEventDraft(
                occurred_at=self._clock(),
                action=audit_action,
                result=audit_result,
                scope=AuditScope.SPACE if space_id is not None else AuditScope.SYSTEM,
                space_id=space_id,
                actor_id=actor_id,
                entity_type=None,
                entity_id=None,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )


class LedgerAuditBinding:
    """Structurally satisfy ledger's FinancialAuditSink."""

    def __init__(self, service: DurableAuditService, *, clock: Clock) -> None:
        self._service = service
        self._clock = clock

    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        transaction_id: str | None,
        correlation_id: str,
    ) -> None:
        try:
            audit_action, operation_kind = _LEDGER_ACTIONS[action]
        except KeyError as error:
            raise ValueError("unsupported ledger audit action") from error
        self._service.append_in_transaction(
            session,
            AuditEventDraft(
                occurred_at=self._clock(),
                action=audit_action,
                result=AuditResult(outcome),
                scope=AuditScope.SPACE,
                space_id=space_id,
                actor_id=None,
                entity_type="transaction" if transaction_id is not None else None,
                entity_id=transaction_id,
                correlation_id=correlation_id,
                metadata=minimize_metadata(audit_action, {"operation_kind": operation_kind}),
            ),
        )


class OutcomeAuditBinding:
    """Generic narrow seam for reconciliation/recovery producers."""

    def __init__(self, service: DurableAuditService, *, clock: Clock) -> None:
        self._service = service
        self._clock = clock

    def record(
        self,
        session: object,
        *,
        action: AuditAction,
        result: AuditResult,
        space_id: str | None,
        actor_id: str | None,
        entity_type: str | None,
        entity_id: str | None,
        correlation_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> AuditEvent:
        return self._service.append_in_transaction(
            session,
            self._draft(
                action=action,
                result=result,
                space_id=space_id,
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                metadata=metadata,
            ),
        )

    def record_durable(
        self,
        *,
        action: AuditAction,
        result: AuditResult,
        space_id: str | None,
        actor_id: str | None,
        entity_type: str | None,
        entity_id: str | None,
        correlation_id: str,
        metadata: Mapping[str, object] | None = None,
    ) -> AuditEvent:
        return self._service.append_durable(
            self._draft(
                action=action,
                result=result,
                space_id=space_id,
                actor_id=actor_id,
                entity_type=entity_type,
                entity_id=entity_id,
                correlation_id=correlation_id,
                metadata=metadata,
            )
        )

    def _draft(
        self,
        *,
        action: AuditAction,
        result: AuditResult,
        space_id: str | None,
        actor_id: str | None,
        entity_type: str | None,
        entity_id: str | None,
        correlation_id: str,
        metadata: Mapping[str, object] | None,
    ) -> AuditEventDraft:
        return AuditEventDraft(
            occurred_at=self._clock(),
            action=action,
            result=result,
            scope=AuditScope.SPACE if space_id is not None else AuditScope.SYSTEM,
            space_id=space_id,
            actor_id=actor_id,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=correlation_id,
            metadata=minimize_metadata(action, metadata),
        )


__all__ = (
    "AuthenticationAuditBinding",
    "LedgerAuditBinding",
    "OutcomeAuditBinding",
)
