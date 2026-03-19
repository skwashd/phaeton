"""
Node catalog storage.

Manages persistence for the versioned node catalog, supporting storage
across multiple n8n releases and lookup by (nodeType, typeVersion) pairs.
Delegates raw I/O to a :class:`~n8n_release_parser.storage.StorageBackend`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from phaeton_models.spec import NodeApiMapping

from n8n_release_parser.differ import build_cumulative_catalog
from n8n_release_parser.models import NodeCatalog, NodeTypeEntry
from n8n_release_parser.storage import LocalStorageBackend, StorageBackend

_API_MAPPINGS_FILENAME = "api_mappings.json"


def _version_to_filename(version: str) -> str:
    """
    Convert a dotted version string to a safe filename component.

    Dots are replaced with underscores (e.g. ``1.20.0`` becomes ``1_20_0``).
    """
    return version.replace(".", "_")


def _filename_to_version(stem: str) -> str:
    """
    Extract the dotted version string from a catalog filename stem.

    The inverse of :func:`_version_to_filename`: strip the ``catalog_``
    prefix and convert underscores back to dots.
    """
    raw = stem.removeprefix("catalog_")
    return raw.replace("_", ".")


class NodeCatalogStore:
    """Manages catalog persistence via a pluggable storage backend."""

    def __init__(self, store_dir_or_backend: Path | StorageBackend) -> None:
        """Initialize with a directory path or a storage backend."""
        if isinstance(store_dir_or_backend, Path):
            self._backend: StorageBackend = LocalStorageBackend(store_dir_or_backend)
        else:
            self._backend = store_dir_or_backend

    def save_catalog(self, catalog: NodeCatalog) -> str:
        """
        Save a catalog.

        Filename: ``catalog_{n8n_version}.json`` where dots in the version
        are replaced with underscores.

        Returns the location identifier (path or URI).
        """
        safe_version = _version_to_filename(catalog.n8n_version)
        key = f"catalog_{safe_version}.json"
        return self._backend.write(key, catalog.model_dump_json(indent=2))

    def load_catalog(self, n8n_version: str) -> NodeCatalog | None:
        """
        Load a specific version's catalog.

        Returns ``None`` if no file exists for the requested version.
        """
        safe_version = _version_to_filename(n8n_version)
        key = f"catalog_{safe_version}.json"
        content = self._backend.read(key)
        if content is None:
            return None
        return NodeCatalog.model_validate_json(content)

    def list_catalogs(self) -> list[tuple[str, datetime]]:
        """
        List all stored catalogs with release dates, sorted newest-first.

        Scans for ``catalog_*.json`` keys, deserialises each, and returns
        ``(n8n_version, release_date)`` tuples ordered by ``release_date``
        descending.
        """
        results: list[tuple[str, datetime]] = []
        for key in self._backend.list_keys("catalog_"):
            content = self._backend.read(key)
            if content is None:
                continue
            catalog = NodeCatalog.model_validate_json(content)
            results.append((catalog.n8n_version, catalog.release_date))
        results.sort(key=lambda item: item[1], reverse=True)
        return results

    def prune_old_catalogs(self, months: int = 12) -> list[str]:
        """
        Remove catalogs older than *months* months.

        Returns the list of pruned version strings.
        """
        now = datetime.now(tz=UTC)
        pruned: list[str] = []
        for key in self._backend.list_keys("catalog_"):
            content = self._backend.read(key)
            if content is None:
                continue
            catalog = NodeCatalog.model_validate_json(content)
            age_days = (now - catalog.release_date).days
            if age_days > months * 30:
                self._backend.delete(key)
                pruned.append(catalog.n8n_version)
        return pruned

    def build_lookup(self) -> dict[tuple[str, int], NodeTypeEntry]:
        """
        Build cumulative lookup map from all stored catalogs.

        Loads every catalog file, sorts them by ``release_date``
        oldest-first, and delegates to
        :func:`~n8n_release_parser.differ.build_cumulative_catalog`.
        """
        catalogs: list[NodeCatalog] = []
        for key in self._backend.list_keys("catalog_"):
            content = self._backend.read(key)
            if content is None:
                continue
            catalogs.append(NodeCatalog.model_validate_json(content))
        catalogs.sort(key=lambda c: c.release_date)
        return build_cumulative_catalog(catalogs)

    def save_api_mappings(self, mappings: list[NodeApiMapping]) -> str:
        """Save API spec mappings to ``api_mappings.json``."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(list[NodeApiMapping])
        content = adapter.dump_json(mappings).decode()
        return self._backend.write(_API_MAPPINGS_FILENAME, content)

    def load_api_mappings(self) -> list[NodeApiMapping]:
        """
        Load saved API spec mappings.

        Returns an empty list when the file does not exist.
        """
        from pydantic import TypeAdapter

        content = self._backend.read(_API_MAPPINGS_FILENAME)
        if content is None:
            return []
        adapter = TypeAdapter(list[NodeApiMapping])
        return list(adapter.validate_json(content))
