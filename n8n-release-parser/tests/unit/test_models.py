"""Tests for the models module."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from n8n_release_parser.models import (
    ApiSpecEntry,
    ApiSpecIndex,
    ChangeType,
    CredentialType,
    NodeApiMapping,
    NodeCatalog,
    NodeChange,
    NodeClassification,
    NodeParameter,
    NodeTypeEntry,
    NpmVersionInfo,
    ReleaseDiff,
    ResourceOperation,
    SpecEndpoint,
)


class TestNodeParameter:
    """Tests for NodeParameter."""

    def test_construction(self) -> None:
        """Test construction."""
        param = NodeParameter(name="channel", display_name="Channel", type="string")
        assert param.name == "channel"
        assert param.display_name == "Channel"
        assert param.type == "string"
        assert param.default is None
        assert param.required is False
        assert param.has_expressions is False

    def test_with_options(self) -> None:
        """Test with options."""
        param = NodeParameter(
            name="operation",
            display_name="Operation",
            type="options",
            options=[{"name": "Send", "value": "send"}],
            required=True,
        )
        assert param.options is not None
        assert len(param.options) == 1
        assert param.required is True

    def test_frozen(self) -> None:
        """Test frozen."""
        param = NodeParameter(name="x", display_name="X", type="string")
        with pytest.raises(ValidationError):
            param.name = "y"


class TestCredentialType:
    """Tests for CredentialType."""

    def test_construction(self) -> None:
        """Test construction."""
        cred = CredentialType(name="slackApi")
        assert cred.name == "slackApi"
        assert cred.required is True

    def test_optional_credential(self) -> None:
        """Test optional credential."""
        cred = CredentialType(name="slackApi", required=False)
        assert cred.required is False


class TestResourceOperation:
    """Tests for ResourceOperation."""

    def test_construction(self) -> None:
        """Test construction."""
        op = ResourceOperation(
            resource="message", operation="send", description="Send a message"
        )
        assert op.resource == "message"
        assert op.operation == "send"


class TestNodeTypeEntry:
    """Tests for NodeTypeEntry."""

    def test_construction(self) -> None:
        """Test construction."""
        entry = NodeTypeEntry(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            display_name="Slack",
            description="Interact with Slack",
            group=["output"],
            credential_types=[CredentialType(name="slackApi")],
            resource_operations=[
                ResourceOperation(resource="message", operation="send")
            ],
            source_n8n_version="1.20.0",
        )
        assert entry.node_type == "n8n-nodes-base.slack"
        assert entry.type_version == 2
        assert len(entry.credential_types) == 1
        assert len(entry.resource_operations) == 1

    def test_defaults(self) -> None:
        """Test defaults."""
        entry = NodeTypeEntry(
            node_type="n8n-nodes-base.set",
            type_version=1,
            display_name="Set",
        )
        assert entry.input_count == 1
        assert entry.output_count == 1
        assert entry.parameters == []
        assert entry.request_defaults is None

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        entry = NodeTypeEntry(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            display_name="Slack",
            parameters=[
                NodeParameter(name="channel", display_name="Channel", type="string")
            ],
        )
        data = json.loads(entry.model_dump_json())
        restored = NodeTypeEntry.model_validate(data)
        assert restored == entry


class TestNodeCatalog:
    """Tests for NodeCatalog."""

    def test_construction(self) -> None:
        """Test construction."""
        now = datetime.now(tz=UTC)
        cat = NodeCatalog(
            n8n_version="1.20.0",
            release_date=now,
            entries=[
                NodeTypeEntry(
                    node_type="n8n-nodes-base.set",
                    type_version=1,
                    display_name="Set",
                )
            ],
            parse_timestamp=now,
        )
        assert cat.n8n_version == "1.20.0"
        assert len(cat.entries) == 1
        assert cat.parser_version == "0.1.0"

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        now = datetime.now(tz=UTC)
        cat = NodeCatalog(n8n_version="1.20.0", release_date=now)
        data = json.loads(cat.model_dump_json())
        restored = NodeCatalog.model_validate(data)
        assert restored == cat


class TestChangeType:
    """Tests for ChangeType."""

    def test_values(self) -> None:
        """Test values."""
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.MODIFIED.value == "modified"


class TestNodeChange:
    """Tests for NodeChange."""

    def test_added(self) -> None:
        """Test added."""
        new_entry = NodeTypeEntry(
            node_type="n8n-nodes-base.newNode",
            type_version=1,
            display_name="New Node",
        )
        change = NodeChange(
            node_type="n8n-nodes-base.newNode",
            change_type=ChangeType.ADDED,
            new_version=new_entry,
        )
        assert change.old_version is None
        assert change.new_version is not None

    def test_modified(self) -> None:
        """Test modified."""
        change = NodeChange(
            node_type="n8n-nodes-base.slack",
            change_type=ChangeType.MODIFIED,
            changed_fields=["parameters", "resource_operations"],
        )
        assert len(change.changed_fields) == 2


class TestReleaseDiff:
    """Tests for ReleaseDiff."""

    def test_construction(self) -> None:
        """Test construction."""
        diff = ReleaseDiff(
            from_version="1.19.0",
            to_version="1.20.0",
            added_count=3,
            removed_count=1,
            modified_count=2,
        )
        assert diff.from_version == "1.19.0"
        assert diff.added_count == 3


class TestSpecEndpoint:
    """Tests for SpecEndpoint."""

    def test_construction(self) -> None:
        """Test construction."""
        ep = SpecEndpoint(
            resource="messages",
            operation="postMessage",
            endpoint="POST /chat.postMessage",
        )
        assert ep.resource == "messages"


class TestApiSpecEntry:
    """Tests for ApiSpecEntry."""

    def test_construction(self) -> None:
        """Test construction."""
        entry = ApiSpecEntry(
            spec_filename="slack-web-api-v2.json",
            service_name="Slack",
            base_urls=["https://slack.com/api"],
            auth_type="oauth2",
            spec_format="openapi3",
        )
        assert entry.spec_filename == "slack-web-api-v2.json"
        assert entry.auth_type == "oauth2"


class TestApiSpecIndex:
    """Tests for ApiSpecIndex."""

    def test_construction(self) -> None:
        """Test construction."""
        now = datetime.now(tz=UTC)
        index = ApiSpecIndex(
            entries=[
                ApiSpecEntry(
                    spec_filename="slack.json",
                    service_name="Slack",
                )
            ],
            index_timestamp=now,
        )
        assert len(index.entries) == 1

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        now = datetime.now(tz=UTC)
        index = ApiSpecIndex(index_timestamp=now)
        data = json.loads(index.model_dump_json())
        restored = ApiSpecIndex.model_validate(data)
        assert restored == index


class TestNodeApiMapping:
    """Tests for NodeApiMapping."""

    def test_construction(self) -> None:
        """Test construction."""
        mapping = NodeApiMapping(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            api_spec="slack-web-api-v2.json",
            spec_format="openapi3",
            operation_mappings={
                "message:send": "POST /chat.postMessage",
                "channel:getAll": "GET /conversations.list",
            },
            credential_type="slackApi",
            auth_type="oauth2",
            unmapped_operations=["message:getPermalink"],
            spec_coverage=0.92,
        )
        assert mapping.spec_coverage == pytest.approx(0.92)
        assert len(mapping.operation_mappings) == 2

    def test_to_plan_json(self) -> None:
        """Test to plan json."""
        mapping = NodeApiMapping(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            api_spec="slack-web-api-v2.json",
            spec_format="openapi3",
            operation_mappings={
                "message:send": "POST /chat.postMessage",
                "channel:getAll": "GET /conversations.list",
            },
            credential_type="slackApi",
            auth_type="oauth2",
            unmapped_operations=["message:getPermalink"],
            spec_coverage=0.92,
        )
        result = mapping.to_plan_json()
        assert result["nodeType"] == "n8n-nodes-base.slack"
        assert result["typeVersion"] == 2
        assert result["apiSpec"] == "slack-web-api-v2.json"
        assert result["specFormat"] == "openapi3"
        assert result["operationMappings"]["message:send"] == "POST /chat.postMessage"
        assert result["credentialType"] == "slackApi"
        assert result["authType"] == "oauth2"
        assert result["unmappedOperations"] == ["message:getPermalink"]
        assert result["specCoverage"] == pytest.approx(0.92)

    def test_plan_json_is_serializable(self) -> None:
        """Test plan json is serializable."""
        mapping = NodeApiMapping(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            api_spec="slack.json",
            spec_format="openapi3",
            spec_coverage=1.0,
        )
        serialized = json.dumps(mapping.to_plan_json())
        parsed = json.loads(serialized)
        assert parsed["nodeType"] == "n8n-nodes-base.slack"

    def test_serialization_roundtrip(self) -> None:
        """Test serialization roundtrip."""
        mapping = NodeApiMapping(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            api_spec="slack.json",
            spec_format="openapi3",
            operation_mappings={"message:send": "POST /chat.postMessage"},
            spec_coverage=0.5,
        )
        data = json.loads(mapping.model_dump_json())
        restored = NodeApiMapping.model_validate(data)
        assert restored == mapping


class TestNodeClassification:
    """Tests for NodeClassification."""

    def test_all_values(self) -> None:
        """Test all values."""
        expected = {
            "AWS_NATIVE",
            "FLOW_CONTROL",
            "TRIGGER",
            "PICOFUN_API",
            "GRAPHQL_API",
            "CODE_JS",
            "CODE_PYTHON",
            "UNSUPPORTED",
        }
        actual = {c.value for c in NodeClassification}
        assert actual == expected


class TestNpmVersionInfo:
    """Tests for NpmVersionInfo."""

    def test_construction(self) -> None:
        """Test construction."""
        info = NpmVersionInfo(
            version="1.20.0",
            publish_date=datetime(2025, 1, 15, tzinfo=UTC),
            tarball_url="https://registry.npmjs.org/n8n-nodes-base/-/n8n-nodes-base-1.20.0.tgz",
        )
        assert info.version == "1.20.0"

    def test_validation_rejects_missing_fields(self) -> None:
        """Test validation rejects missing fields."""
        with pytest.raises(ValidationError):
            NpmVersionInfo(version="1.0.0")  # type: ignore[call-arg]
