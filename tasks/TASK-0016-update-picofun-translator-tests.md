# Update Picofun Translator Tests

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #16

## Overview

The existing `PicoFunTranslator` tests (at `n8n-to-sfn/tests/test_picofun.py`) verify the current placeholder behavior. After the translator rewrite (TASK-0006), these tests must continue passing (backward compatibility), and new tests must cover real code generation, graceful degradation scenarios, and dependency list population.

## Dependencies

- **Blocked by:** TASK-0006 (PicoFunTranslator must be rewritten with bridge support)
- **Blocks:** None

## Acceptance Criteria

1. All existing tests in `test_picofun.py` continue to pass unchanged.
2. `test_generation_with_valid_spec` passes — real spec file + operation_mappings → handler code containing `picorun` imports and function definitions.
3. `test_graceful_degradation_missing_spec` passes — missing spec file → placeholder code + warning comment.
4. `test_graceful_degradation_unmapped_operation` passes — unknown operation → placeholder code + warning comment.
5. `test_graceful_degradation_render_error` passes — PicoFun render failure → placeholder code + warning comment.
6. `test_dependencies_populated` passes — `LambdaArtifact.dependencies` contains `["picorun", "requests", "aws-lambda-powertools"]`.
7. `test_dependencies_include_boto3_with_credentials` passes — when credentials present, dependencies include `"boto3"`.
8. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
9. `uv run pytest tests/test_picofun.py` passes in `n8n-to-sfn/`.
10. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/tests/test_picofun.py`

### Technical Approach

1. `test_generation_with_valid_spec`:
   - Create a minimal OpenAPI 3.0 spec file in `tmp_path`
   - Create a `PicoFunBridge(spec_directory=str(tmp_path))`
   - Create a `ClassifiedNode` with `api_spec="test.json"` and `operation_mappings={"chat:postMessage": "POST /messages"}`
   - Construct `PicoFunTranslator(bridge=bridge)`
   - Call `translate()` and assert `handler_code` contains `picorun` imports

2. `test_graceful_degradation_missing_spec`:
   - Create a `PicoFunBridge(spec_directory=str(tmp_path))` with an empty directory
   - Create a `ClassifiedNode` with `api_spec="nonexistent.json"`
   - Call `translate()` and assert `handler_code` starts with `#` (placeholder comment)

3. `test_graceful_degradation_unmapped_operation`:
   - Create a valid spec file but use node_params with an operation not in the mappings
   - Assert placeholder code is produced

4. `test_graceful_degradation_render_error`:
   - Mock `PicoFunBridge.render_endpoint` to raise an exception
   - Assert placeholder code is produced (no exception propagated)

5. `test_dependencies_populated`:
   - Translate any node and assert `artifact.dependencies == ["picorun", "requests", "aws-lambda-powertools"]`

6. `test_dependencies_include_boto3_with_credentials`:
   - Create a node with `credentials` set
   - Assert `"boto3"` is in `artifact.dependencies`

### Testing Requirements

- Use `tmp_path` fixture for spec files.
- Mock `PicoFunBridge` methods where needed for error injection.
- Existing tests must not be modified (only new tests added).
