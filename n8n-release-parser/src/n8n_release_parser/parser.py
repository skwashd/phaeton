"""
Parse n8n INodeTypeDescription JSON into structured NodeTypeEntry models.

Provides functions to extract node type descriptions from raw JSON dicts
and from n8n-nodes-base package directories. Handles versioned nodes,
resource/operation pair extraction, and request defaults.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from n8n_release_parser.cache import NodeCache, content_hash
from n8n_release_parser.models import (
    CredentialType,
    NodeParameter,
    NodeTypeEntry,
    ResourceOperation,
)

logger = logging.getLogger(__name__)


def _count_connections(connections: list[str] | list[dict[str, str]] | str) -> int:
    """
    Count the number of input or output connections from a description field.

    The ``inputs`` / ``outputs`` field in an n8n node description can be either
    a list of strings (e.g. ``["main"]``) or a list of connection-type objects.
    Each element counts as one connection.
    """
    if isinstance(connections, list):
        return len(connections)
    return 1


def _parse_parameters(properties: list[dict[str, Any]]) -> list[NodeParameter]:
    """Convert raw property dicts into ``NodeParameter`` model instances."""
    params: list[NodeParameter] = []
    for prop in properties:
        params.append(
            NodeParameter(
                name=prop.get("name", ""),
                display_name=prop.get("displayName", ""),
                type=prop.get("type", "string"),
                default=prop.get("default"),
                required=prop.get("required", False),
                options=prop.get("options"),
                has_expressions=bool(prop.get("expressions")),
                display_options=prop.get("displayOptions"),
                description=prop.get("description", ""),
            )
        )
    return params


def _parse_credentials(
    credentials: list[dict[str, Any]] | None,
) -> list[CredentialType]:
    """Convert raw credential dicts into ``CredentialType`` model instances."""
    if not credentials:
        return []
    return [
        CredentialType(
            name=cred.get("name", ""),
            required=cred.get("required", True),
        )
        for cred in credentials
    ]


def _resolve_resource_values(
    show_resource: list[str] | None,
    resources: list[dict[str, Any]],
) -> list[str]:
    """
    Return the list of resource values an operation applies to.

    When ``show_resource`` is provided (from ``displayOptions.show.resource``),
    those values are used directly. Otherwise every known resource value is
    returned.
    """
    if show_resource:
        return list(show_resource)
    return [res.get("value", res.get("name", "")) for res in resources]


def extract_resource_operations(
    properties: list[dict[str, Any]],
) -> list[ResourceOperation]:
    """
    Extract resource/operation pairs from a node's properties array.

    Scans for properties named ``resource`` and ``operation``. Builds
    combinations of resource values crossed with their operations. When an
    operation property specifies ``displayOptions`` that filter by resource,
    only the matching resource values are paired.
    """
    resources: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []

    for prop in properties:
        if prop.get("name") == "resource":
            resources.extend(prop.get("options", []))
        elif prop.get("name") == "operation":
            operations.append(prop)

    if not resources:
        return []

    result: list[ResourceOperation] = []

    for op_prop in operations:
        display_options = op_prop.get("displayOptions", {})
        show_resource = display_options.get("show", {}).get("resource")
        resource_values = _resolve_resource_values(show_resource, resources)

        for op_opt in op_prop.get("options", []):
            op_name = op_opt.get("value", op_opt.get("name", ""))
            op_desc = op_opt.get("description", "")
            for res_value in resource_values:
                result.append(
                    ResourceOperation(
                        resource=res_value,
                        operation=op_name,
                        description=op_desc,
                    )
                )

    return result


def extract_request_defaults(description: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract the ``requestDefaults`` field from a node description.

    Returns ``None`` when the field is absent or empty.
    """
    rd = description.get("requestDefaults")
    if not rd:
        return None
    return dict(rd)


def parse_node_description(description: dict[str, Any]) -> list[NodeTypeEntry]:
    """
    Parse a raw n8n INodeTypeDescription dict into NodeTypeEntry instances.

    Extracts: node type name, version, display name, description, group,
    parameters, credential types, resource/operation pairs, input/output count,
    defaults, and request_defaults.

    For versioned nodes where ``version`` is a list, one ``NodeTypeEntry`` is
    produced per version number.
    """
    name: str = description.get("name", "")
    display_name: str = description.get("displayName", "")
    desc_text: str = description.get("description", "")
    group: list[str] = description.get("group", [])
    defaults: dict[str, Any] = description.get("defaults", {})
    properties: list[dict[str, Any]] = description.get("properties", [])
    credentials = description.get("credentials")
    inputs = description.get("inputs", ["main"])
    outputs = description.get("outputs", ["main"])

    version_raw = description.get("version", 1)
    if isinstance(version_raw, list):
        versions: list[int] = version_raw
    else:
        versions = [int(version_raw)]

    parameters = _parse_parameters(properties)
    credential_types = _parse_credentials(credentials)
    resource_operations = extract_resource_operations(properties)
    request_defaults = extract_request_defaults(description)
    input_count = _count_connections(inputs)
    output_count = _count_connections(outputs)

    entries: list[NodeTypeEntry] = []
    for ver in versions:
        entries.append(
            NodeTypeEntry(
                node_type=name,
                type_version=ver,
                display_name=display_name,
                description=desc_text,
                group=list(group),
                parameters=list(parameters),
                credential_types=list(credential_types),
                resource_operations=list(resource_operations),
                input_count=input_count,
                output_count=output_count,
                default_values=dict(defaults),
                request_defaults=request_defaults,
            )
        )

    return entries


def _collect_node_files(
    base_dir: Path,
    package_dir: Path,
    cache: NodeCache | None,
    entries: list[NodeTypeEntry],
    seen_paths: set[str],
) -> None:
    """Scan *base_dir* for ``.node.json`` files and parse or cache-load them."""
    for json_file in sorted(base_dir.rglob("*.node.json")):
        rel = str(json_file.relative_to(package_dir))
        seen_paths.add(rel)
        try:
            raw = json_file.read_bytes()
            h = content_hash(raw)
            if cache is not None:
                cached = cache.get(rel, h)
                if cached is not None:
                    logger.debug("Cache hit for %s", rel)
                    entries.extend(cached)
                    continue
            desc = json.loads(raw.decode("utf-8"))
            parsed = parse_node_description(desc)
            entries.extend(parsed)
            if cache is not None:
                cache.put(rel, h, parsed)
        except json.JSONDecodeError, KeyError:
            logger.warning("Skipping invalid node file: %s", json_file)


def _try_known_index(
    package_dir: Path,
    cache: NodeCache | None,
) -> list[NodeTypeEntry] | None:
    """Attempt to load entries from ``known/nodes.json``, returning ``None`` on miss."""
    known_index = package_dir / "known" / "nodes.json"
    if not known_index.is_file():
        return None

    logger.info("Loading node index from %s", known_index)
    raw_bytes = known_index.read_bytes()
    file_key = str(known_index.relative_to(package_dir))
    h = content_hash(raw_bytes)

    if cache is not None:
        cached = cache.get(file_key, h)
        if cached is not None:
            logger.debug("Cache hit for %s", file_key)
            cache.save()
            return cached

    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, list):
        return None

    entries: list[NodeTypeEntry] = []
    for desc in data:
        entries.extend(parse_node_description(desc))

    if cache is not None:
        cache.put(file_key, h, entries)
        cache.save()
    return entries


def extract_descriptions_from_package(
    package_dir: Path,
    *,
    cache_dir: Path | None = None,
    no_cache: bool = False,
) -> list[NodeTypeEntry]:
    """
    Extract all node descriptions from an n8n-nodes-base package directory.

    Looks for a ``known/nodes.json`` or similar JSON index of node descriptions.
    Falls back to scanning for individual node description ``.json`` files in
    the ``nodes`` subdirectory.

    When caching is enabled (the default), parsed results are stored keyed by
    SHA-256 content hash so that unchanged files are not re-parsed on
    subsequent runs.

    Args:
        package_dir: Root of the n8n-nodes-base package.
        cache_dir: Directory for the cache file.  ``None`` uses the default
            ``~/.cache/phaeton/release-parser/``.
        no_cache: If ``True``, skip the cache entirely and re-parse every file.

    """
    cache: NodeCache | None = None
    if not no_cache:
        cache = NodeCache(cache_dir) if cache_dir else NodeCache()
        cache.load()

    # Fast path: single index file.
    from_index = _try_known_index(package_dir, cache)
    if from_index is not None:
        return from_index

    entries: list[NodeTypeEntry] = []
    seen_paths: set[str] = set()

    nodes_dir = package_dir / "nodes"
    if nodes_dir.is_dir():
        _collect_node_files(nodes_dir, package_dir, cache, entries, seen_paths)

    dist_dir = package_dir / "dist"
    if not entries and dist_dir.is_dir():
        _collect_node_files(dist_dir, package_dir, cache, entries, seen_paths)

    # Evict cache entries for files that no longer exist.
    if cache is not None:
        for stale in cache.known_paths() - seen_paths:
            cache.remove(stale)
        cache.save()

    return entries
