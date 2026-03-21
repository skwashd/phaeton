# Create Operation Mapper Module

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #5

## Overview

n8n nodes use `resource` and `operation` parameters to describe what API action to perform (e.g., `resource="chat"`, `operation="postMessage"` for Slack). The `ClassifiedNode.operation_mappings` dict (from `NodeApiMapping.operation_mappings` at `phaeton_models/spec.py:57`) maps `"resource:operation"` keys to `"METHOD /path"` values (e.g., `{"chat:postMessage": "POST /chat.postMessage"}`).

The operation mapper module provides a function that resolves n8n node parameters to an HTTP method and path tuple, which the PicoFun bridge can then use to find the matching `Endpoint` in the parsed API spec.

## Dependencies

- **Blocked by:** TASK-0001 (picofun dependency must be resolved first for the component to build)
- **Blocks:** TASK-0006, TASK-0014

## Acceptance Criteria

1. A `resolve_operation_to_endpoint` function exists in `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_operation_mapper.py`.
2. Given `node_params={"resource": "chat", "operation": "postMessage"}` and `operation_mappings={"chat:postMessage": "POST /chat.postMessage"}`, the function returns `("POST", "/chat.postMessage")`.
3. When `resource` is empty or missing, the function falls back to operation-only matching (looks up just `"operation"` as the key).
4. Matching is case-insensitive on the lookup key.
5. Returns `None` when `operation_mappings` is `None` or when no matching key is found.
6. The function has full type annotations and a docstring.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_operation_mapper.py` (new)

### Technical Approach

1. Create `n8n-to-sfn/src/n8n_to_sfn/translators/picofun_operation_mapper.py` with:

   ```python
   from typing import Any

   def resolve_operation_to_endpoint(
       node_params: dict[str, Any],
       operation_mappings: dict[str, Any] | None,
   ) -> tuple[str, str] | None:
       """Map 'resource:operation' → (method, path). Returns None if unmapped."""
   ```

2. Implementation logic:
   - If `operation_mappings` is `None` or empty, return `None`
   - Extract `resource = node_params.get("resource", "")` and `operation = node_params.get("operation", "")`
   - If `operation` is empty, return `None`
   - Build lookup key: `f"{resource}:{operation}"` if resource is non-empty, else just `operation`
   - Build a case-insensitive lookup dict: `{k.lower(): v for k, v in operation_mappings.items()}`
   - Look up the key (lowered). If not found and resource was non-empty, try operation-only key
   - Parse the matched value by splitting on first space: `"POST /chat.postMessage"` → `("POST", "/chat.postMessage")`
   - Return the `(method, path)` tuple, or `None` if not found

### Testing Requirements

- `n8n-to-sfn/tests/test_picofun_operation_mapper.py` (new, created in TASK-0014)
- Test exact resource:operation match
- Test operation-only fallback
- Test case-insensitive matching
- Test None mappings → None result
- Test unmapped operation → None result
