# Contract Tests

**Priority:** Testing
**Effort:** M
**Gap Analysis Ref:** Testing table row 2

## Overview

No contract tests exist between components to verify model compatibility. The shared `phaeton-models` package (TASK-0003) unifies n8n input models, and adapters (TASK-0001, TASK-0002) bridge the remaining gaps, but there are no automated tests that verify the contracts remain compatible as components evolve. Contract tests would catch model drift before it causes runtime failures.

## Dependencies

- **Blocked by:** TASK-0001, TASK-0002, TASK-0003
- **Blocks:** None

## Acceptance Criteria

1. A contract test suite exists at the repository root level (`tests/contract/`).
2. Tests verify that Component 2 output (`ConversionReport`) can be deserialized by the adapter and converted to Component 3 input (`WorkflowAnalysis`).
3. Tests verify that Component 3 output (`TranslationOutput`) can be deserialized by the adapter and converted to Component 4 input (`PackagerInput`).
4. Tests verify JSON schema compatibility: a JSON document produced by Component N can be parsed by Component N+1's adapter.
5. Tests cover all enum value mappings between components.
6. Tests fail loudly when a model change breaks cross-component compatibility.
7. Tests pass with `uv run pytest tests/contract/`.

## Implementation Details

### Files to Modify

- `tests/contract/` (new directory at repo root)
- `tests/contract/conftest.py` (shared fixtures)
- `tests/contract/test_analyzer_to_translator.py`
- `tests/contract/test_translator_to_packager.py`
- `tests/contract/test_shared_models.py`

### Technical Approach

1. **Schema-based contract testing:**
   - Generate JSON schemas from each component's Pydantic models using `Model.model_json_schema()`.
   - Verify that the output schema of Component N is a subset of what the adapter for Component N+1 can accept.

2. **Round-trip contract tests:**
   ```python
   def test_analyzer_output_converts_to_translator_input():
       # Create a representative ConversionReport
       report = ConversionReport(...)
       # Serialize to JSON (as it would cross the boundary)
       json_data = report.model_dump(mode="json")
       # Verify the adapter can convert it
       analysis = convert_report_to_analysis(ConversionReport.model_validate(json_data))
       # Verify the output is valid
       assert isinstance(analysis, WorkflowAnalysis)
   ```

3. **Enum compatibility tests:**
   ```python
   def test_node_category_values_match_classification():
       for cat in NodeCategory:
           assert cat.value in [c.value for c in NodeClassification]
   ```

4. **Shared models tests** (`test_shared_models.py`):
   - Verify that `N8nNode`, `ConnectionTarget`, and `WorkflowSettings` from `phaeton-models` are the same classes imported by both `workflow-analyzer` and `n8n-to-sfn` (identity check via `is`).
   - Verify JSON round-trip fidelity for shared models including all aliased fields.

5. **Key adapter-bridged models to test:**
   - `ConversionReport` (report.py line 13) <-> `WorkflowAnalysis` (analysis.py line 105)
   - `ClassifiedNode` (classification.py line 23) <-> `ClassifiedNode` (analysis.py line 68)
   - `ClassifiedExpression` (expression.py line 16) <-> `ClassifiedExpression` (analysis.py line 49)
   - `TranslationResult` (base.py line 74) / `TranslationOutput` (engine.py line 39) <-> `PackagerInput` (inputs.py line 273)
   - `LambdaRuntime` (base.py line 20) <-> `LambdaRuntime` (inputs.py line 33)
   - `TriggerType` (base.py line 37) <-> `TriggerType` (inputs.py line 40)

### Testing Requirements

- Tests should not require any component to be deployed or running.
- Tests should use representative fixture data that covers all model fields.
- Tests should be fast (< 5 seconds total).
