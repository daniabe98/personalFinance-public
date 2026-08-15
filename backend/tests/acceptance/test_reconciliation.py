from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alembic import command
from app.ledger.domain.transaction import TransactionKind, TransactionStatus
from app.reconciliation.domain.errors import (
    DuplicateCompletedMembershipError,
    IneligibleAccountError,
    IneligibleEntryError,
)
from app.reconciliation.domain.reconciliation import (
    Reconciliation,
    ReconciliationSelection,
)
from app.shared.database import SessionFactory, create_engine, create_session_factory
from app.shared.models_control import AuditEventRecord, ReconciliationEntryRecord
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.models_ledger import (
    AccountRecord,
    CategoryRecord,
    EntryRecord,
    TransactionRecord,
)
from app.shared.unit_of_work import UnitOfWorkFactory
from tests.integration.persistence.conftest import alembic_config

SPACE_ID = "space-1"
OTHER_SPACE_ID = "space-2"
BANK_ID = "bank"
SAVINGS_ID = "savings"
EQUITY_ID = "equity"
EXPENSE_ID = "expense"
INCOME_ID = "income"
JULY_CUTOFF = date(2026, 7, 31)
COMPLETED_AT = datetime(2026, 7, 31, 18, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Harness:
    session_factory: SessionFactory
    unit_of_work_factory: UnitOfWorkFactory


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'reconcile.db').as_posix()}"
    command.upgrade(alembic_config(database_url), "head")
    engine = create_engine(database_url)
    session_factory = create_session_factory(engine)
    with session_factory.begin() as session:
        session.add(UserRecord(id="user-1", username="owner", password_hash="test-only"))
        session.flush()
        session.add_all(
            (
                SpaceRecord(id=SPACE_ID, owner_user_id="user-1", name="Personal"),
                SpaceRecord(id=OTHER_SPACE_ID, owner_user_id="user-1", name="Other"),
            )
        )
        session.flush()
        session.add_all(
            (
                AccountRecord(
                    id=BANK_ID,
                    space_id=SPACE_ID,
                    name="Bank",
                    kind="ASSET",
                    is_reconcilable=True,
                ),
                AccountRecord(
                    id=SAVINGS_ID,
                    space_id=SPACE_ID,
                    name="Savings",
                    kind="ASSET",
                    is_reconcilable=True,
                ),
                AccountRecord(
                    id=EQUITY_ID,
                    space_id=SPACE_ID,
                    name="Internal equity",
                    kind="EQUITY",
                    is_reconcilable=False,
                ),
                CategoryRecord(
                    id=EXPENSE_ID,
                    space_id=SPACE_ID,
                    name="Expense",
                    kind="EXPENSE",
                ),
                CategoryRecord(
                    id=INCOME_ID,
                    space_id=SPACE_ID,
                    name="Income",
                    kind="INCOME",
                ),
            )
        )
    yield Harness(session_factory, UnitOfWorkFactory(session_factory))
    engine.dispose()


class RecordingAuditWriter:
    def __init__(self, *, fail_success_once: bool = False) -> None:
        self._fail_success_once = fail_success_once

    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        reconciliation_id: str | None,
        correlation_id: str,
    ) -> None:
        database = cast(Session, session)
        if outcome == "SUCCESS" and self._fail_success_once:
            self._fail_success_once = False
            raise RuntimeError("injected success audit failure")
        database.add(
            AuditEventRecord(
                id=f"audit-{correlation_id}-{outcome}",
                space_id=space_id,
                occurred_at=COMPLETED_AT,
                action=action,
                outcome=outcome,
                actor_id=None,
                entity_type="reconciliation" if reconciliation_id else None,
                entity_id=reconciliation_id,
                correlation_id=correlation_id,
                details_json=None,
            )
        )


def _entry(
    entry_id: str,
    transaction_id: str,
    *,
    account_id: str | None = None,
    category_id: str | None = None,
    side: str,
    cents: int,
) -> EntryRecord:
    return EntryRecord(
        id=entry_id,
        space_id=SPACE_ID,
        transaction_id=transaction_id,
        account_id=account_id,
        category_id=category_id,
        side=side,
        amount_cents=cents,
    )


def _transaction(
    session: Session,
    transaction_id: str,
    kind: str,
    economic_date: date,
    cash_date: date | None,
    entries: tuple[EntryRecord, ...],
    *,
    description: str | None = None,
    state: str = "POSTED",
) -> None:
    record = TransactionRecord(
        id=transaction_id,
        space_id=SPACE_ID,
        kind=kind,
        state="_POSTING",
        economic_date=economic_date,
        cash_date=cash_date,
        description=description,
    )
    session.add(record)
    session.flush()
    session.add_all(entries)
    session.flush()
    record.state = "POSTED"
    session.flush()
    if state == "VOIDED":
        record.state = "VOIDED"
        session.flush()


def _seed_opening_and_income(harness: Harness) -> None:
    with harness.session_factory() as session, session.begin():
        _transaction(
            session,
            "opening",
            "OPENING",
            date(2026, 7, 1),
            None,
            (
                _entry("opening-bank", "opening", account_id=BANK_ID, side="DEBIT", cents=100_000),
                _entry(
                    "opening-equity",
                    "opening",
                    account_id=EQUITY_ID,
                    side="CREDIT",
                    cents=100_000,
                ),
            ),
        )
        _transaction(
            session,
            "income",
            "INCOME",
            date(2026, 7, 2),
            date(2026, 7, 5),
            (
                _entry("income-bank", "income", account_id=BANK_ID, side="DEBIT", cents=20_000),
                _entry(
                    "income-category",
                    "income",
                    category_id=INCOME_ID,
                    side="CREDIT",
                    cents=20_000,
                ),
            ),
            description="July salary",
        )


def _service(harness: Harness, audit: RecordingAuditWriter):
    from app.reconciliation.adapters.repository import SqlAlchemyReconciliationRepository
    from app.reconciliation.application.service import ReconciliationService

    return ReconciliationService(
        harness.unit_of_work_factory,
        SqlAlchemyReconciliationRepository,
        audit,
        clock=lambda: COMPLETED_AT,
    )


def test_repository_lists_cutoff_candidates_and_excludes_category_and_future(
    harness: Harness,
) -> None:
    from app.reconciliation.adapters.repository import SqlAlchemyReconciliationRepository

    _seed_opening_and_income(harness)
    with harness.session_factory() as session, session.begin():
        _transaction(
            session,
            "future-expense",
            "EXPENSE",
            date(2026, 7, 10),
            date(2026, 8, 1),
            (
                _entry(
                    "future-bank",
                    "future-expense",
                    account_id=BANK_ID,
                    side="CREDIT",
                    cents=1_000,
                ),
                _entry(
                    "future-category",
                    "future-expense",
                    category_id=EXPENSE_ID,
                    side="DEBIT",
                    cents=1_000,
                ),
            ),
        )
    with harness.unit_of_work_factory() as unit_of_work:
        candidates = SqlAlchemyReconciliationRepository(unit_of_work.session).list_candidates(
            SPACE_ID,
            BANK_ID,
            JULY_CUTOFF,
        )

    assert tuple(candidate.entry_id for candidate in candidates) == (
        "opening-bank",
        "income-bank",
    )
    assert tuple(candidate.eligibility_date for candidate in candidates) == (
        date(2026, 7, 1),
        date(2026, 7, 5),
    )
    assert tuple(candidate.description for candidate in candidates) == (
        None,
        "July salary",
    )
    assert tuple(candidate.kind for candidate in candidates) == (
        TransactionKind.OPENING,
        TransactionKind.INCOME,
    )


def test_repository_enforces_completed_membership_uniqueness(harness: Harness) -> None:
    from app.reconciliation.adapters.repository import SqlAlchemyReconciliationRepository

    _seed_opening_and_income(harness)
    with harness.unit_of_work_factory() as unit_of_work:
        repository = SqlAlchemyReconciliationRepository(unit_of_work.session)
        candidate = repository.list_candidates(SPACE_ID, BANK_ID, JULY_CUTOFF)[0]
        first = Reconciliation.draft(
            reconciliation_id="first",
            space_id=SPACE_ID,
            account_id=BANK_ID,
            cutoff_date=JULY_CUTOFF,
            observed_balance_cents=100_000,
            prior_completed_cents=0,
            candidates=(candidate,),
            selection=ReconciliationSelection((candidate.entry_id,)),
        ).complete()
        repository.add_completed(first, COMPLETED_AT)
        unit_of_work.commit()
    with (
        pytest.raises(DuplicateCompletedMembershipError),
        harness.unit_of_work_factory() as unit_of_work,
    ):
        repository = SqlAlchemyReconciliationRepository(unit_of_work.session)
        duplicate = Reconciliation.draft(
            reconciliation_id="second",
            space_id=SPACE_ID,
            account_id=BANK_ID,
            cutoff_date=JULY_CUTOFF,
            observed_balance_cents=100_000,
            prior_completed_cents=0,
            candidates=(candidate,),
            selection=ReconciliationSelection((candidate.entry_id,)),
        ).complete()
        repository.add_completed(duplicate, COMPLETED_AT)


def test_opening_only_completion_is_exact_and_audited_atomically(harness: Harness) -> None:
    _seed_opening_and_income(harness)
    service = _service(harness, RecordingAuditWriter())

    result = service.complete(
        space_id=SPACE_ID,
        account_id=BANK_ID,
        cutoff_date=date(2026, 7, 1),
        observed_balance_cents=100_000,
        entry_ids=("opening-bank",),
        correlation_id="opening-complete",
    )

    assert result.checked_balance_cents == 100_000
    assert result.difference_cents == 0
    with harness.session_factory() as session:
        membership_count = session.scalar(
            select(func.count()).select_from(ReconciliationEntryRecord)
        )
        audit = session.scalar(
            select(AuditEventRecord).where(AuditEventRecord.correlation_id == "opening-complete")
        )
        transaction = session.get(TransactionRecord, "opening")
    assert membership_count == 1
    assert audit is not None and audit.outcome == "SUCCESS"
    assert transaction is not None and transaction.state == "RECONCILED"


def test_prior_completed_balance_is_used_for_next_reconciliation(harness: Harness) -> None:
    _seed_opening_and_income(harness)
    service = _service(harness, RecordingAuditWriter())
    service.complete(
        space_id=SPACE_ID,
        account_id=BANK_ID,
        cutoff_date=date(2026, 7, 1),
        observed_balance_cents=100_000,
        entry_ids=("opening-bank",),
        correlation_id="first-period",
    )

    preview = service.preview(
        space_id=SPACE_ID,
        account_id=BANK_ID,
        cutoff_date=JULY_CUTOFF,
        observed_balance_cents=120_000,
        entry_ids=("income-bank",),
    )

    assert preview.prior_completed_cents == 100_000
    assert preview.selected_effect_cents == 20_000
    assert preview.checked_balance_cents == 120_000


def test_transfer_sides_complete_independently_before_transaction_state_changes(
    harness: Harness,
) -> None:
    with harness.session_factory() as session, session.begin():
        _transaction(
            session,
            "transfer",
            "TRANSFER",
            date(2026, 7, 12),
            date(2026, 7, 12),
            (
                _entry(
                    "transfer-bank",
                    "transfer",
                    account_id=BANK_ID,
                    side="CREDIT",
                    cents=10_000,
                ),
                _entry(
                    "transfer-savings",
                    "transfer",
                    account_id=SAVINGS_ID,
                    side="DEBIT",
                    cents=10_000,
                ),
            ),
        )
    service = _service(harness, RecordingAuditWriter())
    service.complete(
        space_id=SPACE_ID,
        account_id=BANK_ID,
        cutoff_date=JULY_CUTOFF,
        observed_balance_cents=-10_000,
        entry_ids=("transfer-bank",),
        correlation_id="transfer-source",
    )
    with harness.session_factory() as session:
        transfer = session.get(TransactionRecord, "transfer")
        assert transfer is not None and transfer.state == "POSTED"

    service.complete(
        space_id=SPACE_ID,
        account_id=SAVINGS_ID,
        cutoff_date=JULY_CUTOFF,
        observed_balance_cents=10_000,
        entry_ids=("transfer-savings",),
        correlation_id="transfer-destination",
    )
    with harness.session_factory() as session:
        transfer = session.get(TransactionRecord, "transfer")
        assert transfer is not None and transfer.state == "RECONCILED"


def test_original_and_reversal_entries_remain_independent_candidates(harness: Harness) -> None:
    with harness.session_factory() as session, session.begin():
        _transaction(
            session,
            "original",
            "EXPENSE",
            date(2026, 6, 20),
            date(2026, 6, 20),
            (
                _entry(
                    "original-bank",
                    "original",
                    account_id=BANK_ID,
                    side="CREDIT",
                    cents=3_000,
                ),
                _entry(
                    "original-category",
                    "original",
                    category_id=EXPENSE_ID,
                    side="DEBIT",
                    cents=3_000,
                ),
            ),
            state="VOIDED",
        )
        _transaction(
            session,
            "reversal",
            "REVERSAL",
            date(2026, 7, 15),
            date(2026, 7, 15),
            (
                _entry(
                    "reversal-bank",
                    "reversal",
                    account_id=BANK_ID,
                    side="DEBIT",
                    cents=3_000,
                ),
                _entry(
                    "reversal-category",
                    "reversal",
                    category_id=EXPENSE_ID,
                    side="CREDIT",
                    cents=3_000,
                ),
            ),
        )
    service = _service(harness, RecordingAuditWriter())

    candidates = service.list_candidates(SPACE_ID, BANK_ID, JULY_CUTOFF)

    assert {candidate.entry_id for candidate in candidates} == {
        "original-bank",
        "reversal-bank",
    }


def test_same_space_account_and_entry_checks_fail_closed(harness: Harness) -> None:
    _seed_opening_and_income(harness)
    service = _service(harness, RecordingAuditWriter())

    with pytest.raises(IneligibleAccountError):
        service.list_candidates(OTHER_SPACE_ID, BANK_ID, JULY_CUTOFF)
    with pytest.raises(IneligibleEntryError):
        service.preview(
            space_id=SPACE_ID,
            account_id=BANK_ID,
            cutoff_date=JULY_CUTOFF,
            observed_balance_cents=100_000,
            entry_ids=("not-present",),
        )


def test_success_audit_failure_rolls_back_then_persists_minimized_failure(
    harness: Harness,
) -> None:
    _seed_opening_and_income(harness)
    service = _service(harness, RecordingAuditWriter(fail_success_once=True))

    with pytest.raises(RuntimeError, match="injected success audit failure"):
        service.complete(
            space_id=SPACE_ID,
            account_id=BANK_ID,
            cutoff_date=date(2026, 7, 1),
            observed_balance_cents=100_000,
            entry_ids=("opening-bank",),
            correlation_id="rollback-case",
        )

    with harness.session_factory() as session:
        membership_count = session.scalar(
            select(func.count()).select_from(ReconciliationEntryRecord)
        )
        audits = tuple(
            session.scalars(
                select(AuditEventRecord).where(AuditEventRecord.correlation_id == "rollback-case")
            )
        )
        transaction = session.get(TransactionRecord, "opening")
    assert membership_count == 0
    assert tuple(event.outcome for event in audits) == ("FAILURE",)
    assert audits[0].details_json is None
    assert transaction is not None and transaction.state == TransactionStatus.POSTED.value
