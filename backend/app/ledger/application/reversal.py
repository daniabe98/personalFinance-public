"""Period-correct reversal as a new immutable financial event."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from uuid import uuid4

from app.ledger.application.commands import CommandResult, ReverseCommand
from app.ledger.domain.description import (
    normalize_required_description,
    reversal_description,
)
from app.ledger.domain.errors import InvalidLifecycleError
from app.ledger.domain.posting_recipes import reversal_entries
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.ledger.ports.audit import FinancialAuditSink
from app.ledger.ports.repositories import (
    DraftDetails,
    LedgerReadRepository,
    RepositoryFactory,
)
from app.shared.idempotency import IdempotencyStore
from app.shared.unit_of_work import UnitOfWorkFactory


class ReversalService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: RepositoryFactory,
        audit_sink: FinancialAuditSink,
        *,
        today: Callable[[], date],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._audit_sink = audit_sink
        self._today = today

    def reverse(self, command: ReverseCommand) -> CommandResult:
        if command.replacement is not None:
            command = replace(
                command,
                replacement=replace(
                    command.replacement,
                    description=normalize_required_description(command.replacement.description),
                ),
            )
        payload = self._payload(command)
        try:
            with self._unit_of_work_factory() as unit_of_work:
                store = IdempotencyStore(unit_of_work.session)
                reservation = store.reserve(
                    space_id=command.space_id,
                    command_name="reverse_transaction",
                    idempotency_key=command.idempotency_key,
                    payload=payload,
                )
                if reservation.is_replay:
                    return self._replay(reservation.result)
                repository = self._repository_factory(unit_of_work.session)
                original = repository.get_transaction(
                    command.space_id, command.original_transaction_id
                )
                if original.status not in (
                    TransactionStatus.POSTED,
                    TransactionStatus.RECONCILED,
                ):
                    raise InvalidLifecycleError("only posted or reconciled history can be reversed")
                reversal_date = command.economic_date or self._today()
                reversal_cash_date = (
                    None if original.cash_date is None else command.cash_date or self._today()
                )
                reversal = Transaction.posted(
                    uuid4().hex,
                    command.space_id,
                    TransactionKind.REVERSAL,
                    reversal_date,
                    reversal_cash_date,
                    reversal_description(original.description),
                    reversal_entries(uuid4().hex, original.entries),
                )
                repository.add_posted(reversal)
                repository.mark_voided(command.space_id, original.id)
                repository.add_reversal_link(
                    space_id=command.space_id,
                    original_transaction_id=original.id,
                    reversal_transaction_id=reversal.id,
                )
                replacement_id = self._add_replacement(command, repository)
                result = CommandResult(
                    reversal.id,
                    reversal.status.value,
                    replacement_transaction_id=replacement_id,
                )
                store.complete(reservation, result.as_json())
                self._audit_sink.record(
                    unit_of_work.session,
                    action="reverse_transaction",
                    outcome="SUCCESS",
                    space_id=command.space_id,
                    transaction_id=reversal.id,
                    correlation_id=command.idempotency_key,
                )
                unit_of_work.commit()
                return result
        except Exception:
            self._record_failure(command)
            raise

    @staticmethod
    def _add_replacement(command: ReverseCommand, repository: LedgerReadRepository) -> str | None:
        replacement = command.replacement
        if replacement is None:
            return None
        if replacement.space_id != command.space_id:
            raise InvalidLifecycleError("replacement must belong to the same space")
        if replacement.amount_cents <= 0 or isinstance(replacement.amount_cents, bool):
            raise InvalidLifecycleError("replacement amount must be positive integer cents")
        draft = Transaction.draft(
            uuid4().hex,
            replacement.space_id,
            replacement.kind,
            replacement.economic_date,
            replacement.description,
        )
        repository.add_draft(
            draft,
            DraftDetails(
                replacement.amount_cents,
                replacement.account_id,
                replacement.category_id,
                replacement.destination_account_id,
                replacement.cash_date,
                command.original_transaction_id,
            ),
        )
        return draft.id

    def _record_failure(self, command: ReverseCommand) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            self._audit_sink.record(
                unit_of_work.session,
                action="reverse_transaction",
                outcome="FAILURE",
                space_id=command.space_id,
                transaction_id=None,
                correlation_id=command.idempotency_key,
            )
            unit_of_work.commit()

    @staticmethod
    def _replay(result: object) -> CommandResult:
        if not isinstance(result, dict):
            raise RuntimeError("stored reversal result has an invalid shape")
        transaction_id = result.get("transaction_id")
        status = result.get("status")
        replacement_id = result.get("replacement_transaction_id")
        if not isinstance(transaction_id, str) or not isinstance(status, str):
            raise RuntimeError("stored reversal result has an invalid shape")
        if replacement_id is not None and not isinstance(replacement_id, str):
            raise RuntimeError("stored replacement id has an invalid shape")
        return CommandResult(transaction_id, status, True, replacement_id)

    @staticmethod
    def _payload(command: ReverseCommand) -> dict[str, object]:
        replacement = command.replacement
        replacement_payload: dict[str, object] | None = None
        if replacement is not None:
            replacement_payload = {
                "space_id": replacement.space_id,
                "kind": replacement.kind.value,
                "economic_date": replacement.economic_date.isoformat(),
                "description": replacement.description,
                "amount_cents": replacement.amount_cents,
                "account_id": replacement.account_id,
                "category_id": replacement.category_id,
                "destination_account_id": replacement.destination_account_id,
                "cash_date": (
                    replacement.cash_date.isoformat() if replacement.cash_date is not None else None
                ),
            }
        return {
            "original_transaction_id": command.original_transaction_id,
            "economic_date": (
                command.economic_date.isoformat() if command.economic_date is not None else None
            ),
            "cash_date": (command.cash_date.isoformat() if command.cash_date is not None else None),
            "replacement": replacement_payload,
        }


__all__ = ("ReversalService",)
