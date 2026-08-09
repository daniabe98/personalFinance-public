"""Account and flat-category catalog use cases."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from app.ledger.application.commands import CreateAccount, CreateCategory
from app.ledger.domain.account import Account, AccountKind, Category, CategoryKind
from app.ledger.domain.errors import InvalidLifecycleError
from app.ledger.ports.repositories import RepositoryFactory
from app.shared.unit_of_work import UnitOfWorkFactory


class CatalogService:
    def __init__(
        self,
        unit_of_work_factory: UnitOfWorkFactory,
        repository_factory: RepositoryFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._repository_factory = repository_factory

    def create_account(self, command: CreateAccount) -> Account:
        if command.kind not in (AccountKind.ASSET, AccountKind.LIABILITY):
            raise InvalidLifecycleError("only asset or liability accounts are visible")
        account = Account(
            uuid4().hex,
            command.space_id,
            command.name,
            command.kind,
            is_reconcilable=command.is_reconcilable,
        )
        with self._unit_of_work_factory() as unit_of_work:
            self._repository_factory(unit_of_work.session).add_account(account)
            unit_of_work.commit()
        return account

    def create_category(self, command: CreateCategory) -> Category:
        category = Category(uuid4().hex, command.space_id, command.name, command.kind)
        with self._unit_of_work_factory() as unit_of_work:
            self._repository_factory(unit_of_work.session).add_category(category)
            unit_of_work.commit()
        return category

    def ensure_starter_categories(self, space_id: str) -> tuple[Category, Category]:
        starters = (
            ("Other income", CategoryKind.INCOME),
            ("Other expense", CategoryKind.EXPENSE),
        )
        output: list[Category] = []
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            for name, kind in starters:
                existing = repository.find_category_by_name(space_id, name)
                if existing is None:
                    existing = Category(uuid4().hex, space_id, name, kind)
                    repository.add_category(existing)
                output.append(existing)
            unit_of_work.commit()
        return output[0], output[1]

    def rename_account(self, space_id: str, account_id: str, name: str) -> Account:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            account = repository.get_account(space_id, account_id).rename(name)
            repository.update_account(account)
            unit_of_work.commit()
        return account

    def set_account_archived(self, space_id: str, account_id: str, is_archived: bool) -> Account:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            current = repository.get_account(space_id, account_id)
            account = current.archive() if is_archived else current.unarchive()
            repository.update_account(account)
            unit_of_work.commit()
        return account

    def rename_category(self, space_id: str, category_id: str, name: str) -> Category:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            category = repository.get_category(space_id, category_id).rename(name)
            repository.update_category(category)
            unit_of_work.commit()
        return category

    def set_category_archived(self, space_id: str, category_id: str, is_archived: bool) -> Category:
        with self._unit_of_work_factory() as unit_of_work:
            repository = self._repository_factory(unit_of_work.session)
            current = repository.get_category(space_id, category_id)
            category = current.archive() if is_archived else current.unarchive()
            repository.update_category(category)
            unit_of_work.commit()
        return category

    def list_accounts(self, space_id: str, *, include_archived: bool) -> Sequence[Account]:
        with self._unit_of_work_factory() as unit_of_work:
            return self._repository_factory(unit_of_work.session).list_accounts(
                space_id, include_archived=include_archived
            )

    def list_categories(self, space_id: str, *, include_archived: bool) -> Sequence[Category]:
        with self._unit_of_work_factory() as unit_of_work:
            return self._repository_factory(unit_of_work.session).list_categories(
                space_id, include_archived=include_archived
            )


__all__ = ("CatalogService",)
