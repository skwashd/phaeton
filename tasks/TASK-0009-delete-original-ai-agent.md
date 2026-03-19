# Delete Original Ai Agent Component

**Priority:** P1
**Effort:** XS
**Gap Analysis Ref:** Item #9

## Overview

After the node-translator (TASK-0004) and expression-translator (TASK-0005) components are created, and the `AIAgentClient` is updated to invoke them (TASK-0008), the original `ai-agent/` directory is fully superseded and should be deleted.

## Dependencies

- **Blocked by:** TASK-0004 (node-translator must exist), TASK-0005 (expression-translator must exist), TASK-0008 (client must be updated to not reference ai-agent)
- **Blocks:** None

## Acceptance Criteria

1. The `ai-agent/` directory no longer exists.
2. No imports of `phaeton_ai_agent` exist anywhere in the codebase.
3. No references to `ai-agent` in any `pyproject.toml` dependency lists.
4. `uv run ruff check` passes at the repo root.

## Implementation Details

### Files to Modify

- `ai-agent/` (delete entire directory)

### Technical Approach

1. Grep the entire codebase for any remaining references to `phaeton_ai_agent` or `ai-agent` (as a dependency). Fix any stragglers.

2. Delete the entire `ai-agent/` directory: `rm -rf ai-agent/`.

3. Check the root `pyproject.toml` and any workspace configuration for references to `ai-agent` and remove them.

4. Run a final grep to confirm no orphaned references.

### Testing Requirements

- Verify `uv run pytest` passes in `n8n-to-sfn/` (the primary consumer).
- Verify `uv run pytest` passes in `node-translator/` and `expression-translator/`.
- Verify no import errors when running any component's test suite.
