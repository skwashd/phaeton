# Translation Engine Service Entry Point

**Priority:** P1
**Effort:** S
**Gap Analysis Ref:** Item #15

## Overview

The `n8n-to-sfn` package is library-only. It has no `__main__.py`, no `cli.py`, and no `console_scripts` entry in `pyproject.toml`. As a microservice, it needs a service entry point (e.g., Lambda handler or API endpoint) that the orchestration layer can invoke. The service entry point should accept a `WorkflowAnalysis` payload and return a `TranslationResult`.

## Dependencies

- **Blocked by:** None
- **Blocks:** TASK-0007, TASK-0008

## Acceptance Criteria

1. A Lambda handler module exists at `n8n-to-sfn/src/n8n_to_sfn/handler.py` (or similar).
2. The handler accepts a JSON payload conforming to `WorkflowAnalysis` schema.
3. The handler instantiates a `TranslationEngine` with all registered translators.
4. The handler returns a JSON response conforming to `TranslationOutput` schema.
5. Error responses include structured error information (error type, message, traceback).
6. The handler can be invoked as an AWS Lambda function or as a local function for testing.
7. `uv run pytest` passes in `n8n-to-sfn/`.
8. `uv run ruff check` passes in `n8n-to-sfn/`.

## Implementation Details

### Files to Modify

- `n8n-to-sfn/src/n8n_to_sfn/handler.py` (new)
- `n8n-to-sfn/pyproject.toml` (no console_scripts needed, but may add entry point metadata)
- `n8n-to-sfn/tests/test_handler.py` (new)

### Technical Approach

1. **Lambda handler:**
   ```python
   def handler(event: dict, context: Any) -> dict:
       analysis = WorkflowAnalysis.model_validate(event)
       engine = TranslationEngine(
           translators=[
               FlowControlTranslator(),
               CodeNodeTranslator(),
               # ... all registered translators
           ],
           ai_agent=None,  # or AIAgentClient() when available
       )
       output = engine.translate(analysis)
       return output.model_dump(mode="json")
   ```

2. **Translator registration:**
   - Create a factory function `create_default_engine() -> TranslationEngine` that registers all available translators.
   - Import all translator classes: `FlowControlTranslator` (from `flow_control.py` line 476), `CodeNodeTranslator` (from `code_node.py` line 137), and any other translator classes.

3. **Error handling:**
   - Wrap the handler in try/except.
   - Return structured error responses with HTTP-compatible status codes for API Gateway integration.
   - Log errors with structured logging.

4. **Local testing support:**
   - The handler should be callable as `handler(event_dict, None)` for local testing.
   - Add a `if __name__ == "__main__"` block for CLI invocation during development.

### Testing Requirements

- `n8n-to-sfn/tests/test_handler.py`
- Test handler with a valid `WorkflowAnalysis` payload.
- Test handler with an invalid payload returns a structured error.
- Test handler with a workflow that has translatable and untranslatable nodes.
- Test that the response conforms to `TranslationOutput` schema.
