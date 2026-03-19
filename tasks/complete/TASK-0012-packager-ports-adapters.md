# Refactor Packager Ports And Adapters

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #12

## Overview

The packager's CLI in `__main__.py` is already fairly clean, and the handler has S3 upload logic which is appropriate as a Lambda adapter concern. The main change is moving Typer to the `dev` dependency group so it's not bundled in the Lambda deployment.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0019 (Lambda code asset exclusions)

## Acceptance Criteria

1. Typer is in the `dev` dependency group, not production `dependencies`.
2. The handler does NOT import the CLI module or Typer.
3. `uv run pytest` passes in `packager/`.
4. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/__main__.py`
- `packager/pyproject.toml`

### Technical Approach

1. **Move Typer to dev deps** in `pyproject.toml`:
   ```toml
   [dependency-groups]
   dev = ["typer>=0.9", ...]
   ```

2. **Verify `__main__.py`** only imports Typer at the module level (which is fine for a dev-only entry point). Ensure the handler module (`handler.py`) does not import from `__main__.py`.

3. If any production code paths import Typer transitively, refactor to break that dependency.

### Testing Requirements

- Run existing tests to verify no regressions.
- Verify handler can be imported without Typer installed (conceptually — Typer will still be available in dev, but no production code path should require it).
