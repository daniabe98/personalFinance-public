"""Exact canonical JSON for durable command identity."""

from __future__ import annotations

import hashlib
import json
from typing import cast

type JsonValue = bool | int | str | list[JsonValue] | dict[str, JsonValue] | None


def _normalize_json_value(value: object) -> JsonValue:
    if value is None:
        return None
    if type(value) is bool:
        return value
    if type(value) is int:
        return cast(int, value)
    if type(value) is str:
        return value
    if type(value) is list:
        items = cast(list[object], value)
        return [_normalize_json_value(item) for item in items]
    if type(value) is dict:
        items = cast(dict[object, object], value)
        normalized: dict[str, JsonValue] = {}
        for key, item in items.items():
            if type(key) is not str:
                raise TypeError("canonical JSON object keys must be strings")
            normalized[key] = _normalize_json_value(item)
        return normalized
    raise TypeError(f"unsupported canonical JSON value type: {type(value).__name__}")


def canonical_json_bytes(payload: object) -> bytes:
    """Serialize exact JSON data deterministically without float coercion."""
    normalized = _normalize_json_value(payload)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_payload_hash(payload: object) -> str:
    """Return the lowercase SHA-256 digest of a canonical request payload."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


__all__ = ("JsonValue", "canonical_json_bytes", "canonical_payload_hash")
