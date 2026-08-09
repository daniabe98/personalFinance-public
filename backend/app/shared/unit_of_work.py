"""Command-scoped SQLAlchemy transaction ownership."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, SessionTransaction

from app.shared.database import SessionFactory


class SqlAlchemyUnitOfWork:
    """Own exactly one session and transaction for one application command."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._transaction: SessionTransaction | None = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work has not been entered")
        return self._session

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError("unit of work cannot be entered twice")
        self._session = self._session_factory()
        self._transaction = self._session.begin()
        return self

    def commit(self) -> None:
        """Commit the active command transaction explicitly."""
        if self._transaction is None or not self._transaction.is_active:
            raise RuntimeError("unit of work has no active transaction")
        try:
            self._transaction.commit()
        except BaseException:
            self._rollback()
            raise

    def _rollback(self) -> None:
        if self._transaction is not None and self._transaction.is_active:
            self._transaction.rollback()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        del exception_type, exception, traceback
        try:
            self._rollback()
        finally:
            if self._session is not None:
                self._session.close()
            self._session = None
            self._transaction = None
        return False


class UnitOfWorkFactory:
    """Injectable callable that creates fresh command scopes."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)


__all__ = ("SqlAlchemyUnitOfWork", "UnitOfWorkFactory")
