# Set Edit Fields Node

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #21

## Overview

The Set node (`n8n-nodes-base.set`) is used in most workflows for data transformation. It maps to a `PassState` with `Output` using JSONata expressions. All generated state machines must use the modern Step Functions JSONata query language -- `ResultSelector` and `ResultPath` are part of the legacy JSONPath syntax and must not be used. The field mapping expressions need translation from n8n's format to JSONata.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A new translator class `SetNodeTranslator` exists that handles `n8n-nodes-base.set` nodes.
2. The translator produces a `PassState` with `Output` containing JSONata expressions.
3. Field assignments from n8n parameters are correctly translated to JSONata output expressions.
4. The translator does NOT use `ResultSelector`, `ResultPath`, or any legacy JSONPath constructs.
5. String, number, boolean, and expression field types are all handled.
6. The translator handles both "Set Specified" mode and "Keep Only Set" mode from n8n.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/set_node.py` (new)
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (register new translator)
- `n8n-to-sfn/tests/test_set_node_translator.py` (new)

### Technical Approach

1. **PassState with JSONata Output:**
   ```json
   {
     "Type": "Pass",
     "QueryLanguage": "JSONata",
     "Output": "{% { 'field1': $states.input.value1, 'field2': 'literal' } %}"
   }
   ```

2. **n8n Set node parameter structure:**
   - `node.parameters.mode`: `"manual"` (set specified) or `"raw"` (JSON expression).
   - `node.parameters.assignments.assignments`: Array of `{ name, value, type }` for manual mode.
   - `node.parameters.jsonOutput`: Raw JSON expression for raw mode.

3. **Field type mapping:**
   - `type: "string"` -> JSONata string literal or expression.
   - `type: "number"` -> JSONata number literal.
   - `type: "boolean"` -> JSONata boolean literal.
   - n8n expressions (`={{ ... }}`) -> JSONata expressions referencing `$states.input`.

4. **Keep Only Set mode:**
   - When `keepOnlySet` is true, the output contains only the specified fields.
   - When false, the output merges specified fields into the existing input.

### Testing Requirements

- Test manual mode with string, number, and boolean field assignments.
- Test raw JSON expression mode.
- Test with n8n expressions that reference upstream node data.
- Test "keep only set" vs merge modes.
- Validate generated ASL uses JSONata and not legacy JSONPath.
