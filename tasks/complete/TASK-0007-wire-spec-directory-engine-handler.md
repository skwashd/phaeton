# Wire Spec Directory Engine Handler

**Priority:** P0
**Effort:** S
**Gap Analysis Ref:** Item #7

## Overview

The `spec_directory` field (added in TASK-0002) and the rewritten `PicoFunTranslator` (TASK-0006) need to be wired through the `TranslationEngine` and Lambda handler entry point. Currently, `TranslationEngine.__init__()` (at `n8n-to-sfn/src/n8n_to_sfn/engine.py`, line 59) does not accept a `spec_directory` parameter, and `create_default_engine()` (at `n8n-to-sfn/src/n8n_to_sfn/handler.py`, line 35) does not read environment variables for spec configuration or construct the `PicoFunBridge`.

This task completes the P0 wiring: environment variables configure the spec source, the handler builds the bridge and fetcher, and the engine passes the spec directory through to the translation context.

## Dependencies

- **Blocked by:** TASK-0002 (TranslationContext.spec_directory field), TASK-0006 (rewritten PicoFunTranslator with bridge support)
- **Blocks:** None

## Acceptance Criteria

1. `TranslationEngine.__init__()` accepts `spec_directory: str = ""` and stores it as `self._spec_directory`.
2. `TranslationEngine` passes `spec_directory` to `TranslationContext` when constructing it.
3. `create_default_engine()` in `handler.py` reads `PHAETON_SPEC_BUCKET` and `PHAETON_SPEC_PREFIX` environment variables.
4. When `PHAETON_SPEC_BUCKET` is set, a `SpecFetcher` is created with a temp directory cache.
5. A `PicoFunBridge` is constructed with the spec_directory and passed to `PicoFunTranslator(bridge=bridge)`.
6. When `PHAETON_SPEC_BUCKET` is not set, the engine still works with `spec_directory=""` (graceful degradation).
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/engine.py`
- `n8n-to-sfn/src/n8n_to_sfn/handler.py`

### Technical Approach

1. In `engine.py`, modify `TranslationEngine.__init__()` (line 59):
   ```python
   def __init__(self, ..., spec_directory: str = "") -> None:
       ...
       self._spec_directory = spec_directory
   ```

2. In `engine.py`, where `TranslationContext` is constructed (line 71):
   ```python
   context = TranslationContext(analysis=analysis, spec_directory=self._spec_directory)
   ```

3. In `handler.py`, update `create_default_engine()` (line 35):
   ```python
   import os
   import tempfile
   from n8n_to_sfn.translators.spec_fetcher import SpecFetcher
   from n8n_to_sfn.translators.picofun_bridge import PicoFunBridge

   spec_bucket = os.environ.get("PHAETON_SPEC_BUCKET", "")
   spec_prefix = os.environ.get("PHAETON_SPEC_PREFIX", "specs/")
   spec_directory = ""

   if spec_bucket:
       cache_dir = tempfile.mkdtemp(prefix="phaeton-specs-")
       fetcher = SpecFetcher(bucket=spec_bucket, prefix=spec_prefix, cache_dir=cache_dir)
       spec_directory = cache_dir
   ```

4. Pass the bridge to `PicoFunTranslator`:
   ```python
   bridge = PicoFunBridge(spec_directory=spec_directory) if spec_directory else None
   picofun_translator = PicoFunTranslator(bridge=bridge)
   ```

5. Pass `spec_directory` to the engine constructor.

### Testing Requirements

- Existing engine and handler tests must continue passing.
- Test that engine passes `spec_directory` through to `TranslationContext`.
- Test handler with and without `PHAETON_SPEC_BUCKET` environment variable set.
