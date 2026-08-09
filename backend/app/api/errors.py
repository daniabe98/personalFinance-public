"""Stable, minimized RFC 9457-style problem responses."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.ledger.domain.errors import (
    ArchivedEntityError,
    EntityNotFoundError,
    InvalidLifecycleError,
    LedgerError,
    OwnershipError,
    UnbalancedTransactionError,
)
from app.reconciliation.domain.errors import ReconciliationError
from app.shared.idempotency import IdempotencyConflictError, IdempotencyInProgressError

PROBLEM_MEDIA_TYPE = "application/problem+json"


@dataclass(frozen=True, slots=True)
class Problem:
    status: int
    code: str
    title: str
    detail: str

    def response(self, request: Request) -> JSONResponse:
        return JSONResponse(
            status_code=self.status,
            media_type=PROBLEM_MEDIA_TYPE,
            content={
                "type": f"https://personal-finance.local/problems/{self.code}",
                "title": self.title,
                "status": self.status,
                "detail": self.detail,
                "code": self.code,
                "instance": request.url.path,
            },
        )


def _http_problem(error: HTTPException) -> Problem:
    if error.status_code == status.HTTP_401_UNAUTHORIZED:
        return Problem(
            401,
            "authentication_required",
            "Inicia sesión",
            "Necesitas una sesión válida.",
        )
    if error.status_code == status.HTTP_403_FORBIDDEN:
        return Problem(
            403,
            "request_not_allowed",
            "Petición no permitida",
            "Recarga la página e inténtalo de nuevo.",
        )
    return Problem(
        error.status_code,
        "request_failed",
        "No se pudo completar",
        "Revisa la petición.",
    )


def _domain_problem(error: Exception) -> Problem:
    if isinstance(error, EntityNotFoundError):
        return Problem(404, "not_found", "No encontrado", "El elemento solicitado no existe.")
    if isinstance(error, OwnershipError):
        return Problem(404, "not_found", "No encontrado", "El elemento solicitado no existe.")
    if isinstance(error, ArchivedEntityError):
        return Problem(
            409, "archived_entity", "Elemento archivado", "Desarchívalo antes de continuar."
        )
    if isinstance(error, (IdempotencyConflictError, IdempotencyInProgressError)):
        return Problem(
            409,
            "idempotency_conflict",
            "Operación ya utilizada",
            "Usa una clave nueva para una operación diferente.",
        )
    if isinstance(error, InvalidLifecycleError):
        return Problem(
            409,
            "invalid_state",
            "Cambio no permitido",
            "Actualiza la información y vuelve a intentarlo.",
        )
    if isinstance(error, UnbalancedTransactionError):
        return Problem(
            422,
            "invalid_operation",
            "Operación no válida",
            "Revisa los datos de la operación.",
        )
    return Problem(
        422,
        "business_rule",
        "No se pudo completar",
        "Revisa los datos y vuelve a intentarlo.",
    )


def install_problem_handlers(app: FastAPI) -> None:
    """Install the sole public error translation boundary."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, error: HTTPException) -> JSONResponse:
        if request.url.path.startswith("/api/v1/auth/"):
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": str(error.detail)},
                headers=error.headers,
            )
        return _http_problem(error).response(request)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del error
        return Problem(
            422,
            "invalid_request",
            "Datos no válidos",
            "Revisa los campos enviados.",
        ).response(request)

    @app.exception_handler(LedgerError)
    @app.exception_handler(ReconciliationError)
    @app.exception_handler(IdempotencyConflictError)
    @app.exception_handler(IdempotencyInProgressError)
    @app.exception_handler(ValueError)
    async def domain_exception_handler(request: Request, error: Exception) -> JSONResponse:
        return _domain_problem(error).response(request)


__all__ = ("install_problem_handlers",)
