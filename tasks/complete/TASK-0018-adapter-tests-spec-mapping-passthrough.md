# Adapter Tests Spec Mapping Passthrough

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #18

## Overview

The `convert_report_to_analysis()` adapter function (modified in TASK-0008) gains an optional `node_spec_mappings` parameter that populates `api_spec` and `operation_mappings` on classified nodes. These tests verify the new parameter works correctly, including backward compatibility when the parameter is omitted.

Tests are added to the existing adapter test file at `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py`.

## Dependencies

- **Blocked by:** TASK-0008 (adapter must accept node_spec_mappings)
- **Blocks:** None

## Acceptance Criteria

1. `test_convert_with_node_spec_mappings` passes — `convert_report_to_analysis()` with `node_spec_mappings` populates `api_spec` and `operation_mappings` on matching `ClassifiedNode` instances.
2. `test_convert_without_node_spec_mappings` passes — backward compat: `None` mappings produces nodes with `api_spec=None` and `operation_mappings=None`.
3. `test_convert_partial_spec_mappings` passes — only matching node types get populated, others remain `None`.
4. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
5. `uv run pytest tests/test_adapter_analyzer_to_translator.py` passes in `shared/phaeton-models/`.
6. `uv run ruff check` passes in `shared/phaeton-models/`.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/tests/test_adapter_analyzer_to_translator.py`

### Technical Approach

1. `test_convert_with_node_spec_mappings`:
   ```python
   def test_convert_with_node_spec_mappings(sample_report: ...) -> None:
       """Test that node_spec_mappings populates api_spec and operation_mappings."""
       mappings = {
           "n8n-nodes-base.slack": {
               "api_spec": "slack.json",
               "operation_mappings": {"chat:postMessage": "POST /chat.postMessage"},
           }
       }
       result = convert_report_to_analysis(sample_report, node_spec_mappings=mappings)
       slack_nodes = [n for n in result.classified_nodes if n.node.type == "n8n-nodes-base.slack"]
       for node in slack_nodes:
           assert node.api_spec == "slack.json"
           assert node.operation_mappings == {"chat:postMessage": "POST /chat.postMessage"}
   ```

2. `test_convert_without_node_spec_mappings`:
   ```python
   def test_convert_without_node_spec_mappings(sample_report: ...) -> None:
       """Test backward compat: None mappings leaves api_spec and operation_mappings as None."""
       result = convert_report_to_analysis(sample_report)
       for node in result.classified_nodes:
           assert node.api_spec is None
           assert node.operation_mappings is None
   ```

3. `test_convert_partial_spec_mappings`:
   - Provide mappings for only one of the node types in the sample report
   - Assert matched node has populated fields, unmatched nodes remain `None`

4. Use existing test fixtures (`sample_report`) from the test file if available, or create minimal fixtures.

### Testing Requirements

- Tests are added to the existing file, not a new file.
- Use existing fixtures where possible.
- Follow project conventions: `-> None` return annotations, docstrings on all test functions.
