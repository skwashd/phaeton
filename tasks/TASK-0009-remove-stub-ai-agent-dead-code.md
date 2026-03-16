# Remove Stub Ai Agent Dead Code

**Priority:** P2
**Effort:** XS
**Gap Analysis Ref:** Item #9

## Overview

`StubAIAgent` at `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py:90-110` raises `NotImplementedError` on both methods and is never used now that `AIAgentClient` exists. The `PROMPT_TEMPLATE` in the same file (lines 39-66) duplicates the one in `ai-agent/src/phaeton_ai_agent/agent.py:22-59`.

Both the unused class and the duplicated prompt template should be removed to reduce dead code and prevent divergence.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. `StubAIAgent` class is removed from `fallback.py`.
2. The duplicated `PROMPT_TEMPLATE` constant (lines 39-66) is removed from `fallback.py`.
3. No remaining references to `StubAIAgent` or the removed `PROMPT_TEMPLATE` exist in the codebase.
4. `uv run pytest` passes in `n8n-to-sfn/`.
5. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py`

### Technical Approach

1. Remove the `PROMPT_TEMPLATE` constant at lines 39-66.
2. Remove the `StubAIAgent` class at lines 90-110.
3. Search the codebase for any imports or references to `StubAIAgent` and remove them:
   ```bash
   grep -r "StubAIAgent" n8n-to-sfn/
   ```
4. If `fallback.py` becomes empty (or only has imports), consider whether the file itself should be removed or if other code in it is still needed.

### Testing Requirements

- `n8n-to-sfn/tests/` — run existing tests to verify nothing depends on `StubAIAgent`.
- Grep the codebase to confirm no references remain.
