# Add Spec Directory Translation Context

**Priority:** P0
**Effort:** XS
**Gap Analysis Ref:** Item #2

## Overview

The `TranslationContext` Pydantic model (at `n8n-to-sfn/src/n8n_to_sfn/translators/base.py`, line 59) needs a `spec_directory: str = ""` field. This field holds the local filesystem path where downloaded API spec files are cached. PicoFun's `Spec` class needs a file path to parse specs, and translators access the spec directory through the shared context object.

The empty default preserves backward compatibility — when no spec directory is configured, the `PicoFunTranslator` falls back to placeholder code (graceful degradation). All existing tests and callers that construct `TranslationContext` without a `spec_directory` will continue to work unchanged.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0007

## Acceptance Criteria

1. `TranslationContext` has a `spec_directory: str` field with default value `""`.
2. Existing code that constructs `TranslationContext` without `spec_directory` continues to work (backward compatible default).
3. `TranslationContext(analysis=..., spec_directory="/tmp/specs")` round-trips correctly via Pydantic serialization.
4. `uv run pytest` passes in `n8n-to-sfn/`.
5. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/translators/base.py`

### Technical Approach

1. In `n8n-to-sfn/src/n8n_to_sfn/translators/base.py`, locate the `TranslationContext` model (line 59).
2. Add a new field:
   ```python
   spec_directory: str = ""
   ```
3. The field should be placed after the existing fields. Since `TranslationContext` uses `frozen=True`, no setter is needed.

### Testing Requirements

- Existing tests in `n8n-to-sfn/tests/` must continue passing without modification.
- Optionally add a small test verifying `TranslationContext` accepts `spec_directory` and defaults to `""`.
