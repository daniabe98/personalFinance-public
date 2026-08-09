"""Authenticated request and unsafe-method protection dependencies."""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.identity.application.service import AuthenticatedPrincipal

SESSION_COOKIE_NAME = "__Host-pf_session"
CSRF_HEADER_NAME = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SessionVerifier(Protocol):
    def authenticate(
        self,
        session_token: str,
        *,
        at: object = None,
    ) -> AuthenticatedPrincipal | None: ...

    def validate_csrf(self, session_token: str, csrf_token: str) -> bool: ...
    def csrf_for_session(self, session_token: str) -> str | None: ...


def _session_manager(request: Request) -> SessionVerifier:
    manager = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise RuntimeError("session manager is not configured")
    return manager


def _configured_origin(request: Request) -> str:
    origin = getattr(request.app.state, "allowed_origin", None)
    if not isinstance(origin, str):
        raise RuntimeError("allowed origin is not configured")
    return origin


def _is_origin(value: str) -> bool:
    parsed = urlsplit(value)
    transport_is_allowed = parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )
    return (
        transport_is_allowed
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def require_same_origin(request: Request) -> None:
    """Reject absent, malformed or non-exact Origin values."""
    presented = request.headers.get("Origin")
    expected = _configured_origin(request)
    if (
        presented is None
        or not _is_origin(presented)
        or not _is_origin(expected)
        or presented.rstrip("/") != expected.rstrip("/")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="same-origin request required",
        )


def require_authenticated_principal(request: Request) -> AuthenticatedPrincipal:
    """Resolve a secure host cookie into the minimal trusted principal."""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    principal = (
        _session_manager(request).authenticate(session_token) if session_token is not None else None
    )
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return principal


def require_unsafe_request_protection(request: Request) -> AuthenticatedPrincipal:
    """Require authentication plus exact Origin and session-bound CSRF."""
    principal = require_authenticated_principal(request)
    if request.method in UNSAFE_METHODS:
        require_same_origin(request)
        session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
        csrf_token = request.headers.get(CSRF_HEADER_NAME, "")
        if not _session_manager(request).validate_csrf(session_token, csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="valid CSRF token required",
            )
    return principal


__all__ = (
    "SESSION_COOKIE_NAME",
    "require_authenticated_principal",
    "require_same_origin",
    "require_unsafe_request_protection",
)
