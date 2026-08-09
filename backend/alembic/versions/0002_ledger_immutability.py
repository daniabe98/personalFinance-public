"""Persist draft details and protect posted transaction snapshots.

Revision ID: 0002_ledger_immutability
Revises: 0001_initial
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op

revision = "0002_ledger_immutability"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

CREATE_DRAFT_DETAILS = """
CREATE TABLE IF NOT EXISTS ledger_draft_details (
    transaction_id VARCHAR(36) NOT NULL PRIMARY KEY,
    space_id VARCHAR(36) NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    account_id VARCHAR(36),
    category_id VARCHAR(36),
    destination_account_id VARCHAR(36),
    cash_date DATE,
    replacement_of_transaction_id VARCHAR(36),
    FOREIGN KEY (space_id, transaction_id)
        REFERENCES transactions (space_id, id) ON DELETE CASCADE
)
"""

POSTED_SNAPSHOT_UPDATE_GUARD = """
CREATE TRIGGER guard_posted_transaction_snapshot_update
BEFORE UPDATE OF space_id, kind, economic_date, cash_date, description ON transactions
WHEN OLD.state IN ('POSTED', 'RECONCILED', 'VOIDED')
BEGIN
    SELECT RAISE(ABORT, 'posted transaction snapshot is immutable');
END
"""

POSTED_TRANSACTION_DELETE_GUARD = """
CREATE TRIGGER guard_posted_transaction_delete
BEFORE DELETE ON transactions
WHEN OLD.state IN ('POSTED', 'RECONCILED', 'VOIDED')
BEGIN
    SELECT RAISE(ABORT, 'posted transaction history is immutable');
END
"""

POSTED_LIFECYCLE_GUARD = """
CREATE TRIGGER guard_posted_transaction_lifecycle
BEFORE UPDATE OF state ON transactions
WHEN OLD.state IN ('POSTED', 'RECONCILED', 'VOIDED')
AND NOT (
    NEW.state = OLD.state
    OR (OLD.state = 'POSTED' AND NEW.state IN ('RECONCILED', 'VOIDED'))
    OR (OLD.state = 'RECONCILED' AND NEW.state = 'VOIDED')
)
BEGIN
    SELECT RAISE(ABORT, 'posted transaction lifecycle cannot move backwards');
END
"""


def upgrade() -> None:
    op.execute(CREATE_DRAFT_DETAILS)
    op.execute(POSTED_SNAPSHOT_UPDATE_GUARD)
    op.execute(POSTED_TRANSACTION_DELETE_GUARD)
    op.execute(POSTED_LIFECYCLE_GUARD)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS guard_posted_transaction_lifecycle")
    op.execute("DROP TRIGGER IF EXISTS guard_posted_transaction_delete")
    op.execute("DROP TRIGGER IF EXISTS guard_posted_transaction_snapshot_update")
    op.execute("DROP TABLE IF EXISTS ledger_draft_details")
