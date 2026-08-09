from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.audit.adapters.bindings import (
    AuthenticationAuditBinding,
    LedgerAuditBinding,
    OutcomeAuditBinding,
)
from app.audit.adapters.repository import SqlAlchemyAuditRepository
from app.audit.application.service import AuditQueryService, DurableAuditService
from app.audit.domain.event import (
    AuditAction,
    AuditEventDraft,
    AuditResult,
    AuditScope,
)
from app.shared import models_ledger
from tests.support.ledger import OTHER_SPACE_ID, SPACE_ID

del models_ledger


def _draft(
    *,
    action: AuditAction = AuditAction.POSTING,
    result: AuditResult = AuditResult.SUCCESS,
    space_id: str | None = SPACE_ID,
    correlation_id: str = "request-1",
    occurred_at: datetime | None = None,
) -> AuditEventDraft:
    return AuditEventDraft(
        occurred_at=occurred_at or datetime(2026, 7, 23, 20, 0, tzinfo=UTC),
        action=action,
        result=result,
        scope=AuditScope.SPACE if space_id is not None else AuditScope.SYSTEM,
        space_id=space_id,
        actor_id="user-1" if space_id is not None else None,
        entity_type="transaction" if space_id is not None else None,
        entity_id="tx-1" if space_id is not None else None,
        correlation_id=correlation_id,
    )


def test_success_audit_joins_caller_transaction_and_failure_is_fresh(
    ledger_uow_factory,
) -> None:
    uow_factory = ledger_uow_factory
    service = DurableAuditService(uow_factory, SqlAlchemyAuditRepository)
    queries = AuditQueryService(uow_factory, SqlAlchemyAuditRepository)

    with uow_factory() as unit_of_work:
        service.append_in_transaction(unit_of_work.session, _draft(correlation_id="rolled-back"))
    assert queries.for_space(SPACE_ID, limit=10).events == ()

    with uow_factory() as unit_of_work:
        committed = service.append_in_transaction(
            unit_of_work.session, _draft(correlation_id="committed")
        )
        unit_of_work.commit()
    failure = service.append_durable(
        _draft(
            result=AuditResult.FAILURE,
            correlation_id="failure",
            occurred_at=datetime(2026, 7, 23, 20, 1, tzinfo=UTC),
        )
    )

    page = queries.for_space(SPACE_ID, limit=10)
    assert {event.id for event in page.events} == {committed.id, failure.id}
    assert [event.correlation_id for event in page.events] == ["failure", "committed"]


def test_scope_pagination_is_default_deny_and_deterministic(ledger_uow_factory) -> None:
    uow_factory = ledger_uow_factory
    service = DurableAuditService(uow_factory, SqlAlchemyAuditRepository)
    queries = AuditQueryService(uow_factory, SqlAlchemyAuditRepository)
    base = datetime(2026, 7, 23, 20, 0, tzinfo=UTC)
    for index in range(3):
        service.append_durable(
            _draft(correlation_id=f"space-{index}", occurred_at=base + timedelta(seconds=index))
        )
    service.append_durable(_draft(space_id=OTHER_SPACE_ID, correlation_id="other-space"))
    service.append_durable(
        _draft(
            action=AuditAction.LOGIN,
            result=AuditResult.FAILURE,
            space_id=None,
            correlation_id="system",
        )
    )

    first = queries.for_space(SPACE_ID, limit=2)
    second = queries.for_space(SPACE_ID, limit=2, cursor=first.next_cursor)

    assert [event.correlation_id for event in first.events] == ["space-2", "space-1"]
    assert [event.correlation_id for event in second.events] == ["space-0"]
    assert [event.correlation_id for event in queries.system(limit=10).events] == ["system"]
    assert not hasattr(SqlAlchemyAuditRepository, "update")
    assert not hasattr(SqlAlchemyAuditRepository, "delete")


def test_bindings_route_identity_ledger_and_generic_producer_shapes(
    ledger_uow_factory,
) -> None:
    uow_factory = ledger_uow_factory
    service = DurableAuditService(uow_factory, SqlAlchemyAuditRepository)
    queries = AuditQueryService(uow_factory, SqlAlchemyAuditRepository)

    def clock() -> datetime:
        return datetime(2026, 7, 23, 20, 0, tzinfo=UTC)

    authentication = AuthenticationAuditBinding(service, clock=clock)
    ledger = LedgerAuditBinding(service, clock=clock)
    outcome = OutcomeAuditBinding(service, clock=clock)

    authentication.record_authentication(
        action="LOGIN",
        result="FAILURE",
        actor_id=None,
        space_id=None,
        correlation_id="login-failure",
    )
    with uow_factory() as unit_of_work:
        ledger.record(
            unit_of_work.session,
            action="create_income",
            outcome="SUCCESS",
            space_id=SPACE_ID,
            transaction_id="tx-1",
            correlation_id="posting",
        )
        outcome.record(
            unit_of_work.session,
            action=AuditAction.RECONCILIATION,
            result=AuditResult.SUCCESS,
            space_id=SPACE_ID,
            actor_id="user-1",
            entity_type="reconciliation",
            entity_id="reconciliation-1",
            correlation_id="reconciliation",
            metadata={"status": "COMPLETED"},
        )
        unit_of_work.commit()

    assert {event.action for event in queries.for_space(SPACE_ID, limit=10).events} == {
        AuditAction.RECONCILIATION,
        AuditAction.POSTING,
    }
    assert queries.system(limit=10).events[0].correlation_id == "login-failure"


@pytest.mark.parametrize(
    "action",
    [AuditAction.BACKUP, AuditAction.RESTORE, AuditAction.REVERSAL],
)
def test_generic_binding_covers_remaining_producer_families(
    ledger_uow_factory,
    action: AuditAction,
) -> None:
    uow_factory = ledger_uow_factory
    service = DurableAuditService(uow_factory, SqlAlchemyAuditRepository)
    binding = OutcomeAuditBinding(service, clock=lambda: datetime(2026, 7, 23, 20, 0, tzinfo=UTC))
    with uow_factory() as unit_of_work:
        binding.record(
            unit_of_work.session,
            action=action,
            result=AuditResult.FAILURE,
            space_id=SPACE_ID,
            actor_id="user-1",
            entity_type=action.value.lower(),
            entity_id="entity-1",
            correlation_id=f"{action.value.lower()}-1",
            metadata={},
        )
        unit_of_work.commit()
