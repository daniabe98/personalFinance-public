"""Consistent SQLite online backup and fresh-connection verification."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class SqliteBackupError(RuntimeError):
    """SQLite could not produce or verify a recovery artifact."""


class SqliteOnlineBackup:
    def copy(self, source: Path, destination: Path) -> None:
        if not source.is_file():
            raise SqliteBackupError("source database is unavailable")
        try:
            with (
                closing(sqlite3.connect(source)) as source_connection,
                closing(sqlite3.connect(destination)) as destination_connection,
            ):
                source_connection.backup(destination_connection)
        except sqlite3.Error as error:
            raise SqliteBackupError("SQLite online backup failed") from error

    def verify(self, database: Path) -> bool:
        if not database.is_file():
            return False
        uri = f"{database.resolve().as_uri()}?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                rows = tuple(row[0] for row in connection.execute("PRAGMA integrity_check"))
        except sqlite3.Error:
            return False
        return rows == ("ok",)


__all__ = ("SqliteBackupError", "SqliteOnlineBackup")
