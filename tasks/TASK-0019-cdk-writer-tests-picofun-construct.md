# Cdk Writer Tests Picofun Construct

**Priority:** P2
**Effort:** S
**Gap Analysis Ref:** Item #19

## Overview

The CDK writer modifications (TASK-0012) add PicoFun construct support — skipping PICOFUN_API_CLIENT functions from the regular Lambda section, adding the PicoFun construct import, and generating a new construct instantiation section. These tests verify all four changes work correctly and that the writer produces valid Python code.

## Dependencies

- **Blocked by:** TASK-0012 (CDK writer must have PicoFun construct support)
- **Blocks:** None

## Acceptance Criteria

1. `test_picofun_functions_excluded_from_lambda_section` passes — `PICOFUN_API_CLIENT` functions are not in `_wf_lambda_functions()` output.
2. `test_picofun_import_added` passes — PicoFun construct import is present when PicoFun functions exist.
3. `test_picofun_construct_section_generated` passes — `_wf_picofun_construct()` produces valid Python code.
4. `test_no_picofun_section_when_no_functions` passes — no PicoFun sections when no `PICOFUN_API_CLIENT` functions.
5. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
6. `uv run pytest tests/test_cdk_writer_picofun.py` passes in `packager/`.
7. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/tests/test_cdk_writer_picofun.py` (new)

### Technical Approach

1. Create test fixtures for `LambdaFunctionSpec` with different function types:
   ```python
   @pytest.fixture
   def picofun_spec() -> LambdaFunctionSpec:
       """Create a PicoFun API client function spec."""
       return LambdaFunctionSpec(
           function_name="slack_post_message",
           function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
           runtime="python",
           handler_code="...",
           dependencies=["picorun", "requests"],
       )

   @pytest.fixture
   def regular_spec() -> LambdaFunctionSpec:
       """Create a regular Python function spec."""
       return LambdaFunctionSpec(
           function_name="process_data",
           function_type=LambdaFunctionType.CODE_NODE_PYTHON,
           runtime="python",
           handler_code="...",
           dependencies=[],
       )
   ```

2. `test_picofun_functions_excluded_from_lambda_section`:
   - Call `_wf_lambda_functions()` with a mix of PicoFun and regular specs
   - Assert the output does NOT contain the PicoFun function name as a `lambda_.Function` construct
   - Assert the output DOES contain the regular function name

3. `test_picofun_import_added`:
   - Call `_wf_imports()` with `has_picofun=True`
   - Assert `"from construct import PicoFunConstruct"` is in the output

4. `test_picofun_construct_section_generated`:
   - Call `_wf_picofun_construct()` with a mock `PicoFunOutput`
   - Assert the output contains `PicoFunConstruct(` instantiation
   - Verify the output is syntactically valid Python (use `compile()`)

5. `test_no_picofun_section_when_no_functions`:
   - Generate the full workflow stack with only regular functions
   - Assert no PicoFun-related imports or construct sections appear

### Testing Requirements

- Use the CDK writer's internal methods directly for targeted testing.
- Validate generated Python syntax with `compile()` where appropriate.
- Follow project conventions: `-> None` return annotations, docstrings on all test functions.
