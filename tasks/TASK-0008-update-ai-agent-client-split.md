# Update Ai Agent Client For Split Agents

**Priority:** P1
**Effort:** M
**Gap Analysis Ref:** Item #8

## Overview

`n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py` currently sends both `translate_node` and `translate_expression` operations to a single Lambda via the `AI_AGENT_FUNCTION_NAME` environment variable. The request payload includes an `operation` field that the ai-agent handler uses to route to the correct function.

With the ai-agent split into two independent Lambdas (node-translator and expression-translator), the client must invoke two separate Lambda functions. Each Lambda accepts a flat request payload (no `operation` wrapper). The `AIAgentClient` constructor needs to accept two function names, and each method invokes the appropriate Lambda.

The `AIAgentProtocol` in `fallback.py` stays the same interface — it defines `translate_node()` and `translate_expression()` methods. Only the `AIAgentClient` implementation changes.

## Dependencies

- **Blocked by:** TASK-0004 (node-translator Lambda contract must exist), TASK-0005 (expression-translator Lambda contract must exist)
- **Blocks:** TASK-0009 (ai-agent can only be deleted after client no longer references it), TASK-0015 (TranslationEngineStack needs the new env vars)

## Acceptance Criteria

1. `AIAgentClient.__init__()` accepts two function name parameters: `node_translator_function_name` and `expression_translator_function_name`.
2. `translate_node()` invokes the node translator Lambda with a flat payload (no `operation` field).
3. `translate_expression()` invokes the expression translator Lambda with a flat payload (no `operation` field).
4. `AIAgentProtocol` in `fallback.py` is unchanged.
5. `create_default_engine()` in `handler.py` reads `NODE_TRANSLATOR_FUNCTION_NAME` and `EXPRESSION_TRANSLATOR_FUNCTION_NAME` environment variables (replacing `AI_AGENT_FUNCTION_NAME`).
6. No remaining references to `AI_AGENT_FUNCTION_NAME` exist in `n8n-to-sfn/`.
7. No remaining imports from `phaeton_ai_agent` exist in `n8n-to-sfn/`.
8. `uv run pytest` passes in `n8n-to-sfn/`.
9. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/client.py`
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py` (verify unchanged)
- `n8n-to-sfn/src/n8n_to_sfn/handler.py`
- `n8n-to-sfn/tests/` (update client tests)

### Technical Approach

1. **Update `client.py`:**
   - Change `AIAgentClient.__init__` to accept `node_translator_function_name: str` and `expression_translator_function_name: str` instead of a single `function_name: str`.
   - Update `translate_node()` to invoke `self._node_translator_function_name` with a flat payload: just the request fields, no `{"operation": "translate_node", ...}` wrapper.
   - Update `translate_expression()` to invoke `self._expression_translator_function_name` with a flat payload.
   - Remove any `Confidence` import from `phaeton_ai_agent` — it should come from `phaeton_models`.

2. **Verify `fallback.py`:**
   - Confirm `AIAgentProtocol` still defines `translate_node()` and `translate_expression()` with the same signatures. No changes needed.

3. **Update `handler.py`:**
   - In `create_default_engine()`, replace:
     ```python
     ai_agent_function = os.environ["AI_AGENT_FUNCTION_NAME"]
     ```
     with:
     ```python
     node_translator_function = os.environ["NODE_TRANSLATOR_FUNCTION_NAME"]
     expression_translator_function = os.environ["EXPRESSION_TRANSLATOR_FUNCTION_NAME"]
     ```
   - Pass both to `AIAgentClient(node_translator_function, expression_translator_function)`.

4. **Update tests:**
   - Update client test fixtures to provide two function names.
   - Update mock Lambda invocations to expect flat payloads without `operation` field.
   - Verify both `translate_node` and `translate_expression` invoke the correct Lambda.

### Testing Requirements

- Test `translate_node()` invokes the node translator Lambda with correct flat payload.
- Test `translate_expression()` invokes the expression translator Lambda with correct flat payload.
- Test that each method calls the correct Lambda function name.
- Test error handling for both invocations.
- Test `create_default_engine()` reads the correct environment variables.
