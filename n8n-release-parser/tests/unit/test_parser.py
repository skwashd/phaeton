from typing import Any

from n8n_release_parser.parser import (
    extract_request_defaults,
    extract_resource_operations,
    parse_node_description,
)

# ---------------------------------------------------------------------------
# Fixtures: raw n8n INodeTypeDescription dicts
# ---------------------------------------------------------------------------

SIMPLE_SET_NODE: dict[str, Any] = {
    "displayName": "Set",
    "name": "n8n-nodes-base.set",
    "group": ["input"],
    "version": 1,
    "description": "Sets values on items and optionally remove other values",
    "defaults": {"name": "Set", "color": "#0000FF"},
    "inputs": ["main"],
    "outputs": ["main"],
    "properties": [
        {
            "displayName": "Keep Only Set",
            "name": "keepOnlySet",
            "type": "boolean",
            "default": False,
            "description": "If only the values set on this node should be kept and all others removed",
        },
        {
            "displayName": "Values to Set",
            "name": "values",
            "type": "fixedCollection",
            "default": {},
            "description": "The value to set",
        },
    ],
}

SLACK_LIKE_NODE: dict[str, Any] = {
    "displayName": "Slack",
    "name": "n8n-nodes-base.slack",
    "group": ["output"],
    "version": 2,
    "description": "Consume Slack API",
    "defaults": {"name": "Slack"},
    "inputs": ["main"],
    "outputs": ["main"],
    "credentials": [
        {"name": "slackApi", "required": True},
        {"name": "slackOAuth2Api", "required": False},
    ],
    "requestDefaults": {
        "baseURL": "https://slack.com/api",
        "headers": {"Content-Type": "application/json"},
    },
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
                    "description": "Send a message to a channel",
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
                {
                    "name": "Create",
                    "value": "create",
                    "description": "Create a channel",
                },
            ],
        },
        {
            "displayName": "Channel",
            "name": "channel",
            "type": "string",
            "default": "",
            "required": True,
            "description": "The channel to send the message to",
        },
    ],
}

WEBHOOK_TRIGGER_NODE: dict[str, Any] = {
    "displayName": "Webhook",
    "name": "n8n-nodes-base.webhook",
    "group": ["trigger"],
    "version": 1,
    "description": "Starts the workflow when a webhook is called",
    "defaults": {"name": "Webhook"},
    "inputs": [],
    "outputs": ["main"],
    "properties": [
        {
            "displayName": "HTTP Method",
            "name": "httpMethod",
            "type": "options",
            "default": "GET",
            "options": [
                {"name": "GET", "value": "GET"},
                {"name": "POST", "value": "POST"},
            ],
            "description": "The HTTP method to listen to",
        },
        {
            "displayName": "Path",
            "name": "path",
            "type": "string",
            "default": "",
            "required": True,
            "description": "The path to listen to",
        },
    ],
}

VERSIONED_NODE: dict[str, Any] = {
    "displayName": "HTTP Request",
    "name": "n8n-nodes-base.httpRequest",
    "group": ["input"],
    "version": [1, 2, 3],
    "description": "Makes an HTTP request and returns the response data",
    "defaults": {"name": "HTTP Request", "color": "#2200DD"},
    "inputs": ["main"],
    "outputs": ["main"],
    "properties": [
        {
            "displayName": "URL",
            "name": "url",
            "type": "string",
            "default": "",
            "required": True,
            "description": "The URL to make the request to",
        },
    ],
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseSimpleNode:
    def test_parse_simple_node(self) -> None:
        entries = parse_node_description(SIMPLE_SET_NODE)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.node_type == "n8n-nodes-base.set"
        assert entry.type_version == 1
        assert entry.display_name == "Set"
        assert (
            entry.description
            == "Sets values on items and optionally remove other values"
        )
        assert entry.group == ["input"]
        assert len(entry.parameters) == 2
        assert entry.parameters[0].name == "keepOnlySet"
        assert entry.parameters[0].type == "boolean"
        assert entry.parameters[0].default is False
        assert entry.parameters[1].name == "values"
        assert entry.credential_types == []
        assert entry.resource_operations == []
        assert entry.input_count == 1
        assert entry.output_count == 1
        assert entry.default_values == {"name": "Set", "color": "#0000FF"}
        assert entry.request_defaults is None


class TestParseNodeWithResources:
    def test_parse_node_with_resources(self) -> None:
        entries = parse_node_description(SLACK_LIKE_NODE)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.node_type == "n8n-nodes-base.slack"
        assert entry.type_version == 2
        assert entry.display_name == "Slack"

        assert len(entry.credential_types) == 2
        assert entry.credential_types[0].name == "slackApi"
        assert entry.credential_types[0].required is True
        assert entry.credential_types[1].name == "slackOAuth2Api"
        assert entry.credential_types[1].required is False

        assert entry.request_defaults is not None
        assert entry.request_defaults["baseURL"] == "https://slack.com/api"

        assert len(entry.resource_operations) == 4
        ro_pairs = [(ro.resource, ro.operation) for ro in entry.resource_operations]
        assert ("message", "send") in ro_pairs
        assert ("message", "update") in ro_pairs
        assert ("channel", "getAll") in ro_pairs
        assert ("channel", "create") in ro_pairs


class TestParseTriggerNode:
    def test_parse_trigger_node(self) -> None:
        entries = parse_node_description(WEBHOOK_TRIGGER_NODE)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.node_type == "n8n-nodes-base.webhook"
        assert entry.group == ["trigger"]
        assert entry.input_count == 0
        assert entry.output_count == 1
        assert entry.resource_operations == []
        assert entry.credential_types == []
        assert len(entry.parameters) == 2
        assert entry.parameters[0].name == "httpMethod"
        assert entry.parameters[1].name == "path"
        assert entry.parameters[1].required is True


class TestParseVersionedNode:
    def test_parse_versioned_node(self) -> None:
        entries = parse_node_description(VERSIONED_NODE)
        assert len(entries) == 3
        for i, ver in enumerate([1, 2, 3]):
            assert entries[i].type_version == ver
            assert entries[i].node_type == "n8n-nodes-base.httpRequest"
            assert entries[i].display_name == "HTTP Request"
            assert len(entries[i].parameters) == 1
            assert entries[i].parameters[0].name == "url"


class TestExtractResourceOperations:
    def test_extract_resource_operations(self) -> None:
        properties = SLACK_LIKE_NODE["properties"]
        ops = extract_resource_operations(properties)
        assert len(ops) == 4
        ro_pairs = [(ro.resource, ro.operation) for ro in ops]
        assert ("message", "send") in ro_pairs
        assert ("message", "update") in ro_pairs
        assert ("channel", "getAll") in ro_pairs
        assert ("channel", "create") in ro_pairs
        send_op = next(ro for ro in ops if ro.operation == "send")
        assert send_op.description == "Send a message to a channel"

    def test_extract_resource_operations_empty(self) -> None:
        properties: list[dict[str, Any]] = [
            {
                "displayName": "Value",
                "name": "value",
                "type": "string",
                "default": "",
            },
        ]
        ops = extract_resource_operations(properties)
        assert ops == []


class TestExtractRequestDefaults:
    def test_extract_request_defaults(self) -> None:
        result = extract_request_defaults(SLACK_LIKE_NODE)
        assert result is not None
        assert result["baseURL"] == "https://slack.com/api"
        assert result["headers"] == {"Content-Type": "application/json"}

    def test_extract_request_defaults_missing(self) -> None:
        result = extract_request_defaults(SIMPLE_SET_NODE)
        assert result is None
