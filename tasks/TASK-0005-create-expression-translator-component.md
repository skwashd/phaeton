# Create Expression Translator Component

**Priority:** P0
**Effort:** L
**Gap Analysis Ref:** Item #5

## Overview

The `ai-agent/` component currently handles both node translation and expression translation. This task extracts the expression translation responsibility into a new `expression-translator/` component.

The expression translator uses a Strands Agent with Bedrock to translate n8n expressions (e.g., `{{ $json.field }}`, `{{ $node["Name"].json.data }}`) into JSONata expressions compatible with AWS Step Functions. Unlike node translation which outputs ASL state definitions, expression translation outputs JSONata strings.

The new component follows ports-and-adapters: core logic in `agent.py`, Lambda handler adapter in `handler.py`, dev-only CLI adapter in `cli.py`. The handler accepts a flat request (no `operation` routing).

## Dependencies

- **Blocked by:** TASK-0001 (Confidence enum must be in phaeton-models first)
- **Blocks:** TASK-0008 (client update needs the new Lambda contract), TASK-0009 (ai-agent deletion), TASK-0014 (deployment stack)

## Acceptance Criteria

1. `expression-translator/` directory exists with a complete Python package structure.
2. `pyproject.toml` declares the package with correct dependencies (strands-agents, phaeton-models, boto3).
3. `agent.py` contains a `translate_expression()` function that accepts an expression translation request and returns a JSONata expression with confidence.
4. The Strands Agent uses a system prompt specifically tailored for expression-to-JSONata translation (focused on JSONata syntax, n8n expression patterns, Step Functions intrinsic functions).
5. `handler.py` implements a Lambda handler that deserializes the event directly as an expression translation request (no `operation` field routing).
6. `cli.py` provides a Typer CLI for dev/testing.
7. Typer is a `dev` dependency, not a production dependency.
8. `_generate_tag_suffix()` and `_parse_json_response()` utilities are included (duplicated, not shared).
9. `uv run pytest` passes in `expression-translator/`.
10. `uv run ruff check` passes in `expression-translator/`.
11. `uv run ty check` passes in `expression-translator/`.

## Implementation Details

### Files to Modify

- `expression-translator/pyproject.toml` (new)
- `expression-translator/src/phaeton_expression_translator/__init__.py` (new)
- `expression-translator/src/phaeton_expression_translator/agent.py` (new)
- `expression-translator/src/phaeton_expression_translator/models.py` (new)
- `expression-translator/src/phaeton_expression_translator/handler.py` (new)
- `expression-translator/src/phaeton_expression_translator/cli.py` (new)
- `expression-translator/tests/__init__.py` (new)
- `expression-translator/tests/conftest.py` (new)
- `expression-translator/tests/test_agent.py` (new)
- `expression-translator/tests/test_handler.py` (new)
- `expression-translator/tests/test_models.py` (new)

### Technical Approach

1. **Read source material** from `ai-agent/`:
   - `ai-agent/src/phaeton_ai_agent/agent.py`: Extract `translate_expression()`, `EXPRESSION_PROMPT_TEMPLATE`, `_generate_tag_suffix()`, `_parse_json_response()`.
   - `ai-agent/src/phaeton_ai_agent/models.py`: Extract `ExpressionTranslationRequest` and `ExpressionResponse`.
   - `ai-agent/src/phaeton_ai_agent/handler.py`: Extract the `translate_expression` branch.
   - `ai-agent/tests/test_agent.py`: Extract expression translation tests.

2. **Create `pyproject.toml`** following the pattern of other components. Key dependencies:
   - `strands-agents` and `strands-agents-bedrock` for the AI agent
   - `phaeton-models` for `Confidence` enum
   - `pydantic` for request/response models
   - `typer` in `[dependency-groups] dev`
   - Build system: `uv_build`

3. **Create `models.py`** with:
   - `ExpressionTranslationRequest`: Pydantic model with the n8n expression string, surrounding context (node type, field path), and any available schema hints. Use `frozen=True`.
   - `ExpressionTranslationResponse`: Pydantic model with the JSONata expression string, confidence, and warnings. Use `frozen=True`. Import `Confidence` from `phaeton_models`.

4. **Create `agent.py`** with:
   - A module-level `EXPRESSION_PROMPT_TEMPLATE` tailored for expression translation. This should focus on: n8n expression syntax patterns (`$json`, `$node`, `$env`, `$binary`), JSONata output syntax, Step Functions intrinsic functions as alternatives, common mappings.
   - `_generate_tag_suffix()`: Copied from ai-agent.
   - `_parse_json_response()`: Copied from ai-agent.
   - `translate_expression()`: Core function that builds the prompt, invokes the Strands Agent, parses the response, and returns an `ExpressionTranslationResponse`.

5. **Create `handler.py`** with:
   - `handler(event, context)`: Lambda entry point. Deserializes `event` directly as `ExpressionTranslationRequest`. Calls `translate_expression()`. Returns `ExpressionTranslationResponse.model_dump()`.

6. **Create `cli.py`** with:
   - A Typer app with a `translate` command that reads a JSON file or accepts an expression string, calls `translate_expression()`, and prints the result.

7. **Create tests** mirroring existing patterns.

### Testing Requirements

- `test_models.py`: Verify request/response serialization. Test frozen immutability. Test Confidence enum in response.
- `test_agent.py`: Mock the Strands Agent. Test successful translation of common n8n expressions (`{{ $json.field }}`, `{{ $node["Name"].json }}`, `{{ $env.VAR }}`). Test parse failure handling. Test empty response.
- `test_handler.py`: Test handler with valid event, missing fields, agent errors.
- All tests must have docstrings, `-> None` return annotations, and type annotations per project conventions.
