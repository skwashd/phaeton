"""
Google Sheets node translator.

Converts ``n8n-nodes-base.googleSheets`` nodes into Step Functions
``http:invoke`` Task states targeting the Google Sheets REST API v4.
"""

from __future__ import annotations

from typing import Any

from n8n_to_sfn.translators.saas import BaseSaaSTranslator, OperationMapping

_SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

_OPERATIONS: dict[str, OperationMapping] = {
    "sheet:appendOrUpdate": OperationMapping(
        method="POST",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}/values/{{range}}:append",
    ),
    "sheet:append": OperationMapping(
        method="POST",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}/values/{{range}}:append",
    ),
    "sheet:read": OperationMapping(
        method="GET",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}/values/{{range}}",
    ),
    "sheet:update": OperationMapping(
        method="PUT",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}/values/{{range}}",
    ),
    "sheet:clear": OperationMapping(
        method="POST",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}/values/{{range}}:clear",
    ),
    "sheet:delete": OperationMapping(
        method="POST",
        endpoint_template=f"{_SHEETS_API}/{{spreadsheetId}}:batchUpdate",
    ),
    "spreadsheet:create": OperationMapping(
        method="POST",
        endpoint_template=_SHEETS_API,
    ),
}


class GoogleSheetsTranslator(BaseSaaSTranslator):
    """Translates Google Sheets nodes into Sheets API ``http:invoke`` calls."""

    @property
    def node_type(self) -> str:
        """Return the n8n Google Sheets node type."""
        return "n8n-nodes-base.googleSheets"

    @property
    def api_base_url(self) -> str:
        """Return the Google Sheets API base URL."""
        return _SHEETS_API

    @property
    def credential_type(self) -> str:
        """Return the Google Sheets credential type."""
        return "googleSheetsOAuth2Api"

    @property
    def auth_type(self) -> str:
        """Return the Google Sheets auth type."""
        return "oauth2"

    @property
    def operations(self) -> dict[str, OperationMapping]:
        """Return Google Sheets operation mappings."""
        return _OPERATIONS

    def _build_request_body(
        self,
        op_key: str,
        params: dict[str, Any],
        mapping: OperationMapping | None,
    ) -> dict[str, Any]:
        """Build Google Sheets-specific request body."""
        body: dict[str, Any] = {}

        if op_key in ("sheet:append", "sheet:appendOrUpdate", "sheet:update"):
            values = params.get("values", params.get("rows", []))
            body["values"] = values if isinstance(values, list) else [values]
            body["majorDimension"] = params.get("majorDimension", "ROWS")
            body["range"] = params.get("range", "Sheet1")
        elif op_key == "sheet:delete":
            sheet_id = params.get("sheetId", 0)
            start_index = params.get("startIndex", 0)
            end_index = params.get("endIndex", 1)
            body["requests"] = [
                {
                    "deleteRange": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start_index,
                            "endRowIndex": end_index,
                        },
                        "shiftDimension": "ROWS",
                    },
                }
            ]
        elif op_key == "spreadsheet:create":
            body["properties"] = {"title": params.get("title", "Untitled")}
        else:
            skip_keys = {"resource", "operation"}
            body = {k: v for k, v in params.items() if k not in skip_keys}

        return body
