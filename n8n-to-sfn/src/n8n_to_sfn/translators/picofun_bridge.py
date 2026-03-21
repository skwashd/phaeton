"""
PicoFun bridge module wrapping all PicoFun library interactions.

Provides a clean internal interface over PicoFun's spec parsing,
endpoint matching, and Lambda code generation capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from picofun.config import Config
from picofun.lambda_generator import LambdaGenerator
from picofun.models import Endpoint as PicoFunEndpoint
from picofun.spec import Spec
from picofun.template import Template

_HTTP_METHODS = frozenset({"get", "put", "post", "delete", "patch", "head"})


@dataclass(frozen=True)
class Endpoint:
    """A single API endpoint extracted from a parsed spec."""

    method: str
    path: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ApiSpec:
    """Parsed API specification with extracted endpoints and server info."""

    servers: list[dict[str, Any]] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _extract_servers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract server list from OpenAPI 3.x or Swagger 2.0 spec."""
    if "servers" in raw:
        return list(raw["servers"])

    # Swagger 2.0 format
    host = raw.get("host", "")
    base_path = raw.get("basePath", "")
    schemes = raw.get("schemes", ["https"])
    if host:
        scheme = schemes[0] if schemes else "https"
        url = f"{scheme}://{host}{base_path}".rstrip("/")
        return [{"url": url}]

    return []


def _extract_endpoints(raw: dict[str, Any]) -> list[Endpoint]:
    """Extract all endpoints from the spec paths."""
    endpoints: list[Endpoint] = []
    for path, path_details in raw.get("paths", {}).items():
        for method, details in path_details.items():
            if method.lower() in _HTTP_METHODS:
                endpoints.append(
                    Endpoint(method=method.lower(), path=path, details=details)
                )
    return endpoints


def _create_config() -> Config:
    """Create a PicoFun Config with defaults, bypassing TOML file requirement."""
    return Config()


class PicoFunBridge:
    """
    Bridge wrapping PicoFun library interactions behind a clean interface.

    Provides spec parsing, endpoint lookup, and Lambda handler code generation
    without exposing PicoFun internals to the rest of the translation engine.
    """

    def __init__(self, spec_directory: str = "") -> None:
        """
        Initialize bridge with path to local spec file directory.

        Args:
            spec_directory: Directory containing API spec files.

        """
        self._spec_directory = spec_directory

    def load_api_spec(self, spec_filename: str) -> ApiSpec:
        """
        Parse a spec file and return a structured ApiSpec.

        Auto-detects JSON and YAML formats. Supports both OpenAPI 3.x
        and Swagger 2.0 specs.

        Args:
            spec_filename: Name of the spec file within the spec directory.

        Returns:
            Parsed ApiSpec containing servers, endpoints, and raw data.

        """
        spec_path = str(Path(self._spec_directory) / spec_filename)
        raw = Spec(spec_path).parse()
        return ApiSpec(
            servers=_extract_servers(raw),
            endpoints=_extract_endpoints(raw),
            raw=raw,
        )

    def find_endpoint(
        self, api_spec: ApiSpec, method: str, path: str
    ) -> Endpoint | None:
        """
        Find a matching endpoint in the ApiSpec by HTTP method and path.

        Args:
            api_spec: Parsed API specification to search.
            method: HTTP method (case-insensitive).
            path: API endpoint path.

        Returns:
            Matching Endpoint or None if not found.

        """
        method_lower = method.lower()
        for endpoint in api_spec.endpoints:
            if endpoint.method == method_lower and endpoint.path == path:
                return endpoint
        return None

    def render_endpoint(self, base_url: str, endpoint: Endpoint, namespace: str) -> str:
        """
        Render Lambda handler code for a single endpoint.

        Uses PicoFun's LambdaGenerator to produce Python code containing
        picorun imports for API request handling.

        Args:
            base_url: The API server base URL.
            endpoint: The endpoint to generate a handler for.
            namespace: Lambda function namespace prefix.

        Returns:
            Formatted Python handler code as a string.

        """
        config = _create_config()
        template = Template(str(config.template_path))
        generator = LambdaGenerator(template, namespace, config)
        pf_endpoint = PicoFunEndpoint(
            method=endpoint.method,
            path=endpoint.path,
            extra=endpoint.details,
        )
        return generator.render(base_url, pf_endpoint)
