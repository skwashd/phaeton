"""Tests for the NodeCatalogStore persistence layer."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from phaeton_models.spec import NodeApiMapping

from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.models import (
    NodeCatalog,
    NodeTypeEntry,
)
from n8n_release_parser.storage_s3 import S3StorageBackend


def _make_catalog(
    version: str,
    release_date: datetime,
    entries: list[NodeTypeEntry] | None = None,
) -> NodeCatalog:
    """Build a minimal NodeCatalog for testing."""
    return NodeCatalog(
        n8n_version=version,
        release_date=release_date,
        entries=entries or [],
    )


def _make_entry(
    node_type: str = "n8n-nodes-base.slack",
    type_version: int = 1,
    display_name: str = "Slack",
    source_version: str = "",
) -> NodeTypeEntry:
    return NodeTypeEntry(
        node_type=node_type,
        type_version=type_version,
        display_name=display_name,
        source_n8n_version=source_version,
    )


class TestNodeCatalogStore:
    """Tests for NodeCatalogStore."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Test save load roundtrip."""
        store = NodeCatalogStore(tmp_path / "catalogs")
        cat = _make_catalog(
            "1.20.0",
            datetime(2025, 1, 15, tzinfo=UTC),
            entries=[_make_entry()],
        )

        saved_loc = store.save_catalog(cat)
        assert isinstance(saved_loc, str)
        assert "catalog_1_20_0.json" in saved_loc

        loaded = store.load_catalog("1.20.0")
        assert loaded is not None
        assert loaded.n8n_version == cat.n8n_version
        assert loaded.release_date == cat.release_date
        assert len(loaded.entries) == 1
        assert loaded.entries[0].node_type == "n8n-nodes-base.slack"

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Test load nonexistent returns none."""
        store = NodeCatalogStore(tmp_path / "catalogs")
        result = store.load_catalog("99.99.99")
        assert result is None

    def test_list_catalogs_ordering(self, tmp_path: Path) -> None:
        """Test list catalogs ordering."""
        store = NodeCatalogStore(tmp_path / "catalogs")

        dates = [
            ("1.18.0", datetime(2024, 11, 1, tzinfo=UTC)),
            ("1.20.0", datetime(2025, 1, 15, tzinfo=UTC)),
            ("1.19.0", datetime(2024, 12, 1, tzinfo=UTC)),
        ]
        for version, dt in dates:
            store.save_catalog(_make_catalog(version, dt))

        listing = store.list_catalogs()
        assert len(listing) == 3

        # Newest first
        assert listing[0][0] == "1.20.0"
        assert listing[1][0] == "1.19.0"
        assert listing[2][0] == "1.18.0"

        # Dates should be descending
        assert listing[0][1] > listing[1][1] > listing[2][1]

    def test_prune_old_catalogs(self, tmp_path: Path) -> None:
        """Test prune old catalogs."""
        store = NodeCatalogStore(tmp_path / "catalogs")

        now = datetime.now(tz=UTC)
        old_date = now - timedelta(days=400)  # older than 12 months
        recent_date = now - timedelta(days=30)  # well within 12 months

        store.save_catalog(_make_catalog("1.10.0", old_date))
        store.save_catalog(_make_catalog("1.20.0", recent_date))

        pruned = store.prune_old_catalogs(months=12)

        assert "1.10.0" in pruned
        assert "1.20.0" not in pruned

        # Old one should be gone
        assert store.load_catalog("1.10.0") is None
        # Recent one should remain
        assert store.load_catalog("1.20.0") is not None

    def test_build_lookup_multiple_catalogs(self, tmp_path: Path) -> None:
        """Test build lookup multiple catalogs."""
        store = NodeCatalogStore(tmp_path / "catalogs")

        entry_v1_old = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack Old",
            source_version="1.18.0",
        )
        entry_unique = _make_entry(
            node_type="n8n-nodes-base.github",
            type_version=1,
            display_name="GitHub",
            source_version="1.18.0",
        )
        entry_v1_new = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack New",
            source_version="1.20.0",
        )
        entry_v2 = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            display_name="Slack V2",
            source_version="1.20.0",
        )

        store.save_catalog(
            _make_catalog(
                "1.18.0",
                datetime(2024, 11, 1, tzinfo=UTC),
                entries=[entry_v1_old, entry_unique],
            ),
        )
        store.save_catalog(
            _make_catalog(
                "1.20.0",
                datetime(2025, 1, 15, tzinfo=UTC),
                entries=[entry_v1_new, entry_v2],
            ),
        )

        lookup = store.build_lookup()

        # Newer release overrides the old Slack v1
        assert lookup[("n8n-nodes-base.slack", 1)].display_name == "Slack New"
        # New entry from v1.20.0
        assert lookup[("n8n-nodes-base.slack", 2)].display_name == "Slack V2"
        # Preserved from old release
        assert lookup[("n8n-nodes-base.github", 1)].display_name == "GitHub"

    def test_save_load_api_mappings_roundtrip(self, tmp_path: Path) -> None:
        """Test save load api mappings roundtrip."""
        store = NodeCatalogStore(tmp_path / "catalogs")

        mappings = [
            NodeApiMapping(
                node_type="n8n-nodes-base.slack",
                type_version=1,
                api_spec="slack_openapi.json",
                spec_format="openapi3",
                operation_mappings={"message:send": "POST /chat.postMessage"},
                credential_type="slackOAuth2Api",
                auth_type="oauth2",
                unmapped_operations=["reaction:add"],
                spec_coverage=0.75,
            ),
            NodeApiMapping(
                node_type="n8n-nodes-base.github",
                type_version=1,
                api_spec="github_openapi.json",
                spec_format="openapi3",
            ),
        ]

        saved_loc = store.save_api_mappings(mappings)
        assert isinstance(saved_loc, str)
        assert "api_mappings.json" in saved_loc

        loaded = store.load_api_mappings()
        assert len(loaded) == 2
        assert loaded[0].node_type == "n8n-nodes-base.slack"
        assert loaded[0].spec_coverage == 0.75
        assert loaded[0].operation_mappings == {
            "message:send": "POST /chat.postMessage",
        }
        assert loaded[1].node_type == "n8n-nodes-base.github"

    def test_empty_store(self, tmp_path: Path) -> None:
        """Test empty store."""
        store = NodeCatalogStore(tmp_path / "catalogs")

        assert store.list_catalogs() == []
        assert store.build_lookup() == {}
        assert store.load_api_mappings() == []
        assert store.prune_old_catalogs() == []


_S3_BUCKET = "test-catalog-bucket"
_S3_REGION = "us-east-1"


@pytest.fixture
def s3_store() -> Generator[NodeCatalogStore]:
    """Provide s3_store fixture."""
    with mock_aws():
        client = boto3.client("s3", region_name=_S3_REGION)
        client.create_bucket(Bucket=_S3_BUCKET)
        backend = S3StorageBackend(
            bucket=_S3_BUCKET,
            prefix="catalogs",
            region_name=_S3_REGION,
        )
        yield NodeCatalogStore(backend)


class TestNodeCatalogStoreWithS3:
    """Tests for NodeCatalogStoreWithS3."""

    def test_save_load_roundtrip(self, s3_store: NodeCatalogStore) -> None:
        """Test save load roundtrip."""
        cat = _make_catalog(
            "1.20.0",
            datetime(2025, 1, 15, tzinfo=UTC),
            entries=[_make_entry()],
        )

        saved_loc = s3_store.save_catalog(cat)
        assert saved_loc.startswith("s3://")
        assert "catalog_1_20_0.json" in saved_loc

        loaded = s3_store.load_catalog("1.20.0")
        assert loaded is not None
        assert loaded.n8n_version == cat.n8n_version
        assert len(loaded.entries) == 1

    def test_load_nonexistent_returns_none(self, s3_store: NodeCatalogStore) -> None:
        """Test load nonexistent returns none."""
        assert s3_store.load_catalog("99.99.99") is None

    def test_list_catalogs_ordering(self, s3_store: NodeCatalogStore) -> None:
        """Test list catalogs ordering."""
        dates = [
            ("1.18.0", datetime(2024, 11, 1, tzinfo=UTC)),
            ("1.20.0", datetime(2025, 1, 15, tzinfo=UTC)),
            ("1.19.0", datetime(2024, 12, 1, tzinfo=UTC)),
        ]
        for version, dt in dates:
            s3_store.save_catalog(_make_catalog(version, dt))

        listing = s3_store.list_catalogs()
        assert len(listing) == 3
        assert listing[0][0] == "1.20.0"
        assert listing[1][0] == "1.19.0"
        assert listing[2][0] == "1.18.0"

    def test_save_load_api_mappings(self, s3_store: NodeCatalogStore) -> None:
        """Test save load api mappings."""
        mappings = [
            NodeApiMapping(
                node_type="n8n-nodes-base.slack",
                type_version=1,
                api_spec="slack_openapi.json",
                spec_format="openapi3",
            ),
        ]

        saved_loc = s3_store.save_api_mappings(mappings)
        assert saved_loc.startswith("s3://")

        loaded = s3_store.load_api_mappings()
        assert len(loaded) == 1
        assert loaded[0].node_type == "n8n-nodes-base.slack"

    def test_empty_store(self, s3_store: NodeCatalogStore) -> None:
        """Test empty store."""
        assert s3_store.list_catalogs() == []
        assert s3_store.build_lookup() == {}
        assert s3_store.load_api_mappings() == []
        assert s3_store.prune_old_catalogs() == []
