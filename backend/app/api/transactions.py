"""Closed authenticated HTTP commands for financial operations."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Protocol, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.api.dependencies import (
    require_authenticated_principal,
    require_unsafe_request_protection,
)
from app.identity.application.service import AuthenticatedPrincipal
from app.ledger.application.commands import (
    CommandResult,
    DraftCommand,
    ExpenseCommand,
    IncomeCommand,
    OpeningCommand,
    PostDraft,
    ReverseCommand,
    TransferCommand,
)
from app.ledger.application.queries import TransactionView
from app.ledger.domain.entry import EntrySide
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus

router = APIRouter(tags=["transactions"])
ReadPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


def _require_write_principal(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_unsafe_request_protection)],
    csrf_token: Annotated[str, Header(alias="X-CSRF-Token")],
) -> AuthenticatedPrincipal:
    del csrf_token
    return principal


WritePrincipal = Annotated[AuthenticatedPrincipal, Depends(_require_write_principal)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]


class FinancialCommandsPort(Protocol):
    def create_draft(self, command: DraftCommand) -> Transaction: ...
    def update_draft(self, transaction_id: str, command: DraftCommand) -> Transaction: ...
    def discard_draft(self, space_id: str, transaction_id: str) -> None: ...
    def post_draft(self, command: PostDraft) -> CommandResult: ...
    def create_opening(self, command: OpeningCommand) -> CommandResult: ...
    def create_income(self, command: IncomeCommand) -> CommandResult: ...
    def create_expense(self, command: ExpenseCommand) -> CommandResult: ...
    def create_transfer(self, command: TransferCommand) -> CommandResult: ...


class LedgerQueriesPort(Protocol):
    def get_transaction(self, space_id: str, transaction_id: str) -> TransactionView: ...
    def list_transactions(
        self, space_id: str, *, limit: int, offset: int
    ) -> tuple[TransactionView, ...]: ...


class ReversalPort(Protocol):
    def reverse(self, command: ReverseCommand) -> CommandResult: ...


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: TransactionKind
    economic_date: date
    description: str | None = Field(default=None, max_length=500)
    amount_cents: StrictInt
    account_id: str | None = None
    category_id: str | None = None
    destination_account_id: str | None = None
    cash_date: date | None = None


class PostDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_date: date | None = None


class OpeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str
    amount_cents: StrictInt
    economic_date: date
    description: str | None = Field(default=None, max_length=500)


class CategoryMovementRequest(OpeningRequest):
    category_id: str
    cash_date: date | None = None


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: str
    destination_account_id: str
    amount_cents: StrictInt
    economic_date: date
    cash_date: date | None = None
    description: str | None = Field(default=None, max_length=500)


class ReversalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    economic_date: date | None = None
    cash_date: date | None = None
    description: str | None = Field(default=None, max_length=500)


class CommandResponse(BaseModel):
    transaction_id: str
    status: str
    replayed: bool
    replacement_transaction_id: str | None = None


class TransactionResponse(BaseModel):
    id: str
    kind: TransactionKind
    status: TransactionStatus
    status_label: str
    economic_date: date
    cash_date: date | None
    description: str | None
    amount_cents: StrictInt | None = None
    account_id: str | None = None
    category_id: str | None = None
    destination_account_id: str | None = None
    original_transaction_id: str | None = None
    reversal_transaction_id: str | None = None
    corrected_original_transaction_id: str | None = None
    replacement_transaction_id: str | None = None


def _commands(request: Request) -> FinancialCommandsPort:
    value = getattr(request.app.state, "financial_command_service", None)
    if value is None:
        raise RuntimeError("financial command service is not configured")
    return cast(FinancialCommandsPort, value)


def _queries(request: Request) -> LedgerQueriesPort:
    value = getattr(request.app.state, "ledger_query_service", None)
    if value is None:
        raise RuntimeError("ledger query service is not configured")
    return cast(LedgerQueriesPort, value)


def _reversals(request: Request) -> ReversalPort:
    value = getattr(request.app.state, "reversal_service", None)
    if value is None:
        raise RuntimeError("reversal service is not configured")
    return cast(ReversalPort, value)


def _correlation_id(request: Request) -> str:
    value = request.headers.get("X-Request-ID")
    return value if value is not None and 1 <= len(value) <= 120 else str(uuid4())


def _command(value: CommandResult) -> CommandResponse:
    return CommandResponse(
        transaction_id=value.transaction_id,
        status=value.status,
        replayed=value.replayed,
        replacement_transaction_id=value.replacement_transaction_id,
    )


def _transaction(value: Transaction | TransactionView) -> TransactionResponse:
    status_value = value.status
    amount_cents, account_id, category_id, destination_account_id = _read_details(value)
    draft_details = value.draft_details if isinstance(value, TransactionView) else None
    return TransactionResponse(
        id=str(value.id),
        kind=value.kind,
        status=status_value,
        status_label=str(getattr(value, "status_label", status_value)),
        economic_date=value.economic_date,
        cash_date=draft_details.cash_date if draft_details is not None else value.cash_date,
        description=value.description,
        amount_cents=amount_cents,
        account_id=account_id,
        category_id=category_id,
        destination_account_id=destination_account_id,
        original_transaction_id=getattr(value, "original_transaction_id", None),
        reversal_transaction_id=getattr(value, "reversal_transaction_id", None),
        corrected_original_transaction_id=getattr(value, "corrected_original_transaction_id", None),
        replacement_transaction_id=getattr(value, "replacement_transaction_id", None),
    )


def _read_details(
    value: Transaction | TransactionView,
) -> tuple[int | None, str | None, str | None, str | None]:
    if isinstance(value, TransactionView) and value.draft_details is not None:
        details = value.draft_details
        return (
            details.amount_cents,
            details.account_id,
            details.category_id,
            details.destination_account_id,
        )
    entries = value.entries
    if not entries:
        return None, None, None, None

    amount_cents = entries[0].amount_cents
    account_entries = tuple(entry for entry in entries if entry.account_id is not None)
    category_id = next(
        (entry.category_id for entry in entries if entry.category_id is not None),
        None,
    )
    visible_accounts = tuple(
        entry
        for entry in account_entries
        if entry.account_id is not None and not entry.account_id.startswith("opening-equity-")
    )
    if len(visible_accounts) == 1 and len(account_entries) > 1:
        return amount_cents, visible_accounts[0].account_id, category_id, None
    if len(account_entries) > 1 and category_id is None:
        source = next(
            (entry.account_id for entry in account_entries if entry.side is EntrySide.CREDIT),
            None,
        )
        destination = next(
            (entry.account_id for entry in account_entries if entry.side is EntrySide.DEBIT),
            None,
        )
        return amount_cents, source, None, destination
    account_id = next((entry.account_id for entry in account_entries), None)
    return amount_cents, account_id, category_id, None


def _draft_command(space_id: str, payload: DraftRequest) -> DraftCommand:
    return DraftCommand(
        space_id=space_id,
        kind=payload.kind,
        economic_date=payload.economic_date,
        description=payload.description,
        amount_cents=payload.amount_cents,
        account_id=payload.account_id,
        category_id=payload.category_id,
        destination_account_id=payload.destination_account_id,
        cash_date=payload.cash_date,
    )


@router.get("/transactions", response_model=list[TransactionResponse])
def list_transactions(
    request: Request,
    principal: ReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TransactionResponse]:
    return [
        _transaction(value)
        for value in _queries(request).list_transactions(
            principal.space_id, limit=limit, offset=offset
        )
    ]


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str, request: Request, principal: ReadPrincipal
) -> TransactionResponse:
    return _transaction(_queries(request).get_transaction(principal.space_id, transaction_id))


@router.post(
    "/transactions/drafts",
    status_code=status.HTTP_201_CREATED,
    response_model=TransactionResponse,
)
def create_draft(
    payload: DraftRequest, request: Request, principal: WritePrincipal
) -> TransactionResponse:
    return _transaction(
        _commands(request).create_draft(_draft_command(principal.space_id, payload))
    )


@router.patch("/transactions/drafts/{transaction_id}", response_model=TransactionResponse)
def update_draft(
    transaction_id: str,
    payload: DraftRequest,
    request: Request,
    principal: WritePrincipal,
) -> TransactionResponse:
    return _transaction(
        _commands(request).update_draft(transaction_id, _draft_command(principal.space_id, payload))
    )


@router.delete("/transactions/drafts/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_draft(transaction_id: str, request: Request, principal: WritePrincipal) -> Response:
    _commands(request).discard_draft(principal.space_id, transaction_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/transactions/drafts/{transaction_id}/post", response_model=CommandResponse)
def post_draft(
    transaction_id: str,
    payload: PostDraftRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    return _command(
        _commands(request).post_draft(
            PostDraft(
                principal.space_id,
                transaction_id,
                idempotency_key,
                payload.cash_date,
            )
        )
    )


@router.post("/transactions/opening", response_model=CommandResponse)
def create_opening(
    payload: OpeningRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    return _command(
        _commands(request).create_opening(
            OpeningCommand(
                principal.space_id,
                payload.account_id,
                payload.amount_cents,
                payload.economic_date,
                payload.description,
                idempotency_key,
            )
        )
    )


def _category_command(
    payload: CategoryMovementRequest,
    principal: AuthenticatedPrincipal,
    idempotency_key: str,
    command_type: type[IncomeCommand] | type[ExpenseCommand],
) -> IncomeCommand | ExpenseCommand:
    return command_type(
        principal.space_id,
        payload.account_id,
        payload.category_id,
        payload.amount_cents,
        payload.economic_date,
        payload.cash_date,
        payload.description,
        idempotency_key,
    )


@router.post("/transactions/income", response_model=CommandResponse)
def create_income(
    payload: CategoryMovementRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    command = _category_command(payload, principal, idempotency_key, IncomeCommand)
    return _command(_commands(request).create_income(cast(IncomeCommand, command)))


@router.post("/transactions/expense", response_model=CommandResponse)
def create_expense(
    payload: CategoryMovementRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    command = _category_command(payload, principal, idempotency_key, ExpenseCommand)
    return _command(_commands(request).create_expense(cast(ExpenseCommand, command)))


@router.post("/transactions/transfer", response_model=CommandResponse)
def create_transfer(
    payload: TransferRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    return _command(
        _commands(request).create_transfer(
            TransferCommand(
                principal.space_id,
                payload.source_account_id,
                payload.destination_account_id,
                payload.amount_cents,
                payload.economic_date,
                payload.cash_date,
                payload.description,
                idempotency_key,
            )
        )
    )


@router.post("/transactions/{transaction_id}/reverse", response_model=CommandResponse)
def reverse_transaction(
    transaction_id: str,
    payload: ReversalRequest,
    request: Request,
    principal: WritePrincipal,
    idempotency_key: IdempotencyKey,
) -> CommandResponse:
    return _command(
        _reversals(request).reverse(
            ReverseCommand(
                principal.space_id,
                transaction_id,
                payload.economic_date,
                payload.cash_date,
                payload.description,
                idempotency_key,
            )
        )
    )


__all__ = ("router",)
