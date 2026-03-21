# Add Picofun Dep Packager

**Priority:** P1
**Effort:** XS
**Gap Analysis Ref:** Item #9

## Overview

The packager component needs the `picofun` package as a runtime dependency to call PicoFun's `Layer` class (for preparing the picorun Lambda layer directory) and `CdkGenerator` (for producing CDK construct files). Currently, the packager has no PicoFun dependency and treats `PICOFUN_API_CLIENT` functions identically to regular Python Lambda functions.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0010, TASK-0011, TASK-0012

## Acceptance Criteria

1. `"picofun>=0.1.0"` is present in `packager/pyproject.toml` under `[project] dependencies`.
2. `uv sync` completes successfully in `packager/`.
3. `python -c "import picofun"` succeeds in the packager virtual environment.
4. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/pyproject.toml`

### Technical Approach

1. Open `packager/pyproject.toml` and locate the `[project] dependencies` array.
2. Add `"picofun>=0.1.0"` to the list, maintaining alphabetical order with existing entries.
3. Run `uv sync` to resolve and lock the dependency.

### Testing Requirements

- Verify `uv sync` resolves without conflicts.
- Verify `import picofun` works within the packager's environment.
