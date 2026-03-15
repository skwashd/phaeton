"""
Slack node translator.

Converts ``n8n-nodes-base.slack`` nodes into Step Functions
``http:invoke`` Task states targeting the Slack Web API.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn.translators.saas import BaseSaaSTranslator, OperationMapping

_SLACK_API = "https://slack.com/api"

_OPERATIONS: dict[str, OperationMapping] = {
    "message:post": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/chat.postMessage",
    ),
    "message:update": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/chat.update",
    ),
    "message:delete": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/chat.delete",
    ),
    "channel:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_SLACK_API}/conversations.info",
    ),
    "channel:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_SLACK_API}/conversations.list",
    ),
    "channel:create": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/conversations.create",
    ),
    "user:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_SLACK_API}/users.info",
    ),
    "user:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_SLACK_API}/users.list",
    ),
    "reaction:add": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/reactions.add",
    ),
    "file:upload": OperationMapping(
        method="POST",
        endpoint_template=f"{_SLACK_API}/files.upload",
    ),
}


class SlackTranslator(BaseSaaSTranslator):
    """Translates Slack nodes into Slack Web API ``http:invoke`` calls."""

    @property
    def node_type(self) -> str:
        """Return the n8n Slack node type."""
        return "n8n-nodes-base.slack"

    @property
    def api_base_url(self) -> str:
        """Return the Slack API base URL."""
        return _SLACK_API

    @property
    def credential_type(self) -> str:
        """Return the Slack credential type."""
        return "slackOAuth2Api"

    @property
    def auth_type(self) -> str:
        """Return the Slack auth type."""
        return "oauth2"

    @property
    def operations(self) -> dict[str, OperationMapping]:
        """Return Slack operation mappings."""
        return _OPERATIONS

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build Slack-specific request body."""
        body: dict[str, Any] = {}

        if op_key == "message:post":
            body["channel"] = params.get("channel", "")
            body["text"] = params.get("text", "")
            if params.get("attachments"):
                body["attachments"] = params["attachments"]
            if params.get("blocks"):
                body["blocks"] = params["blocks"]
        elif op_key == "message:update":
            body["channel"] = params.get("channel", "")
            body["ts"] = params.get("ts", "")
            body["text"] = params.get("text", "")
        elif op_key == "message:delete":
            body["channel"] = params.get("channel", "")
            body["ts"] = params.get("ts", "")
        elif op_key == "channel:create":
            body["name"] = params.get("name", "")
            if params.get("is_private"):
                body["is_private"] = params["is_private"]
        elif op_key == "reaction:add":
            body["channel"] = params.get("channel", "")
            body["timestamp"] = params.get("timestamp", "")
            body["name"] = params.get("name", "")
        else:
            # GET endpoints and fallback: pass non-routing params
            skip_keys = {"resource", "operation"}
            body = {k: v for k, v in params.items() if k not in skip_keys}

        return body
