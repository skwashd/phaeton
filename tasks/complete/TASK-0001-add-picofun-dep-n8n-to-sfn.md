# Add Picofun Dep N8n To Sfn

**Priority:** P0
**Effort:** XS
**Gap Analysis Ref:** Item #1

## Overview

The `n8n-to-sfn` component needs the `picofun` package as a runtime dependency to call its code generation APIs. Currently, no PicoFun import exists anywhere in the component — the `PicoFunTranslator` produces only placeholder comment strings. Adding this dependency unblocks all modules that will call PicoFun's `Spec`, `LambdaGenerator`, and parser APIs.

PicoFun requires Python >=3.13 (Phaeton requires >=3.14, which is compatible). PicoFun's pydantic==2.12.5 matches Phaeton's pinned version. The dependency should be added as `"picofun>=0.1.0"` to the `[project] dependencies` array.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0003, TASK-0004, TASK-0005, TASK-0006

## Acceptance Criteria

1. `"picofun>=0.1.0"` is present in `n8n-to-sfn/pyproject.toml` under `[project] dependencies`.
2. `uv sync` completes successfully in `n8n-to-sfn/`.
3. `python -c "import picofun"` succeeds in the `n8n-to-sfn` virtual environment.
4. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/pyproject.toml`

### Technical Approach

1. Open `n8n-to-sfn/pyproject.toml` and locate the `[project] dependencies` array.
2. Add `"picofun>=0.1.0"` to the list, maintaining alphabetical order with existing entries.
3. Run `uv sync` to resolve and lock the dependency.

### Testing Requirements

- Verify `uv sync` resolves without conflicts.
- Verify `import picofun` works within the component's environment.
