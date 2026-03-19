# Update Deployment Tests

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #18

## Overview

`deployment/tests/test_synth.py` contains CDK synthesis tests that validate the stack structure. These tests need to be updated to reflect the new stack architecture: two AI translator Lambdas instead of one, a spec-registry stack with S3 bucket and Lambda, and the updated TranslationEngineStack with two environment variables.

## Dependencies

- **Blocked by:** TASK-0017 (app.py and stacks must be finalized)
- **Blocks:** None

## Acceptance Criteria

1. Synthesis tests pass for `NodeTranslatorStack`.
2. Synthesis tests pass for `ExpressionTranslatorStack`.
3. Synthesis tests pass for `SpecRegistryStack`.
4. Synthesis tests validate `TranslationEngineStack` has two env vars (`NODE_TRANSLATOR_FUNCTION_NAME`, `EXPRESSION_TRANSLATOR_FUNCTION_NAME`).
5. No tests reference `AiAgentStack`.
6. `uv run pytest` passes in `deployment/`.
7. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/tests/test_synth.py`

### Technical Approach

1. **Read `test_synth.py`** to understand the existing test patterns and assertions.

2. **Remove `AiAgentStack` tests** — any test that synthesizes or asserts on the old stack.

3. **Add `NodeTranslatorStack` tests:**
   - Synthesize the stack.
   - Assert Lambda function exists with name `phaeton-node-translator`.
   - Assert Bedrock IAM policy is present.

4. **Add `ExpressionTranslatorStack` tests:**
   - Same pattern as node translator.

5. **Add `SpecRegistryStack` tests:**
   - Assert S3 bucket with KMS encryption.
   - Assert Lambda function exists.
   - Assert S3 event notification is configured.

6. **Update `TranslationEngineStack` tests:**
   - Pass two mock functions to the constructor.
   - Assert both `NODE_TRANSLATOR_FUNCTION_NAME` and `EXPRESSION_TRANSLATOR_FUNCTION_NAME` env vars.
   - Assert invoke permissions on both functions.

### Testing Requirements

- All tests must follow project conventions: docstrings, type annotations, `-> None`.
- Run `uv run pytest deployment/tests/` to verify.
