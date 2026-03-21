# Refactor Release Parser Ports And Adapters

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #10

## Overview

The release-parser handler currently only exposes `list_versions` as a Lambda operation. All other operations (fetch releases, diff catalogs, build catalog, generate report) are CLI-only, meaning they can only be invoked via the Typer CLI on a developer's machine. This prevents Step Functions or other Lambda consumers from orchestrating the full release-parsing pipeline.

This task creates a `service.py` core layer that both the CLI and handler call, exposing all operations through the Lambda handler via an `operation` field in the event. Typer is moved to a `dev` dependency group so it's not bundled in the Lambda deployment.

## Dependencies

- **Blocked by:** TASK-0007 (spec code removed — clean codebase to refactor)
- **Blocks:** TASK-0019 (Lambda code asset exclusions depend on CLI being a dev-only module)

## Acceptance Criteria

1. A `service.py` module exists with pure functions for all operations: `list_versions`, `fetch_releases`, `diff_catalogs`, `build_catalog`, `generate_report`.
2. The Lambda handler routes to all operations via an `operation` field in the event.
3. The CLI calls `service.py` functions (not the other way around).
4. The handler does NOT import the CLI module.
5. Typer is in the `dev` dependency group, not production `dependencies`.
6. `uv run pytest` passes in `n8n-release-parser/`.
7. `uv run ruff check` passes in `n8n-release-parser/`.

## Implementation Details

### Files to Modify

- `n8n-release-parser/src/n8n_release_parser/service.py` (new)
- `n8n-release-parser/src/n8n_release_parser/handler.py`
- `n8n-release-parser/src/n8n_release_parser/cli.py`
- `n8n-release-parser/pyproject.toml`
- `n8n-release-parser/tests/test_handler.py`

### Technical Approach

1. **Create `service.py`:** Extract the core logic from `cli.py` into pure functions. Each function accepts explicit parameters (storage backend, version strings, etc.) and returns data — no file I/O, no CLI output, no Typer dependencies.

2. **Refactor `handler.py`:** Import from `service.py`. Add operation routing:
   ```python
   def handler(event: dict, context: Any) -> dict:
       operation = event.get("operation", "list_versions")
       match operation:
           case "list_versions": ...
           case "fetch_releases": ...
           case "diff_catalogs": ...
           case "build_catalog": ...
           case "generate_report": ...
           case _: raise ValueError(f"Unknown operation: {operation}")
   ```

3. **Refactor `cli.py`:** Each Typer command becomes a thin adapter that: parses CLI arguments, calls the appropriate `service.py` function, formats output for the terminal. Import from `service.py`, never from `handler.py`.

4. **Move Typer to dev deps** in `pyproject.toml`:
   ```toml
   [dependency-groups]
   dev = ["typer>=0.9", ...]
   ```

5. **Update tests:** Add handler tests for each new operation. Existing CLI tests may need fixture updates but should largely work via the service layer.

### Testing Requirements

- `test_handler.py`: Test each operation via the handler with mock events.
- `test_service.py` (new if needed): Test service functions directly.
- Verify handler doesn't import typer (check with a targeted import test or grep).
- Run existing test suite to confirm no regressions.
