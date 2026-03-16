# Pydantic Frozen True Project Wide

**Priority:** P0
**Effort:** M
**Gap Analysis Ref:** Item #3

## Overview

The project convention (per CLAUDE.md) requires all Pydantic models to use `frozen=True` for immutable value objects. Only `n8n-release-parser/src/n8n_release_parser/models.py` complies. All models in the following components are mutable:

- `shared/phaeton-models` — `translator_output.py`, `packager_input.py`, `analyzer.py`, `translator.py`, `n8n_workflow.py`
- `workflow-analyzer` — all model files
- `n8n-to-sfn` — all model files
- `packager` — all model files
- `ai-agent` — `models.py` (also covered by TASK-0008 as a standalone fix)
- `deployment` — model classes in stacks

The engine's post-processing steps (`_apply_parallel_for_merges`, `_apply_map_for_split_in_batches`, `_wire_transitions`) mutate state objects in-place (setting `.next`, `.end`), which would break with frozen models. These methods need refactoring to construct new objects instead of mutating before `frozen=True` can be enabled project-wide.

## Dependencies

- **Blocked by:** TASK-0001 (engine model restructuring should complete first), TASK-0002 (shared packager model restructuring should complete first)
- **Blocks:** None

## Acceptance Criteria

1. Every Pydantic model class across all components has `model_config = ConfigDict(frozen=True)`.
2. Engine post-processing methods (`_apply_parallel_for_merges`, `_apply_map_for_split_in_batches`, `_wire_transitions`) are refactored to construct new state objects instead of mutating in-place.
3. No Pydantic model is mutated after construction anywhere in the codebase.
4. `uv run pytest` passes in every component (`shared/phaeton-models/`, `workflow-analyzer/`, `n8n-to-sfn/`, `packager/`, `ai-agent/`, `deployment/`).
5. `uv run ruff check` passes in every component.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/translator_output.py`
- `shared/phaeton-models/src/phaeton_models/packager_input.py`
- `shared/phaeton-models/src/phaeton_models/analyzer.py`
- `shared/phaeton-models/src/phaeton_models/translator.py`
- `shared/phaeton-models/src/phaeton_models/n8n_workflow.py`
- `workflow-analyzer/` — all model files
- `n8n-to-sfn/` — all model files
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` — refactor post-processing methods
- `packager/` — all model files
- `deployment/` — model classes in stacks

### Technical Approach

1. **Start with leaf models:** Add `model_config = ConfigDict(frozen=True)` to models in `shared/phaeton-models` first, then work outward to consumer components.

2. **Refactor engine post-processing:** The critical refactoring is in `n8n-to-sfn/src/n8n_to_sfn/engine.py`. The methods `_apply_parallel_for_merges`, `_apply_map_for_split_in_batches`, and `_wire_transitions` currently mutate state objects by setting `.next` and `.end` attributes. Refactor these to use `model_copy(update={...})` to construct new instances:
   ```python
   # Before (mutation):
   state.next = target_name
   # After (construction):
   state = state.model_copy(update={"next": target_name})
   ```

3. **Component-by-component:** For each component, add `frozen=True` to all model classes, run tests, and fix any mutation sites that break. Common patterns to fix:
   - Direct attribute assignment → `model_copy(update={...})`
   - In-place list/dict modification on model fields → construct new model with updated collection

4. **Deployment stacks:** CDK stack classes that use Pydantic models may need adjustment. These are typically configuration models, not CDK constructs themselves.

### Testing Requirements

- Run `uv run pytest` in each component after adding `frozen=True` — mutation sites will surface as `TypeError: "Model" is frozen`.
- Add tests that verify models cannot be mutated: `with pytest.raises(ValidationError): model.field = new_value`.
- Verify engine post-processing produces correct results after refactoring (existing tests should cover this).
- Run the full contract test suite to ensure cross-component model serialization still works.
