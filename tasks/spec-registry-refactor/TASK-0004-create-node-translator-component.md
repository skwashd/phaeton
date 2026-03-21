# Create Node Translator Component

**Priority:** P0
**Effort:** L
**Gap Analysis Ref:** Item #4

## Overview

The `ai-agent/` component currently handles two distinct responsibilities: node translation (n8n nodes to ASL states) and expression translation (n8n expressions to JSONata). These should be independent microservices. This task extracts the node translation responsibility into a new `node-translator/` component.

The node translator uses a Strands Agent with Bedrock to translate individual n8n workflow nodes into AWS Step Functions ASL state definitions. It receives a node's configuration and context, sends it to an LLM with a specialized system prompt, validates the returned ASL, and returns it with a confidence score.

The new component follows ports-and-adapters: core logic in `agent.py`, Lambda handler adapter in `handler.py`, dev-only CLI adapter in `cli.py`. The handler accepts a flat request (no `operation` routing — unlike the current ai-agent which routes based on an `operation` field).

## Dependencies

- **Blocked by:** TASK-0001 (Confidence enum must be in phaeton-models first)
- **Blocks:** TASK-0008 (client update needs the new Lambda contract), TASK-0009 (ai-agent deletion), TASK-0014 (deployment stack)

## Acceptance Criteria

1. `node-translator/` directory exists with a complete Python package structure.
2. `pyproject.toml` declares the package with correct dependencies (strands-agents, phaeton-models, boto3).
3. `agent.py` contains a `translate_node()` function that accepts a node translation request and returns a response with ASL states and confidence.
4. The Strands Agent uses a system prompt specifically tailored for node-to-ASL translation (not the current generic prompt).
5. `_validate_asl_states()` validates that returned JSON contains valid ASL state structures.
6. `handler.py` implements a Lambda handler that deserializes the event directly as a node translation request (no `operation` field routing).
7. `cli.py` provides a Typer CLI for dev/testing that reads a JSON request file and prints the response.
8. Typer is a `dev` dependency, not a production dependency.
9. `_generate_tag_suffix()` and `_parse_json_response()` utilities are included in the component (duplicated from ai-agent, not shared).
10. `uv run pytest` passes in `node-translator/`.
11. `uv run ruff check` passes in `node-translator/`.
12. `uv run ty check` passes in `node-translator/`.

## Implementation Details

### Files to Modify

- `node-translator/pyproject.toml` (new)
- `node-translator/src/phaeton_node_translator/__init__.py` (new)
- `node-translator/src/phaeton_node_translator/agent.py` (new)
- `node-translator/src/phaeton_node_translator/models.py` (new)
- `node-translator/src/phaeton_node_translator/handler.py` (new)
- `node-translator/src/phaeton_node_translator/cli.py` (new)
- `node-translator/tests/__init__.py` (new)
- `node-translator/tests/conftest.py` (new)
- `node-translator/tests/test_agent.py` (new)
- `node-translator/tests/test_handler.py` (new)
- `node-translator/tests/test_models.py` (new)

### Technical Approach

1. **Read source material** from `ai-agent/`:
   - `ai-agent/src/phaeton_ai_agent/agent.py`: Extract `translate_node()`, `_validate_asl_states()`, `_generate_tag_suffix()`, `_parse_json_response()`, and `NODE_PROMPT_TEMPLATE`.
   - `ai-agent/src/phaeton_ai_agent/models.py`: Extract `NodeTranslationRequest` and `AIAgentResponse`.
   - `ai-agent/src/phaeton_ai_agent/handler.py`: Extract the `translate_node` branch of the handler routing.
   - `ai-agent/tests/test_agent.py`: Extract node translation tests.
   - `ai-agent/tests/test_handler.py`: Extract node handler tests.

2. **Create `pyproject.toml`** following the pattern of other components. Key dependencies:
   - `strands-agents` and `strands-agents-bedrock` for the AI agent
   - `phaeton-models` for `Confidence` enum
   - `pydantic` for request/response models
   - `typer` in `[dependency-groups] dev`
   - Build system: `uv_build`

3. **Create `models.py`** with:
   - `NodeTranslationRequest`: Pydantic model with fields for node type, node config, workflow context, etc. (copy from ai-agent's `NodeTranslationRequest`). Use `frozen=True`.
   - `NodeTranslationResponse`: Pydantic model with ASL states dict, confidence, and any warnings. Use `frozen=True`. Import `Confidence` from `phaeton_models`.

4. **Create `agent.py`** with:
   - A module-level `NODE_PROMPT_TEMPLATE` tailored specifically for node translation (refine the current generic prompt to focus on ASL output, state types, error handling patterns).
   - `_generate_tag_suffix()`: Copied from ai-agent (~5 lines, generates random hex suffix for XML boundary tags).
   - `_parse_json_response()`: Copied from ai-agent (~15 lines, extracts JSON from LLM response text).
   - `_validate_asl_states()`: Validates returned dict has valid ASL state keys (Type, Next/End, etc.).
   - `translate_node()`: Core function that builds the prompt, invokes the Strands Agent, parses the response, validates ASL, and returns a `NodeTranslationResponse`.

5. **Create `handler.py`** with:
   - `handler(event, context)`: Lambda entry point. Deserializes `event` directly as `NodeTranslationRequest` (no `operation` routing). Calls `translate_node()`. Returns `NodeTranslationResponse.model_dump()`.

6. **Create `cli.py`** with:
   - A Typer app with a `translate` command that reads a JSON file, validates as `NodeTranslationRequest`, calls `translate_node()`, and prints the response JSON.

7. **Create tests** mirroring the existing ai-agent test patterns:
   - `test_models.py`: Validate request/response serialization.
   - `test_agent.py`: Test `translate_node()` with mocked Strands Agent. Test `_validate_asl_states()` with valid/invalid inputs. Test `_parse_json_response()` with various LLM output formats.
   - `test_handler.py`: Test the Lambda handler with mock events.
   - `conftest.py`: Shared fixtures (mock agent, sample requests).

### Testing Requirements

- `test_models.py`: Verify `NodeTranslationRequest` and `NodeTranslationResponse` serialize/deserialize correctly. Test `frozen=True` immutability. Test `Confidence` enum values in response.
- `test_agent.py`: Mock the Strands Agent to return canned responses. Test successful translation, ASL validation failure, JSON parse failure, empty response handling.
- `test_handler.py`: Test handler with valid event dict, missing fields, and agent errors.
- All tests must have docstrings, `-> None` return annotations, and type annotations on parameters per project conventions.
