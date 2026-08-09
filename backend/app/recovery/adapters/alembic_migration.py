"""Alembic migration constrained to an isolated recovery database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from importlib.resources import as_file, files
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command


class SchemaMigrationError(RuntimeError):
    """The isolated database could not be brought to the supported schema."""


class AlembicSchemaMigrator:
    def __init__(self, *, backend_root: Path | None = None) -> None:
        self._backend_root = backend_root.resolve() if backend_root is not None else None

    def migrate_and_verify(self, database: Path) -> None:
        if not database.is_file():
            raise SchemaMigrationError("isolated database is unavailable")
        self._migrate_from_available_resources(database)

    def initialize(self, database: Path) -> None:
        """Create or upgrade the configured active database."""
        database.parent.mkdir(parents=True, exist_ok=True)
        self._migrate_from_available_resources(database)

    def _migrate_from_available_resources(self, database: Path) -> None:
        if self._backend_root is not None:
            self._migrate(
                database, self._backend_root / "alembic.ini", self._backend_root / "alembic"
            )
            return
        package = files("app")
        packaged_config = package.joinpath("alembic.ini")
        if not packaged_config.is_file():
            backend_root = Path(__file__).parents[3]
            self._migrate(database, backend_root / "alembic.ini", backend_root / "alembic")
            return
        with (
            as_file(packaged_config) as config_path,
            as_file(package.joinpath("_migrations")) as migrations_path,
        ):
            self._migrate(database, config_path, migrations_path)

    @staticmethod
    def _migrate(database: Path, config_path: Path, migrations_path: Path) -> None:
        config = Config(str(config_path))
        config.set_main_option("script_location", str(migrations_path))
        config.set_main_option(
            "sqlalchemy.url",
            f"sqlite+pysqlite:///{database.resolve().as_posix()}",
        )
        try:
            command.upgrade(config, "head")
            expected_head = ScriptDirectory.from_config(config).get_current_head()
            with closing(sqlite3.connect(database)) as connection:
                actual_head_row = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()
        except (sqlite3.Error, RuntimeError) as error:
            raise SchemaMigrationError("isolated schema migration failed") from error
        actual_head = None if actual_head_row is None else actual_head_row[0]
        if expected_head is None or actual_head != expected_head:
            raise SchemaMigrationError("isolated schema did not reach the supported head")


__all__ = ("AlembicSchemaMigrator", "SchemaMigrationError")
