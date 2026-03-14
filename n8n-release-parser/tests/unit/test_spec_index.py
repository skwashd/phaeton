"""Tests for the spec_index module."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from n8n_release_parser.spec_index import (
    build_spec_index,
    extract_resource_operations_from_spec,
    load_index,
    normalize_base_url,
    save_index,
)

# ---------------------------------------------------------------------------
# Fixture spec data
# ---------------------------------------------------------------------------

ACME_SWAGGER2_SPEC: dict = {
    "swagger": "2.0",
    "info": {"title": "Acme API", "version": "1.0.0"},
    "host": "api.acme.com",
    "basePath": "/v1",
    "schemes": ["https"],
    "securityDefinitions": {
        "api_key": {"type": "apiKey", "name": "X-API-Key", "in": "header"}
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

WIDGET_OPENAPI3_SPEC: dict = {
    "openapi": "3.0.3",
    "info": {"title": "Widget Service", "version": "2.0.0"},
    "servers": [
        {"url": "https://widgets.example.com/api"},
        {"url": "https://staging.widgets.example.com/api"},
    ],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
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


def _write_json_spec(directory: Path, filename: str, spec: dict) -> Path:
    path = directory / filename
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return path


def _write_yaml_spec(directory: Path, filename: str, spec: dict) -> Path:
    path = directory / filename
    path.write_text(yaml.dump(spec, default_flow_style=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildSpecIndexSwagger2:
    """Tests for BuildSpecIndexSwagger2."""

    def test_build_spec_index_swagger2(self, tmp_path: Path) -> None:
        """Test build spec index swagger2."""
        _write_json_spec(tmp_path, "acme.json", ACME_SWAGGER2_SPEC)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.spec_filename == "acme.json"
        assert entry.service_name == "Acme API"
        assert entry.spec_format == "swagger2"
        assert entry.auth_type == "apiKey"
        assert "https://api.acme.com/v1" in entry.base_urls
        assert len(entry.endpoints) == 4

        ops = {ep.operation for ep in entry.endpoints}
        assert "listWidgets" in ops
        assert "createWidget" in ops
        assert "getWidget" in ops
        assert "deleteWidget" in ops


class TestBuildSpecIndexOpenapi3:
    """Tests for BuildSpecIndexOpenapi3."""

    def test_build_spec_index_openapi3(self, tmp_path: Path) -> None:
        """Test build spec index openapi3."""
        _write_json_spec(tmp_path, "widget.json", WIDGET_OPENAPI3_SPEC)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.spec_filename == "widget.json"
        assert entry.service_name == "Widget Service"
        assert entry.spec_format == "openapi3"
        assert entry.auth_type == "bearer"
        assert len(entry.base_urls) == 2
        assert "https://widgets.example.com/api" in entry.base_urls
        assert len(entry.endpoints) == 3


class TestBuildSpecIndexMixed:
    """Tests for BuildSpecIndexMixed."""

    def test_build_spec_index_mixed_directory(self, tmp_path: Path) -> None:
        """Test build spec index mixed directory."""
        _write_json_spec(tmp_path, "acme.json", ACME_SWAGGER2_SPEC)
        _write_json_spec(tmp_path, "widget.json", WIDGET_OPENAPI3_SPEC)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 2
        names = {e.service_name for e in index.entries}
        assert "Acme API" in names
        assert "Widget Service" in names
        formats = {e.spec_format for e in index.entries}
        assert "swagger2" in formats
        assert "openapi3" in formats
        assert index.index_timestamp is not None


class TestNormalizeBaseUrl:
    """Tests for NormalizeBaseUrl."""

    def test_normalize_base_url_various_formats(self) -> None:
        """Test normalize base url various formats."""
        assert normalize_base_url("https://api.example.com/v1/") == "api.example.com/v1"
        assert normalize_base_url("http://api.example.com/v1/") == "api.example.com/v1"
        assert normalize_base_url("https://www.example.com/") == "example.com"
        assert normalize_base_url("http://www.example.com") == "example.com"
        assert normalize_base_url("HTTPS://API.EXAMPLE.COM/V1/") == "api.example.com/v1"
        assert normalize_base_url("api.example.com/v1") == "api.example.com/v1"
        assert normalize_base_url("https://api.example.com///") == "api.example.com"


class TestExtractResourceOperations:
    """Tests for ExtractResourceOperations."""

    def test_extract_resource_operations_from_spec(self) -> None:
        """Test extract resource operations from spec."""
        endpoints = extract_resource_operations_from_spec(ACME_SWAGGER2_SPEC)

        assert len(endpoints) == 4

        endpoint_strs = {ep.endpoint for ep in endpoints}
        assert "GET /widgets" in endpoint_strs
        assert "POST /widgets" in endpoint_strs
        assert "GET /widgets/{id}" in endpoint_strs
        assert "DELETE /widgets/{id}" in endpoint_strs

        for ep in endpoints:
            assert ep.resource == "Widgets"

        ops = {ep.operation for ep in endpoints}
        assert "listWidgets" in ops
        assert "createWidget" in ops


class TestSaveLoadRoundtrip:
    """Tests for SaveLoadRoundtrip."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Test save load roundtrip."""
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        _write_json_spec(specs_dir, "acme.json", ACME_SWAGGER2_SPEC)

        original = build_spec_index(specs_dir)
        index_path = tmp_path / "index.json"
        save_index(original, index_path)

        assert index_path.exists()

        loaded = load_index(index_path)
        assert len(loaded.entries) == len(original.entries)
        assert loaded.entries[0].service_name == original.entries[0].service_name
        assert loaded.entries[0].spec_format == original.entries[0].spec_format
        assert loaded.entries[0].auth_type == original.entries[0].auth_type
        assert loaded.entries[0].base_urls == original.entries[0].base_urls
        assert len(loaded.entries[0].endpoints) == len(original.entries[0].endpoints)
        assert loaded.index_timestamp == original.index_timestamp


class TestHandlesMissingFields:
    """Tests for HandlesMissingFields."""

    def test_handles_missing_fields(self, tmp_path: Path) -> None:
        """Test handles missing fields."""
        minimal_spec: dict = {
            "openapi": "3.0.0",
            "info": {"title": "Bare API", "version": "0.1.0"},
            "paths": {
                "/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        _write_json_spec(tmp_path, "bare.json", minimal_spec)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.service_name == "Bare API"
        assert entry.auth_type == "none"
        assert entry.base_urls == []
        assert entry.spec_format == "openapi3"
        assert len(entry.endpoints) == 1
        ep = entry.endpoints[0]
        assert ep.resource == "health"
        assert ep.endpoint == "GET /health"
        # No operationId, so operation should be derived
        assert "get" in ep.operation


class TestYamlSpecParsing:
    """Tests for YamlSpecParsing."""

    def test_yaml_spec_parsing(self, tmp_path: Path) -> None:
        """Test yaml spec parsing."""
        _write_yaml_spec(tmp_path, "widget.yaml", WIDGET_OPENAPI3_SPEC)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.spec_filename == "widget.yaml"
        assert entry.service_name == "Widget Service"
        assert entry.spec_format == "openapi3"
        assert entry.auth_type == "bearer"
        assert len(entry.endpoints) == 3

    def test_yml_extension(self, tmp_path: Path) -> None:
        """Test yml extension."""
        _write_yaml_spec(tmp_path, "acme.yml", ACME_SWAGGER2_SPEC)
        index = build_spec_index(tmp_path)

        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.spec_filename == "acme.yml"
        assert entry.spec_format == "swagger2"
