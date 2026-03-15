"""
Notion node translator.

Converts ``n8n-nodes-base.notion`` nodes into Step Functions
``http:invoke`` Task states targeting the Notion REST API.
"""

from __future__ import annotations

from typing import Any, ClassVar

from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.saas import BaseSaaSTranslator, OperationMapping

_NOTION_API = "https://api.notion.com/v1"

_OPERATIONS: dict[str, OperationMapping] = {
    "page:create": OperationMapping(
        method="POST",
        endpoint_template=f"{_NOTION_API}/pages",
    ),
    "page:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_NOTION_API}/pages/{{pageId}}",
    ),
    "page:update": OperationMapping(
        method="PATCH",
        endpoint_template=f"{_NOTION_API}/pages/{{pageId}}",
    ),
    "database:get": OperationMapping(
        method="GET",
        endpoint_template=f"{_NOTION_API}/databases/{{databaseId}}",
    ),
    "database:getAll": OperationMapping(
        method="POST",
        endpoint_template=f"{_NOTION_API}/databases/{{databaseId}}/query",
    ),
    "block:getAll": OperationMapping(
        method="GET",
        endpoint_template=f"{_NOTION_API}/blocks/{{blockId}}/children",
    ),
    "block:append": OperationMapping(
        method="PATCH",
        endpoint_template=f"{_NOTION_API}/blocks/{{blockId}}/children",
    ),
    "search:page": OperationMapping(
        method="POST",
        endpoint_template=f"{_NOTION_API}/search",
    ),
}


class NotionTranslator(BaseSaaSTranslator):
    """Translates Notion nodes into Notion API ``http:invoke`` calls."""

    @property
    def node_type(self) -> str:
        """Return the n8n Notion node type."""
        return "n8n-nodes-base.notion"

    @property
    def api_base_url(self) -> str:
        """Return the Notion API base URL."""
        return _NOTION_API

    @property
    def credential_type(self) -> str:
        """Return the Notion credential type."""
        return "notionApi"

    @property
    def auth_type(self) -> str:
        """Return the Notion auth type."""
        return "api_key"

    @property
    def operations(self) -> dict[str, OperationMapping]:
        """Return Notion operation mappings."""
        return _OPERATIONS

    def _build_headers(self, context: TranslationContext) -> dict[str, str]:
        """Build Notion-specific headers including API version."""
        headers = super()._build_headers(context)
        headers["Notion-Version"] = "2022-06-28"
        return headers

    _BODY_BUILDERS: ClassVar[dict[str, str]] = {
        "page:create": "_body_page_create",
        "page:update": "_body_page_update",
        "database:getAll": "_body_database_query",
        "block:append": "_body_block_append",
        "search:page": "_body_search",
    }

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build Notion-specific request body."""
        builder_name = self._BODY_BUILDERS.get(op_key)
        if builder_name is not None:
            return getattr(self, builder_name)(params)
        skip_keys = {"resource", "operation"}
        return {k: v for k, v in params.items() if k not in skip_keys}

    @staticmethod
    def _body_page_create(params: dict[str, Any]) -> dict[str, Any]:
        """Build body for page:create."""
        body: dict[str, Any] = {"parent": {"database_id": params.get("databaseId", "")}}
        if params.get("properties"):
            body["properties"] = params["properties"]
        if params.get("content"):
            body["children"] = params["content"]
        return body

    @staticmethod
    def _body_page_update(params: dict[str, Any]) -> dict[str, Any]:
        """Build body for page:update."""
        body: dict[str, Any] = {}
        if params.get("properties"):
            body["properties"] = params["properties"]
        if params.get("archived") is not None:
            body["archived"] = params["archived"]
        return body

    @staticmethod
    def _body_database_query(params: dict[str, Any]) -> dict[str, Any]:
        """Build body for database:getAll (query)."""
        body: dict[str, Any] = {}
        if params.get("filter"):
            body["filter"] = params["filter"]
        if params.get("sorts"):
            body["sorts"] = params["sorts"]
        if params.get("pageSize"):
            body["page_size"] = params["pageSize"]
        return body

    @staticmethod
    def _body_block_append(params: dict[str, Any]) -> dict[str, Any]:
        """Build body for block:append."""
        return {"children": params.get("children", params.get("blocks", []))}

    @staticmethod
    def _body_search(params: dict[str, Any]) -> dict[str, Any]:
        """Build body for search:page."""
        body: dict[str, Any] = {"query": params.get("query", params.get("text", ""))}
        if params.get("filter"):
            body["filter"] = params["filter"]
        return body
