# Integrate Picofun Writer Pipeline

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #11

## Overview

The `Packager` class (at `packager/src/n8n_to_sfn_packager/packager.py`) orchestrates the packaging pipeline through sequential steps (ASL validation, Lambda writing, SSM generation, IAM generation, CDK writing, report writing). The `PicoFunWriter` (TASK-0010) needs to be called as a new step after Lambda writing but before CDK writing, so that PicoFun artifacts (layer directory, CDK construct file) are available when the CDK writer generates the workflow stack.

The step filters `input_data.lambda_functions` for functions with `function_type == LambdaFunctionType.PICOFUN_API_CLIENT` (enum value at `phaeton_models/packager_input.py:28`). If no PicoFun functions exist, the step is skipped silently.

## Dependencies

- **Blocked by:** TASK-0010 (PicoFunWriter must exist)
- **Blocks:** TASK-0012

## Acceptance Criteria

1. `Packager.__init__()` creates a `PicoFunWriter` instance.
2. A `_step_write_picofun()` method exists on `Packager`.
3. `_step_write_picofun()` is called after `_step_write_lambdas()` and before `_step_write_cdk()` in the `package()` method.
4. The step filters for `LambdaFunctionType.PICOFUN_API_CLIENT` functions.
5. When PicoFun functions exist, `PicoFunWriter.write()` is invoked and `PicoFunOutput` is stored for CDK writer consumption.
6. When no PicoFun functions exist, the step completes silently with no side effects.
7. `uv run pytest` passes in `packager/`.
8. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/packager.py`

### Technical Approach

1. Add import at top of `packager.py`:
   ```python
   from n8n_to_sfn_packager.writers.picofun_writer import PicoFunWriter, PicoFunOutput
   from phaeton_models.packager_input import LambdaFunctionType
   ```

2. In `Packager.__init__()` (line 31), add:
   ```python
   self._picofun_writer = PicoFunWriter()
   ```

3. Add a new method:
   ```python
   def _step_write_picofun(
       self, input_data: PackagerInput, output_dir: Path,
   ) -> PicoFunOutput | None:
       """Generate PicoFun layer and CDK construct if PicoFun functions exist."""
       picofun_functions = [
           f for f in input_data.lambda_functions
           if f.function_type == LambdaFunctionType.PICOFUN_API_CLIENT
       ]
       if not picofun_functions:
           return None
       return self._picofun_writer.write(
           picofun_functions=picofun_functions,
           namespace=input_data.workflow_metadata.workflow_name,
           output_dir=output_dir,
       )
   ```

4. In the `package()` method, call `_step_write_picofun()` after `_step_write_lambdas()` (around line 109) and store the result. Pass the `PicoFunOutput` to `_step_write_cdk()` (or store on `self` for CDK writer access).

### Testing Requirements

- Existing packager tests must continue passing.
- Test with PackagerInput containing PICOFUN_API_CLIENT functions → PicoFunWriter is called.
- Test with PackagerInput containing no PICOFUN_API_CLIENT functions → step is skipped.
