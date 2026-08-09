"""Local-only bootstrap and credential recovery entry point."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from app.identity.application.service import (
    BootstrapAlreadyCompletedError,
    BootstrapRequiredError,
    IdentityService,
)
from app.recovery.application.backup import BackupOperationError, BackupService
from app.recovery.application.restore import RestoreRejectedError, RestoreService
from app.recovery.domain.models import BackupOutcome

EXIT_SUCCESS = 0
EXIT_ALREADY_CONFIGURED = 2
EXIT_BOOTSTRAP_REQUIRED = 3
EXIT_PASSWORD_MISMATCH = 4
EXIT_BACKUP_ALREADY_VALID = 5
EXIT_RECOVERY_FAILED = 6


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal-finance")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="create or upgrade the local database schema")
    bootstrap = commands.add_parser("bootstrap", help="create the local identity once")
    bootstrap.add_argument("--username", required=True)
    bootstrap.add_argument("--space-name", required=True)
    commands.add_parser("reset-credentials", help="rotate the local credential")
    backup = commands.add_parser("backup", help="create today's verified local backup")
    backup.add_argument("--if-due", action="store_true", required=True)
    restore = commands.add_parser("restore", help="restore to a new isolated local database")
    restore.add_argument("--source", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    return parser


def _default_service() -> IdentityService:
    from app.identity.adapters.sessions import build_identity_service

    return build_identity_service()


class _RecoveryAuditAdapter:
    def __init__(self, binding: object) -> None:
        self._binding = binding

    def record(
        self,
        session: object,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None:
        from app.audit.adapters.bindings import OutcomeAuditBinding
        from app.audit.domain.event import AuditAction, AuditResult

        if not isinstance(self._binding, OutcomeAuditBinding):
            raise TypeError("recovery audit binding is unavailable")
        self._binding.record(
            session,
            action=AuditAction(action),
            result=AuditResult(result),
            space_id=None,
            actor_id=None,
            entity_type=None,
            entity_id=None,
            correlation_id=correlation_id,
            metadata={"verification_status": verification_status},
        )

    def record_durable(
        self,
        *,
        action: str,
        result: str,
        correlation_id: str,
        verification_status: str,
    ) -> None:
        from app.audit.adapters.bindings import OutcomeAuditBinding
        from app.audit.domain.event import AuditAction, AuditResult

        if not isinstance(self._binding, OutcomeAuditBinding):
            raise TypeError("recovery audit binding is unavailable")
        self._binding.record_durable(
            action=AuditAction(action),
            result=AuditResult(result),
            space_id=None,
            actor_id=None,
            entity_type=None,
            entity_id=None,
            correlation_id=correlation_id,
            metadata={"verification_status": verification_status},
        )


def _recovery_dependencies():
    from app.audit.adapters.bindings import OutcomeAuditBinding
    from app.audit.adapters.repository import SqlAlchemyAuditRepository
    from app.audit.application.service import DurableAuditService
    from app.shared.config import get_settings
    from app.shared.database import create_engine, create_session_factory
    from app.shared.unit_of_work import UnitOfWorkFactory

    settings = get_settings()
    database_name = make_url(settings.database_url).database
    if database_name is None or database_name == ":memory:":
        raise RuntimeError("recovery requires a file-backed SQLite database")
    active_database = Path(database_name).resolve(strict=True)
    engine = create_engine(settings.database_url, busy_timeout_ms=settings.busy_timeout_ms)
    unit_of_work_factory = UnitOfWorkFactory(create_session_factory(engine))
    durable_audit = DurableAuditService(unit_of_work_factory, SqlAlchemyAuditRepository)
    audit = _RecoveryAuditAdapter(
        OutcomeAuditBinding(durable_audit, clock=lambda: datetime.now(UTC))
    )
    return settings, active_database, unit_of_work_factory, audit, engine


def _active_database(*, must_exist: bool) -> Path:
    from app.shared.config import get_settings

    database_name = make_url(get_settings().database_url).database
    if database_name is None or database_name == ":memory:":
        raise RuntimeError("the command requires a file-backed SQLite database")
    return Path(database_name).resolve(strict=must_exist)


@contextmanager
def _default_backup_service():
    from app.recovery.adapters.filesystem import AtomicBackupStore
    from app.recovery.adapters.run_repository import SqlAlchemyBackupRunRepository
    from app.recovery.adapters.sqlite_backup import SqliteOnlineBackup

    settings, active_database, unit_of_work_factory, audit, engine = _recovery_dependencies()
    try:
        yield BackupService(
            source_database=active_database,
            backup_directory=settings.backup_directory,
            domestic_timezone=settings.domestic_timezone,
            retention=settings.backup_retention,
            unit_of_work_factory=unit_of_work_factory,
            repository_factory=SqlAlchemyBackupRunRepository,
            sqlite_backup=SqliteOnlineBackup(),
            store=AtomicBackupStore(),
            audit=audit,
            clock=lambda: datetime.now(UTC),
        )
    finally:
        engine.dispose()


@contextmanager
def _default_restore_service():
    from app.recovery.adapters.alembic_migration import AlembicSchemaMigrator
    from app.recovery.adapters.filesystem import AtomicBackupStore
    from app.recovery.adapters.run_repository import SqlAlchemyBackupRunRepository
    from app.recovery.adapters.sqlite_backup import SqliteOnlineBackup

    _, active_database, unit_of_work_factory, audit, engine = _recovery_dependencies()
    try:
        yield RestoreService(
            active_database=active_database,
            unit_of_work_factory=unit_of_work_factory,
            repository_factory=SqlAlchemyBackupRunRepository,
            sqlite_backup=SqliteOnlineBackup(),
            store=AtomicBackupStore(),
            migrator=AlembicSchemaMigrator(),
            audit=audit,
        )
    finally:
        engine.dispose()


def _read_confirmed_password(password_prompt: Callable[[str], str]) -> str | None:
    password = password_prompt("Password: ")
    confirmation = password_prompt("Confirm password: ")
    if password != confirmation:
        return None
    return password


def app(
    argv: Sequence[str] | None = None,
    *,
    service: IdentityService | None = None,
    backup_service: BackupService | None = None,
    restore_service: RestoreService | None = None,
    password_prompt: Callable[[str], str] = getpass.getpass,
    stdout: Callable[[str], object] | None = None,
    stderr: Callable[[str], object] | None = None,
) -> int:
    """Run one local command without accepting credentials through argv."""
    write_out = stdout or (lambda message: sys.stdout.write(f"{message}\n"))
    write_error = stderr or (lambda message: sys.stderr.write(f"{message}\n"))
    args = _parser().parse_args(argv)
    if args.command == "migrate":
        from app.recovery.adapters.alembic_migration import (
            AlembicSchemaMigrator,
            SchemaMigrationError,
        )

        try:
            AlembicSchemaMigrator().initialize(_active_database(must_exist=False))
        except (OSError, RuntimeError, SchemaMigrationError):
            write_error("Database migration failed.")
            return EXIT_RECOVERY_FAILED
        write_out("Database schema is ready.")
        return EXIT_SUCCESS
    if args.command == "backup":
        service_context = (
            nullcontext(backup_service) if backup_service is not None else _default_backup_service()
        )
        with service_context as resolved_backup_service:
            try:
                outcome = resolved_backup_service.run_if_due(correlation_id=uuid4().hex)
            except BackupOperationError:
                write_error("Backup failed; no new valid backup was declared.")
                return EXIT_RECOVERY_FAILED
        if outcome is BackupOutcome.ALREADY_VALID:
            write_out("A verified backup already exists today.")
            return EXIT_BACKUP_ALREADY_VALID
        write_out("Backup created and verified.")
        return EXIT_SUCCESS
    if args.command == "restore":
        service_context = (
            nullcontext(restore_service)
            if restore_service is not None
            else _default_restore_service()
        )
        with service_context as resolved_restore_service:
            try:
                resolved_restore_service.restore_isolated(
                    source=args.source,
                    destination=args.destination,
                    correlation_id=uuid4().hex,
                )
            except RestoreRejectedError:
                write_error("Restore failed; no isolated destination was published.")
                return EXIT_RECOVERY_FAILED
        write_out("Backup restored to an isolated destination and verified.")
        return EXIT_SUCCESS

    password = _read_confirmed_password(password_prompt)
    if password is None:
        write_error("Passwords do not match.")
        return EXIT_PASSWORD_MISMATCH
    identity = service or _default_service()

    try:
        if args.command == "bootstrap":
            identity.bootstrap(
                username=args.username,
                password=password,
                space_name=args.space_name,
            )
            write_out("Local identity configured.")
        else:
            identity.reset_credentials(
                new_password=password,
                correlation_id=str(uuid4()),
            )
            write_out("Credentials updated; prior sessions were revoked.")
    except BootstrapAlreadyCompletedError:
        write_error("Local identity is already configured.")
        return EXIT_ALREADY_CONFIGURED
    except BootstrapRequiredError:
        write_error("Local identity must be configured first.")
        return EXIT_BOOTSTRAP_REQUIRED
    return EXIT_SUCCESS


def main() -> int:
    return app()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "EXIT_BACKUP_ALREADY_VALID",
    "EXIT_RECOVERY_FAILED",
    "EXIT_SUCCESS",
    "app",
    "main",
)
