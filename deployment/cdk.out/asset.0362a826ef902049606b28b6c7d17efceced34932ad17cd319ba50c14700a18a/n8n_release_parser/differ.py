"""
Compare two n8n node catalogs and produce a structured diff.

Provides functions to identify added, removed, and modified nodes between
releases, generate human-readable change descriptions, and build cumulative
catalogs across multiple releases.
"""

from __future__ import annotations

from n8n_release_parser.models import (
    ChangeType,
    NodeCatalog,
    NodeChange,
    NodeTypeEntry,
    ReleaseDiff,
)


def diff_catalogs(old: NodeCatalog, new: NodeCatalog) -> ReleaseDiff:
    """
    Compare two catalogs to identify added, removed, and modified nodes.

    Nodes are identified by their (node_type, type_version) tuple.
    """
    old_map: dict[tuple[str, int], NodeTypeEntry] = {
        (e.node_type, e.type_version): e for e in old.entries
    }
    new_map: dict[tuple[str, int], NodeTypeEntry] = {
        (e.node_type, e.type_version): e for e in new.entries
    }

    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    added_keys = sorted(new_keys - old_keys)
    removed_keys = sorted(old_keys - new_keys)
    common_keys = sorted(old_keys & new_keys)

    changes: list[NodeChange] = []

    for key in added_keys:
        changes.append(
            NodeChange(
                node_type=key[0],
                change_type=ChangeType.ADDED,
                new_version=new_map[key],
                changed_fields=[],
            )
        )

    for key in removed_keys:
        changes.append(
            NodeChange(
                node_type=key[0],
                change_type=ChangeType.REMOVED,
                old_version=old_map[key],
                changed_fields=[],
            )
        )

    modified_count = 0
    for key in common_keys:
        old_entry = old_map[key]
        new_entry = new_map[key]
        field_changes = diff_node_entries(old_entry, new_entry)
        if field_changes:
            changes.append(
                NodeChange(
                    node_type=key[0],
                    change_type=ChangeType.MODIFIED,
                    old_version=old_entry,
                    new_version=new_entry,
                    changed_fields=field_changes,
                )
            )
            modified_count += 1

    return ReleaseDiff(
        from_version=old.n8n_version,
        to_version=new.n8n_version,
        changes=changes,
        added_count=len(added_keys),
        removed_count=len(removed_keys),
        modified_count=modified_count,
    )


def diff_node_entries(old: NodeTypeEntry, new: NodeTypeEntry) -> list[str]:
    """
    Compare two versions of the same node.

    Returns human-readable change descriptions like:
    - "Added parameter: headerAuth"
    - "Changed default for parameter timeout: 30 -> 60"
    - "Added operation: message:update"
    - "Removed credential type: slackOAuth"
    """
    descriptions: list[str] = []

    # Compare parameters
    _diff_parameters(old, new, descriptions)

    # Compare credential types
    _diff_credentials(old, new, descriptions)

    # Compare resource operations
    _diff_operations(old, new, descriptions)

    # Compare request_defaults
    _diff_request_defaults(old, new, descriptions)

    # Compare simple scalar/list fields
    if old.display_name != new.display_name:
        descriptions.append(
            f"Changed display_name: {old.display_name!r} -> {new.display_name!r}"
        )

    if old.description != new.description:
        descriptions.append(
            f"Changed description: {old.description!r} -> {new.description!r}"
        )

    if old.input_count != new.input_count:
        descriptions.append(
            f"Changed input_count: {old.input_count} -> {new.input_count}"
        )

    if old.output_count != new.output_count:
        descriptions.append(
            f"Changed output_count: {old.output_count} -> {new.output_count}"
        )

    if old.group != new.group:
        descriptions.append(f"Changed group: {old.group!r} -> {new.group!r}")

    return descriptions


def build_cumulative_catalog(
    catalogs: list[NodeCatalog],
) -> dict[tuple[str, int], NodeTypeEntry]:
    """
    Build cumulative map of all node type versions across releases.

    Given catalogs sorted oldest-first, builds a lookup where newer releases
    override older ones for the same (nodeType, typeVersion), but versions that
    existed only in older releases are preserved.
    """
    result: dict[tuple[str, int], NodeTypeEntry] = {}
    for catalog in catalogs:
        for entry in catalog.entries:
            key = (entry.node_type, entry.type_version)
            result[key] = entry
    return result


def _diff_parameters(
    old: NodeTypeEntry,
    new: NodeTypeEntry,
    descriptions: list[str],
) -> None:
    """Compare parameters between two node entries and append descriptions."""
    old_params = {p.name: p for p in old.parameters}
    new_params = {p.name: p for p in new.parameters}

    old_names = set(old_params.keys())
    new_names = set(new_params.keys())

    for name in sorted(new_names - old_names):
        descriptions.append(f"Added parameter: {name}")

    for name in sorted(old_names - new_names):
        descriptions.append(f"Removed parameter: {name}")

    for name in sorted(old_names & new_names):
        old_p = old_params[name]
        new_p = new_params[name]
        if old_p.default != new_p.default:
            descriptions.append(
                f"Changed default for parameter {name}: {old_p.default!r} -> {new_p.default!r}"
            )
        if old_p.type != new_p.type:
            descriptions.append(
                f"Changed type for parameter {name}: {old_p.type!r} -> {new_p.type!r}"
            )
        if old_p.required != new_p.required:
            descriptions.append(
                f"Changed required for parameter {name}: {old_p.required} -> {new_p.required}"
            )


def _diff_credentials(
    old: NodeTypeEntry,
    new: NodeTypeEntry,
    descriptions: list[str],
) -> None:
    """Compare credential types between two node entries and append descriptions."""
    old_creds = {c.name: c for c in old.credential_types}
    new_creds = {c.name: c for c in new.credential_types}

    old_names = set(old_creds.keys())
    new_names = set(new_creds.keys())

    for name in sorted(new_names - old_names):
        descriptions.append(f"Added credential type: {name}")

    for name in sorted(old_names - new_names):
        descriptions.append(f"Removed credential type: {name}")

    for name in sorted(old_names & new_names):
        old_c = old_creds[name]
        new_c = new_creds[name]
        if old_c.required != new_c.required:
            descriptions.append(
                f"Changed required for credential {name}: {old_c.required} -> {new_c.required}"
            )


def _diff_operations(
    old: NodeTypeEntry,
    new: NodeTypeEntry,
    descriptions: list[str],
) -> None:
    """Compare resource operations between two node entries and append descriptions."""
    old_ops = {f"{o.resource}:{o.operation}" for o in old.resource_operations}
    new_ops = {f"{o.resource}:{o.operation}" for o in new.resource_operations}

    for op in sorted(new_ops - old_ops):
        descriptions.append(f"Added operation: {op}")

    for op in sorted(old_ops - new_ops):
        descriptions.append(f"Removed operation: {op}")


def _diff_request_defaults(
    old: NodeTypeEntry,
    new: NodeTypeEntry,
    descriptions: list[str],
) -> None:
    """Compare request_defaults between two node entries and append descriptions."""
    if old.request_defaults != new.request_defaults:
        descriptions.append(
            f"Changed request_defaults: {old.request_defaults!r} -> {new.request_defaults!r}"
        )
