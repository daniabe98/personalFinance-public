"""FastAPI composition root."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.errors import install_problem_handlers
from app.api.router import api_router
from app.audit.adapters.bindings import (
    AuthenticationAuditBinding,
    LedgerAuditBinding,
    OutcomeAuditBinding,
)
from app.audit.adapters.repository import SqlAlchemyAuditRepository
from app.audit.application.service import AuditQueryService, DurableAuditService
from app.audit.domain.event import AuditAction, AuditResult
from app.identity.adapters.passwords import Argon2PasswordHasher
from app.identity.adapters.sessions import (
    OpaqueSessionManager,
    SqlAlchemyIdentityTransactionFactory,
)
from app.identity.application.service import IdentityService
from app.ledger.adapters.repositories import SqlAlchemyLedgerRepository
from app.ledger.application.catalog import CatalogService
from app.ledger.application.handlers import FinancialCommandService
from app.ledger.application.queries import LedgerQueryService
from app.ledger.application.reversal import ReversalService
from app.reconciliation.adapters.repository import SqlAlchemyReconciliationRepository
from app.reconciliation.application.service import ReconciliationService
from app.recovery.adapters.run_repository import SqlAlchemyBackupStatusReader
from app.recovery.application.status import BackupStatusQuery
from app.reporting.adapters.sql_queries import SqlAlchemyReportingLedgerReader
from app.reporting.application.queries import ReportQueryService
from app.shared.config import Settings, get_settings
from app.shared.database import create_engine, create_session_factory
from app.shared.models_identity import SpaceRecord
from app.shared.unit_of_work import UnitOfWorkFactory

ReadinessProbe = Callable[[], bool]


def packaged_spa() -> Path | None:
    """Resolve an explicit or wheel-packaged SPA without relying on the checkout."""
    configured = os.environ.get("PERSONAL_FINANCE_SPA_DIR")
    candidate = (
        Path(configured).resolve() if configured else Path(__file__).resolve().parent / "static"
    )
    index = candidate / "index.html"
    return candidate if index.is_file() else None


def _database_probe(settings: Settings) -> bool:
    engine = create_engine(settings.database_url, busy_timeout_ms=settings.busy_timeout_ms)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    finally:
        engine.dispose()


class _ReconciliationAuditBinding:
    """Adapt reconciliation's producer-owned port to durable audit."""

    def __init__(self, binding: OutcomeAuditBinding) -> None:
        self._binding = binding

    def record(
        self,
        session: object,
        *,
        action: str,
        outcome: str,
        space_id: str,
        reconciliation_id: str | None,
        correlation_id: str,
    ) -> None:
        if action != "complete_reconciliation":
            raise ValueError("unsupported reconciliation audit action")
        self._binding.record(
            session,
            action=AuditAction.RECONCILIATION,
            result=AuditResult(outcome),
            space_id=space_id,
            actor_id=None,
            entity_type="reconciliation" if reconciliation_id is not None else None,
            entity_id=reconciliation_id,
            correlation_id=correlation_id,
            metadata={"status": "COMPLETED" if outcome == "SUCCESS" else "FAILED"},
        )


def _compose_services(settings: Settings) -> dict[str, object]:
    """Compose all currently implemented capabilities on one database/UoW."""
    engine = create_engine(settings.database_url, busy_timeout_ms=settings.busy_timeout_ms)
    session_factory = create_session_factory(engine)
    unit_of_work_factory = UnitOfWorkFactory(session_factory)

    def now() -> datetime:
        return datetime.now(UTC)

    durable_audit = DurableAuditService(unit_of_work_factory, SqlAlchemyAuditRepository)
    authentication_audit = AuthenticationAuditBinding(durable_audit, clock=now)
    ledger_audit = LedgerAuditBinding(durable_audit, clock=now)
    reconciliation_audit = _ReconciliationAuditBinding(
        OutcomeAuditBinding(durable_audit, clock=now)
    )
    sessions = OpaqueSessionManager(session_factory)
    identity = IdentityService(
        transaction_factory=SqlAlchemyIdentityTransactionFactory(session_factory),
        password_hasher=Argon2PasswordHasher(),
        sessions=sessions,
        audit_sink=authentication_audit,
        clock=now,
    )
    catalog = CatalogService(unit_of_work_factory, SqlAlchemyLedgerRepository)
    space_ids: tuple[str, ...] = ()
    if inspect(engine).has_table(SpaceRecord.__tablename__):
        with session_factory() as database:
            space_ids = tuple(database.scalars(select(SpaceRecord.id)))
    for space_id in space_ids:
        catalog.ensure_starter_categories(space_id)
    return {
        "engine": engine,
        "identity_service": identity,
        "session_manager": sessions,
        "catalog_service": catalog,
        "financial_command_service": FinancialCommandService(
            unit_of_work_factory, SqlAlchemyLedgerRepository, ledger_audit
        ),
        "ledger_query_service": LedgerQueryService(
            unit_of_work_factory, SqlAlchemyLedgerRepository
        ),
        "reversal_service": ReversalService(
            unit_of_work_factory,
            SqlAlchemyLedgerRepository,
            ledger_audit,
            today=lambda: datetime.now(ZoneInfo(settings.domestic_timezone)).date(),
        ),
        "reconciliation_service": ReconciliationService(
            unit_of_work_factory,
            SqlAlchemyReconciliationRepository,
            reconciliation_audit,
        ),
        "report_query_service": ReportQueryService(
            unit_of_work_factory, SqlAlchemyReportingLedgerReader
        ),
        "audit_query_service": AuditQueryService(unit_of_work_factory, SqlAlchemyAuditRepository),
        "backup_status_query": BackupStatusQuery(
            SqlAlchemyBackupStatusReader(unit_of_work_factory),
            domestic_date=datetime.now(ZoneInfo(settings.domestic_timezone)).date(),
            retention_count=settings.backup_retention,
        ),
    }


def create_app(
    *,
    settings: Settings | None = None,
    readiness_probe: ReadinessProbe | None = None,
    identity_service: IdentityService | None = None,
    session_manager: object | None = None,
    allowed_origin: str | None = None,
    catalog_service: object | None = None,
    financial_command_service: object | None = None,
    ledger_query_service: object | None = None,
    reversal_service: object | None = None,
    reconciliation_service: object | None = None,
    report_query_service: object | None = None,
    audit_query_service: object | None = None,
    backup_status_query: object | None = None,
) -> FastAPI:
    """Create the HTTP application with explicit dependency injection seams."""
    resolved_settings = settings
    if resolved_settings is None and readiness_probe is None:
        resolved_settings = get_settings()
    if allowed_origin is None:
        allowed_origin = os.environ.get("PF_ALLOWED_ORIGIN")
    probe = readiness_probe or (
        lambda: _database_probe(
            resolved_settings if resolved_settings is not None else get_settings()
        )
    )
    composed: dict[str, Any] = {}
    if resolved_settings is not None and allowed_origin is not None:
        composed = _compose_services(resolved_settings)

    composed_engine = composed.get("engine")

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if isinstance(composed_engine, Engine):
                composed_engine.dispose()

    app = FastAPI(title="Personal Finance", lifespan=lifespan)
    app.state.identity_service = identity_service or composed.get("identity_service")
    app.state.session_manager = session_manager or composed.get("session_manager")
    app.state.allowed_origin = allowed_origin
    app.state.catalog_service = catalog_service or composed.get("catalog_service")
    app.state.financial_command_service = financial_command_service or composed.get(
        "financial_command_service"
    )
    app.state.ledger_query_service = ledger_query_service or composed.get("ledger_query_service")
    app.state.reversal_service = reversal_service or composed.get("reversal_service")
    app.state.reconciliation_service = reconciliation_service or composed.get(
        "reconciliation_service"
    )
    app.state.report_query_service = report_query_service or composed.get("report_query_service")
    app.state.audit_query_service = audit_query_service or composed.get("audit_query_service")
    app.state.backup_status_query = backup_status_query or composed.get("backup_status_query")
    app.state.database_engine = composed.get("engine")
    install_problem_handlers(app)
    app.include_router(api_router)
    if (
        app.state.identity_service is not None
        and app.state.session_manager is not None
        and allowed_origin is not None
    ):
        app.include_router(auth_router)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        try:
            is_ready = probe()
        except (OSError, RuntimeError, SQLAlchemyError):
            is_ready = False
        if not is_ready:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unavailable"},
            )
        return JSONResponse(content={"status": "ready"})

    spa = packaged_spa()
    if spa is not None:
        assets = spa / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="spa-assets")

        @app.api_route(
            "/api/{reserved_path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
            include_in_schema=False,
        )
        @app.api_route(
            "/health/{reserved_path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
            include_in_schema=False,
        )
        def reserved_not_found(reserved_path: str) -> None:
            del reserved_path
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        @app.get("/{spa_path:path}", include_in_schema=False)
        def spa_fallback(spa_path: str) -> FileResponse:
            if (
                spa_path == "api"
                or spa_path.startswith("api/")
                or spa_path == "health"
                or spa_path.startswith("health/")
                or spa_path == "assets"
                or spa_path.startswith("assets/")
            ):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
            return FileResponse(spa / "index.html", media_type="text/html")

    return app


__all__ = ("create_app", "packaged_spa")
