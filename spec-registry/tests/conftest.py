"""Shared fixtures for the spec registry test suite."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex, SpecEndpoint

# ---------------------------------------------------------------------------
# Sample spec data
# ---------------------------------------------------------------------------

ACME_SWAGGER2_SPEC: dict[str, Any] = {
    "swagger": "2.0",
    "info": {"title": "Acme API", "version": "1.0.0"},
    "host": "api.acme.com",
    "basePath": "/v1",
    "schemes": ["https"],
    "securityDefinitions": {
        "api_key": {"type": "apiKey", "name": "X-API-Key", "in": "header"},
    },
    "paths": {
        "/widgets": {
            "get": {
                "tags": ["Widgets"],
                "operationId": "listWidgets",
                "summary": "List all widgets",
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "tags": ["Widgets"],
                "operationId": "createWidget",
                "summary": "Create a widget",
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/widgets/{id}": {
            "get": {
                "tags": ["Widgets"],
                "operationId": "getWidget",
                "summary": "Get a widget by ID",
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "tags": ["Widgets"],
                "operationId": "deleteWidget",
                "summary": "Delete a widget",
                "responses": {"204": {"description": "Deleted"}},
            },
        },
    },
}

WIDGET_OPENAPI3_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {"title": "Widget Service", "version": "2.0.0"},
    "servers": [
        {"url": "https://widgets.example.com/api"},
        {"url": "https://staging.widgets.example.com/api"},
    ],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        },
    },
    "paths": {
        "/items": {
            "get": {
                "tags": ["Items"],
                "operationId": "getItems",
                "summary": "List items",
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "tags": ["Items"],
                "operationId": "createItem",
                "summary": "Create an item",
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/items/{itemId}": {
            "put": {
                "tags": ["Items"],
                "operationId": "updateItem",
                "summary": "Update an item",
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_json_spec(directory: Path, filename: str, spec: dict[str, Any]) -> Path:
    """Write a spec dict as JSON to a file in *directory*."""
    path = directory / filename
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return path


def write_yaml_spec(directory: Path, filename: str, spec: dict[str, Any]) -> Path:
    """Write a spec dict as YAML to a file in *directory*."""
    path = directory / filename
    path.write_text(yaml.dump(spec, default_flow_style=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slack_spec() -> ApiSpecEntry:
    """Provide a Slack API spec entry."""
    return ApiSpecEntry(
        spec_filename="n8n-nodes-base.Slack.json",
        service_name="Slack",
        base_urls=["https://slack.com/api"],
        auth_type="oauth2",
        spec_format="openapi3",
        endpoints=[
            SpecEndpoint(
                resource="message",
                operation="postMessage",
                endpoint="POST /chat.postMessage",
            ),
            SpecEndpoint(
                resource="channel",
                operation="list",
                endpoint="GET /conversations.list",
            ),
            SpecEndpoint(
                resource="channel",
                operation="create",
                endpoint="POST /conversations.create",
            ),
        ],
    )


@pytest.fixture
def github_spec() -> ApiSpecEntry:
    """Provide a GitHub API spec entry."""
    return ApiSpecEntry(
        spec_filename="n8n-nodes-base.Github.json",
        service_name="GitHub",
        base_urls=["https://api.github.com"],
        auth_type="bearer",
        spec_format="openapi3",
        endpoints=[
            SpecEndpoint(
                resource="repos",
                operation="listForUser",
                endpoint="GET /users/{username}/repos",
            ),
            SpecEndpoint(
                resource="issues",
                operation="create",
                endpoint="POST /repos/{owner}/{repo}/issues",
            ),
        ],
    )


@pytest.fixture
def spec_index(slack_spec: ApiSpecEntry, github_spec: ApiSpecEntry) -> ApiSpecIndex:
    """Provide a spec index with Slack and GitHub entries."""
    return ApiSpecIndex(
        entries=[slack_spec, github_spec],
        index_timestamp=datetime.now(tz=UTC),
    )
