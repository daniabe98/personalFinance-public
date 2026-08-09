"""Atomic same-filesystem publication and verified-only retention."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class BackupStoreError(RuntimeError):
    """A recovery artifact could not be safely published or removed."""


class AtomicBackupStore:
    def temporary_for(self, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        return Path(raw_path)

    def publish(self, temporary: Path, destination: Path) -> None:
        if temporary.parent.resolve() != destination.parent.resolve():
            raise BackupStoreError("temporary and destination must share a filesystem directory")
        try:
            self._sync_file(temporary)
            os.replace(temporary, destination)
            self._sync_directory(destination.parent)
        except OSError as error:
            raise BackupStoreError("atomic recovery publication failed") from error

    def cleanup(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise BackupStoreError("recovery cleanup failed") from error

    def prune_verified(self, verified: tuple[Path, ...], *, keep: int) -> None:
        if keep < 1:
            raise ValueError("retention must keep at least one verified backup")
        for obsolete in verified[keep:]:
            self.cleanup(obsolete)
            self._sync_directory(obsolete.parent)

    @staticmethod
    def _sync_file(path: Path) -> None:
        with path.open("rb+") as stream:
            os.fsync(stream.fileno())

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


__all__ = ("AtomicBackupStore", "BackupStoreError")
