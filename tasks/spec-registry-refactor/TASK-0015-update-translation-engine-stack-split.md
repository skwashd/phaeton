# Update Translation Engine Stack For Split Agents

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #15

## Overview

The `TranslationEngineStack` currently accepts a single `ai_agent_function` parameter and sets one `AI_AGENT_FUNCTION_NAME` environment variable on the translation engine Lambda. With the ai-agent split, it needs to accept two function parameters and set two environment variables.

## Dependencies

- **Blocked by:** TASK-0008 (client updated to read two env vars)
- **Blocks:** TASK-0017 (app.py wiring passes two functions)

## Acceptance Criteria

1. `TranslationEngineStack` constructor accepts `node_translator_function` and `expression_translator_function` parameters.
2. Lambda environment variables `NODE_TRANSLATOR_FUNCTION_NAME` and `EXPRESSION_TRANSLATOR_FUNCTION_NAME` are set.
3. `grant_invoke()` is called on both functions.
4. The old `AI_AGENT_FUNCTION_NAME` env var and single function parameter are removed.
5. `uv run pytest` passes in `deployment/`.
6. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/stacks/translation_engine_stack.py`

### Technical Approach

1. **Read `translation_engine_stack.py`** to understand the current constructor signature and how it wires the ai-agent function.

2. **Update constructor** to accept two function parameters:
   ```python
   def __init__(self, scope, construct_id, *,
                node_translator_function: lambda_.IFunction,
                expression_translator_function: lambda_.IFunction,
                **kwargs):
   ```

3. **Update environment variables:**
   ```python
   environment={
       "NODE_TRANSLATOR_FUNCTION_NAME": node_translator_function.function_name,
       "EXPRESSION_TRANSLATOR_FUNCTION_NAME": expression_translator_function.function_name,
   }
   ```

4. **Grant invoke on both:**
   ```python
   node_translator_function.grant_invoke(self.function)
   expression_translator_function.grant_invoke(self.function)
   ```

5. Remove any references to `AI_AGENT_FUNCTION_NAME` or single `ai_agent_function` parameter.

### Testing Requirements

- Update synth tests to pass two mock functions to the stack.
- Verify both env vars appear in the synthesized template.
- Verify both invoke permissions are granted.
