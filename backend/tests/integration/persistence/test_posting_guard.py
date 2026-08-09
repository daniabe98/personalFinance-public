from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _seed_draft(connection, *, amounts: tuple[int, ...]) -> None:
    connection.execute(
        text("INSERT INTO users (id, username, password_hash) VALUES ('u1', 'operator', 'hash')")
    )
    connection.execute(
        text("INSERT INTO spaces (id, owner_user_id, name) VALUES ('s1', 'u1', 'Home')")
    )
    connection.execute(
        text(
            """
            INSERT INTO accounts (id, space_id, name, kind)
            VALUES ('a1', 's1', 'Cash', 'ASSET')
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO transactions (id, space_id, kind, state, economic_date)
            VALUES ('t1', 's1', 'TRANSFER', 'DRAFT', '2026-07-23')
            """
        )
    )
    for index, amount in enumerate(amounts):
        side = "DEBIT" if index == 0 else "CREDIT"
        connection.execute(
            text(
                """
                INSERT INTO entries
                    (id, space_id, transaction_id, account_id, side, amount_cents)
                VALUES (:id, 's1', 't1', 'a1', :side, :amount)
                """
            ),
            {"id": f"e{index}", "side": side, "amount": amount},
        )


@pytest.mark.parametrize("amounts", [(100,), (100, 99)])
def test_raw_sql_cannot_finalize_an_invalid_posting(migrated_engine, amounts) -> None:
    with migrated_engine.begin() as connection:
        _seed_draft(connection, amounts=amounts)
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE transactions SET state = 'POSTED' WHERE id = 't1'"))


def test_balanced_two_entry_posting_can_be_finalized(migrated_engine) -> None:
    with migrated_engine.begin() as connection:
        _seed_draft(connection, amounts=(100, 100))
        connection.execute(text("UPDATE transactions SET state = 'POSTED' WHERE id = 't1'"))
        state = connection.execute(
            text("SELECT state FROM transactions WHERE id = 't1'")
        ).scalar_one()
        assert state == "POSTED"
