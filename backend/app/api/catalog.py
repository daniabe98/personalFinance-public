"""Authenticated HTTP adapter for visible accounts and categories."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import (
    require_authenticated_principal,
    require_unsafe_request_protection,
)
from app.identity.application.service import AuthenticatedPrincipal
from app.ledger.application.commands import CreateAccount, CreateCategory
from app.ledger.application.queries import AccountView, CategoryView
from app.ledger.domain.account import Account, AccountKind, Category, CategoryKind

router = APIRouter(tags=["catalog"])
ReadPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_principal)]


def _require_write_principal(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_unsafe_request_protection)],
    csrf_token: Annotated[str, Header(alias="X-CSRF-Token")],
) -> AuthenticatedPrincipal:
    del csrf_token
    return principal


WritePrincipal = Annotated[AuthenticatedPrincipal, Depends(_require_write_principal)]


class CatalogPort(Protocol):
    def create_account(self, command: CreateAccount) -> Account: ...
    def create_category(self, command: CreateCategory) -> Category: ...
    def rename_account(self, space_id: str, account_id: str, name: str) -> Account: ...
    def set_account_archived(
        self, space_id: str, account_id: str, is_archived: bool
    ) -> Account: ...
    def rename_category(self, space_id: str, category_id: str, name: str) -> Category: ...
    def set_category_archived(
        self, space_id: str, category_id: str, is_archived: bool
    ) -> Category: ...
    def list_accounts(
        self, space_id: str, *, include_archived: bool
    ) -> Sequence[Account | AccountView]: ...
    def list_categories(
        self, space_id: str, *, include_archived: bool
    ) -> Sequence[Category | CategoryView]: ...


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    kind: AccountKind
    is_reconcilable: bool = True


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    kind: CategoryKind


class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class AccountResponse(BaseModel):
    id: str
    name: str
    kind: AccountKind
    is_archived: bool
    is_reconcilable: bool
    balance_cents: int
    currency: str = "EUR"


class CategoryResponse(BaseModel):
    id: str
    name: str
    kind: CategoryKind
    is_archived: bool


def _service(request: Request) -> CatalogPort:
    service = getattr(request.app.state, "catalog_service", None)
    if service is None:
        raise RuntimeError("catalog service is not configured")
    return cast(CatalogPort, service)


def _account(value: Account | AccountView) -> AccountResponse:
    return AccountResponse(
        id=str(value.id),
        name=str(value.name),
        kind=value.kind,
        is_archived=bool(value.is_archived),
        is_reconcilable=bool(value.is_reconcilable),
        balance_cents=int(getattr(value, "balance_cents", 0)),
    )


def _category(value: Category | CategoryView) -> CategoryResponse:
    return CategoryResponse(
        id=str(value.id),
        name=str(value.name),
        kind=value.kind,
        is_archived=bool(value.is_archived),
    )


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(
    request: Request,
    principal: ReadPrincipal,
    include_archived: Annotated[bool, Query()] = False,
) -> list[AccountResponse]:
    values = _service(request).list_accounts(principal.space_id, include_archived=include_archived)
    return [_account(value) for value in values]


@router.post("/accounts", status_code=status.HTTP_201_CREATED, response_model=AccountResponse)
def create_account(
    payload: AccountCreate, request: Request, principal: WritePrincipal
) -> AccountResponse:
    value = _service(request).create_account(
        CreateAccount(
            principal.space_id,
            payload.name,
            payload.kind,
            payload.is_reconcilable,
        )
    )
    return _account(value)


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
def rename_account(
    account_id: str, payload: RenameRequest, request: Request, principal: WritePrincipal
) -> AccountResponse:
    return _account(_service(request).rename_account(principal.space_id, account_id, payload.name))


@router.post("/accounts/{account_id}/archive", response_model=AccountResponse)
def archive_account(
    account_id: str, request: Request, principal: WritePrincipal
) -> AccountResponse:
    return _account(_service(request).set_account_archived(principal.space_id, account_id, True))


@router.post("/accounts/{account_id}/unarchive", response_model=AccountResponse)
def unarchive_account(
    account_id: str, request: Request, principal: WritePrincipal
) -> AccountResponse:
    return _account(_service(request).set_account_archived(principal.space_id, account_id, False))


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(
    request: Request,
    principal: ReadPrincipal,
    include_archived: Annotated[bool, Query()] = False,
) -> list[CategoryResponse]:
    values = _service(request).list_categories(
        principal.space_id, include_archived=include_archived
    )
    return [_category(value) for value in values]


@router.post("/categories", status_code=status.HTTP_201_CREATED, response_model=CategoryResponse)
def create_category(
    payload: CategoryCreate, request: Request, principal: WritePrincipal
) -> CategoryResponse:
    return _category(
        _service(request).create_category(
            CreateCategory(principal.space_id, payload.name, payload.kind)
        )
    )


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def rename_category(
    category_id: str,
    payload: RenameRequest,
    request: Request,
    principal: WritePrincipal,
) -> CategoryResponse:
    return _category(
        _service(request).rename_category(principal.space_id, category_id, payload.name)
    )


@router.post("/categories/{category_id}/archive", response_model=CategoryResponse)
def archive_category(
    category_id: str, request: Request, principal: WritePrincipal
) -> CategoryResponse:
    return _category(_service(request).set_category_archived(principal.space_id, category_id, True))


@router.post("/categories/{category_id}/unarchive", response_model=CategoryResponse)
def unarchive_category(
    category_id: str, request: Request, principal: WritePrincipal
) -> CategoryResponse:
    return _category(
        _service(request).set_category_archived(principal.space_id, category_id, False)
    )


__all__ = ("router",)
