"""Command-scoped orchestration for drafts and closed financial recipes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, is_dataclass
from datetime import date
from uuid import uuid4

from app.ledger.application.commands import (
    CommandResult,
    DraftCommand,
    ExpenseCommand,
    IncomeCommand,
    OpeningCommand,
    PostDraft,
    TransferCommand,
)
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.errors import ArchivedEntityError, InvalidLifecycleError
from app.ledger.domain.posting_recipes import (
    expense_entries,
    income_entries,
    opening_entries,
    transfer_entries,
)
from app.ledger.domain.transaction import Transaction, TransactionKind
from app.ledger.ports.audit import FinancialAuditSink
from app.ledger.ports.repositories import DraftDetails, LedgerReadRepository, RepositoryFactory
from app.shared.idempotency import IdempotencyReservation, IdempotencyStore
from app.shared.unit_of_work import UnitOfWorkFactory

PostedBuilder = Callable[[LedgerReadRepository], Transaction]


class FinancialCommandService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: RepositoryFactory,
        audit_sink: FinancialAuditSink,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory
        self._audit_sink = audit_sink

    def create_draft(self, command: DraftCommand) -> Transaction:
        self._validate_draft(command)
        draft = Transaction.draft(
            uuid4().hex,
            command.space_id,
            command.kind,
            command.economic_date,
            command.description,
        )
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            self._validate_selections(repository, command)
            repository.add_draft(draft, self._details(command))
            unit_of_work.commit()
        return draft

    def update_draft(self, transaction_id: str, command: DraftCommand) -> Transaction:
        self._validate_draft(command)
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            current = repository.get_transaction(command.space_id, transaction_id)
            revised = Transaction.draft(
                current.id,
                current.space_id,
                command.kind,
                command.economic_date,
                command.description,
            )
            self._validate_selections(repository, command)
            repository.update_draft(revised, self._details(command))
            unit_of_work.commit()
        return revised

    def discard_draft(self, space_id: str, transaction_id: str) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            self._repository_factory(unit_of_work.session).discard_draft(space_id, transaction_id)
            unit_of_work.commit()

    def list_transactions(self, space_id: str) -> tuple[Transaction, ...]:
        with self._unit_of_work_factory() as unit_of_work:
            return tuple(
                self._repository_factory(unit_of_work.session).list_transactions(
                    space_id, limit=100, offset=0
                )
            )

    def post_draft(self, command: PostDraft) -> CommandResult:
        payload = {
            "transaction_id": command.transaction_id,
            "cash_date": command.cash_date.isoformat() if command.cash_date else None,
        }

        def build(repository: LedgerReadRepository) -> Transaction:
            draft = repository.get_transaction(command.space_id, command.transaction_id)
            details = repository.get_draft_details(command.space_id, command.transaction_id)
            draft_command = DraftCommand(
                space_id=draft.space_id,
                kind=draft.kind,
                economic_date=draft.economic_date,
                description=draft.description,
                amount_cents=details.amount_cents,
                account_id=details.account_id,
                category_id=details.category_id,
                destination_account_id=details.destination_account_id,
                cash_date=command.cash_date or details.cash_date,
            )
            self._validate_selections(repository, draft_command)
            return self._posted_from_draft(draft.id, draft_command, repository)

        return self._post_idempotently(
            space_id=command.space_id,
            command_name="post_draft",
            idempotency_key=command.idempotency_key,
            payload=payload,
            build=build,
            existing_draft=True,
        )

    def create_opening(self, command: OpeningCommand) -> CommandResult:
        payload = self._payload(command)

        def build(repository: LedgerReadRepository) -> Transaction:
            account = self._active_account(repository, command.space_id, command.account_id)
            equity = self._ensure_equity(repository, command.space_id)
            return Transaction.posted(
                uuid4().hex,
                command.space_id,
                TransactionKind.OPENING,
                command.economic_date,
                None,
                command.description,
                opening_entries(
                    command.space_id,
                    account.id,
                    account.kind,
                    equity.id,
                    command.amount_cents,
                ),
            )

        return self._post_idempotently(
            command.space_id,
            "create_opening",
            command.idempotency_key,
            payload,
            build,
        )

    def create_income(self, command: IncomeCommand) -> CommandResult:
        return self._create_category_movement(command, TransactionKind.INCOME)

    def create_expense(self, command: ExpenseCommand) -> CommandResult:
        return self._create_category_movement(command, TransactionKind.EXPENSE)

    def create_transfer(self, command: TransferCommand) -> CommandResult:
        payload = self._payload(command)

        def build(repository: LedgerReadRepository) -> Transaction:
            self._active_account(repository, command.space_id, command.source_account_id)
            self._active_account(repository, command.space_id, command.destination_account_id)
            cash_date = command.cash_date or command.economic_date
            return Transaction.posted(
                uuid4().hex,
                command.space_id,
                TransactionKind.TRANSFER,
                command.economic_date,
                cash_date,
                command.description,
                transfer_entries(
                    command.space_id,
                    command.source_account_id,
                    command.destination_account_id,
                    command.amount_cents,
                ),
            )

        return self._post_idempotently(
            command.space_id,
            "create_transfer",
            command.idempotency_key,
            payload,
            build,
        )

    def _create_category_movement(
        self, command: IncomeCommand | ExpenseCommand, kind: TransactionKind
    ) -> CommandResult:
        payload = self._payload(command)

        def build(repository: LedgerReadRepository) -> Transaction:
            self._active_account(repository, command.space_id, command.account_id)
            category = self._active_category(repository, command.space_id, command.category_id)
            expected = (
                CategoryKind.INCOME if kind is TransactionKind.INCOME else CategoryKind.EXPENSE
            )
            if category.kind is not expected:
                raise InvalidLifecycleError("category kind does not match the command")
            recipe = income_entries if kind is TransactionKind.INCOME else expense_entries
            return Transaction.posted(
                uuid4().hex,
                command.space_id,
                kind,
                command.economic_date,
                command.cash_date or command.economic_date,
                command.description,
                recipe(
                    command.space_id,
                    command.account_id,
                    command.category_id,
                    command.amount_cents,
                ),
            )

        return self._post_idempotently(
            command.space_id,
            f"create_{kind.value.lower()}",
            command.idempotency_key,
            payload,
            build,
        )

    def _post_idempotently(
        self,
        space_id: str,
        command_name: str,
        idempotency_key: str,
        payload: object,
        build: PostedBuilder,
        *,
        existing_draft: bool = False,
    ) -> CommandResult:
        try:
            with self._unit_of_work_factory() as unit_of_work:
                store = IdempotencyStore(unit_of_work.session)
                reservation = store.reserve(
                    space_id=space_id,
                    command_name=command_name,
                    idempotency_key=idempotency_key,
                    payload=payload,
                )
                replay = self._replay(reservation)
                if replay is not None:
                    return replay
                repository = self._repository_factory(unit_of_work.session)
                transaction = build(repository)
                if existing_draft:
                    repository.post_existing_draft(transaction)
                else:
                    repository.add_posted(transaction)
                result = CommandResult(transaction.id, transaction.status.value)
                store.complete(reservation, result.as_json())
                self._audit_sink.record(
                    unit_of_work.session,
                    action=command_name,
                    outcome="SUCCESS",
                    space_id=space_id,
                    transaction_id=transaction.id,
                    correlation_id=idempotency_key,
                )
                unit_of_work.commit()
                return result
        except Exception:
            self._record_failure(space_id, command_name, idempotency_key)
            raise

    def _record_failure(self, space_id: str, command_name: str, correlation_id: str) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            self._audit_sink.record(
                unit_of_work.session,
                action=command_name,
                outcome="FAILURE",
                space_id=space_id,
                transaction_id=None,
                correlation_id=correlation_id,
            )
            unit_of_work.commit()

    @staticmethod
    def _replay(reservation: IdempotencyReservation) -> CommandResult | None:
        if not reservation.is_replay:
            return None
        result = reservation.result
        if not isinstance(result, dict):
            raise RuntimeError("stored idempotency result has an invalid shape")
        transaction_id = result.get("transaction_id")
        status = result.get("status")
        replacement = result.get("replacement_transaction_id")
        if not isinstance(transaction_id, str) or not isinstance(status, str):
            raise RuntimeError("stored idempotency result has an invalid shape")
        if replacement is not None and not isinstance(replacement, str):
            raise RuntimeError("stored replacement id has an invalid shape")
        return CommandResult(transaction_id, status, True, replacement)

    @staticmethod
    def _details(command: DraftCommand) -> DraftDetails:
        return DraftDetails(
            command.amount_cents,
            command.account_id,
            command.category_id,
            command.destination_account_id,
            command.cash_date,
        )

    @staticmethod
    def _validate_draft(command: DraftCommand) -> None:
        if command.amount_cents <= 0 or isinstance(command.amount_cents, bool):
            raise InvalidLifecycleError("draft amount must be positive integer cents")

    def _validate_selections(self, repository: LedgerReadRepository, command: DraftCommand) -> None:
        if command.account_id is None:
            raise InvalidLifecycleError("the movement requires an account")
        self._active_account(repository, command.space_id, command.account_id)
        if command.kind in (TransactionKind.INCOME, TransactionKind.EXPENSE):
            if command.category_id is None:
                raise InvalidLifecycleError("the movement requires a category")
            self._active_category(repository, command.space_id, command.category_id)
        if command.kind is TransactionKind.TRANSFER:
            if command.destination_account_id is None:
                raise InvalidLifecycleError("the transfer requires a destination account")
            self._active_account(repository, command.space_id, command.destination_account_id)

    def _posted_from_draft(
        self,
        transaction_id: str,
        command: DraftCommand,
        repository: LedgerReadRepository,
    ) -> Transaction:
        if command.account_id is None:
            raise InvalidLifecycleError("the movement requires an account")
        cash_date = command.cash_date or command.economic_date
        if command.kind is TransactionKind.OPENING:
            account = self._active_account(repository, command.space_id, command.account_id)
            equity = self._ensure_equity(repository, command.space_id)
            entries = opening_entries(
                command.space_id,
                account.id,
                account.kind,
                equity.id,
                command.amount_cents,
            )
            cash_date = None
        elif command.kind is TransactionKind.INCOME and command.category_id is not None:
            entries = income_entries(
                command.space_id, command.account_id, command.category_id, command.amount_cents
            )
        elif command.kind is TransactionKind.EXPENSE and command.category_id is not None:
            entries = expense_entries(
                command.space_id, command.account_id, command.category_id, command.amount_cents
            )
        elif (
            command.kind is TransactionKind.TRANSFER and command.destination_account_id is not None
        ):
            entries = transfer_entries(
                command.space_id,
                command.account_id,
                command.destination_account_id,
                command.amount_cents,
            )
        else:
            raise InvalidLifecycleError("draft selections do not match its operation kind")
        return Transaction.posted(
            transaction_id,
            command.space_id,
            command.kind,
            command.economic_date,
            cash_date,
            command.description,
            entries,
        )

    @staticmethod
    def _active_account(repository: LedgerReadRepository, space_id: str, account_id: str):
        account = repository.get_account(space_id, account_id)
        if account.is_archived:
            raise ArchivedEntityError("archived accounts cannot receive new operations")
        if account.kind is AccountKind.EQUITY:
            raise InvalidLifecycleError(
                "technical equity accounts cannot receive household operations"
            )
        return account

    @staticmethod
    def _active_category(repository: LedgerReadRepository, space_id: str, category_id: str):
        category = repository.get_category(space_id, category_id)
        if category.is_archived:
            raise ArchivedEntityError("archived categories cannot receive new operations")
        return category

    @staticmethod
    def _ensure_equity(repository: LedgerReadRepository, space_id: str):
        account_id = f"opening-equity-{space_id}"
        try:
            return repository.get_account(space_id, account_id)
        except LookupError:
            from app.ledger.domain.account import Account

            account = Account(
                account_id,
                space_id,
                "Opening equity",
                AccountKind.EQUITY,
                is_reconcilable=False,
            )
            repository.add_account(account)
            return account

    @staticmethod
    def _payload(command: object) -> dict[str, object]:
        if not is_dataclass(command):
            raise TypeError("financial command payload must be a dataclass")
        payload_fields: dict[str, object] = {}
        for field in fields(command):
            name = field.name
            if name == "idempotency_key":
                continue
            value = getattr(command, name)
            payload_fields[name] = value.isoformat() if isinstance(value, date) else value
        return payload_fields


__all__ = ("FinancialCommandService",)
