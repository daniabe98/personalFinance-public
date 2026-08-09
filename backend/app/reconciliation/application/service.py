"""Atomic reconciliation orchestration over core-owned ports."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from app.ledger.application.state_projection import project_transaction_state
from app.ledger.domain.transaction import TransactionStatus
from app.reconciliation.domain.errors import IneligibleEntryError
from app.reconciliation.domain.reconciliation import (
    Reconciliation,
    ReconciliationCandidate,
    ReconciliationSelection,
    ReconciliationStatus,
)
from app.reconciliation.ports.repository import (
    ReconciliationAuditWriter,
    ReconciliationRepository,
    RepositoryFactory,
)
from app.shared.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    reconciliation_id: str
    status: ReconciliationStatus
    account_id: str
    cutoff_date: date
    observed_balance_cents: int
    prior_completed_cents: int
    selected_effect_cents: int
    checked_balance_cents: int
    difference_cents: int
    selected_entry_ids: tuple[str, ...]
    transaction_states: tuple[tuple[str, TransactionStatus], ...] = ()


class ReconciliationService:
    """Recalculate, persist and audit one exact account reconciliation."""

    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: RepositoryFactory,
        audit_writer: ReconciliationAuditWriter,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._audit_writer = audit_writer
        self._clock = clock

    def list_candidates(
        self,
        space_id: str,
        account_id: str,
        cutoff_date: date,
    ) -> tuple[ReconciliationCandidate, ...]:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            return tuple(repository.list_candidates(space_id, account_id, cutoff_date))

    def preview(
        self,
        *,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        entry_ids: Sequence[str],
    ) -> ReconciliationResult:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            reconciliation = self._draft(
                repository,
                reconciliation_id=uuid4().hex,
                space_id=space_id,
                account_id=account_id,
                cutoff_date=cutoff_date,
                observed_balance_cents=observed_balance_cents,
                entry_ids=entry_ids,
            )
            return self._result(reconciliation)

    def complete(
        self,
        *,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        entry_ids: Sequence[str],
        correlation_id: str,
    ) -> ReconciliationResult:
        reconciliation_id = uuid4().hex
        try:
            with self._unit_of_work_factory() as unit_of_work:
                repository = self._repository_factory(unit_of_work.session)
                reconciliation = self._draft(
                    repository,
                    reconciliation_id=reconciliation_id,
                    space_id=space_id,
                    account_id=account_id,
                    cutoff_date=cutoff_date,
                    observed_balance_cents=observed_balance_cents,
                    entry_ids=entry_ids,
                ).complete()
                completed_at = self._utc_now()
                repository.add_completed(reconciliation, completed_at)
                states = self._project_affected_transactions(
                    repository,
                    reconciliation.space_id,
                    reconciliation.selection.entry_ids,
                )
                self._audit_writer.record(
                    unit_of_work.session,
                    action="complete_reconciliation",
                    outcome="SUCCESS",
                    space_id=space_id,
                    reconciliation_id=reconciliation.id,
                    correlation_id=correlation_id,
                )
                unit_of_work.commit()
                return self._result(reconciliation, transaction_states=states)
        except Exception:
            self._record_failure(
                space_id=space_id,
                correlation_id=correlation_id,
            )
            raise

    def _draft(
        self,
        repository: ReconciliationRepository,
        *,
        reconciliation_id: str,
        space_id: str,
        account_id: str,
        cutoff_date: date,
        observed_balance_cents: int,
        entry_ids: Sequence[str],
    ) -> Reconciliation:
        candidates = tuple(repository.list_candidates(space_id, account_id, cutoff_date))
        candidate_ids = {candidate.entry_id for candidate in candidates}
        selected_ids = tuple(entry_ids)
        if any(entry_id not in candidate_ids for entry_id in selected_ids):
            raise IneligibleEntryError("selected entry is not an eligible candidate")
        return Reconciliation.draft(
            reconciliation_id=reconciliation_id,
            space_id=space_id,
            account_id=account_id,
            cutoff_date=cutoff_date,
            observed_balance_cents=observed_balance_cents,
            prior_completed_cents=repository.prior_completed_cents(
                space_id,
                account_id,
                cutoff_date,
            ),
            candidates=candidates,
            selection=ReconciliationSelection(selected_ids),
        )

    def _project_affected_transactions(
        self,
        repository: ReconciliationRepository,
        space_id: str,
        entry_ids: Sequence[str],
    ) -> tuple[tuple[str, TransactionStatus], ...]:
        accounts = tuple(repository.reconcilable_accounts(space_id))
        projected: list[tuple[str, TransactionStatus]] = []
        for transaction in repository.transactions_for_entries(space_id, entry_ids):
            state = project_transaction_state(
                transaction,
                accounts,
                repository.completed_entry_ids(space_id, transaction.id),
            )
            repository.set_transaction_state(space_id, transaction.id, state)
            projected.append((transaction.id, state))
        return tuple(projected)

    def _record_failure(self, *, space_id: str, correlation_id: str) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            self._audit_writer.record(
                unit_of_work.session,
                action="complete_reconciliation",
                outcome="FAILURE",
                space_id=space_id,
                reconciliation_id=None,
                correlation_id=correlation_id,
            )
            unit_of_work.commit()

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _result(
        reconciliation: Reconciliation,
        *,
        transaction_states: tuple[tuple[str, TransactionStatus], ...] = (),
    ) -> ReconciliationResult:
        return ReconciliationResult(
            reconciliation_id=reconciliation.id,
            status=reconciliation.status,
            account_id=reconciliation.account_id,
            cutoff_date=reconciliation.cutoff_date,
            observed_balance_cents=reconciliation.observed_balance_cents,
            prior_completed_cents=reconciliation.prior_completed_cents,
            selected_effect_cents=reconciliation.selected_effect_cents,
            checked_balance_cents=reconciliation.checked_balance_cents,
            difference_cents=reconciliation.difference_cents,
            selected_entry_ids=reconciliation.selection.entry_ids,
            transaction_states=transaction_states,
        )


__all__ = ("ReconciliationResult", "ReconciliationService")
