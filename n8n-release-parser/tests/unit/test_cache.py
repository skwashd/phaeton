"""Tests for the cache module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from n8n_release_parser.cache import PARSER_VERSION, NodeCache, content_hash
from n8n_release_parser.models import NodeTypeEntry
from n8n_release_parser.parser import (
    extract_descriptions_from_package,
    parse_node_description,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_NODE: dict[str, Any] = {
    "displayName": "Set",
    "name": "n8n-nodes-base.set",
    "group": ["input"],
    "version": 1,
    "description": "Sets values",
    "defaults": {"name": "Set"},
    "inputs": ["main"],
    "outputs": ["main"],
    "properties": [],
}


def _make_entry(**overrides: object) -> NodeTypeEntry:
    """Create a minimal ``NodeTypeEntry`` for testing."""
    defaults: dict[str, object] = {
        "node_type": "n8n-nodes-base.set",
        "type_version": 1,
        "display_name": "Set",
    }
    defaults.update(overrides)
    return NodeTypeEntry(**defaults)  # type: ignore[arg-type]


def _write_node_file(base: Path, rel_path: str, desc: dict[str, Any]) -> Path:
    """Write a node JSON file under *base* and return its full path."""
    fp = base / rel_path
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(desc), encoding="utf-8")
    return fp


# ---------------------------------------------------------------------------
# NodeCache unit tests
# ---------------------------------------------------------------------------


class TestNodeCacheGetPut:
    """Tests for NodeCache get/put operations."""

    def test_put_and_get_roundtrip(self, tmp_path: Path) -> None:
        """Put entries and retrieve them by matching hash."""
        cache = NodeCache(tmp_path)
        entry = _make_entry()
        cache.put("nodes/Set.node.json", "abc123", [entry])

        result = cache.get("nodes/Set.node.json", "abc123")
        assert result is not None
        assert len(result) == 1
        assert result[0] == entry

    def test_get_returns_none_on_hash_mismatch(self, tmp_path: Path) -> None:
        """Cache miss when hash differs."""
        cache = NodeCache(tmp_path)
        cache.put("nodes/Set.node.json", "abc123", [_make_entry()])

        assert cache.get("nodes/Set.node.json", "different_hash") is None

    def test_get_returns_none_for_unknown_path(self, tmp_path: Path) -> None:
        """Cache miss for a path that was never cached."""
        cache = NodeCache(tmp_path)
        assert cache.get("nodes/Unknown.node.json", "abc123") is None


class TestNodeCacheRemove:
    """Tests for NodeCache.remove."""

    def test_remove_deletes_entry(self, tmp_path: Path) -> None:
        """Remove an existing cache entry."""
        cache = NodeCache(tmp_path)
        cache.put("nodes/Set.node.json", "abc123", [_make_entry()])
        cache.remove("nodes/Set.node.json")
        assert cache.get("nodes/Set.node.json", "abc123") is None

    def test_remove_nonexistent_is_noop(self, tmp_path: Path) -> None:
        """Removing a path that doesn't exist does not raise."""
        cache = NodeCache(tmp_path)
        cache.remove("nodes/missing.node.json")


class TestNodeCachePersistence:
    """Tests for NodeCache save/load."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Entries survive a save/load cycle."""
        cache = NodeCache(tmp_path)
        entry = _make_entry()
        cache.put("nodes/Set.node.json", "abc123", [entry])
        cache.save()

        cache2 = NodeCache(tmp_path)
        cache2.load()
        result = cache2.get("nodes/Set.node.json", "abc123")
        assert result is not None
        assert result[0] == entry

    def test_load_creates_empty_cache_when_no_file(self, tmp_path: Path) -> None:
        """Loading from a non-existent directory yields an empty cache."""
        cache = NodeCache(tmp_path / "nonexistent")
        cache.load()
        assert cache.known_paths() == set()

    def test_load_handles_corrupt_json(self, tmp_path: Path) -> None:
        """Corrupt cache file is discarded gracefully."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("NOT VALID JSON", encoding="utf-8")

        cache = NodeCache(tmp_path)
        cache.load()
        assert cache.known_paths() == set()

    def test_load_handles_invalid_structure(self, tmp_path: Path) -> None:
        """Cache file with wrong top-level type is discarded."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        cache = NodeCache(tmp_path)
        cache.load()
        assert cache.known_paths() == set()

    def test_load_handles_missing_fields(self, tmp_path: Path) -> None:
        """Cache file with missing entries field falls back to empty."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(
            json.dumps({"parser_version": PARSER_VERSION}),
            encoding="utf-8",
        )

        cache = NodeCache(tmp_path)
        cache.load()
        assert cache.known_paths() == set()


class TestNodeCacheVersionInvalidation:
    """Tests for parser-version based cache invalidation."""

    def test_version_change_invalidates_cache(self, tmp_path: Path) -> None:
        """Cache is discarded when the parser version changes."""
        cache = NodeCache(tmp_path)
        cache.put("nodes/Set.node.json", "abc123", [_make_entry()])
        cache.save()

        # Tamper with the saved version.
        cache_file = tmp_path / "cache.json"
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        data["parser_version"] = "0.0.0-old"
        cache_file.write_text(json.dumps(data), encoding="utf-8")

        cache2 = NodeCache(tmp_path)
        cache2.load()
        assert cache2.known_paths() == set()


# ---------------------------------------------------------------------------
# Integration with extract_descriptions_from_package
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Cache hit: unchanged file reuses cached entries without re-parsing."""

    def test_cache_hit_skips_parsing(self, tmp_path: Path) -> None:
        """Second call with same content does not call parse_node_description."""
        pkg = tmp_path / "pkg"
        _write_node_file(pkg, "nodes/Set/Set.node.json", SIMPLE_NODE)
        cache_dir = tmp_path / "cache"

        # First run — populates cache.
        first = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert len(first) == 1

        # Second run — should hit cache, not re-parse.
        with patch(
            "n8n_release_parser.parser.parse_node_description",
            wraps=parse_node_description,
        ) as mock_parse:
            second = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
            mock_parse.assert_not_called()

        assert second == first


class TestCacheMiss:
    """Cache miss: changed file content triggers re-parsing."""

    def test_changed_file_reparsed(self, tmp_path: Path) -> None:
        """Changing file content causes a re-parse and cache update."""
        pkg = tmp_path / "pkg"
        node_file = _write_node_file(pkg, "nodes/Set/Set.node.json", SIMPLE_NODE)
        cache_dir = tmp_path / "cache"

        first = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert first[0].description == "Sets values"

        # Modify the file.
        modified = {**SIMPLE_NODE, "description": "Updated description"}
        node_file.write_text(json.dumps(modified), encoding="utf-8")

        second = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert second[0].description == "Updated description"


class TestNewFile:
    """New file is parsed and cached."""

    def test_added_file_parsed(self, tmp_path: Path) -> None:
        """Adding a new node file picks it up on the next run."""
        pkg = tmp_path / "pkg"
        _write_node_file(pkg, "nodes/Set/Set.node.json", SIMPLE_NODE)
        cache_dir = tmp_path / "cache"

        first = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert len(first) == 1

        # Add a second node file.
        new_node = {**SIMPLE_NODE, "name": "n8n-nodes-base.code", "displayName": "Code"}
        _write_node_file(pkg, "nodes/Code/Code.node.json", new_node)

        second = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert len(second) == 2


class TestDeletedFile:
    """Deleted file has its cache entry removed."""

    def test_deleted_file_evicted(self, tmp_path: Path) -> None:
        """Removing a node file evicts its cache entry."""
        pkg = tmp_path / "pkg"
        node_file = _write_node_file(pkg, "nodes/Set/Set.node.json", SIMPLE_NODE)
        cache_dir = tmp_path / "cache"

        extract_descriptions_from_package(pkg, cache_dir=cache_dir)

        # Verify cache has the entry.
        cache = NodeCache(cache_dir)
        cache.load()
        assert len(cache.known_paths()) > 0

        # Delete the file and re-run.
        node_file.unlink()

        result = extract_descriptions_from_package(pkg, cache_dir=cache_dir)
        assert result == []

        # Verify cache entry was evicted.
        cache2 = NodeCache(cache_dir)
        cache2.load()
        assert len(cache2.known_paths()) == 0


class TestNoCache:
    """The --no-cache flag bypasses the cache."""

    def test_no_cache_always_parses(self, tmp_path: Path) -> None:
        """With no_cache=True every file is re-parsed."""
        pkg = tmp_path / "pkg"
        _write_node_file(pkg, "nodes/Set/Set.node.json", SIMPLE_NODE)

        with patch(
            "n8n_release_parser.parser.parse_node_description",
            wraps=parse_node_description,
        ) as mock_parse:
            extract_descriptions_from_package(pkg, no_cache=True)
            assert mock_parse.call_count == 1
            mock_parse.reset_mock()

            # Even a second call should re-parse.
            extract_descriptions_from_package(pkg, no_cache=True)
            assert mock_parse.call_count == 1


class TestContentHash:
    """Tests for the content_hash helper."""

    def test_deterministic(self) -> None:
        """Same bytes produce the same hash."""
        data = b"hello world"
        assert content_hash(data) == content_hash(data)

    def test_different_content_different_hash(self) -> None:
        """Different bytes produce different hashes."""
        assert content_hash(b"a") != content_hash(b"b")
