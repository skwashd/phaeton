# Update Lambda Code Assets

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #19

## Overview

With the ports-and-adapters refactoring, CLI modules are now dev-only and should not be bundled in Lambda deployments. CDK `Code.from_asset()` paths need to exclude CLI modules from the Lambda code bundles. This may require adjusting asset paths or adding exclusion patterns in the bundling options.

## Dependencies

- **Blocked by:** TASK-0010 (release-parser P&A), TASK-0011 (workflow-analyzer P&A), TASK-0012 (packager P&A), TASK-0013 (n8n-to-sfn CLI), TASK-0014 (translator stacks), TASK-0016 (spec-registry stack)
- **Blocks:** None

## Acceptance Criteria

1. Lambda code bundles for all components exclude `cli.py` and `__main__.py` (dev-only modules).
2. CDK synthesis succeeds for all stacks.
3. No Typer import errors in Lambda runtime (since Typer is a dev-only dependency).
4. `uv run pytest` passes in `deployment/`.
5. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/stacks/release_parser_stack.py`
- `deployment/stacks/workflow_analyzer_stack.py`
- `deployment/stacks/translation_engine_stack.py`
- `deployment/stacks/packager_stack.py`
- `deployment/stacks/node_translator_stack.py`
- `deployment/stacks/expression_translator_stack.py`
- `deployment/stacks/spec_registry_stack.py`

### Technical Approach

1. **Read each stack file** to understand how `Code.from_asset()` is currently configured.

2. **Add exclusion patterns** to `BundlingOptions` or use `Code.from_asset()` with `exclude` parameter:
   ```python
   code=lambda_.Code.from_asset(
       "../component/src",
       exclude=["*/cli.py", "*/__main__.py"],
   )
   ```
   Or if using `BundlingOptions`, add the exclude there.

3. **Verify** that the handler module and all its imports are still included. Only CLI-specific modules should be excluded.

4. The exact approach depends on how each stack currently bundles code — some may use `Code.from_asset()` directly, others may use `BundlingOptions` with `pip install`.

### Testing Requirements

- CDK synthesis tests should still pass.
- Verify excluded files don't appear in the synthesized asset paths (check CloudFormation template or asset staging).
