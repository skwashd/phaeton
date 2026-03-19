"""
API spec matching.

Matches n8n node types to API spec entries using the spec file naming
convention.  Spec files are named to map to n8n node names
(e.g. ``n8n-nodes-base.Slack.json``), which is the contract between
the registry and consumers.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex

# Suffixes commonly appended to node type service names that should be
# stripped for comparison purposes.
_SERVICE_NAME_SUFFIXES = re.compile(r"(api|v\d+|trigger)$", re.IGNORECASE)


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


def _extract_service_from_node_type(node_type: str) -> str:
    """
    Extract the service name portion from an n8n node type string.

    For example, ``n8n-nodes-base.slack`` yields ``slack``.
    """
    parts = node_type.rsplit(".", maxsplit=1)
    return parts[-1] if len(parts) > 1 else parts[0]


def _extract_service_from_filename(filename: str) -> str:
    """
    Extract the service name portion from a spec filename.

    Handles filenames like ``n8n-nodes-base.Slack.json`` by stripping the
    file extension and extracting the last dotted segment.
    """
    stem = PurePosixPath(filename).stem
    parts = stem.rsplit(".", maxsplit=1)
    return parts[-1] if len(parts) > 1 else parts[0]


def match_node_type(
    node_type: str,
    spec_index: ApiSpecIndex,
) -> ApiSpecEntry | None:
    """
    Match an n8n node type to a spec entry.

    Uses a two-stage strategy:

    1. **Filename convention** — checks if any spec filename contains the
       node's service name segment (e.g. ``Slack`` in
       ``n8n-nodes-base.Slack.json`` matches ``n8n-nodes-base.slack``).
    2. **Service name fallback** — normalizes the node's service name and
       each spec's ``service_name`` field and compares them.

    Returns the best matching :class:`ApiSpecEntry`, or ``None``.
    """
    node_service = _extract_service_from_node_type(node_type)
    normalized_node = _normalize_service_name(node_service)

    if not normalized_node:
        return None

    # Stage 1: filename convention match
    for entry in spec_index.entries:
        file_service = _extract_service_from_filename(entry.spec_filename)
        if _normalize_service_name(file_service) == normalized_node:
            return entry

    # Stage 2: service name match
    for entry in spec_index.entries:
        if _normalize_service_name(entry.service_name) == normalized_node:
            return entry

    return None


def match_all_nodes(
    node_types: list[str],
    spec_index: ApiSpecIndex,
) -> dict[str, ApiSpecEntry]:
    """
    Batch match node type strings to spec entries.

    Returns a dict mapping each matched node type to its
    :class:`ApiSpecEntry`.  Node types with no match are omitted.
    """
    results: dict[str, ApiSpecEntry] = {}
    for node_type in node_types:
        entry = match_node_type(node_type, spec_index)
        if entry is not None:
            results[node_type] = entry
    return results
