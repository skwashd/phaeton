# Ai Agent Hardcoded Aws Region

**Priority:** P2
**Effort:** XS
**Gap Analysis Ref:** Item #7

## Overview

At `ai-agent/src/phaeton_ai_agent/agent.py:95`, the Bedrock model region is hardcoded:

```python
region_name="us-east-1",
```

This must be configurable via the environment variable `AWS_REGION`, with a fallback to `us-east-1` when it is undefined. Hardcoding the region prevents deployment to other AWS regions and violates the principle of environment-driven configuration.

## Dependencies

- **Blocked by:** None
- **Blocks:** None

## Acceptance Criteria

1. The Bedrock client region is read from the `AWS_REGION` environment variable.
2. When `AWS_REGION` is not set, it falls back to `us-east-1`.
3. No hardcoded region string remains in the Bedrock client initialization.
4. `uv run pytest` passes in `ai-agent/`.
5. `uv run ruff check` passes in `ai-agent/`.

## Implementation Details

### Files to Modify

- `ai-agent/src/phaeton_ai_agent/agent.py`

### Technical Approach

1. At line 95, replace the hardcoded region with an environment variable lookup:
   ```python
   import os
   region_name=os.environ.get("AWS_REGION", "us-east-1"),
   ```

### Testing Requirements

- `ai-agent/tests/test_agent.py` — test that the region is read from `AWS_REGION` environment variable.
- Test fallback: when `AWS_REGION` is not set, `us-east-1` is used.
- Use `monkeypatch.setenv` / `monkeypatch.delenv` to test both paths.
