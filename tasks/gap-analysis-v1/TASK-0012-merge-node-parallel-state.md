# Merge Node Parallel State

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #12

## Overview

The Merge node translator (`_translate_merge` in `flow_control.py` lines 317-335) emits only a `PassState` with a warning: "Merge node requires a Parallel state wrapping all upstream branches. This placeholder must be replaced during post-processing." No post-processing step exists. Workflows with Merge nodes (joining parallel branches) will produce invalid state machines that have a dangling PassState instead of a Parallel state aggregating branches.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The Merge node translator produces a valid `Parallel` state that wraps all upstream branches.
2. The engine's graph traversal identifies the branch fork point and all parallel branches leading to the Merge node.
3. Each branch in the Parallel state contains the correct sequence of states from the fork point to the Merge node.
4. The Parallel state's `ResultSelector` or output processing correctly combines branch outputs according to the Merge node's mode (append, combine, etc.).
5. `uv run pytest` passes in `n8n-to-sfn/`.
6. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (may need post-processing step)
- `n8n-to-sfn/tests/` (add Merge node tests)

### Technical Approach

1. **Graph analysis approach** (in `engine.py`):
   - After initial node translation, add a post-processing step that detects Merge nodes.
   - For each Merge node, walk the dependency graph backwards to find the common fork point (the node where branches diverge).
   - Collect all states between the fork point and the Merge node into separate branches.
   - Replace the fork-to-merge region with a single `Parallel` state containing the branches.

2. **Merge node handler** (in `flow_control.py`):
   - `_translate_merge` should emit metadata indicating it's a merge point, including:
     - The merge mode from `node.node.parameters` (e.g., `"mode": "append"`, `"combine"`, `"chooseBranch"`, `"multiplex"`).
     - The expected number of input branches.
   - The actual Parallel state construction happens in the post-processing step.

3. **Parallel state structure** (ASL):
   ```json
   {
     "Type": "Parallel",
     "Branches": [
       { "StartAt": "BranchAStart", "States": { ... } },
       { "StartAt": "BranchBStart", "States": { ... } }
     ],
     "ResultSelector": { ... },
     "Next": "..."
   }
   ```

4. Use `TranslationContext.analysis.dependency_edges` to determine branch structure.

### Testing Requirements

- Test a workflow with two branches merging: If -> Branch A / Branch B -> Merge.
- Test a workflow with three or more branches.
- Test different merge modes (append, combine).
- Verify the resulting ASL is valid with `jsonschema` validation.
