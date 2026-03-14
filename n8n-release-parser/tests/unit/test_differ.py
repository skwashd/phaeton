"""Tests for the release differ module."""

from datetime import UTC, datetime

from n8n_release_parser.differ import (
    build_cumulative_catalog,
    diff_catalogs,
    diff_node_entries,
)
from n8n_release_parser.models import (
    ChangeType,
    CredentialType,
    NodeCatalog,
    NodeParameter,
    NodeTypeEntry,
    ResourceOperation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 1, 1, tzinfo=UTC)


def _make_catalog(
    version: str,
    entries: list[NodeTypeEntry] | None = None,
) -> NodeCatalog:
    return NodeCatalog(
        n8n_version=version,
        release_date=_NOW,
        entries=entries or [],
    )


def _make_entry(
    node_type: str = "n8n-nodes-base.slack",
    type_version: int = 1,
    display_name: str = "Slack",
    *,
    parameters: list[NodeParameter] | None = None,
    credential_types: list[CredentialType] | None = None,
    resource_operations: list[ResourceOperation] | None = None,
    request_defaults: dict | None = None,
    description: str = "",
    source_n8n_version: str = "1.0.0",
) -> NodeTypeEntry:
    return NodeTypeEntry(
        node_type=node_type,
        type_version=type_version,
        display_name=display_name,
        description=description,
        parameters=parameters or [],
        credential_types=credential_types or [],
        resource_operations=resource_operations or [],
        request_defaults=request_defaults,
        source_n8n_version=source_n8n_version,
    )


# ---------------------------------------------------------------------------
# diff_catalogs tests
# ---------------------------------------------------------------------------


class TestDiffCatalogs:
    """Tests for DiffCatalogs."""

    def test_diff_identifies_added_nodes(self) -> None:
        """Test diff identifies added nodes."""
        old = _make_catalog("1.0.0", entries=[])
        new_entry = _make_entry(node_type="n8n-nodes-base.slack", type_version=1)
        new = _make_catalog("1.1.0", entries=[new_entry])

        result = diff_catalogs(old, new)

        assert result.from_version == "1.0.0"
        assert result.to_version == "1.1.0"
        assert result.added_count == 1
        assert result.removed_count == 0
        assert result.modified_count == 0
        assert len(result.changes) == 1
        assert result.changes[0].change_type == ChangeType.ADDED
        assert result.changes[0].node_type == "n8n-nodes-base.slack"
        assert result.changes[0].new_version == new_entry

    def test_diff_identifies_removed_nodes(self) -> None:
        """Test diff identifies removed nodes."""
        old_entry = _make_entry(node_type="n8n-nodes-base.slack", type_version=1)
        old = _make_catalog("1.0.0", entries=[old_entry])
        new = _make_catalog("1.1.0", entries=[])

        result = diff_catalogs(old, new)

        assert result.added_count == 0
        assert result.removed_count == 1
        assert result.modified_count == 0
        assert len(result.changes) == 1
        assert result.changes[0].change_type == ChangeType.REMOVED
        assert result.changes[0].node_type == "n8n-nodes-base.slack"
        assert result.changes[0].old_version == old_entry

    def test_diff_identifies_modified_nodes(self) -> None:
        """Test diff identifies modified nodes."""
        old_entry = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack",
        )
        new_entry = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack v2",
        )
        old = _make_catalog("1.0.0", entries=[old_entry])
        new = _make_catalog("1.1.0", entries=[new_entry])

        result = diff_catalogs(old, new)

        assert result.added_count == 0
        assert result.removed_count == 0
        assert result.modified_count == 1
        assert len(result.changes) == 1
        change = result.changes[0]
        assert change.change_type == ChangeType.MODIFIED
        assert change.node_type == "n8n-nodes-base.slack"
        assert change.old_version == old_entry
        assert change.new_version == new_entry
        assert any("display_name" in f for f in change.changed_fields)

    def test_diff_no_changes(self) -> None:
        """Test diff no changes."""
        entry = _make_entry(node_type="n8n-nodes-base.slack", type_version=1)
        old = _make_catalog("1.0.0", entries=[entry])
        new = _make_catalog("1.1.0", entries=[entry])

        result = diff_catalogs(old, new)

        assert result.added_count == 0
        assert result.removed_count == 0
        assert result.modified_count == 0
        assert len(result.changes) == 0


# ---------------------------------------------------------------------------
# diff_node_entries tests
# ---------------------------------------------------------------------------


class TestDiffNodeEntries:
    """Tests for DiffNodeEntries."""

    def test_diff_node_entries_parameter_changes(self) -> None:
        """Test diff node entries parameter changes."""
        old_entry = _make_entry(
            parameters=[
                NodeParameter(
                    name="timeout",
                    display_name="Timeout",
                    type="number",
                    default=30,
                ),
                NodeParameter(
                    name="deprecated_param",
                    display_name="Deprecated",
                    type="string",
                ),
            ],
        )
        new_entry = _make_entry(
            parameters=[
                NodeParameter(
                    name="timeout",
                    display_name="Timeout",
                    type="number",
                    default=60,
                ),
                NodeParameter(
                    name="headerAuth",
                    display_name="Header Auth",
                    type="boolean",
                ),
            ],
        )

        changes = diff_node_entries(old_entry, new_entry)

        assert "Added parameter: headerAuth" in changes
        assert "Removed parameter: deprecated_param" in changes
        assert "Changed default for parameter timeout: 30 -> 60" in changes

    def test_diff_node_entries_credential_changes(self) -> None:
        """Test diff node entries credential changes."""
        old_entry = _make_entry(
            credential_types=[
                CredentialType(name="slackOAuth", required=True),
                CredentialType(name="slackApi", required=True),
            ],
        )
        new_entry = _make_entry(
            credential_types=[
                CredentialType(name="slackApi", required=True),
                CredentialType(name="slackBotToken", required=False),
            ],
        )

        changes = diff_node_entries(old_entry, new_entry)

        assert "Added credential type: slackBotToken" in changes
        assert "Removed credential type: slackOAuth" in changes

    def test_diff_node_entries_operation_changes(self) -> None:
        """Test diff node entries operation changes."""
        old_entry = _make_entry(
            resource_operations=[
                ResourceOperation(
                    resource="message", operation="send", description="Send a message"
                ),
                ResourceOperation(
                    resource="message",
                    operation="delete",
                    description="Delete a message",
                ),
            ],
        )
        new_entry = _make_entry(
            resource_operations=[
                ResourceOperation(
                    resource="message", operation="send", description="Send a message"
                ),
                ResourceOperation(
                    resource="message",
                    operation="update",
                    description="Update a message",
                ),
            ],
        )

        changes = diff_node_entries(old_entry, new_entry)

        assert "Added operation: message:update" in changes
        assert "Removed operation: message:delete" in changes

    def test_diff_node_entries_no_changes(self) -> None:
        """Test diff node entries no changes."""
        entry = _make_entry(
            parameters=[
                NodeParameter(name="url", display_name="URL", type="string"),
            ],
            credential_types=[
                CredentialType(name="httpBasicAuth", required=True),
            ],
            resource_operations=[
                ResourceOperation(resource="data", operation="get"),
            ],
        )

        changes = diff_node_entries(entry, entry)

        assert changes == []

    def test_diff_node_entries_parameter_type_change(self) -> None:
        """Test diff node entries parameter type change."""
        old_entry = _make_entry(
            parameters=[
                NodeParameter(name="value", display_name="Value", type="string"),
            ],
        )
        new_entry = _make_entry(
            parameters=[
                NodeParameter(name="value", display_name="Value", type="number"),
            ],
        )

        changes = diff_node_entries(old_entry, new_entry)

        assert "Changed type for parameter value: 'string' -> 'number'" in changes

    def test_diff_node_entries_request_defaults_change(self) -> None:
        """Test diff node entries request defaults change."""
        old_entry = _make_entry(
            request_defaults={"baseURL": "https://api.example.com/v1"},
        )
        new_entry = _make_entry(
            request_defaults={"baseURL": "https://api.example.com/v2"},
        )

        changes = diff_node_entries(old_entry, new_entry)

        assert any("request_defaults" in c for c in changes)


# ---------------------------------------------------------------------------
# build_cumulative_catalog tests
# ---------------------------------------------------------------------------


class TestBuildCumulativeCatalog:
    """Tests for BuildCumulativeCatalog."""

    def test_build_cumulative_catalog_basic(self) -> None:
        """Test build cumulative catalog basic."""
        entry_a = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            source_n8n_version="1.0.0",
        )
        entry_b = _make_entry(
            node_type="n8n-nodes-base.github",
            type_version=1,
            source_n8n_version="1.0.0",
        )
        catalog = _make_catalog("1.0.0", entries=[entry_a, entry_b])

        result = build_cumulative_catalog([catalog])

        assert len(result) == 2
        assert ("n8n-nodes-base.slack", 1) in result
        assert ("n8n-nodes-base.github", 1) in result
        assert result[("n8n-nodes-base.slack", 1)] == entry_a
        assert result[("n8n-nodes-base.github", 1)] == entry_b

    def test_build_cumulative_catalog_override(self) -> None:
        """Test build cumulative catalog override."""
        old_entry = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack Old",
            source_n8n_version="1.0.0",
        )
        new_entry = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack New",
            source_n8n_version="1.1.0",
        )
        cat_old = _make_catalog("1.0.0", entries=[old_entry])
        cat_new = _make_catalog("1.1.0", entries=[new_entry])

        result = build_cumulative_catalog([cat_old, cat_new])

        assert result[("n8n-nodes-base.slack", 1)] == new_entry
        assert result[("n8n-nodes-base.slack", 1)].display_name == "Slack New"

    def test_build_cumulative_catalog_preserves_old_versions(self) -> None:
        """Test build cumulative catalog preserves old versions."""
        entry_v1 = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack v1",
            source_n8n_version="1.0.0",
        )
        entry_v2 = _make_entry(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            display_name="Slack v2",
            source_n8n_version="1.1.0",
        )
        cat_old = _make_catalog("1.0.0", entries=[entry_v1])
        cat_new = _make_catalog("1.1.0", entries=[entry_v2])

        result = build_cumulative_catalog([cat_old, cat_new])

        assert len(result) == 2
        assert result[("n8n-nodes-base.slack", 1)] == entry_v1
        assert result[("n8n-nodes-base.slack", 2)] == entry_v2
