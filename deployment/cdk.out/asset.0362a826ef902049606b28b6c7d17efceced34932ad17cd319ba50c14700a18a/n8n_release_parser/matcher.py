"""
API spec matching.

Matches n8n nodes to API specs using URL fuzzy-matching, service name
matching, and operation verification. Generates mapping files linking
n8n node operations to spec endpoint paths.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from n8n_release_parser.models import (
    ApiSpecEntry,
    ApiSpecIndex,
    NodeApiMapping,
    NodeCatalog,
    NodeTypeEntry,
)
from n8n_release_parser.spec_index import normalize_base_url

# Suffixes commonly appended to node type service names that should be
# stripped for comparison purposes.
_SERVICE_NAME_SUFFIXES = re.compile(r"(api|v\d+|trigger)$", re.IGNORECASE)


def extract_base_url_from_node(node: NodeTypeEntry) -> str | None:
    """
    Extract base URL from node's request_defaults.

    Looks for ``baseURL`` or ``url`` keys in the node's *request_defaults*
    dict and returns the first one found, or *None* if neither is present.
    """
    if not node.request_defaults:
        return None

    for key in ("baseURL", "url"):
        value = node.request_defaults.get(key)
        if value and isinstance(value, str):
            return value

    return None


def fuzzy_match_url(
    node_url: str,
    spec_index: ApiSpecIndex,
    threshold: float = 0.8,
) -> list[ApiSpecEntry]:
    """
    Find specs whose base URLs match the node's URL.

    Normalizes both the *node_url* and each spec entry's base URLs using
    :func:`normalize_base_url`, then scores them with
    :func:`rapidfuzz.fuzz.ratio`.  Only entries exceeding *threshold*
    (0-to-1 scale) are returned, sorted best-match-first.
    """
    normalized_node = normalize_base_url(node_url)
    if not normalized_node:
        return []

    scored: list[tuple[float, ApiSpecEntry]] = []

    for entry in spec_index.entries:
        best_score = 0.0
        for base_url in entry.base_urls:
            normalized_spec = normalize_base_url(base_url)
            if not normalized_spec:
                continue
            score = fuzz.ratio(normalized_node, normalized_spec) / 100.0
            best_score = max(best_score, score)
        if best_score >= threshold:
            scored.append((best_score, entry))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [entry for _, entry in scored]


def _normalize_service_name(name: str) -> str:
    """Lowercase a service name and strip common suffixes."""
    result = name.lower().strip()
    # Repeatedly strip known suffixes (handles e.g. "SlackApiV2")
    changed = True
    while changed:
        changed = False
        m = _SERVICE_NAME_SUFFIXES.search(result)
        if m:
            result = result[: m.start()].rstrip("_- ")
            changed = True
    return result


def match_by_service_name(
    node_type: str,
    spec_index: ApiSpecIndex,
) -> list[ApiSpecEntry]:
    """
    Match by extracting service name from node type.

    For example, ``n8n-nodes-base.slack`` yields ``slack``.  The extracted
    name is compared against each spec's *service_name* first exactly, then
    via fuzzy comparison.  Results are returned sorted by match quality.
    """
    parts = node_type.rsplit(".", maxsplit=1)
    raw_service = parts[-1] if len(parts) > 1 else parts[0]
    normalized_node_service = _normalize_service_name(raw_service)

    if not normalized_node_service:
        return []

    scored: list[tuple[float, ApiSpecEntry]] = []

    for entry in spec_index.entries:
        normalized_spec_service = _normalize_service_name(entry.service_name)
        if not normalized_spec_service:
            continue

        if normalized_node_service == normalized_spec_service:
            scored.append((1.0, entry))
        else:
            score = fuzz.ratio(normalized_node_service, normalized_spec_service) / 100.0
            if score >= 0.7:
                scored.append((score, entry))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [entry for _, entry in scored]


def map_operations(
    node: NodeTypeEntry,
    spec: ApiSpecEntry,
) -> tuple[dict[str, str], list[str]]:
    """
    Map node's resource/operations to spec endpoints.

    Returns a tuple of (*mapped*, *unmapped*) where *mapped* is a dict
    mapping ``"resource:operation"`` to ``"METHOD /path"`` and *unmapped*
    is a list of ``"resource:operation"`` strings with no spec match.
    """
    mapped: dict[str, str] = {}
    unmapped: list[str] = []

    for ro in node.resource_operations:
        node_key = f"{ro.resource}:{ro.operation}"
        best_score = 0.0
        best_endpoint = ""

        for ep in spec.endpoints:
            spec_key = f"{ep.resource}:{ep.operation}"
            score = fuzz.ratio(node_key.lower(), spec_key.lower()) / 100.0
            if score > best_score:
                best_score = score
                best_endpoint = ep.endpoint

        if best_score >= 0.5:
            mapped[node_key] = best_endpoint
        else:
            unmapped.append(node_key)

    return mapped, unmapped


def calculate_spec_coverage(mapped: dict[str, str], unmapped: list[str]) -> float:
    """
    Calculate fraction of node's operations successfully mapped.

    Returns a float between 0.0 and 1.0.  When there are no operations at
    all (both *mapped* and *unmapped* are empty), returns 0.0.
    """
    total = len(mapped) + len(unmapped)
    if total == 0:
        return 0.0
    return len(mapped) / total


def match_node_to_spec(
    node: NodeTypeEntry,
    spec_index: ApiSpecIndex,
) -> NodeApiMapping | None:
    """
    Match an n8n node to an API spec.

    Strategy: URL match -> name match -> operation verification.
    Returns a :class:`NodeApiMapping` if a suitable spec is found, or
    *None* otherwise.
    """
    candidates: list[ApiSpecEntry] = []

    # 1. Try URL-based matching
    node_url = extract_base_url_from_node(node)
    if node_url:
        candidates = fuzzy_match_url(node_url, spec_index)

    # 2. Fall back to service name matching
    if not candidates:
        candidates = match_by_service_name(node.node_type, spec_index)

    if not candidates:
        return None

    # 3. For each candidate, map operations and pick best coverage
    best_mapping: NodeApiMapping | None = None
    best_coverage = -1.0

    for spec in candidates:
        mapped, unmapped_ops = map_operations(node, spec)
        coverage = calculate_spec_coverage(mapped, unmapped_ops)

        if coverage > best_coverage:
            best_coverage = coverage

            credential_type = ""
            if node.credential_types:
                credential_type = node.credential_types[0].name

            best_mapping = NodeApiMapping(
                node_type=node.node_type,
                type_version=node.type_version,
                api_spec=spec.spec_filename,
                spec_format=spec.spec_format,
                operation_mappings=mapped,
                credential_type=credential_type,
                auth_type=spec.auth_type,
                unmapped_operations=unmapped_ops,
                spec_coverage=coverage,
            )

    return best_mapping


def match_all_nodes(
    catalog: NodeCatalog,
    spec_index: ApiSpecIndex,
) -> list[NodeApiMapping]:
    """
    Batch match all nodes in a catalog.

    Iterates over every entry in *catalog* and attempts to match it to a
    spec in *spec_index*.  Only successful matches are included in the
    returned list.
    """
    results: list[NodeApiMapping] = []
    for node in catalog.entries:
        mapping = match_node_to_spec(node, spec_index)
        if mapping is not None:
            results.append(mapping)
    return results
