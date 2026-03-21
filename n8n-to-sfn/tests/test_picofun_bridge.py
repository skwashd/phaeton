"""Tests for PicoFunBridge spec parsing, endpoint matching, and code rendering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n8n_to_sfn.translators.picofun_bridge import ApiSpec, Endpoint, PicoFunBridge


@pytest.fixture
def openapi3_spec(tmp_path: Path) -> Path:
    """Create a minimal OpenAPI 3.0 spec file."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/messages": {
                "post": {
                    "operationId": "postMessage",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = tmp_path / "test_openapi3.json"
    spec_file.write_text(json.dumps(spec))
    return spec_file


@pytest.fixture
def swagger2_spec(tmp_path: Path) -> Path:
    """Create a minimal Swagger 2.0 spec file."""
    spec = {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0"},
        "host": "api.example.com",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = tmp_path / "test_swagger2.json"
    spec_file.write_text(json.dumps(spec))
    return spec_file


class TestLoadApiSpec:
    """Tests for PicoFunBridge.load_api_spec."""

    def test_load_api_spec_openapi3(self, openapi3_spec: Path) -> None:
        """Parse a minimal OpenAPI 3.0 spec file into an ApiSpec."""
        bridge = PicoFunBridge(spec_directory=str(openapi3_spec.parent))
        api_spec = bridge.load_api_spec(openapi3_spec.name)

        assert isinstance(api_spec, ApiSpec)
        assert len(api_spec.endpoints) == 1
        assert api_spec.endpoints[0].method == "post"
        assert api_spec.endpoints[0].path == "/messages"
        assert len(api_spec.servers) == 1
        assert api_spec.servers[0]["url"] == "https://api.example.com"

    def test_load_api_spec_swagger2(self, swagger2_spec: Path) -> None:
        """Parse a minimal Swagger 2.0 spec file into an ApiSpec."""
        bridge = PicoFunBridge(spec_directory=str(swagger2_spec.parent))
        api_spec = bridge.load_api_spec(swagger2_spec.name)

        assert isinstance(api_spec, ApiSpec)
        assert len(api_spec.endpoints) == 1
        assert api_spec.endpoints[0].method == "get"
        assert api_spec.endpoints[0].path == "/users"
        assert len(api_spec.servers) == 1
        assert "api.example.com" in api_spec.servers[0]["url"]


class TestFindEndpoint:
    """Tests for PicoFunBridge.find_endpoint."""

    def test_find_endpoint_exact_match(self, openapi3_spec: Path) -> None:
        """Find endpoint by exact method and path."""
        bridge = PicoFunBridge(spec_directory=str(openapi3_spec.parent))
        api_spec = bridge.load_api_spec(openapi3_spec.name)

        result = bridge.find_endpoint(api_spec, "POST", "/messages")

        assert result is not None
        assert isinstance(result, Endpoint)
        assert result.method == "post"
        assert result.path == "/messages"

    def test_find_endpoint_not_found(self, openapi3_spec: Path) -> None:
        """Return None for non-existent method and path."""
        bridge = PicoFunBridge(spec_directory=str(openapi3_spec.parent))
        api_spec = bridge.load_api_spec(openapi3_spec.name)

        assert bridge.find_endpoint(api_spec, "GET", "/nonexistent") is None
        assert bridge.find_endpoint(api_spec, "DELETE", "/messages") is None


class TestRenderEndpoint:
    """Tests for PicoFunBridge.render_endpoint."""

    def test_render_endpoint(self, openapi3_spec: Path) -> None:
        """Produce non-empty Python code containing picorun imports."""
        bridge = PicoFunBridge(spec_directory=str(openapi3_spec.parent))
        api_spec = bridge.load_api_spec(openapi3_spec.name)
        endpoint = bridge.find_endpoint(api_spec, "POST", "/messages")
        assert endpoint is not None

        code = bridge.render_endpoint("https://api.example.com", endpoint, "test")

        assert isinstance(code, str)
        assert len(code) > 0
        assert "picorun" in code
