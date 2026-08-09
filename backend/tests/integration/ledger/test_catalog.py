from __future__ import annotations

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import CreateAccount, CreateCategory
from app.ledger.domain.account import Account, AccountKind, CategoryKind
from tests.support.ledger import SPACE_ID


def test_catalog_creates_renames_archives_and_unarchives_without_delete(
    ledger_uow_factory,
) -> None:
    service = CatalogService(ledger_uow_factory, SqlAlchemyLedgerRepository)
    account = service.create_account(
        CreateAccount(SPACE_ID, "Current account", AccountKind.ASSET, True)
    )
    category = service.create_category(CreateCategory(SPACE_ID, "Groceries", CategoryKind.EXPENSE))

    renamed = service.rename_account(SPACE_ID, account.id, "Household account")
    archived = service.set_account_archived(SPACE_ID, account.id, True)
    restored = service.set_account_archived(SPACE_ID, account.id, False)
    archived_category = service.set_category_archived(SPACE_ID, category.id, True)

    assert renamed.name == "Household account"
    assert archived.is_archived is True
    assert restored.is_archived is False
    assert archived_category.is_archived is True
    assert service.list_accounts(SPACE_ID, include_archived=True)[0].id == account.id
    assert service.list_categories(SPACE_ID, include_archived=True)[0].id == category.id
    assert not hasattr(service, "delete_account")


def test_starter_categories_are_idempotent_and_flat(ledger_uow_factory) -> None:
    service = CatalogService(ledger_uow_factory, SqlAlchemyLedgerRepository)

    first = service.ensure_starter_categories(SPACE_ID)
    second = service.ensure_starter_categories(SPACE_ID)

    assert [(item.name, item.kind) for item in first] == [
        ("Other income", CategoryKind.INCOME),
        ("Other expense", CategoryKind.EXPENSE),
    ]
    assert [item.id for item in second] == [item.id for item in first]


def test_technical_equity_accounts_are_never_listed(ledger_uow_factory) -> None:
    factory = ledger_uow_factory
    service = CatalogService(factory, SqlAlchemyLedgerRepository)
    with factory() as unit_of_work:
        SqlAlchemyLedgerRepository(unit_of_work.session).add_account(
            Account(
                "opening-equity",
                SPACE_ID,
                "Opening equity",
                AccountKind.EQUITY,
                is_reconcilable=False,
            )
        )
        unit_of_work.commit()

    assert service.list_accounts(SPACE_ID, include_archived=True) == ()
