# Populate Api Spec Operation Mappings Adapter

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #8

## Overview

The `ClassifiedNode.api_spec` and `ClassifiedNode.operation_mappings` fields exist in `phaeton_models/translator.py:92-93` but are never populated. The `convert_report_to_analysis()` function (at `shared/phaeton-models/src/phaeton_models/adapters/analyzer_to_translator.py`, line 55) currently converts the workflow analyzer report into a `TranslationAnalysis` but does not wire spec-registry data into the classified nodes.

This task extends `convert_report_to_analysis()` to accept an optional `node_spec_mappings` parameter containing spec data per node type. The data originates from spec-registry's `matcher.match_all_nodes()` which returns `dict[str, ApiSpecEntry]`. The orchestration layer converts this to a plain dict before passing it to the adapter.

**Critical constraint**: `phaeton-models` is a leaf dependency and MUST NOT import from service packages. The parameter is typed as `dict[str, dict[str, Any]]` (no external imports). The dict structure mirrors `NodeApiMapping` fields: `{"api_spec": "slack.json", "operation_mappings": {"chat:postMessage": "POST /chat.postMessage"}}`.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0018

## Acceptance Criteria

1. `convert_report_to_analysis()` accepts an optional `node_spec_mappings: dict[str, dict[str, Any]] | None = None` parameter.
2. When `node_spec_mappings` is provided, `_convert_node()` looks up the node type and populates `api_spec` and `operation_mappings` on the resulting `SfnClassifiedNode`.
3. When `node_spec_mappings` is `None` or the node type is not in the dict, `api_spec` and `operation_mappings` remain `None` (backward compatible).
4. No imports from service packages (`n8n-to-sfn`, `packager`, `spec-registry`, etc.) are added to `phaeton-models`.
5. `uv run pytest` passes in `shared/phaeton-models/`.
6. `uv run ruff check` passes in `shared/phaeton-models/`.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/adapters/analyzer_to_translator.py`

### Technical Approach

1. Update `convert_report_to_analysis()` signature (line 55) to accept:
   ```python
   def convert_report_to_analysis(
       report: ...,
       node_spec_mappings: dict[str, dict[str, Any]] | None = None,
   ) -> TranslationAnalysis:
   ```

2. Pass `node_spec_mappings` through to `_convert_node()` (line 95).

3. In `_convert_node()`, after constructing the `SfnClassifiedNode`, look up `cn.node.type` in `node_spec_mappings`:
   ```python
   spec_data = node_spec_mappings.get(cn.node.type, {}) if node_spec_mappings else {}
   api_spec = spec_data.get("api_spec")
   operation_mappings = spec_data.get("operation_mappings")
   ```

4. Pass `api_spec` and `operation_mappings` to the `SfnClassifiedNode` constructor. Since the model is frozen, these must be set at construction time.

5. Ensure the `dict[str, dict[str, Any]]` type is used — no imports from `phaeton_models.spec` or any service package for the parameter type. The `Any` import comes from `typing`.

### Testing Requirements

- `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py` (updated in TASK-0018)
- Test with node_spec_mappings populating api_spec and operation_mappings
- Test backward compat: None mappings leaves fields as None
- Test partial mappings: only matching node types get populated
