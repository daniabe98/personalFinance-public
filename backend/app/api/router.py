"""Single versioned HTTP composition surface."""

from fastapi import APIRouter, Security
from fastapi.security import APIKeyCookie

from app.api.audit import router as audit_router
from app.api.catalog import router as catalog_router
from app.api.reconciliations import router as reconciliations_router
from app.api.recovery import router as recovery_router
from app.api.reports import router as reports_router
from app.api.transactions import router as transactions_router

_session_cookie = APIKeyCookie(name="__Host-pf_session", auto_error=False)
api_router = APIRouter(
    prefix="/api/v1",
    dependencies=[Security(_session_cookie)],
)
api_router.include_router(catalog_router)
api_router.include_router(transactions_router)
api_router.include_router(reconciliations_router)
api_router.include_router(reports_router)
api_router.include_router(audit_router)
api_router.include_router(recovery_router)

__all__ = ("api_router",)
