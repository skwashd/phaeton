"""Unit tests for the operation mapper module."""

from n8n_to_sfn.translators.picofun_operation_mapper import (
    resolve_operation_to_endpoint,
)


def test_exact_resource_operation_match() -> None:
    """Test exact resource:operation mapping returns correct method and path."""
    result = resolve_operation_to_endpoint(
        node_params={"resource": "chat", "operation": "postMessage"},
        operation_mappings={"chat:postMessage": "POST /chat.postMessage"},
    )
    assert result == ("POST", "/chat.postMessage")


def test_operation_only_match() -> None:
    """Test operation-only fallback when resource is empty."""
    result = resolve_operation_to_endpoint(
        node_params={"operation": "getAll"},
        operation_mappings={"getAll": "GET /items"},
    )
    assert result == ("GET", "/items")


def test_case_insensitive_match() -> None:
    """Test case-insensitive comparison on the lookup key."""
    result = resolve_operation_to_endpoint(
        node_params={"resource": "Chat", "operation": "POSTMESSAGE"},
        operation_mappings={"chat:postMessage": "POST /chat.postMessage"},
    )
    assert result == ("POST", "/chat.postMessage")


def test_returns_none_when_unmapped() -> None:
    """Test unknown operation returns None."""
    result = resolve_operation_to_endpoint(
        node_params={"resource": "chat", "operation": "unknown"},
        operation_mappings={"chat:postMessage": "POST /chat.postMessage"},
    )
    assert result is None


def test_returns_none_when_mappings_is_none() -> None:
    """Test None mappings returns None."""
    result = resolve_operation_to_endpoint(
        node_params={"resource": "chat", "operation": "postMessage"},
        operation_mappings=None,
    )
    assert result is None
