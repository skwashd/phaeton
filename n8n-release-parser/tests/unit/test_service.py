"""Tests for the service layer."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from n8n_release_parser import service
from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.models import (
    NodeCatalog,
    NodeTypeEntry,
    NpmVersionInfo,
)


def _make_entry(
    node_type: str = "n8n-nodes-base.slack",
    type_version: int = 1,
    display_name: str = "Slack",
) -> NodeTypeEntry:
    """Create a minimal node type entry for testing."""
    return NodeTypeEntry(
        node_type=node_type,
        type_version=type_version,
        display_name=display_name,
    )


def _make_catalog(
    version: str,
    release_date: datetime,
    entries: list[NodeTypeEntry] | None = None,
) -> NodeCatalog:
    """Create a minimal catalog for testing."""
    return NodeCatalog(
        n8n_version=version,
        release_date=release_date,
        entries=entries or [],
    )


class TestListVersions:
    """Tests for the list_versions service function."""

    def test_list_versions_calls_fetcher(self) -> None:
        """Test list_versions delegates to fetcher."""
        expected = [
            NpmVersionInfo(
                version="1.20.0",
                publish_date=datetime(2025, 2, 1, tzinfo=UTC),
                tarball_url="https://example.com/1.20.0.tgz",
            ),
        ]
        with patch(
            "n8n_release_parser.service.list_versions",
            wraps=service.list_versions,
        ), patch(
            "n8n_release_parser.fetcher.list_versions",
            return_value=expected,
        ):
            result = service.list_versions(months=6)

        assert result == expected


class TestFetchReleases:
    """Tests for the fetch_releases service function."""

    def test_fetch_releases_delegates_to_list_versions(self) -> None:
        """Test fetch_releases is an alias for list_versions."""
        expected = [
            NpmVersionInfo(
                version="1.20.0",
                publish_date=datetime(2025, 2, 1, tzinfo=UTC),
                tarball_url="https://example.com/1.20.0.tgz",
            ),
        ]
        with patch(
            "n8n_release_parser.fetcher.list_versions",
            return_value=expected,
        ):
            result = service.fetch_releases(months=3)

        assert result == expected


class TestDiffCatalogs:
    """Tests for the diff_catalogs service function."""

    def test_diff_catalogs_success(self, tmp_path: Path) -> None:
        """Test diff_catalogs returns a ReleaseDiff."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog(
                "1.19.0",
                datetime(2025, 1, 1, tzinfo=UTC),
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack")],
            ),
        )
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=[
                    _make_entry("n8n-nodes-base.slack", 1, "Slack Updated"),
                    _make_entry("n8n-nodes-base.discord", 1, "Discord"),
                ],
            ),
        )

        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)
        result = service.diff_catalogs(backend, "1.19.0", "1.20.0")

        assert result.from_version == "1.19.0"
        assert result.to_version == "1.20.0"
        assert result.added_count == 1

    def test_diff_catalogs_missing_old_version(self, tmp_path: Path) -> None:
        """Test diff_catalogs raises ValueError for missing old catalog."""
        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            service.diff_catalogs(backend, "1.19.0", "1.20.0")

    def test_diff_catalogs_missing_new_version(self, tmp_path: Path) -> None:
        """Test diff_catalogs raises ValueError for missing new catalog."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog("1.19.0", datetime(2025, 1, 1, tzinfo=UTC)),
        )

        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            service.diff_catalogs(backend, "1.19.0", "1.20.0")


class TestBuildCatalog:
    """Tests for the build_catalog service function."""

    def test_build_catalog_success(self, tmp_path: Path) -> None:
        """Test build_catalog returns lookup dict."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack")],
            ),
        )

        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)
        result = service.build_catalog(backend)

        assert ("n8n-nodes-base.slack", 1) in result

    def test_build_catalog_empty_store(self, tmp_path: Path) -> None:
        """Test build_catalog with empty store returns empty dict."""
        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)
        result = service.build_catalog(backend)

        assert result == {}


class TestGenerateReport:
    """Tests for the generate_report service function."""

    def test_generate_report_success(self, tmp_path: Path) -> None:
        """Test generate_report returns report dict."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack")],
            ),
        )

        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)
        result = service.generate_report(backend)

        assert "total_priority_nodes" in result
        assert "mapped_priority_nodes" in result
        assert "missing_mappings" in result
        assert "breakdown" in result

    def test_generate_report_empty_store(self, tmp_path: Path) -> None:
        """Test generate_report raises ValueError for empty store."""
        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)

        with pytest.raises(ValueError, match="No catalogs found"):
            service.generate_report(backend)


class TestListCatalogs:
    """Tests for the list_catalogs service function."""

    def test_list_catalogs_success(self, tmp_path: Path) -> None:
        """Test list_catalogs returns formatted list."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog("1.20.0", datetime(2025, 2, 1, tzinfo=UTC)),
        )

        from n8n_release_parser.storage import LocalStorageBackend

        backend = LocalStorageBackend(tmp_path)
        result = service.list_catalogs(backend)

        assert len(result) == 1
        assert result[0]["version"] == "1.20.0"
        assert "release_date" in result[0]
