# Supported Node Types Reference

**Priority:** Documentation
**Effort:** S
**Gap Analysis Ref:** Docs table row 2

## Overview

No reference exists documenting which n8n node types are supported by Phaeton, what translation strategy is used for each, and what limitations exist. Users need this reference to understand which of their workflows can be converted and what manual adjustments might be needed.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. A `docs/supported-node-types.md` file exists with a comprehensive table of all supported and unsupported node types.
2. Each supported node type includes: n8n type name, display name, translation strategy, and known limitations.
3. Node types are organized by classification category (`AWS_NATIVE`, `FLOW_CONTROL`, `TRIGGER`, `CODE_JS`, `CODE_PYTHON`, `PICOFUN_API`, `UNSUPPORTED`).
4. The document is auto-generatable from the codebase (translator dispatch tables and Release Parser metadata).
5. The document clearly indicates which nodes are fully supported, partially supported, or unsupported.

## Implementation Details

### Files to Modify

- `docs/supported-node-types.md` (new)

### Technical Approach

1. **Document structure:**
   - **Summary table:** Count of supported/partial/unsupported nodes.
   - **Fully Supported Nodes:** Nodes with complete translators.
   - **Partially Supported Nodes:** Nodes with limitations or placeholder behavior.
   - **Unsupported Nodes:** Nodes that cannot be converted (will be flagged by the analyzer).
   - **Classification Categories:** Explanation of each `NodeClassification` value.

2. **Content for each node type:**
   ```markdown
   | n8n Type | Display Name | Category | Strategy | Limitations |
   |----------|-------------|----------|----------|-------------|
   | `n8n-nodes-base.if` | IF | FLOW_CONTROL | Choice State | None |
   | `n8n-nodes-base.switch` | Switch | FLOW_CONTROL | Choice State | None |
   | `n8n-nodes-base.merge` | Merge | FLOW_CONTROL | Parallel State | Placeholder only (TASK-0012) |
   | `n8n-nodes-base.code` | Code | CODE_JS/CODE_PYTHON | Lambda Function | n8n globals not shimmed (TASK-0014) |
   ```

3. **Auto-generation script:**
   - Parse the `FlowControlTranslator._DISPATCH` table from `flow_control.py`.
   - Parse the `CodeNodeTranslator.can_translate` method from `code_node.py`.
   - Cross-reference with `NodeClassification` enum values from `analysis.py`.
   - Use Release Parser's `NodeTypeEntry` data for display names.

4. **Limitations cross-references:**
   - Link to relevant TASK files for nodes with known limitations.

### Testing Requirements

- Verify the document lists all node types handled by existing translators.
- Verify no node type is listed as both "supported" and "unsupported".
- If an auto-generation script is created, verify its output matches the manual document.
