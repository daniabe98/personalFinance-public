"""Transaction-bound durable idempotency storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.canonical_json import (
    JsonValue,
    _normalize_json_value,
    canonical_json_bytes,
    canonical_payload_hash,
)
from app.shared.models_ledger import IdempotencyRecord


class IdempotencyConflictError(ValueError):
    """Raised when a key is reused for a different command or payload."""


class IdempotencyInProgressError(RuntimeError):
    """Raised when an existing reservation has no committed result."""


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    """Outcome of reserving a command key in the caller's transaction."""

    record_id: str
    is_replay: bool
    result: JsonValue | None = None


class IdempotencyStore:
    """Reserve and complete command keys without owning commit boundaries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve(
        self,
        *,
        space_id: str,
        command_name: str,
        idempotency_key: str,
        payload: object,
    ) -> IdempotencyReservation:
        if not command_name or not idempotency_key:
            raise ValueError("command_name and idempotency_key must not be empty")
        payload_hash = canonical_payload_hash(payload)
        existing = self._find(space_id=space_id, idempotency_key=idempotency_key)
        if existing is not None:
            return self._resolve(existing, command_name=command_name, payload_hash=payload_hash)

        record = IdempotencyRecord(
            id=uuid4().hex,
            space_id=space_id,
            command_name=command_name,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
        )
        self._session.add(record)
        self._session.flush()
        return IdempotencyReservation(record_id=record.id, is_replay=False)

    def complete(
        self,
        reservation: IdempotencyReservation,
        result: object,
    ) -> None:
        if reservation.is_replay:
            raise ValueError("a replayed reservation cannot be completed again")
        result_json = canonical_json_bytes(result).decode("utf-8")
        record = self._session.get(IdempotencyRecord, reservation.record_id)
        if record is None:
            raise RuntimeError("idempotency reservation is not active")
        record.result_json = result_json
        record.completed_at = datetime.now(UTC)

    def _find(self, *, space_id: str, idempotency_key: str) -> IdempotencyRecord | None:
        statement = select(IdempotencyRecord).where(
            IdempotencyRecord.space_id == space_id,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )
        return self._session.scalar(statement)

    @staticmethod
    def _resolve(
        record: IdempotencyRecord,
        *,
        command_name: str,
        payload_hash: str,
    ) -> IdempotencyReservation:
        if record.command_name != command_name or record.payload_hash != payload_hash:
            raise IdempotencyConflictError(
                "idempotency key was already used for another command or payload"
            )
        if record.result_json is None:
            raise IdempotencyInProgressError("idempotent command has no completed result")
        decoded: object = json.loads(record.result_json)
        return IdempotencyReservation(
            record_id=record.id,
            is_replay=True,
            result=_normalize_json_value(decoded),
        )


__all__ = (
    "IdempotencyConflictError",
    "IdempotencyInProgressError",
    "IdempotencyReservation",
    "IdempotencyStore",
)
