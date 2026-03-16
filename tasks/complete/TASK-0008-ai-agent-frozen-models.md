# Ai Agent Frozen Models

**Priority:** P2
**Effort:** XS
**Gap Analysis Ref:** Item #8

## Overview

All four Pydantic models in `ai-agent/src/phaeton_ai_agent/models.py:19-55` lack `model_config = ConfigDict(frozen=True)`:

- `NodeTranslationRequest`
- `ExpressionTranslationRequest`
- `AIAgentResponse`
- `ExpressionResponse`

This is a subset of the project-wide P0 issue #3, but called out separately since the ai-agent is a standalone service with its own deployment lifecycle and can be fixed independently.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. All four Pydantic model classes in `ai-agent/src/phaeton_ai_agent/models.py` have `model_config = ConfigDict(frozen=True)`.
2. No code in the ai-agent mutates model instances after construction.
3. `uv run pytest` passes in `ai-agent/`.
4. `uv run ruff check` passes in `ai-agent/`.

## Implementation Details

### Files to Modify

- `ai-agent/src/phaeton_ai_agent/models.py`

### Technical Approach

1. Add `from pydantic import ConfigDict` to the imports (if not already present).
2. Add `model_config = ConfigDict(frozen=True)` to each of the four model classes:
   - `NodeTranslationRequest` (line ~19)
   - `ExpressionTranslationRequest` (line ~30)
   - `AIAgentResponse` (line ~40)
   - `ExpressionResponse` (line ~50)
3. Search for any code that mutates these model instances after construction and refactor to use `model_copy(update={...})`.

### Testing Requirements

- `ai-agent/tests/` — run existing tests to verify nothing mutates the models.
- Optionally add a test that verifies mutation raises an error: `with pytest.raises(ValidationError): request.node_json = "new"`.
