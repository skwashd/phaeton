# Split In Batches Map State

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #13

## Overview

The SplitInBatches translator (`_translate_split_in_batches` in `flow_control.py` lines 284-315) creates a `MapState` with `MaxConcurrency: 1` but the `ItemProcessor` contains only a single placeholder `PassState`. The warning states: "inner workflow body must be inserted into the ItemProcessor.States block after full graph traversal." No graph traversal post-processing step fills this in. Workflows using SplitInBatches will produce Map states that process each batch with a no-op PassState.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The SplitInBatches translator produces a valid `Map` state with the correct inner states in the `ItemProcessor`.
2. The engine identifies the loop body — all nodes between SplitInBatches and its loop-back connection — and inserts them into the `ItemProcessor.States` block.
3. `MaxConcurrency` is set correctly based on node parameters (default 1 for batch processing).
4. The batch size from `node.node.parameters.batchSize` is reflected in the Map state configuration.
5. The inner states chain correctly with proper `Next` transitions and a terminal state with `End: true`.
6. `uv run pytest` passes in `n8n-to-sfn/`.
7. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (post-processing step)
- `n8n-to-sfn/tests/` (add SplitInBatches tests)

### Technical Approach

1. **Loop body detection** (in `engine.py`):
   - After initial translation, detect SplitInBatches nodes (type `n8n-nodes-base.splitInBatches`, constant `_TYPE_SPLIT_IN_BATCHES`).
   - For each SplitInBatches node, find its "done" output (output index 0) and "loop" output (output index 1) from the dependency graph.
   - Collect all nodes reachable from the "loop" output until they loop back to the SplitInBatches node. These form the inner body.
   - Remove these states from the top-level state machine and insert them into the `ItemProcessor.States` block.

2. **SplitInBatches handler** (in `flow_control.py`):
   - `_translate_split_in_batches` should emit the `Map` state skeleton with `ItemProcessor.ProcessorConfig.Mode = "INLINE"`.
   - Include metadata marking this as a loop requiring post-processing, with the node name for the engine to identify.
   - Read `batchSize` from `node.node.parameters.get("batchSize", 10)`.

3. **Map state structure** (ASL):
   ```json
   {
     "Type": "Map",
     "MaxConcurrency": 1,
     "ItemProcessor": {
       "ProcessorConfig": { "Mode": "INLINE" },
       "StartAt": "FirstInnerState",
       "States": { ... }
     },
     "Next": "..."
   }
   ```

4. The placeholder `PassState` named `{node_name}_Item` should be replaced with actual inner states.

### Testing Requirements

- Test a SplitInBatches workflow with a simple loop body (1-2 nodes).
- Test with a multi-step loop body.
- Test with custom batch size.
- Verify the inner states are removed from top-level and placed inside `ItemProcessor`.
- Validate the resulting ASL with `jsonschema`.
