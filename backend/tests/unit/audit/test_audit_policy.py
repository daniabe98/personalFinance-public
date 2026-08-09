from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.audit.adapters.redaction import AuditMetadataRejectedError, minimize_metadata
from app.audit.domain.event import (
    AuditAction,
    AuditEventDraft,
    AuditResult,
    AuditScope,
)


def test_audit_draft_is_closed_utc_and_immutable() -> None:
    draft = AuditEventDraft(
        occurred_at=datetime(2026, 7, 23, 20, 0, tzinfo=UTC),
        action=AuditAction.POSTING,
        result=AuditResult.SUCCESS,
        scope=AuditScope.SPACE,
        space_id="space-1",
        actor_id="user-1",
        entity_type="transaction",
        entity_id="tx-1",
        correlation_id="request-1",
        metadata=minimize_metadata(AuditAction.POSTING, {"operation_kind": "INCOME"}),
    )

    assert draft.metadata == (("operation_kind", "INCOME"),)
    assert draft.space_id == "space-1"
    with pytest.raises((AttributeError, TypeError)):
        draft.__setattr__("correlation_id", "changed")


def test_actorless_authentication_failure_uses_system_scope() -> None:
    draft = AuditEventDraft(
        occurred_at=datetime(2026, 7, 23, 20, 0, tzinfo=UTC),
        action=AuditAction.LOGIN,
        result=AuditResult.FAILURE,
        scope=AuditScope.SYSTEM,
        space_id=None,
        actor_id=None,
        entity_type=None,
        entity_id=None,
        correlation_id="login-1",
    )

    assert draft.actor_id is None
    assert draft.space_id is None


@pytest.mark.parametrize(
    "occurred_at",
    [
        datetime(2026, 7, 23, 20, 0),
        datetime(2026, 7, 23, 21, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
)
def test_audit_requires_explicit_utc(occurred_at: datetime) -> None:
    with pytest.raises(ValueError, match="UTC"):
        AuditEventDraft(
            occurred_at=occurred_at,
            action=AuditAction.BACKUP,
            result=AuditResult.SUCCESS,
            scope=AuditScope.SYSTEM,
            space_id=None,
            actor_id=None,
            entity_type="backup",
            entity_id="backup-1",
            correlation_id="backup-1",
        )


@pytest.mark.parametrize(
    "action,metadata",
    [
        (AuditAction.LOGIN, {"username": "owner"}),
        (AuditAction.LOGIN, {"password": "secret"}),
        (AuditAction.POSTING, {"amount_cents": 100}),
        (AuditAction.POSTING, {"entries": "payload"}),
        (AuditAction.BACKUP, {"path": "/private/backup.sqlite3"}),
        (AuditAction.LOGIN, {"reason": "Bearer abcdefghijklmnopqrstuvwxyz"}),
        (AuditAction.LOGIN, {"cookie": "__Host-session=secret"}),
        (AuditAction.LOGIN, {"csrf_token": "secret"}),
        (AuditAction.LOGIN, {"password_hash": "hash"}),
    ],
)
def test_redaction_rejects_secret_and_financial_payloads(
    action: AuditAction, metadata: dict[str, object]
) -> None:
    with pytest.raises(AuditMetadataRejectedError):
        minimize_metadata(action, metadata)


@pytest.mark.parametrize(
    "action,metadata",
    [
        (AuditAction.LOGIN, {"reason": "invalid_credentials"}),
        (AuditAction.POSTING, {"operation_kind": "EXPENSE"}),
        (AuditAction.REVERSAL, {"operation_kind": "REVERSAL"}),
        (AuditAction.RECONCILIATION, {"status": "COMPLETED"}),
        (AuditAction.BACKUP, {"verification_status": "VALID"}),
        (AuditAction.RESTORE, {"verification_status": "VALID"}),
    ],
)
def test_redaction_accepts_only_action_specific_scalars(
    action: AuditAction, metadata: dict[str, object]
) -> None:
    assert minimize_metadata(action, metadata)
