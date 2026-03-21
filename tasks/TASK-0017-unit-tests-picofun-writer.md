# Unit Tests Picofun Writer

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #17

## Overview

The `PicoFunWriter` class (created in TASK-0010) generates PicoFun-specific packaging artifacts (picorun Lambda layer and CDK construct file). These tests verify the writer's behavior by mocking PicoFun's `Layer` and `CdkGenerator` classes to avoid external dependencies and filesystem side effects.

## Dependencies

- **Blocked by:** TASK-0010 (PicoFunWriter must exist)
- **Blocks:** None

## Acceptance Criteria

1. `test_write_creates_layer_directory` passes — verify layer directory exists after `write()`.
2. `test_write_creates_cdk_construct` passes — verify CDK construct file is generated.
3. `test_write_returns_output_metadata` passes — verify `PicoFunOutput` contains correct layer_dir and construct_file paths.
4. `test_skip_when_no_picofun_functions` passes — verify writer is not invoked when the function list is empty.
5. All test functions have `-> None` return annotations, docstrings, and type annotations on all parameters.
6. `uv run pytest tests/test_picofun_writer.py` passes in `packager/`.
7. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/tests/test_picofun_writer.py` (new)

### Technical Approach

1. Mock PicoFun's `Layer` and `CdkGenerator`:
   ```python
   @patch("n8n_to_sfn_packager.writers.picofun_writer.CdkGenerator")
   @patch("n8n_to_sfn_packager.writers.picofun_writer.Layer")
   def test_write_creates_layer_directory(
       mock_layer_cls: MagicMock,
       mock_cdk_gen_cls: MagicMock,
       tmp_path: Path,
   ) -> None:
       """Test that write creates the picorun layer directory."""
   ```

2. `test_write_creates_layer_directory`:
   - Call `writer.write(picofun_functions=[...], namespace="test", output_dir=tmp_path)`
   - Assert `mock_layer_cls().prepare()` was called
   - Assert the returned `PicoFunOutput.layer_dir` path is correct

3. `test_write_creates_cdk_construct`:
   - Assert `mock_cdk_gen_cls().generate()` was called
   - Assert the returned `PicoFunOutput.construct_file` path is correct

4. `test_write_returns_output_metadata`:
   - Verify both fields of `PicoFunOutput` are `Path` objects pointing to expected locations

5. `test_skip_when_no_picofun_functions`:
   - This tests the `_step_write_picofun()` logic in `Packager`, or alternatively tests `PicoFunWriter.write()` with an empty list — verify no PicoFun API calls are made

6. Create a helper fixture for `LambdaFunctionSpec` with `function_type=LambdaFunctionType.PICOFUN_API_CLIENT`.

### Testing Requirements

- All PicoFun library calls are mocked.
- Use `tmp_path` fixture for output directory.
- Follow project conventions: `-> None` return annotations, docstrings on all test functions.
