from __future__ import annotations

from pathlib import Path

import pytest

from app.shared import models_control, models_identity, models_ledger
from app.shared.canonical_json import canonical_json_bytes, canonical_payload_hash
from app.shared.database import Base, create_engine, create_session_factory
from app.shared.idempotency import IdempotencyConflictError, IdempotencyStore
from app.shared.models_identity import SpaceRecord, UserRecord
from app.shared.unit_of_work import SqlAlchemyUnitOfWork

del models_control, models_identity, models_ledger


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'finance.db').as_posix()}"


def _initialize(database_url: str, *, spaces: tuple[str, ...] = ("s1",)) -> None:
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        unit_of_work.session.add(UserRecord(id="u1", username="operator", password_hash="hash"))
        unit_of_work.session.flush()
        unit_of_work.session.add_all(
            SpaceRecord(id=space_id, owner_user_id="u1", name=space_id) for space_id in spaces
        )
        unit_of_work.commit()
    engine.dispose()


def test_canonical_hash_is_stable_and_exact() -> None:
    first = {"amount_cents": 1250, "metadata": {"b": True, "a": None}}
    second = {"metadata": {"a": None, "b": True}, "amount_cents": 1250}

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_payload_hash(first) == canonical_payload_hash(second)
    assert canonical_json_bytes(first) == (b'{"amount_cents":1250,"metadata":{"a":null,"b":true}}')


@pytest.mark.parametrize("unsupported", [1.2, b"bytes", (1, 2), {1: "not-string"}])
def test_canonical_json_rejects_unsupported_or_non_exact_values(unsupported: object) -> None:
    with pytest.raises(TypeError):
        canonical_json_bytes(unsupported)


def test_same_request_replays_serialized_result_after_restart(database_url: str) -> None:
    _initialize(database_url)
    engine = create_engine(database_url)
    factory = create_session_factory(engine)
    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        store = IdempotencyStore(unit_of_work.session)
        reservation = store.reserve(
            space_id="s1",
            command_name="create_transfer",
            idempotency_key="request-1",
            payload={"to": "a2", "from": "a1", "amount_cents": 500},
        )
        assert reservation.is_replay is False
        store.complete(reservation, {"transaction_id": "t1", "amount_cents": 500})
        unit_of_work.commit()
    engine.dispose()

    reopened_engine = create_engine(database_url)
    reopened_factory = create_session_factory(reopened_engine)
    with SqlAlchemyUnitOfWork(reopened_factory) as unit_of_work:
        replay = IdempotencyStore(unit_of_work.session).reserve(
            space_id="s1",
            command_name="create_transfer",
            idempotency_key="request-1",
            payload={"amount_cents": 500, "from": "a1", "to": "a2"},
        )
        assert replay.is_replay is True
        assert replay.result == {"amount_cents": 500, "transaction_id": "t1"}
    reopened_engine.dispose()


def test_changed_payload_and_command_collision_are_rejected(database_url: str) -> None:
    _initialize(database_url)
    engine = create_engine(database_url)
    factory = create_session_factory(engine)
    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        store = IdempotencyStore(unit_of_work.session)
        reservation = store.reserve(
            space_id="s1",
            command_name="create_income",
            idempotency_key="request-1",
            payload={"amount_cents": 100},
        )
        store.complete(reservation, {"transaction_id": "t1"})
        unit_of_work.commit()

    for command_name, payload in (
        ("create_income", {"amount_cents": 101}),
        ("create_expense", {"amount_cents": 100}),
    ):
        with (
            pytest.raises(IdempotencyConflictError),
            SqlAlchemyUnitOfWork(factory) as unit_of_work,
        ):
            IdempotencyStore(unit_of_work.session).reserve(
                space_id="s1",
                command_name=command_name,
                idempotency_key="request-1",
                payload=payload,
            )
    engine.dispose()


def test_same_key_is_independent_between_spaces(database_url: str) -> None:
    _initialize(database_url, spaces=("s1", "s2"))
    engine = create_engine(database_url)
    factory = create_session_factory(engine)

    for space_id in ("s1", "s2"):
        with SqlAlchemyUnitOfWork(factory) as unit_of_work:
            store = IdempotencyStore(unit_of_work.session)
            reservation = store.reserve(
                space_id=space_id,
                command_name="create_opening",
                idempotency_key="request-1",
                payload={"amount_cents": 100},
            )
            assert reservation.is_replay is False
            store.complete(reservation, {"space_id": space_id})
            unit_of_work.commit()
    engine.dispose()


def test_rolled_back_reservation_does_not_block_retry(database_url: str) -> None:
    _initialize(database_url)
    engine = create_engine(database_url)
    factory = create_session_factory(engine)

    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        first = IdempotencyStore(unit_of_work.session).reserve(
            space_id="s1",
            command_name="create_expense",
            idempotency_key="request-1",
            payload={"amount_cents": 100},
        )
        assert first.is_replay is False

    with SqlAlchemyUnitOfWork(factory) as unit_of_work:
        retry = IdempotencyStore(unit_of_work.session).reserve(
            space_id="s1",
            command_name="create_expense",
            idempotency_key="request-1",
            payload={"amount_cents": 100},
        )
        assert retry.is_replay is False
        IdempotencyStore(unit_of_work.session).complete(retry, {"transaction_id": "t1"})
        unit_of_work.commit()
    engine.dispose()
