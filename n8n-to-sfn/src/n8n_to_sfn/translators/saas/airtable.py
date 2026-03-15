"""
Airtable node translator.

Converts ``n8n-nodes-base.airtable`` nodes into Step Functions
``http:invoke`` Task states targeting the Airtable REST API.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn.translators.saas import BaseSaaSTranslator, OperationMapping

_AIRTABLE_API = "https://api.airtable.com/v0"

_OPERATIONS: dict[str, OperationMapping] = {
    "record:create": OperationMapping(
        method="POST",
        endpoint_template=f"{_AIRTABLE_API}/{{baseId}}/{{tableId}}",
    ),
    "record:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_AIRTABLE_API}/{{baseId}}/{{tableId}}/{{recordId}}",
    ),
    "record:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_AIRTABLE_API}/{{baseId}}/{{tableId}}",
    ),
    "record:update": OperationMapping(
        method="PATCH",
        endpoint_template=f"{_AIRTABLE_API}/{{baseId}}/{{tableId}}",
    ),
    "record:delete": OperationMapping(
        method="DELETE",
        endpoint_template=f"{_AIRTABLE_API}/{{baseId}}/{{tableId}}/{{recordId}}",
    ),
}


class AirtableTranslator(BaseSaaSTranslator):
    """Translates Airtable nodes into Airtable API ``http:invoke`` calls."""

    @property
    def node_type(self) -> str:
        """Return the n8n Airtable node type."""
        return "n8n-nodes-base.airtable"

    @property
    def api_base_url(self) -> str:
        """Return the Airtable API base URL."""
        return _AIRTABLE_API

    @property
    def credential_type(self) -> str:
        """Return the Airtable credential type."""
        return "airtableApi"

    @property
    def auth_type(self) -> str:
        """Return the Airtable auth type."""
        return "api_key"

    @property
    def operations(self) -> dict[str, OperationMapping]:
        """Return Airtable operation mappings."""
        return _OPERATIONS

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build Airtable-specific request body."""
        body: dict[str, Any] = {}

        if op_key == "record:create":
            fields = params.get("fields", {})
            body["fields"] = fields
            if params.get("typecast"):
                body["typecast"] = True
        elif op_key == "record:update":
            records = params.get("records", [])
            if records:
                body["records"] = records
            else:
                record_id = params.get("recordId", "")
                fields = params.get("fields", {})
                body["records"] = [{"id": record_id, "fields": fields}]
            if params.get("typecast"):
                body["typecast"] = True
        else:
            skip_keys = {"resource", "operation", "baseId", "tableId", "recordId"}
            body = {k: v for k, v in params.items() if k not in skip_keys}

        return body
