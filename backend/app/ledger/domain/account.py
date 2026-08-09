"""Visible financial accounts and flat categories."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from app.ledger.domain.errors import InvalidLifecycleError


class AccountKind(StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"


class CategoryKind(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


def _validated_name(name: str) -> str:
    normalized = name.strip()
    if not normalized or len(normalized) > 120:
        raise ValueError("name must contain between 1 and 120 characters")
    return normalized


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    space_id: str
    name: str
    kind: AccountKind
    is_archived: bool = False
    is_reconcilable: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_name(self.name))
        if self.kind is AccountKind.EQUITY and self.is_reconcilable:
            raise InvalidLifecycleError("equity accounts cannot be reconcilable")

    def rename(self, name: str) -> Account:
        return replace(self, name=_validated_name(name))

    def archive(self) -> Account:
        return replace(self, is_archived=True)

    def unarchive(self) -> Account:
        return replace(self, is_archived=False)


@dataclass(frozen=True, slots=True)
class Category:
    id: str
    space_id: str
    name: str
    kind: CategoryKind
    is_archived: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _validated_name(self.name))

    def rename(self, name: str) -> Category:
        return replace(self, name=_validated_name(name))

    def archive(self) -> Category:
        return replace(self, is_archived=True)

    def unarchive(self) -> Category:
        return replace(self, is_archived=False)


__all__ = ("Account", "AccountKind", "Category", "CategoryKind")
