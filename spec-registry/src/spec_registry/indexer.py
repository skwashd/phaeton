"""
API spec indexing.

Builds a searchable index from Swagger 2.0 and OpenAPI 3.x spec files,
mapping each spec to its service name, base URLs, authentication type,
and resource/operation/endpoint tuples.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex, SpecEndpoint

from spec_registry.storage import StorageBackend


def normalize_base_url(url: str) -> str:
    """Normalize a URL for matching: lowercase, strip trailing slashes, strip protocol."""
    result = url.lower().strip()
    for prefix in ("https://", "http://"):
        if result.startswith(prefix):
            result = result[len(prefix) :]
            break
    if result.startswith("www."):
        result = result[4:]
    return result.rstrip("/")


def _classify_single_scheme(definition: dict) -> str | None:
    """
    Classify a single security scheme definition into a canonical auth type.

    Returns one of oauth2, bearer, apiKey, basic, or None if unrecognised.
    """
    scheme_type = definition.get("type", "").lower()
    if scheme_type == "oauth2":
        return "oauth2"
    if scheme_type == "apikey":
        return "apiKey"
    if scheme_type == "basic":
        return "basic"
    if scheme_type == "http":
        http_scheme = definition.get("scheme", "").lower()
        return {"bearer": "bearer", "basic": "basic"}.get(http_scheme)
    return None


def _extract_security_schemes(spec: dict) -> dict:
    """Pull the security-scheme mapping from either Swagger 2 or OpenAPI 3."""
    if "securityDefinitions" in spec:
        return spec["securityDefinitions"]
    components = spec.get("components", {})
    if isinstance(components, dict) and "securitySchemes" in components:
        return components["securitySchemes"]
    return {}


def _detect_auth_type(spec: dict) -> str:
    """
    Detect the authentication type from a parsed API spec.

    Inspects securityDefinitions (Swagger 2.0) or
    components.securitySchemes (OpenAPI 3.x) and returns one of:
    oauth2, bearer, apiKey, basic, none.
    """
    schemes = _extract_security_schemes(spec)
    if not schemes:
        return "none"

    types_found: set[str] = set()
    for _name, definition in schemes.items():
        classified = _classify_single_scheme(definition)
        if classified:
            types_found.add(classified)

    # Priority order: oauth2 > bearer > apiKey > basic
    for auth in ("oauth2", "bearer", "apiKey", "basic"):
        if auth in types_found:
            return auth

    return "none"


def _extract_base_urls_swagger2(spec: dict) -> list[str]:
    """Extract base URLs from a Swagger 2.0 spec."""
    host = spec.get("host", "")
    base_path = spec.get("basePath", "")
    if not host:
        return []
    schemes = spec.get("schemes", ["https"])
    urls: list[str] = []
    for scheme in schemes:
        url = f"{scheme}://{host}{base_path}".rstrip("/")
        urls.append(url)
    return urls


def _extract_base_urls_openapi3(spec: dict) -> list[str]:
    """Extract base URLs from an OpenAPI 3.x spec."""
    servers = spec.get("servers", [])
    return [s["url"].rstrip("/") for s in servers if "url" in s]


def extract_resource_operations_from_spec(spec: dict) -> list[SpecEndpoint]:
    """Extract resource/operation/endpoint triples from an API spec's paths."""
    paths = spec.get("paths", {})
    http_methods = {"get", "post", "put", "delete", "patch"}
    endpoints: list[SpecEndpoint] = []

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in http_methods:
            if method not in path_item:
                continue
            operation_def = path_item[method]
            if not isinstance(operation_def, dict):
                continue

            # Resource: first tag or first meaningful path segment
            tags = operation_def.get("tags", [])
            if tags:
                resource = tags[0]
            else:
                segments = [s for s in path.split("/") if s and not s.startswith("{")]
                resource = segments[0] if segments else "default"

            # Operation: operationId or derived from method+path
            operation_id = operation_def.get("operationId")
            operation = operation_id or f"{method}_{path.replace('/', '_').strip('_')}"

            endpoint_str = f"{method.upper()} {path}"
            endpoints.append(
                SpecEndpoint(
                    resource=resource,
                    operation=operation,
                    endpoint=endpoint_str,
                )
            )

    return endpoints


def build_spec_index(specs_dir: Path) -> ApiSpecIndex:
    """
    Scan a directory of API spec files and build a searchable index.

    Handles both JSON and YAML files, both Swagger 2.0 and OpenAPI 3.x.
    """
    entries: list[ApiSpecEntry] = []
    spec_files = sorted(
        p
        for p in specs_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".json", ".yaml", ".yml"}
    )

    for spec_file in spec_files:
        content = spec_file.read_text(encoding="utf-8")
        if spec_file.suffix.lower() == ".json":
            spec = json.loads(content)
        else:
            spec = yaml.safe_load(content)

        if not isinstance(spec, dict):
            continue

        # Detect format
        if "swagger" in spec and str(spec["swagger"]).startswith("2."):
            spec_format = "swagger2"
        elif "openapi" in spec:
            spec_format = "openapi3"
        else:
            spec_format = "openapi3"

        # Extract service name
        info = spec.get("info", {})
        service_name = info.get("title", "") if isinstance(info, dict) else ""
        if not service_name:
            service_name = spec_file.stem

        # Extract base URLs
        if spec_format == "swagger2":
            base_urls = _extract_base_urls_swagger2(spec)
        else:
            base_urls = _extract_base_urls_openapi3(spec)

        # Extract auth type
        auth_type = _detect_auth_type(spec)

        # Extract endpoints
        endpoints = extract_resource_operations_from_spec(spec)

        entries.append(
            ApiSpecEntry(
                spec_filename=spec_file.name,
                service_name=service_name,
                base_urls=base_urls,
                auth_type=auth_type,
                spec_format=spec_format,
                endpoints=endpoints,
            )
        )

    return ApiSpecIndex(
        entries=entries,
        index_timestamp=datetime.now(tz=UTC),
    )


def save_index(index: ApiSpecIndex, path: Path) -> None:
    """Serialize the spec index to JSON."""
    path.write_text(index.model_dump_json(indent=2), encoding="utf-8")


def load_index(path: Path) -> ApiSpecIndex:
    """Load a previously saved spec index from JSON."""
    content = path.read_text(encoding="utf-8")
    return ApiSpecIndex.model_validate_json(content)


def save_index_to_backend(
    index: ApiSpecIndex,
    backend: StorageBackend,
    key: str = "spec_index.json",
) -> str:
    """Serialize the spec index to a storage backend and return the location."""
    return backend.write(key, index.model_dump_json(indent=2))


def load_index_from_backend(
    backend: StorageBackend,
    key: str = "spec_index.json",
) -> ApiSpecIndex | None:
    """Load a spec index from a storage backend.  Returns ``None`` if not found."""
    content = backend.read(key)
    if content is None:
        return None
    return ApiSpecIndex.model_validate_json(content)
