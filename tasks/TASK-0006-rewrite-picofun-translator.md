# Rewrite Picofun Translator

**Priority:** P0
**Effort:** L
**Gap Analysis Ref:** Item #6

## Overview

The current `PicoFunTranslator.translate()` (at `n8n-to-sfn/src/n8n_to_sfn/translators/picofun.py`, line 57) creates a `LambdaArtifact` with comment-only placeholder code at lines 98-107:

```python
lambda_artifact = LambdaArtifact(
    function_name=func_name,
    runtime=LambdaRuntime.PYTHON,
    handler_code=f"# PicoFun-generated client for {node.node.type}\n"
    f"# API spec: {node.api_spec or 'unknown'}\n"
    f"# This code is generated externally by PicoFun.\n",
    dependencies=[],
    directory_name=func_name,
)
```

No real code generation occurs. This task replaces the placeholder with actual PicoFun-powered code generation, using the `PicoFunBridge` (TASK-0004), `SpecFetcher` (TASK-0003), and operation mapper (TASK-0005). The translator must gracefully degrade to placeholder code when any step fails — it must NEVER fail the pipeline.

## Dependencies

- **Blocked by:** TASK-0001 (picofun dependency), TASK-0003 (spec fetcher), TASK-0004 (bridge module), TASK-0005 (operation mapper)
- **Blocks:** TASK-0007, TASK-0016

## Acceptance Criteria

1. `PicoFunTranslator.__init__` accepts an optional `PicoFunBridge` instance.
2. When `bridge` is provided and `node.api_spec` is set, the translator generates real handler code via PicoFun.
3. Generated `handler_code` contains `picorun` imports and a handler function definition.
4. `LambdaArtifact.dependencies` is set to `["picorun", "requests", "aws-lambda-powertools"]`.
5. When credentials are present on the node, `"boto3"` is added to dependencies.
6. Metadata fields `picofun_spec`, `picofun_function_names`, and `picofun_namespace` are stored on the artifact for packager consumption.
7. When `api_spec` is not set, or `bridge` is `None`, or any generation step fails → placeholder code is produced with a warning. The translator NEVER raises an exception that stops the pipeline.
8. All existing tests continue to pass (backward compatibility with placeholder fallback).
9. `uv run pytest` passes in `n8n-to-sfn/`.
10. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/picofun.py`

### Technical Approach

1. Add `__init__` to `PicoFunTranslator`:
   ```python
   def __init__(self, bridge: PicoFunBridge | None = None) -> None:
       self._bridge = bridge
   ```

2. Add `_generate_handler_code()` private method:
   - Check preconditions: `self._bridge` is not None, `node.api_spec` is set
   - Call `resolve_operation_to_endpoint(node_params, node.operation_mappings)` from the operation mapper to get `(method, path)`
   - Call `self._bridge.load_api_spec(node.api_spec)` to parse the spec
   - Call `self._bridge.find_endpoint(api_spec, method, path)` to find the endpoint
   - Call `self._bridge.render_endpoint(base_url, endpoint, namespace)` to render the code
   - Return the rendered handler code string
   - Wrap the entire flow in a `try/except` that catches all exceptions and returns `None` on failure

3. In `translate()`, replace the placeholder code block (lines 98-107):
   - Attempt `_generate_handler_code()`
   - If it returns `None`, fall back to the existing placeholder code with an added warning comment
   - If it returns code, use that as `handler_code`

4. Update `dependencies`:
   ```python
   dependencies = ["picorun", "requests", "aws-lambda-powertools"]
   if node.credentials:
       dependencies.append("boto3")
   ```

5. Store PicoFun metadata on the artifact (via `metadata` dict or additional fields):
   - `picofun_spec`: the spec filename
   - `picofun_function_names`: list of generated function names
   - `picofun_namespace`: the namespace used for code generation

### Testing Requirements

- `n8n-to-sfn/tests/test_picofun.py` (updated in TASK-0016)
- Test real code generation with valid spec + operation_mappings
- Test graceful degradation: missing spec, unmapped operation, render error
- Test dependencies list population
- Test backward compat: existing tests still pass with `bridge=None`
