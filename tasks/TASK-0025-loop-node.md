# Loop Node

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #25

## Overview

The Loop node (`n8n-nodes-base.loop`) is distinct from SplitInBatches and requires a different Map/iterator pattern in Step Functions. It is not currently in the dispatch table of the `FlowControlTranslator`. Workflows using the Loop node will fall through to the unknown handler and produce a placeholder PassState.

## Dependencies

- **Blocked by:** TASK-0013 (SplitInBatches Map state pattern should be established first as a reference)
- **Blocks:** None

## Acceptance Criteria

1. The Loop node type (`n8n-nodes-base.loop`) is added to the `FlowControlTranslator` dispatch table.
2. The translator produces a valid `Map` state or iteration pattern in ASL.
3. Loop body nodes are correctly identified and placed inside the iterator.
4. Loop count/condition from n8n parameters is mapped to the Map state configuration.
5. Both count-based and condition-based loops are supported.
6. `uv run pytest` passes in `n8n-to-sfn/`.
7. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/flow_control.py`
- `n8n-to-sfn/tests/test_loop_node.py` (new)

### Technical Approach

1. **Add Loop node constant:**
   ```python
   _TYPE_LOOP = "n8n-nodes-base.loop"
   ```

2. **Add to dispatch table** (in `_DISPATCH` dict):
   ```python
   _TYPE_LOOP: _translate_loop,
   ```

3. **Loop translation function:**
   - `_translate_loop(node, context) -> TranslationResult`
   - For count-based loops: Map state iterating over a generated array of the specified size.
   - For condition-based loops: Choice state + loop-back pattern (while-loop equivalent in ASL).

4. **Count-based loop (Map state approach):**
   ```json
   {
     "Type": "Map",
     "ItemsPath": "{% $range($states.input.loopCount) %}",
     "MaxConcurrency": 1,
     "ItemProcessor": {
       "ProcessorConfig": { "Mode": "INLINE" },
       "StartAt": "LoopBody",
       "States": { ... }
     }
   }
   ```

5. **Condition-based loop (Choice + loop-back):**
   ```json
   {
     "Type": "Choice",
     "Choices": [
       { "Condition": "{% ... %}", "Next": "LoopBody" }
     ],
     "Default": "LoopExit"
   }
   ```

6. **Loop body detection** follows the same pattern as SplitInBatches (TASK-0013).

### Testing Requirements

- Test count-based loop with a fixed iteration count.
- Test condition-based loop with a simple condition.
- Test loop body detection from the dependency graph.
- Validate generated ASL structure.
