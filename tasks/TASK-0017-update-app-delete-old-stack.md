# Update Deployment App And Delete Old Stack

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #17

## Overview

The deployment `app.py` currently imports and instantiates `AiAgentStack` to deploy the single ai-agent Lambda. With the split into node-translator and expression-translator, `app.py` needs to import the two new translator stacks and the spec-registry stack, wire them together, and the old `AiAgentStack` can be deleted.

## Dependencies

- **Blocked by:** TASK-0014 (translator stacks must exist), TASK-0015 (TranslationEngineStack updated for two functions), TASK-0016 (SpecRegistryStack must exist)
- **Blocks:** TASK-0018 (deployment tests depend on the new app structure)

## Acceptance Criteria

1. `app.py` imports `NodeTranslatorStack`, `ExpressionTranslatorStack`, and `SpecRegistryStack`.
2. `app.py` no longer imports `AiAgentStack`.
3. Both translator functions are passed to `TranslationEngineStack`.
4. `ai_agent_stack.py` is deleted.
5. `uv run pytest` passes in `deployment/`.
6. `uv run ruff check` passes in `deployment/`.

## Implementation Details

### Files to Modify

- `deployment/app.py`
- `deployment/stacks/ai_agent_stack.py` (delete)

### Technical Approach

1. **Update `app.py`:**
   - Remove `from stacks.ai_agent_stack import AiAgentStack`.
   - Add imports for `NodeTranslatorStack`, `ExpressionTranslatorStack`, `SpecRegistryStack`.
   - Instantiate both translator stacks and spec-registry stack.
   - Pass both translator functions to `TranslationEngineStack`:
     ```python
     node_translator = NodeTranslatorStack(app, "NodeTranslator")
     expression_translator = ExpressionTranslatorStack(app, "ExpressionTranslator")
     spec_registry = SpecRegistryStack(app, "SpecRegistry")

     translation_engine = TranslationEngineStack(
         app, "TranslationEngine",
         node_translator_function=node_translator.function,
         expression_translator_function=expression_translator.function,
     )
     ```

2. **Delete `ai_agent_stack.py`.**

3. Verify no remaining references to `AiAgentStack` in the codebase.

### Testing Requirements

- CDK synth should succeed for the full app.
- Verify all stacks are instantiated and wired correctly.
