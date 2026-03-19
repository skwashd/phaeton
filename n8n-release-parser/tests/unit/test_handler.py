"""Tests for the Lambda handler operation routing."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.handler import handler
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


class TestListVersionsOperation:
    """Tests for the list_versions handler operation."""

    def test_list_versions_default(self) -> None:
        """Test list_versions with default months."""
        versions = [
            NpmVersionInfo(
                version="1.20.0",
                publish_date=datetime(2025, 2, 1, tzinfo=UTC),
                tarball_url="https://example.com/1.20.0.tgz",
            ),
        ]
        with patch("n8n_release_parser.service.list_versions", return_value=versions):
            result = handler({}, None)

        assert result["status"] == "success"
        assert result["months"] == 12
        assert result["version_count"] == 1
        assert result["versions"][0]["version"] == "1.20.0"

    def test_list_versions_custom_months(self) -> None:
        """Test list_versions with custom months parameter."""
        with patch("n8n_release_parser.service.list_versions", return_value=[]):
            result = handler({"months": 6}, None)

        assert result["status"] == "success"
        assert result["months"] == 6
        assert result["version_count"] == 0

    def test_list_versions_invalid_months(self) -> None:
        """Test list_versions rejects invalid months."""
        result = handler({"months": -1}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400

    def test_list_versions_non_integer_months(self) -> None:
        """Test list_versions rejects non-integer months."""
        result = handler({"months": "six"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400


class TestFetchReleasesOperation:
    """Tests for the fetch_releases handler operation."""

    def test_fetch_releases_routes_correctly(self) -> None:
        """Test fetch_releases delegates to list_versions logic."""
        versions = [
            NpmVersionInfo(
                version="1.20.0",
                publish_date=datetime(2025, 2, 1, tzinfo=UTC),
                tarball_url="https://example.com/1.20.0.tgz",
            ),
        ]
        with patch("n8n_release_parser.service.list_versions", return_value=versions):
            result = handler({"operation": "fetch_releases", "months": 3}, None)

        assert result["status"] == "success"
        assert result["version_count"] == 1


class TestDiffCatalogsOperation:
    """Tests for the diff_catalogs handler operation."""

    def test_diff_catalogs_success(self, tmp_path: Path) -> None:
        """Test diff_catalogs with valid catalogs."""
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
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack Updated")],
            ),
        )

        result = handler(
            {
                "operation": "diff_catalogs",
                "store_uri": str(tmp_path),
                "old_version": "1.19.0",
                "new_version": "1.20.0",
            },
            None,
        )

        assert result["status"] == "success"
        assert "diff" in result
        assert result["diff"]["from_version"] == "1.19.0"
        assert result["diff"]["to_version"] == "1.20.0"

    def test_diff_catalogs_missing_params(self) -> None:
        """Test diff_catalogs rejects missing parameters."""
        result = handler({"operation": "diff_catalogs"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400

    def test_diff_catalogs_missing_catalog(self, tmp_path: Path) -> None:
        """Test diff_catalogs with a nonexistent catalog version."""
        result = handler(
            {
                "operation": "diff_catalogs",
                "store_uri": str(tmp_path),
                "old_version": "1.19.0",
                "new_version": "1.20.0",
            },
            None,
        )

        assert "error" in result
        assert result["error"]["status_code"] == 500
        assert "not found" in result["error"]["message"]


class TestBuildCatalogOperation:
    """Tests for the build_catalog handler operation."""

    def test_build_catalog_success(self, tmp_path: Path) -> None:
        """Test build_catalog with stored catalogs."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack")],
            ),
        )

        result = handler(
            {"operation": "build_catalog", "store_uri": str(tmp_path)},
            None,
        )

        assert result["status"] == "success"
        assert result["entry_count"] == 1
        assert result["entries"][0]["node_type"] == "n8n-nodes-base.slack"

    def test_build_catalog_missing_store_uri(self) -> None:
        """Test build_catalog rejects missing store_uri."""
        result = handler({"operation": "build_catalog"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400

    def test_build_catalog_empty_store(self, tmp_path: Path) -> None:
        """Test build_catalog with empty store returns empty entries."""
        result = handler(
            {"operation": "build_catalog", "store_uri": str(tmp_path)},
            None,
        )

        assert result["status"] == "success"
        assert result["entry_count"] == 0


class TestGenerateReportOperation:
    """Tests for the generate_report handler operation."""

    def test_generate_report_success(self, tmp_path: Path) -> None:
        """Test generate_report with a catalog in the store."""
        store = NodeCatalogStore(tmp_path)
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 2, 1, tzinfo=UTC),
                entries=[_make_entry("n8n-nodes-base.slack", 1, "Slack")],
            ),
        )

        result = handler(
            {"operation": "generate_report", "store_uri": str(tmp_path)},
            None,
        )

        assert result["status"] == "success"
        assert "report" in result
        assert "total_priority_nodes" in result["report"]

    def test_generate_report_missing_store_uri(self) -> None:
        """Test generate_report rejects missing store_uri."""
        result = handler({"operation": "generate_report"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400

    def test_generate_report_empty_store(self, tmp_path: Path) -> None:
        """Test generate_report with empty store returns error."""
        result = handler(
            {"operation": "generate_report", "store_uri": str(tmp_path)},
            None,
        )

        assert "error" in result
        assert result["error"]["status_code"] == 500
        assert "No catalogs found" in result["error"]["message"]


class TestUnknownOperation:
    """Tests for unknown operation handling."""

    def test_unknown_operation(self) -> None:
        """Test handler rejects unknown operations."""
        result = handler({"operation": "invalid_op"}, None)
        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert "Unknown operation" in result["error"]["message"]


class TestHandlerDoesNotImportCli:
    """Verify handler module does not depend on CLI/typer."""

    def test_handler_does_not_import_typer(self) -> None:
        """Test that handler.py does not import typer."""
        import n8n_release_parser.handler as handler_mod

        source = Path(handler_mod.__file__).read_text(encoding="utf-8")
        assert "import typer" not in source
        assert "from typer" not in source

    def test_handler_does_not_import_cli(self) -> None:
        """Test that handler.py does not import the CLI module."""
        import n8n_release_parser.handler as handler_mod

        source = Path(handler_mod.__file__).read_text(encoding="utf-8")
        assert "from n8n_release_parser.cli" not in source
        assert "import n8n_release_parser.cli" not in source
