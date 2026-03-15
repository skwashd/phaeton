# Deduplicate N8n Node Models

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #3

## Overview

Two independent copies of `N8nNode` exist in separate packages. While fields are structurally identical today (same names, types, and aliases), they are separate Python classes. JSON round-tripping works, but any `isinstance` check or type annotation across package boundaries will fail. As the components evolve independently, these models will diverge silently, creating hard-to-debug incompatibilities.

The duplicated models are:
- `workflow-analyzer/src/workflow_analyzer/models/n8n_workflow.py`: `N8nNode`, `ConnectionTarget`, `WorkflowSettings`
- `n8n-to-sfn/src/n8n_to_sfn/models/n8n.py`: `N8nNode`, `N8nConnectionTarget`, `N8nSettings`

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0001

## Acceptance Criteria

1. A single canonical definition of `N8nNode` exists, used by both `workflow-analyzer` and `n8n-to-sfn`.
2. All Pydantic v2 features (model_validator, field_validator, model_json_schema) work correctly on the shared model.
3. Both packages import `N8nNode` from the same source, a shared package.
4. `ConnectionTarget` / `N8nConnectionTarget` and `WorkflowSettings` / `N8nSettings` are similarly unified.
5. All existing tests in both packages pass with the unified models.
6. `uv run pytest` passes in both `workflow-analyzer/` and `n8n-to-sfn/`.
7. `uv run ruff check` passes in both packages.

## Implementation Details

### Files to Modify

- `workflow-analyzer/src/workflow_analyzer/models/n8n_workflow.py`
- `n8n-to-sfn/src/n8n_to_sfn/models/n8n.py`
- `workflow-analyzer/pyproject.toml` (if adding shared dependency)
- `n8n-to-sfn/pyproject.toml` (if adding shared dependency)

### Technical Approach

**Shared `phaeton-models` package (recommended)**

1. Create a new package `shared/phaeton-models/` with Pydantic v2 models.
2. Move `N8nNode`, `ConnectionTarget` / `N8nConnectionTarget`, `WorkflowSettings` / `N8nSettings` into the shared package.
3. Unify field names — use the `workflow-analyzer` names (`ConnectionTarget`, `WorkflowSettings`) as canonical, since they follow Python conventions without the `N8n` prefix redundancy.
4. Both `workflow-analyzer` and `n8n-to-sfn` add `phaeton-models` as a dependency.
5. Update imports in both packages.

**Field reference (both are identical):**

| Field | Type |
|-------|------|
| `id` | `str` |
| `name` | `str` |
| `type` | `str` |
| `type_version` | `int \| float` (alias `typeVersion`) |
| `position` | `list[float]` |
| `parameters` | `dict[str, Any]` (default `{}`) |
| `credentials` | `dict[str, Any] \| None` |
| `disabled` | `bool \| None` |
| `notes` | `str \| None` |
| `continue_on_fail` | `bool \| None` (alias `continueOnFail`) |
| `on_error` | `str \| None` (alias `onError`) |
| `retry_on_fail` | `bool \| None` (alias `retryOnFail`) |
| `max_tries` | `int \| None` (alias `maxTries`) |
| `wait_between_tries` | `int \| None` (alias `waitBetweenTries`) |
| `execute_once` | `bool \| None` (alias `executeOnce`) |

### Testing Requirements

- Run `uv run pytest` in both `workflow-analyzer/` and `n8n-to-sfn/` after unification.
- Add a test that creates an `N8nNode` from JSON, serializes it back, and verifies round-trip fidelity including all aliased fields.
- Verify `isinstance` checks work across package boundaries.
