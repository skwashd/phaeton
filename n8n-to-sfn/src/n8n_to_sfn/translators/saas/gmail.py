"""
Gmail node translator.

Converts ``n8n-nodes-base.gmail`` nodes into Step Functions
``http:invoke`` Task states targeting the Gmail REST API.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn.translators.saas import BaseSaaSTranslator, OperationMapping

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

_OPERATIONS: dict[str, OperationMapping] = {
    "message:send": OperationMapping(
        method="POST",
        endpoint_template=f"{_GMAIL_API}/messages/send",
    ),
    "message:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_GMAIL_API}/messages/{{messageId}}",
    ),
    "message:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_GMAIL_API}/messages",
    ),
    "message:delete": OperationMapping(
        method="DELETE",
        endpoint_template=f"{_GMAIL_API}/messages/{{messageId}}",
    ),
    "message:reply": OperationMapping(
        method="POST",
        endpoint_template=f"{_GMAIL_API}/messages/send",
    ),
    "draft:create": OperationMapping(
        method="POST",
        endpoint_template=f"{_GMAIL_API}/drafts",
    ),
    "draft:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_GMAIL_API}/drafts/{{draftId}}",
    ),
    "draft:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_GMAIL_API}/drafts",
    ),
    "label:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_GMAIL_API}/labels",
    ),
}


class GmailTranslator(BaseSaaSTranslator):
    """Translates Gmail nodes into Gmail API ``http:invoke`` calls."""

    @property
    def node_type(self) -> str:
        """Return the n8n Gmail node type."""
        return "n8n-nodes-base.gmail"

    @property
    def api_base_url(self) -> str:
        """Return the Gmail API base URL."""
        return _GMAIL_API

    @property
    def credential_type(self) -> str:
        """Return the Gmail credential type."""
        return "gmailOAuth2Api"

    @property
    def auth_type(self) -> str:
        """Return the Gmail auth type."""
        return "oauth2"

    @property
    def operations(self) -> dict[str, OperationMapping]:
        """Return Gmail operation mappings."""
        return _OPERATIONS

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build Gmail-specific request body."""
        body: dict[str, Any] = {}

        if op_key in ("message:send", "message:reply"):
            body["raw"] = self._build_raw_message(params)
            if op_key == "message:reply" and params.get("threadId"):
                body["threadId"] = params["threadId"]
        elif op_key == "draft:create":
            body["message"] = {"raw": self._build_raw_message(params)}
        elif op_key.endswith(":getAll"):
            if params.get("q"):
                body["q"] = params["q"]
            if params.get("maxResults"):
                body["maxResults"] = params["maxResults"]
        else:
            skip_keys = {"resource", "operation"}
            body = {k: v for k, v in params.items() if k not in skip_keys}

        return body

    @staticmethod
    def _build_raw_message(params: dict[str, Any]) -> str:
        """Build a placeholder RFC 2822 message reference from parameters."""
        to = params.get("toRecipients", params.get("to", ""))
        subject = params.get("subject", "")
        message = params.get("message", params.get("body", ""))
        cc = params.get("ccRecipients", params.get("cc", ""))
        bcc = params.get("bccRecipients", params.get("bcc", ""))

        headers = f"To: {to}\nSubject: {subject}"
        if cc:
            headers += f"\nCc: {cc}"
        if bcc:
            headers += f"\nBcc: {bcc}"

        return f"{headers}\n\n{message}"
