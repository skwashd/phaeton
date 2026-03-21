# Unit Tests Picofun Bridge

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #13

## Overview

The `PicoFunBridge` class (created in TASK-0004) wraps all PicoFun library interactions. It needs comprehensive unit tests covering spec parsing (both OpenAPI 3.0 and Swagger 2.0), endpoint matching, and code rendering. Tests should use temporary spec files created with `tmp_path` to avoid filesystem side effects.

## Dependencies

- **Blocked by:** TASK-0004 (PicoFunBridge must exist)
- **Blocks:** None

## Acceptance Criteria

1. `test_load_api_spec_openapi3` passes — parses a minimal OpenAPI 3.0 spec file into an `ApiSpec`.
2. `test_load_api_spec_swagger2` passes — parses a minimal Swagger 2.0 spec file into an `ApiSpec`.
3. `test_find_endpoint_exact_match` passes — finds endpoint by exact method+path.
4. `test_find_endpoint_not_found` passes — returns `None` for non-existent method+path.
5. `test_render_endpoint` passes — produces non-empty Python code containing `picorun` imports.
6. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
7. `uv run pytest tests/test_picofun_bridge.py` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/tests/test_picofun_bridge.py` (new)

### Technical Approach

1. Create minimal OpenAPI 3.0 spec fixture:
   ```python
   @pytest.fixture
   def openapi3_spec(tmp_path: Path) -> Path:
       """Create a minimal OpenAPI 3.0 spec file."""
       spec = {
           "openapi": "3.0.0",
           "info": {"title": "Test API", "version": "1.0"},
           "servers": [{"url": "https://api.example.com"}],
           "paths": {
               "/messages": {
                   "post": {
                       "operationId": "postMessage",
                       "responses": {"200": {"description": "OK"}},
                   }
               }
           },
       }
       spec_file = tmp_path / "test_openapi3.json"
       spec_file.write_text(json.dumps(spec))
       return spec_file
   ```

2. Create minimal Swagger 2.0 spec fixture similarly (with `"swagger": "2.0"`, `"host"`, `"basePath"`).

3. Test `load_api_spec`:
   - Construct `PicoFunBridge(spec_directory=str(tmp_path))`
   - Call `bridge.load_api_spec("test_openapi3.json")`
   - Assert the result is an `ApiSpec` with at least one endpoint

4. Test `find_endpoint`:
   - Load the spec, then call `bridge.find_endpoint(api_spec, "POST", "/messages")`
   - Assert the result is an `Endpoint` with matching method and path
   - Call with non-existent path, assert `None`

5. Test `render_endpoint`:
   - Find a valid endpoint, call `bridge.render_endpoint("https://api.example.com", endpoint, "test")`
   - Assert non-empty string containing `picorun` or handler function markers

### Testing Requirements

- Use `tmp_path` fixture for all spec files (no hardcoded paths).
- Tests should be self-contained — no network calls, no S3 access.
- Follow project conventions: `-> None` return annotations, docstrings on all test methods.
