# Lambda Layers Shared Deps

**Priority:** P2
**Effort:** M
**Gap Analysis Ref:** Item #30

## Overview

Each generated Lambda function bundles its own dependencies. Workflows with multiple Code nodes or Lambda-backed integrations duplicate shared libraries (e.g., `luxon`, AWS SDK). Lambda Layers would reduce package sizes and cold start times by sharing common dependencies across functions.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The generated CDK stack creates Lambda Layers for shared dependencies.
2. Common dependencies (e.g., `luxon`, `aws-sdk`, `aws-xray-sdk`) are extracted into shared layers.
3. Lambda functions reference the shared layer instead of bundling these dependencies individually.
4. Each layer contains only the dependencies needed by the functions that use it.
5. Layer versioning is handled correctly (new layer version when dependencies change).
6. Individual function package sizes are reduced.
7. `uv run pytest` passes in `packager/`.
8. `uv run ruff check` passes in `packager/`.

## Implementation Details

### Files to Modify

- `packager/src/n8n_to_sfn_packager/writers/cdk_writer.py`
- `packager/src/n8n_to_sfn_packager/writers/lambda_writer.py` (if exists, or modify relevant writer)
- `packager/tests/` (update/add tests)

### Technical Approach

1. **Dependency analysis:**
   - Collect all dependencies from all `LambdaFunctionSpec` entries.
   - Group common dependencies shared by 2+ functions.
   - Create one or more layers for shared dependencies.

2. **Layer generation in CDK:**
   ```python
   shared_layer = lambda_.LayerVersion(self, "SharedDepsLayer",
       code=lambda_.Code.from_asset("layers/shared"),
       compatible_runtimes=[lambda_.Runtime.NODEJS_20_X, lambda_.Runtime.PYTHON_3_12],
       description="Shared dependencies for Phaeton workflow",
   )

   fn = lambda_.Function(self, "Handler",
       layers=[shared_layer],
       ...
   )
   ```

3. **Layer content structure:**
   - Node.js: `nodejs/node_modules/` directory.
   - Python: `python/lib/python3.x/site-packages/` directory.

4. **Dependency grouping strategy:**
   - Group 1: AWS SDK extensions (X-Ray, etc.) — shared across all functions.
   - Group 2: Runtime utilities (`luxon`, etc.) — shared across Code node functions.
   - Group 3: Application-specific libraries — per-function (not layered).

5. **Integration with Lambda function packaging:**
   - When generating function code bundles, exclude dependencies that are in a shared layer.
   - The function's `package.json` or `requirements.txt` should only include non-layered deps.

### Testing Requirements

- Test layer generation with multiple functions sharing dependencies.
- Test that function packages exclude layered dependencies.
- Test with no shared dependencies (no layer generated).
- Test with mixed runtimes (Node.js + Python functions).
