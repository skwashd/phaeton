from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from n8n_release_parser import differ, matcher, parser, priority, spec_index
from n8n_release_parser.catalog import NodeCatalogStore
from n8n_release_parser.models import (
    NodeApiMapping,
    NodeCatalog,
    NodeClassification,
    NodeParameter,
    NodeTypeEntry,
    ResourceOperation,
)


@pytest.mark.integration
def test_parse_diff_store_pipeline(tmp_path: Path) -> None:
    desc_v1 = {
        "displayName": "Slack",
        "name": "n8n-nodes-base.slack",
        "group": ["output"],
        "version": 1,
        "description": "Consume Slack API",
        "defaults": {"name": "Slack"},
        "inputs": ["main"],
        "outputs": ["main"],
        "credentials": [{"name": "slackApi", "required": True}],
        "requestDefaults": {"baseURL": "https://slack.com/api"},
        "properties": [
            {
                "displayName": "Resource",
                "name": "resource",
                "type": "options",
                "default": "message",
                "options": [{"name": "Message", "value": "message"}],
            },
            {
                "displayName": "Operation",
                "name": "operation",
                "type": "options",
                "default": "send",
                "displayOptions": {"show": {"resource": ["message"]}},
                "options": [
                    {
                        "name": "Send",
                        "value": "send",
                        "description": "Send a message",
                    },
                ],
            },
        ],
    }

    desc_v2 = {
        "displayName": "Slack",
        "name": "n8n-nodes-base.slack",
        "group": ["output"],
        "version": 2,
        "description": "Consume Slack API v2",
        "defaults": {"name": "Slack"},
        "inputs": ["main"],
        "outputs": ["main"],
        "credentials": [
            {"name": "slackApi", "required": True},
            {"name": "slackOAuth2Api", "required": False},
        ],
        "requestDefaults": {"baseURL": "https://slack.com/api"},
        "properties": [
            {
                "displayName": "Resource",
                "name": "resource",
                "type": "options",
                "default": "message",
                "options": [
                    {"name": "Message", "value": "message"},
                    {"name": "Channel", "value": "channel"},
                ],
            },
            {
                "displayName": "Operation",
                "name": "operation",
                "type": "options",
                "default": "send",
                "displayOptions": {"show": {"resource": ["message"]}},
                "options": [
                    {
                        "name": "Send",
                        "value": "send",
                        "description": "Send a message",
                    },
                    {
                        "name": "Update",
                        "value": "update",
                        "description": "Update a message",
                    },
                ],
            },
            {
                "displayName": "Operation",
                "name": "operation",
                "type": "options",
                "default": "getAll",
                "displayOptions": {"show": {"resource": ["channel"]}},
                "options": [
                    {
                        "name": "Get All",
                        "value": "getAll",
                        "description": "Get all channels",
                    },
                ],
            },
        ],
    }

    entries_v1 = parser.parse_node_description(desc_v1)
    entries_v2 = parser.parse_node_description(desc_v2)

    assert len(entries_v1) == 1
    assert len(entries_v2) == 1
    assert entries_v1[0].type_version == 1
    assert entries_v2[0].type_version == 2

    now = datetime.now(tz=UTC)
    cat_v1 = NodeCatalog(
        n8n_version="1.19.0",
        release_date=now,
        entries=entries_v1,
    )
    cat_v2 = NodeCatalog(
        n8n_version="1.20.0",
        release_date=now,
        entries=entries_v2,
    )

    store = NodeCatalogStore(tmp_path / "catalogs")
    store.save_catalog(cat_v1)
    store.save_catalog(cat_v2)

    loaded_v1 = store.load_catalog("1.19.0")
    loaded_v2 = store.load_catalog("1.20.0")
    assert loaded_v1 is not None
    assert loaded_v2 is not None
    assert loaded_v1.n8n_version == "1.19.0"
    assert loaded_v2.n8n_version == "1.20.0"
    assert len(loaded_v1.entries) == 1
    assert len(loaded_v2.entries) == 1
    assert loaded_v1.entries[0].node_type == "n8n-nodes-base.slack"
    assert loaded_v2.entries[0].node_type == "n8n-nodes-base.slack"

    diff = differ.diff_catalogs(loaded_v1, loaded_v2)
    assert diff.from_version == "1.19.0"
    assert diff.to_version == "1.20.0"
    # v1 has (slack,1) and v2 has (slack,2) — so 1 added, 1 removed
    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.modified_count == 0


@pytest.mark.integration
def test_spec_index_match_pipeline(tmp_path: Path) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Slack"},
        "servers": [{"url": "https://slack.com/api"}],
        "paths": {
            "/chat.postMessage": {
                "post": {
                    "operationId": "postMessage",
                    "tags": ["chat"],
                    "responses": {"200": {"description": "OK"}},
                },
            },
            "/conversations.list": {
                "get": {
                    "operationId": "listConversations",
                    "tags": ["conversations"],
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
            },
        },
    }
    spec_file = specs_dir / "slack_openapi.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")

    index = spec_index.build_spec_index(specs_dir)
    assert len(index.entries) == 1
    assert index.entries[0].service_name == "Slack"
    assert index.entries[0].auth_type == "bearer"

    slack_entry = NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=1,
        display_name="Slack",
        request_defaults={"baseURL": "https://slack.com/api"},
        resource_operations=[
            ResourceOperation(resource="message", operation="send"),
            ResourceOperation(resource="channel", operation="getAll"),
        ],
    )
    cat = NodeCatalog(
        n8n_version="1.20.0",
        release_date=datetime.now(tz=UTC),
        entries=[slack_entry],
    )

    mappings = matcher.match_all_nodes(cat, index)
    assert len(mappings) >= 1
    slack_mapping = mappings[0]
    assert slack_mapping.node_type == "n8n-nodes-base.slack"
    assert slack_mapping.api_spec == "slack_openapi.json"

    store = NodeCatalogStore(tmp_path / "store")
    store.save_api_mappings(mappings)
    loaded_mappings = store.load_api_mappings()
    assert len(loaded_mappings) == len(mappings)
    assert loaded_mappings[0].node_type == "n8n-nodes-base.slack"


@pytest.mark.integration
def test_priority_classification_pipeline() -> None:
    aws_node = NodeTypeEntry(
        node_type="n8n-nodes-base.awsS3",
        type_version=1,
        display_name="AWS S3",
    )
    if_node = NodeTypeEntry(
        node_type="n8n-nodes-base.if",
        type_version=1,
        display_name="IF",
    )
    trigger_node = NodeTypeEntry(
        node_type="n8n-nodes-base.scheduleTrigger",
        type_version=1,
        display_name="Schedule Trigger",
        group=["trigger"],
    )
    code_node = NodeTypeEntry(
        node_type="n8n-nodes-base.code",
        type_version=1,
        display_name="Code",
        parameters=[
            NodeParameter(
                name="language",
                display_name="Language",
                type="options",
                default="python",
            ),
        ],
    )
    slack_node = NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=1,
        display_name="Slack",
    )

    cat = NodeCatalog(
        n8n_version="1.20.0",
        release_date=datetime.now(tz=UTC),
        entries=[aws_node, if_node, trigger_node, code_node, slack_node],
    )

    mock_mapping = NodeApiMapping(
        node_type="n8n-nodes-base.slack",
        type_version=1,
        api_spec="slack_openapi.json",
        spec_format="openapi3",
    )

    assert priority.classify_node(aws_node, None) == NodeClassification.AWS_NATIVE
    assert priority.classify_node(if_node, None) == NodeClassification.FLOW_CONTROL
    assert priority.classify_node(trigger_node, None) == NodeClassification.TRIGGER
    assert priority.classify_node(code_node, None) == NodeClassification.CODE_PYTHON
    assert (
        priority.classify_node(slack_node, mock_mapping)
        == NodeClassification.PICOFUN_API
    )

    report = priority.priority_coverage_report(cat, [mock_mapping])
    assert "total_priority_nodes" in report
    assert "mapped_priority_nodes" in report
    assert "missing_mappings" in report
    assert "breakdown" in report
    assert isinstance(report["breakdown"], dict)
    breakdown = report["breakdown"]
    assert "core_flow_control" in breakdown
    assert "aws_service" in breakdown
    assert "top_50" in breakdown


@pytest.mark.integration
def test_full_pipeline_with_store(tmp_path: Path) -> None:
    set_desc = {
        "displayName": "Set",
        "name": "n8n-nodes-base.set",
        "group": ["input"],
        "version": 1,
        "description": "Sets values on items",
        "defaults": {"name": "Set"},
        "inputs": ["main"],
        "outputs": ["main"],
        "properties": [
            {
                "displayName": "Keep Only Set",
                "name": "keepOnlySet",
                "type": "boolean",
                "default": False,
            },
        ],
    }

    slack_desc = {
        "displayName": "Slack",
        "name": "n8n-nodes-base.slack",
        "group": ["output"],
        "version": 1,
        "description": "Consume Slack API",
        "defaults": {"name": "Slack"},
        "inputs": ["main"],
        "outputs": ["main"],
        "credentials": [{"name": "slackApi", "required": True}],
        "requestDefaults": {"baseURL": "https://slack.com/api"},
        "properties": [
            {
                "displayName": "Resource",
                "name": "resource",
                "type": "options",
                "default": "message",
                "options": [{"name": "Message", "value": "message"}],
            },
            {
                "displayName": "Operation",
                "name": "operation",
                "type": "options",
                "default": "send",
                "displayOptions": {"show": {"resource": ["message"]}},
                "options": [
                    {
                        "name": "Send",
                        "value": "send",
                        "description": "Send a message",
                    },
                ],
            },
        ],
    }

    github_desc = {
        "displayName": "GitHub",
        "name": "n8n-nodes-base.github",
        "group": ["output"],
        "version": 1,
        "description": "Consume GitHub API",
        "defaults": {"name": "GitHub"},
        "inputs": ["main"],
        "outputs": ["main"],
        "properties": [],
    }

    set_entries = parser.parse_node_description(set_desc)
    slack_entries = parser.parse_node_description(slack_desc)
    github_entries = parser.parse_node_description(github_desc)

    now = datetime.now(tz=UTC)
    cat_v1 = NodeCatalog(
        n8n_version="1.19.0",
        release_date=now,
        entries=set_entries + slack_entries,
    )
    cat_v2 = NodeCatalog(
        n8n_version="1.20.0",
        release_date=now,
        entries=set_entries + slack_entries + github_entries,
    )

    store = NodeCatalogStore(tmp_path / "store")
    store.save_catalog(cat_v1)
    store.save_catalog(cat_v2)

    listing = store.list_catalogs()
    assert len(listing) == 2
    versions = {v for v, _d in listing}
    assert "1.19.0" in versions
    assert "1.20.0" in versions

    loaded_v1 = store.load_catalog("1.19.0")
    loaded_v2 = store.load_catalog("1.20.0")
    assert loaded_v1 is not None
    assert loaded_v2 is not None

    diff = differ.diff_catalogs(loaded_v1, loaded_v2)
    assert diff.added_count == 1  # github added
    assert diff.removed_count == 0
    assert diff.modified_count == 0

    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Slack"},
        "servers": [{"url": "https://slack.com/api"}],
        "paths": {
            "/chat.postMessage": {
                "post": {
                    "operationId": "postMessage",
                    "tags": ["chat"],
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
            },
        },
    }
    (specs_dir / "slack_openapi.json").write_text(json.dumps(spec), encoding="utf-8")

    index = spec_index.build_spec_index(specs_dir)
    mappings = matcher.match_all_nodes(loaded_v2, index)

    store.save_api_mappings(mappings)
    reloaded_mappings = store.load_api_mappings()
    assert len(reloaded_mappings) == len(mappings)

    report = priority.priority_coverage_report(loaded_v2, reloaded_mappings)
    assert isinstance(report["total_priority_nodes"], int)
    assert isinstance(report["mapped_priority_nodes"], int)
    assert isinstance(report["missing_mappings"], list)
    assert isinstance(report["breakdown"], dict)


@pytest.mark.integration
def test_cumulative_lookup(tmp_path: Path) -> None:
    store = NodeCatalogStore(tmp_path / "store")

    entry_slack_v1 = NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=1,
        display_name="Slack v1.18",
        source_n8n_version="1.18.0",
    )
    entry_github = NodeTypeEntry(
        node_type="n8n-nodes-base.github",
        type_version=1,
        display_name="GitHub",
        source_n8n_version="1.18.0",
    )
    entry_slack_v1_updated = NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=1,
        display_name="Slack v1.19",
        source_n8n_version="1.19.0",
    )
    entry_jira = NodeTypeEntry(
        node_type="n8n-nodes-base.jira",
        type_version=1,
        display_name="Jira",
        source_n8n_version="1.19.0",
    )
    entry_slack_v2 = NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=2,
        display_name="Slack V2",
        source_n8n_version="1.20.0",
    )

    store.save_catalog(
        NodeCatalog(
            n8n_version="1.18.0",
            release_date=datetime(2024, 11, 1, tzinfo=UTC),
            entries=[entry_slack_v1, entry_github],
        ),
    )
    store.save_catalog(
        NodeCatalog(
            n8n_version="1.19.0",
            release_date=datetime(2024, 12, 1, tzinfo=UTC),
            entries=[entry_slack_v1_updated, entry_jira],
        ),
    )
    store.save_catalog(
        NodeCatalog(
            n8n_version="1.20.0",
            release_date=datetime(2025, 1, 15, tzinfo=UTC),
            entries=[entry_slack_v2],
        ),
    )

    lookup = store.build_lookup()

    # Latest version of slack v1 (from 1.19.0) overrides older
    assert ("n8n-nodes-base.slack", 1) in lookup
    assert lookup[("n8n-nodes-base.slack", 1)].display_name == "Slack v1.19"

    # Slack v2 from 1.20.0
    assert ("n8n-nodes-base.slack", 2) in lookup
    assert lookup[("n8n-nodes-base.slack", 2)].display_name == "Slack V2"

    # GitHub preserved from 1.18.0 (only in older release)
    assert ("n8n-nodes-base.github", 1) in lookup
    assert lookup[("n8n-nodes-base.github", 1)].display_name == "GitHub"

    # Jira from 1.19.0
    assert ("n8n-nodes-base.jira", 1) in lookup
    assert lookup[("n8n-nodes-base.jira", 1)].display_name == "Jira"

    # Total: 4 unique (node_type, type_version) pairs
    assert len(lookup) == 4
