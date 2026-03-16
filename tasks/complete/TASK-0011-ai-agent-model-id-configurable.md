# Ai Agent Model Id Configurable

**Priority:** P2
**Effort:** XS
**Gap Analysis Ref:** Item #11

## Overview

At `ai-agent/src/phaeton_ai_agent/agent.py:94`, the Bedrock model ID is hardcoded to `us.anthropic.claude-sonnet-4-20250514`. Newer models in the Claude 4.5/4.6 family are available and may produce better translation results. The model ID should be configurable via an environment variable so it can be updated without code changes.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The Bedrock model ID is read from the `BEDROCK_MODEL_ID` environment variable.
2. When `BEDROCK_MODEL_ID` is not set, it falls back to the current default (`us.anthropic.claude-sonnet-4-20250514`).
3. No hardcoded model ID string remains in the Bedrock client initialization (except as the default fallback value).
4. `uv run pytest` passes in `ai-agent/`.
5. `uv run ruff check` passes in `ai-agent/`.

## Implementation Details

### Files to Modify

- `ai-agent/src/phaeton_ai_agent/agent.py`

### Technical Approach

1. At line 94, replace the hardcoded model ID with an environment variable lookup:
   ```python
   import os

   _DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514"

   # In the agent initialization:
   model_id=os.environ.get("BEDROCK_MODEL_ID", _DEFAULT_MODEL_ID),
   ```

2. This can be combined with TASK-0007 (hardcoded region) into a single change since both are in the same function.

### Testing Requirements

- `ai-agent/tests/test_agent.py` — test that the model ID is read from `BEDROCK_MODEL_ID` environment variable.
- Test fallback: when `BEDROCK_MODEL_ID` is not set, the default is used.
- Use `monkeypatch.setenv` / `monkeypatch.delenv` to test both paths.
