"""
Content-hash cache for parsed node descriptions.

Caches ``NodeTypeEntry`` results keyed by file path and SHA-256 content hash,
allowing ``extract_descriptions_from_package`` to skip re-parsing unchanged
``.node.json`` files on subsequent runs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from n8n_release_parser.models import NodeTypeEntry

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "phaeton" / "release-parser"
_CACHE_FILENAME = "cache.json"

# Tied to pyproject.toml version; bump forces full re-parse.
PARSER_VERSION = "0.1.0"


def content_hash(data: bytes) -> str:
    """Return the hex SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


class NodeCache:
    """JSON-file backed cache of parsed node descriptions."""

    def __init__(self, cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
        """Initialize with the given *cache_dir* for persistence."""
        self._cache_dir = cache_dir
        self._cache_file = cache_dir / _CACHE_FILENAME
        self._data: dict[str, dict[str, Any]] = {}
        self._parser_version: str = PARSER_VERSION
        self._dirty = False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the cache from disk, discarding it on version mismatch or corruption."""
        if not self._cache_file.is_file():
            return
        try:
            raw = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Cache file corrupt; starting fresh")
            self._data = {}
            self._dirty = True
            return

        if not isinstance(raw, dict):
            logger.warning("Cache file corrupt; starting fresh")
            self._data = {}
            self._dirty = True
            return

        stored_version = raw.get("parser_version", "")
        if stored_version != self._parser_version:
            logger.info(
                "Cache parser version changed (%s -> %s); invalidating",
                stored_version,
                self._parser_version,
            )
            self._data = {}
            self._dirty = True
            return

        entries = raw.get("entries", {})
        if not isinstance(entries, dict):
            logger.warning("Cache file corrupt; starting fresh")
            self._data = {}
            self._dirty = True
            return

        self._data = entries

    def save(self) -> None:
        """Persist the cache to disk if it has been modified."""
        if not self._dirty:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "parser_version": self._parser_version,
            "entries": self._data,
        }
        self._cache_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._dirty = False

    # ------------------------------------------------------------------
    # Lookup / mutation
    # ------------------------------------------------------------------

    def get(self, file_path: str, file_hash: str) -> list[NodeTypeEntry] | None:
        """Return cached entries when *file_hash* matches, else ``None``."""
        entry = self._data.get(file_path)
        if entry is None:
            return None
        if entry.get("sha256") != file_hash:
            return None
        try:
            return [NodeTypeEntry.model_validate(e) for e in entry["entries"]]
        except KeyError, TypeError, ValueError:
            logger.warning("Failed to deserialize cache entry for %s", file_path)
            return None

    def put(self, file_path: str, file_hash: str, entries: list[NodeTypeEntry]) -> None:
        """Store parsed entries for *file_path* with its content hash."""
        self._data[file_path] = {
            "sha256": file_hash,
            "entries": [e.model_dump(mode="json") for e in entries],
        }
        self._dirty = True

    def remove(self, file_path: str) -> None:
        """Remove a cached entry (e.g. when the source file is deleted)."""
        if self._data.pop(file_path, None) is not None:
            self._dirty = True

    def known_paths(self) -> set[str]:
        """Return the set of file paths currently in the cache."""
        return set(self._data)
