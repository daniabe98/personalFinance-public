from __future__ import annotations

from datetime import date
from typing import cast

import pytest

from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import (
    CreateAccount,
    CreateCategory,
    DraftCommand,
    PostDraft,
)
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.domain.errors import InvalidLifecycleError
from app.ledger.domain.transaction import Transaction, TransactionKind, TransactionStatus
from app.ledger.ports.audit import NullFinancialAuditSink
from app.ledger.ports.repositories import DraftDetails
from tests.support.ledger import SPACE_ID


def _services(uow_factory):
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    commands = FinancialCommandService(
        uow_factory,
        SqlAlchemyLedgerRepository,
        NullFinancialAuditSink(),
    )
    return uow_factory, catalog, commands


def test_draft_is_effect_free_editable_discardable_and_postable(ledger_uow_factory) -> None:
    uow_factory, catalog, service = _services(ledger_uow_factory)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    draft = service.create_draft(
        DraftCommand(
            space_id=SPACE_ID,
            kind=TransactionKind.INCOME,
            economic_date=date(2026, 7, 1),
            description="  First  ",
            amount_cents=1000,
            account_id=account.id,
            category_id=category.id,
        )
    )
    revised = service.update_draft(
        draft.id,
        DraftCommand(
            space_id=SPACE_ID,
            kind=TransactionKind.INCOME,
            economic_date=date(2026, 7, 2),
            description="  Revised  ",
            amount_cents=1200,
            account_id=account.id,
            category_id=category.id,
        ),
    )

    assert draft.description == "First"
    assert revised.description == "Revised"

    with uow_factory() as unit_of_work:
        repository = SqlAlchemyLedgerRepository(unit_of_work.session)
        assert repository.account_balance_cents(SPACE_ID, account.id) == 0
        assert repository.get_transaction(SPACE_ID, draft.id).entries == ()

    result = service.post_draft(PostDraft(SPACE_ID, revised.id, "post-1"))
    replay = service.post_draft(PostDraft(SPACE_ID, revised.id, "post-1"))

    assert result.transaction_id == revised.id
    assert replay.replayed is True
    with uow_factory() as unit_of_work:
        transaction = SqlAlchemyLedgerRepository(unit_of_work.session).get_transaction(
            SPACE_ID, revised.id
        )
        assert transaction.status is TransactionStatus.POSTED
        assert transaction.cash_date == date(2026, 7, 2)


def test_discard_removes_only_draft(ledger_uow_factory) -> None:
    _, catalog, service = _services(ledger_uow_factory)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Food", CategoryKind.EXPENSE))
    draft = service.create_draft(
        DraftCommand(
            SPACE_ID,
            TransactionKind.EXPENSE,
            date(2026, 7, 1),
            "Discard me",
            500,
            account.id,
            category.id,
        )
    )

    service.discard_draft(SPACE_ID, draft.id)

    assert service.list_transactions(SPACE_ID) == ()


@pytest.mark.parametrize("description", [None, "", "   ", "x" * 501])
def test_create_and_update_draft_reject_invalid_description(
    ledger_uow_factory,
    description: str | None,
) -> None:
    _, catalog, service = _services(ledger_uow_factory)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))

    def command(value: str) -> DraftCommand:
        return DraftCommand(
            SPACE_ID,
            TransactionKind.INCOME,
            date(2026, 7, 1),
            value,
            1000,
            account.id,
            category.id,
        )

    with pytest.raises(InvalidLifecycleError, match="description"):
        service.create_draft(command(cast(str, description)))

    draft = service.create_draft(command("Valid description"))
    with pytest.raises(InvalidLifecycleError, match="description"):
        service.update_draft(draft.id, command(cast(str, description)))


def test_legacy_null_draft_remains_readable_but_cannot_be_posted(ledger_uow_factory) -> None:
    uow_factory, catalog, service = _services(ledger_uow_factory)
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    legacy = Transaction.draft(
        "legacy-draft",
        SPACE_ID,
        TransactionKind.INCOME,
        date(2026, 7, 1),
        None,
    )
    with uow_factory() as unit_of_work:
        repository = SqlAlchemyLedgerRepository(unit_of_work.session)
        repository.add_draft(
            legacy,
            DraftDetails(1000, account.id, category.id, None, None),
        )
        unit_of_work.commit()

    transactions = service.list_transactions(SPACE_ID)

    assert transactions[0].description is None
    with pytest.raises(InvalidLifecycleError, match="description"):
        service.post_draft(PostDraft(SPACE_ID, legacy.id, "post-legacy"))
