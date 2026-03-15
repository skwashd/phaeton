"""
Storage backend abstraction.

Defines a ``StorageBackend`` protocol for raw I/O (read, write, delete,
list, exists) and a ``LocalStorageBackend`` implementation backed by the
local filesystem.  A factory function :func:`create_backend` detects
``s3://`` URIs and returns the appropriate backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for pluggable storage backends."""

    def read(self, key: str) -> str | None:
        """Read the content stored at *key*, or ``None`` if it does not exist."""
        ...

    def write(self, key: str, content: str) -> str:
        """Write *content* to *key* and return a location identifier."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object at *key*.  No error if it does not exist."""
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return keys whose names start with *prefix*."""
        ...

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        ...


class LocalStorageBackend:
    """Storage backend backed by a local directory."""

    def __init__(self, root: Path) -> None:
        """Initialize with the root directory."""
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def read(self, key: str) -> str | None:
        """Read the content stored at *key*, or ``None`` if it does not exist."""
        path = self._root / key
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, key: str, content: str) -> str:
        """Write *content* to *key* and return the absolute path as a string."""
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)

    def delete(self, key: str) -> None:
        """Delete the file at *key*.  No error if it does not exist."""
        path = self._root / key
        if path.exists():
            path.unlink()

    def list_keys(self, prefix: str = "") -> list[str]:
        """Return keys whose names start with *prefix*."""
        results: list[str] = []
        for path in self._root.iterdir():
            if path.is_file() and path.name.startswith(prefix):
                results.append(path.name)
        return sorted(results)

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        return (self._root / key).exists()


def create_backend(location: str) -> StorageBackend:
    """
    Create a storage backend from a location string.

    * Plain paths are wrapped in :class:`LocalStorageBackend`.
    * ``s3://bucket/prefix`` URIs produce an :class:`S3StorageBackend`
      (lazy-imported to avoid pulling in ``boto3`` unless needed).
    """
    if location.startswith("s3://"):
        from n8n_release_parser.storage_s3 import S3StorageBackend

        without_scheme = location[5:]
        parts = without_scheme.split("/", 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        return S3StorageBackend(bucket=bucket, prefix=prefix)

    return LocalStorageBackend(Path(location))
