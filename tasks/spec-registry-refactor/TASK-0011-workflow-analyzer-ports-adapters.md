# Refactor Workflow Analyzer Ports And Adapters

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #11

## Overview

The workflow-analyzer handler already cleanly calls `analyzer.analyze_dict()`, which is good. However, `analyze_and_render()` mixes core analysis with file I/O (writing report files to disk), and Typer is a production dependency when it should only be needed for dev/testing.

This task splits `analyze_and_render()` so that the core `analyze()` logic returns data and the rendering/file-writing stays in the CLI adapter only. Typer is moved to the `dev` dependency group.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0019 (Lambda code asset exclusions)

## Acceptance Criteria

1. Core analysis logic returns data without performing file I/O.
2. File writing and report rendering are only in the CLI adapter.
3. The handler does NOT import the CLI module or Typer.
4. Typer is in the `dev` dependency group, not production `dependencies`.
5. `uv run pytest` passes in `workflow-analyzer/`.
6. `uv run ruff check` passes in `workflow-analyzer/`.

## Implementation Details

### Files to Modify

- `workflow-analyzer/src/workflow_analyzer/analyzer.py`
- `workflow-analyzer/src/workflow_analyzer/cli.py`
- `workflow-analyzer/pyproject.toml`

### Technical Approach

1. **In `analyzer.py`:** Identify `analyze_and_render()` or similar functions that mix analysis with file I/O. Split into:
   - `analyze()` / `analyze_dict()`: Pure analysis, returns data (already exists for the handler path).
   - Remove or deprecate any functions that write files directly.

2. **In `cli.py`:** Move file-writing logic here. The CLI command calls `analyze()` to get results, then writes the report file(s) itself.

3. **Move Typer to dev deps** in `pyproject.toml`:
   ```toml
   [dependency-groups]
   dev = ["typer>=0.9", ...]
   ```

4. Verify the handler imports only from `analyzer.py`, never from `cli.py`.

### Testing Requirements

- Run existing tests to verify no regressions.
- Verify handler path still works (calls `analyze_dict()` and returns JSON).
- Verify CLI path still works (analysis + file output).
