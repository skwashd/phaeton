# Add Confidence Enum To Phaeton Models

**Priority:** P0
**Effort:** XS
**Gap Analysis Ref:** Item #1

## Overview

The `Confidence` enum (HIGH, MEDIUM, LOW) is currently defined in `ai-agent/src/phaeton_ai_agent/models.py` and consumed across component boundaries by `n8n-to-sfn` via its `AIAgentClient`. This cross-component import violates the architectural principle that services never import from each other's packages. The enum needs to live in the shared `phaeton-models` package so both the new AI agent components (node-translator, expression-translator) and the translation engine can import it without coupling.

`Confidence` is a boundary contract type — it appears in the JSON response from the AI agent Lambdas and is interpreted by the translation engine to make fallback decisions. This makes it a textbook candidate for `phaeton-models`.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0004 (node-translator imports Confidence from phaeton-models), TASK-0005 (expression-translator imports Confidence from phaeton-models)

## Acceptance Criteria

1. A `Confidence` StrEnum with values `HIGH`, `MEDIUM`, `LOW` exists in `phaeton_models.confidence`.
2. `Confidence` is re-exported from `phaeton_models.__init__`.
3. `ai-agent/src/phaeton_ai_agent/models.py` imports `Confidence` from `phaeton_models` instead of defining it locally.
4. `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py` imports `Confidence` from `phaeton_models` instead of `phaeton_ai_agent`.
5. No remaining imports of `Confidence` from `phaeton_ai_agent` exist in the codebase.
6. `uv run pytest` passes in `shared/phaeton-models/`.
7. `uv run pytest` passes in `ai-agent/`.
8. `uv run pytest` passes in `n8n-to-sfn/`.
9. `uv run ruff check` passes in all three packages.

## Implementation Details

### Files to Modify

- `shared/phaeton-models/src/phaeton_models/confidence.py` (new)
- `shared/phaeton-models/src/phaeton_models/__init__.py`
- `ai-agent/src/phaeton_ai_agent/models.py`
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py`

### Technical Approach

1. Create `shared/phaeton-models/src/phaeton_models/confidence.py`:
   ```python
   """Confidence level enum for AI agent translation responses."""

   from enum import StrEnum


   class Confidence(StrEnum):
       """Confidence level indicating translation quality."""

       HIGH = "HIGH"
       MEDIUM = "MEDIUM"
       LOW = "LOW"
   ```

2. Add `Confidence` to the `__init__.py` re-exports in `shared/phaeton-models/src/phaeton_models/__init__.py`.

3. In `ai-agent/src/phaeton_ai_agent/models.py`, remove the local `Confidence` class definition and replace with:
   ```python
   from phaeton_models import Confidence
   ```
   Ensure all existing references to `Confidence` in the ai-agent package still resolve.

4. In `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py`, update the import to:
   ```python
   from phaeton_models import Confidence
   ```

5. Grep the entire codebase for any other imports of `Confidence` from `phaeton_ai_agent` and update them.

### Testing Requirements

- Verify `from phaeton_models import Confidence` works and `Confidence.HIGH.value == "HIGH"`.
- Run existing test suites in `ai-agent/` and `n8n-to-sfn/` — they should pass without modification since the enum values are identical.
- No new test file needed; the enum is trivial and covered by existing consumer tests.
