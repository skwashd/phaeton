"""
Node catalog storage.

Manages persistence for the versioned node catalog, supporting storage
across multiple n8n releases and lookup by (nodeType, typeVersion) pairs.
Uses a directory of JSON files as the storage backend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from n8n_release_parser.differ import build_cumulative_catalog
from n8n_release_parser.models import NodeApiMapping, NodeCatalog, NodeTypeEntry

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
    """Manages catalog persistence using JSON files."""

    def __init__(self, store_dir: Path) -> None:
        """Initialize with the storage directory."""
        self._store_dir = store_dir
        self._store_dir.mkdir(parents=True, exist_ok=True)

    def save_catalog(self, catalog: NodeCatalog) -> Path:
        """
        Save a catalog to disk.

        Filename: ``catalog_{n8n_version}.json`` where dots in the version
        are replaced with underscores.
        """
        safe_version = _version_to_filename(catalog.n8n_version)
        path = self._store_dir / f"catalog_{safe_version}.json"
        path.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_catalog(self, n8n_version: str) -> NodeCatalog | None:
        """
        Load a specific version's catalog.

        Returns ``None`` if no file exists for the requested version.
        """
        safe_version = _version_to_filename(n8n_version)
        path = self._store_dir / f"catalog_{safe_version}.json"
        if not path.exists():
            return None
        return NodeCatalog.model_validate_json(path.read_text(encoding="utf-8"))

    def list_catalogs(self) -> list[tuple[str, datetime]]:
        """
        List all stored catalogs with release dates, sorted newest-first.

        Scans for ``catalog_*.json`` files, deserialises each, and returns
        ``(n8n_version, release_date)`` tuples ordered by ``release_date``
        descending.
        """
        results: list[tuple[str, datetime]] = []
        for path in self._store_dir.glob("catalog_*.json"):
            catalog = NodeCatalog.model_validate_json(
                path.read_text(encoding="utf-8"),
            )
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
        for path in self._store_dir.glob("catalog_*.json"):
            catalog = NodeCatalog.model_validate_json(
                path.read_text(encoding="utf-8"),
            )
            age_days = (now - catalog.release_date).days
            if age_days > months * 30:
                path.unlink()
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
        for path in self._store_dir.glob("catalog_*.json"):
            catalogs.append(
                NodeCatalog.model_validate_json(
                    path.read_text(encoding="utf-8"),
                ),
            )
        catalogs.sort(key=lambda c: c.release_date)
        return build_cumulative_catalog(catalogs)

    def save_api_mappings(self, mappings: list[NodeApiMapping]) -> Path:
        """Save API spec mappings to ``api_mappings.json``."""
        from pydantic import TypeAdapter

        adapter = TypeAdapter(list[NodeApiMapping])
        path = self._store_dir / _API_MAPPINGS_FILENAME
        path.write_text(adapter.dump_json(mappings).decode(), encoding="utf-8")
        return path

    def load_api_mappings(self) -> list[NodeApiMapping]:
        """
        Load saved API spec mappings.

        Returns an empty list when the file does not exist.
        """
        from pydantic import TypeAdapter

        path = self._store_dir / _API_MAPPINGS_FILENAME
        if not path.exists():
            return []
        adapter = TypeAdapter(list[NodeApiMapping])
        return list(adapter.validate_json(path.read_text(encoding="utf-8")))
