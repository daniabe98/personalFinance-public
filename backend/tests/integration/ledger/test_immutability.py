from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.commands import CreateAccount, CreateCategory, IncomeCommand
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.domain.account import AccountKind, CategoryKind
from app.ledger.ports.audit import NullFinancialAuditSink
from app.shared.database import create_engine, create_session_factory
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.unit_of_work import UnitOfWorkFactory
from tests.integration.persistence.conftest import alembic_config
from tests.support.ledger import SPACE_ID


def test_posted_snapshot_and_entries_are_immutable_but_lifecycle_is_narrow(tmp_path) -> None:
    database_path = tmp_path / "immutable.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory.begin() as session:
        session.add(UserRecord(id="user-1", username="owner", password_hash="test-only"))
        session.flush()
        session.add(SpaceRecord(id=SPACE_ID, owner_user_id="user-1", name="Personal"))
    uow_factory = UnitOfWorkFactory(session_factory)
    catalog = CatalogService(uow_factory, SqlAlchemyLedgerRepository)
    service = FinancialCommandService(
        uow_factory, SqlAlchemyLedgerRepository, NullFinancialAuditSink()
    )
    account = catalog.create_account(CreateAccount(SPACE_ID, "Bank", AccountKind.ASSET, True))
    category = catalog.create_category(CreateCategory(SPACE_ID, "Salary", CategoryKind.INCOME))
    result = service.create_income(
        IncomeCommand(
            SPACE_ID,
            account.id,
            category.id,
            100,
            date(2026, 7, 1),
            None,
            "Original",
            "immutable-income",
        )
    )

    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.execute(
            text("UPDATE transactions SET description='changed' WHERE id=:id"),
            {"id": result.transaction_id},
        )
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.execute(
            text("UPDATE entries SET amount_cents=999 WHERE transaction_id=:transaction_id"),
            {"transaction_id": result.transaction_id},
        )

    with session_factory.begin() as session:
        session.execute(
            text("UPDATE transactions SET state='RECONCILED' WHERE id=:id"),
            {"id": result.transaction_id},
        )
        session.execute(
            text("UPDATE transactions SET state='VOIDED' WHERE id=:id"),
            {"id": result.transaction_id},
        )
    engine.dispose()
