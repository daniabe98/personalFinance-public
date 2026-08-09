from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.shared.models_identity import SessionRecord, SpaceRecord, UserRecord


def test_identity_records_and_ownership_are_persisted(mapped_engine) -> None:
    now = datetime.now(UTC)
    with Session(mapped_engine) as session:
        session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
        session.flush()
        session.add(SpaceRecord(id="s1", owner_user_id="u1", name="Home"))
        session.add(
            SessionRecord(
                id="session-1",
                user_id="u1",
                token_hash="opaque-hash",
                csrf_token_hash="csrf-hash",
                expires_at=now + timedelta(hours=1),
            )
        )
        session.commit()

    with Session(mapped_engine) as session:
        space = session.get(SpaceRecord, "s1")
        persisted_session = session.get(SessionRecord, "session-1")
        assert space is not None
        assert persisted_session is not None
        assert space.owner_user_id == "u1"
        assert persisted_session.expires_at is not None


def test_space_cannot_reference_an_unknown_owner(mapped_engine) -> None:
    with Session(mapped_engine) as session:
        session.add(SpaceRecord(id="s1", owner_user_id="missing", name="Home"))
        with pytest.raises(IntegrityError):
            session.commit()
