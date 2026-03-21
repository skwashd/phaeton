"""Operation mapper for resolving n8n node parameters to HTTP method and path."""

from typing import Any


def resolve_operation_to_endpoint(
    node_params: dict[str, Any],
    operation_mappings: dict[str, Any] | None,
) -> tuple[str, str] | None:
    """
    Map n8n resource:operation parameters to an HTTP (method, path) tuple.

    Resolves n8n node parameters (resource and operation) against an operation
    mappings dictionary to produce the corresponding HTTP method and path.

    Args:
        node_params: Dictionary of n8n node parameters containing 'resource'
            and/or 'operation' keys.
        operation_mappings: Dictionary mapping 'resource:operation' keys to
            'METHOD /path' values, or None.

    Returns:
        A (method, path) tuple if a match is found, or None if unmapped.

    """
    if not operation_mappings:
        return None

    resource = node_params.get("resource", "")
    operation = node_params.get("operation", "")

    if not operation:
        return None

    lookup_key = f"{resource}:{operation}" if resource else operation

    ci_mappings = {k.lower(): v for k, v in operation_mappings.items()}

    value = ci_mappings.get(lookup_key.lower())

    if value is None and resource:
        value = ci_mappings.get(operation.lower())

    if value is None:
        return None

    method, _, path = value.partition(" ")
    return (method, path)
