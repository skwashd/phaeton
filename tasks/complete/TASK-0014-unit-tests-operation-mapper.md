# Unit Tests Operation Mapper

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #14

## Overview

The `resolve_operation_to_endpoint()` function (created in TASK-0005) maps n8n node `resource`/`operation` parameters to HTTP method+path tuples using operation mappings. These tests verify all matching scenarios: exact match, operation-only fallback, case insensitivity, and edge cases (None mappings, unmapped operations).

## Dependencies

- **Blocked by:** TASK-0005 (operation mapper module must exist)
- **Blocks:** None

## Acceptance Criteria

1. `test_exact_resource_operation_match` passes — `{"resource": "chat", "operation": "postMessage"}` with `{"chat:postMessage": "POST /chat.postMessage"}` returns `("POST", "/chat.postMessage")`.
2. `test_operation_only_match` passes — when resource is empty, falls back to operation-only lookup.
3. `test_case_insensitive_match` passes — case-insensitive comparison on the lookup key.
4. `test_returns_none_when_unmapped` passes — unknown operation returns `None`.
5. `test_returns_none_when_mappings_is_none` passes — `None` mappings returns `None`.
6. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
7. `uv run pytest tests/test_picofun_operation_mapper.py` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/tests/test_picofun_operation_mapper.py` (new)

### Technical Approach

1. Import the function under test:
   ```python
   from n8n_to_sfn.translators.picofun_operation_mapper import resolve_operation_to_endpoint
   ```

2. `test_exact_resource_operation_match`:
   ```python
   def test_exact_resource_operation_match() -> None:
       """Test exact resource:operation mapping returns correct method and path."""
       result = resolve_operation_to_endpoint(
           node_params={"resource": "chat", "operation": "postMessage"},
           operation_mappings={"chat:postMessage": "POST /chat.postMessage"},
       )
       assert result == ("POST", "/chat.postMessage")
   ```

3. `test_operation_only_match`:
   ```python
   def test_operation_only_match() -> None:
       """Test operation-only fallback when resource is empty."""
       result = resolve_operation_to_endpoint(
           node_params={"operation": "getAll"},
           operation_mappings={"getAll": "GET /items"},
       )
       assert result == ("GET", "/items")
   ```

4. `test_case_insensitive_match` — use mixed-case keys.

5. `test_returns_none_when_unmapped` — use an operation key not in mappings.

6. `test_returns_none_when_mappings_is_none` — pass `operation_mappings=None`.

### Testing Requirements

- Pure unit tests, no fixtures needed.
- Follow project conventions: `-> None` return annotations, docstrings on all test functions.
