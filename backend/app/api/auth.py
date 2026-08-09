"""Audited authentication HTTP routes."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.dependencies import (
    SESSION_COOKIE_NAME,
    _session_manager,
    require_authenticated_principal,
    require_same_origin,
    require_unsafe_request_protection,
)
from app.identity.application.service import (
    AuthenticatedPrincipal,
    AuthenticationFailedError,
    IdentityService,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=120)
    password: SecretStr


def _identity_service(request: Request) -> IdentityService:
    service = getattr(request.app.state, "identity_service", None)
    if not isinstance(service, IdentityService):
        raise RuntimeError("identity service is not configured")
    return service


def _correlation_id(request: Request) -> str:
    presented = request.headers.get("X-Request-ID")
    if presented is not None and 1 <= len(presented) <= 120:
        return presented
    return str(uuid4())


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> JSONResponse:
    """Create a strict host-cookie session without returning its bearer."""
    require_same_origin(request)
    try:
        grant = _identity_service(request).login(
            username=payload.username,
            password=payload.password.get_secret_value(),
            correlation_id=_correlation_id(request),
        )
    except AuthenticationFailedError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        ) from error
    response = JSONResponse(
        content={
            "csrf_token": grant.csrf_token,
            "expires_at": grant.expires_at.isoformat(),
            "user_id": grant.principal_user_id,
            "space_id": grant.principal_space_id,
        }
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=grant.session_token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_unsafe_request_protection),
    ],
) -> Response:
    """Revoke the current session and expire its exact host cookie."""
    session_token = request.cookies[SESSION_COOKIE_NAME]
    _identity_service(request).logout(
        session_token=session_token,
        principal_user_id=principal.user_id,
        principal_space_id=principal.space_id,
        correlation_id=_correlation_id(request),
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/session")
def current_session(
    request: Request,
    principal: Annotated[
        AuthenticatedPrincipal,
        Depends(require_authenticated_principal),
    ],
) -> dict[str, str]:
    """Return the principal and its stable CSRF token."""
    csrf_token = _session_manager(request).csrf_for_session(
        request.cookies.get(SESSION_COOKIE_NAME, "")
    )
    if csrf_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return {
        "user_id": principal.user_id,
        "space_id": principal.space_id,
        "username": principal.username,
        "csrf_token": csrf_token,
    }


__all__ = ("router",)
