# Ai Agent Fallback Service

**Priority:** P1
**Effort:** L
**Gap Analysis Ref:** Item #8

## Overview

The `StubAIAgent` class in `fallback.py` raises `NotImplementedError` for both `translate_node()` and `translate_expression()`. Any workflow containing a node or expression that falls through to the AI agent path will crash the translation pipeline. A prompt template (`PROMPT_TEMPLATE`) is defined but never wired to an LLM. The `AITranslationResult` model wrapping confidence scores is also defined but unused.

This should be built as a new standalone component (Component 5) using the AWS Strands Agents framework, deployed on AWS AgentCore. The Translation Engine would invoke this service when it encounters nodes or expressions it cannot translate with its built-in translators.

## Dependencies

- **Blocked by:** TASK-0015 (Translation Engine needs a service entry point to invoke the agent)
- **Blocks:** TASK-0024

## Acceptance Criteria

1. A new component `ai-agent/` exists with its own `pyproject.toml`, source directory, and tests.
2. The agent service implements the `AIAgentProtocol` interface (defined in `fallback.py` line 68): `translate_node(node, context) -> TranslationResult` and `translate_expression(expr, node, context) -> str`.
3. The agent uses AWS Strands Agents framework with the existing `PROMPT_TEMPLATE` (or an improved version).
4. The `AITranslationResult` model (with `result`, `confidence`, `explanation` fields) is used to wrap responses.
5. The `Confidence` enum (`HIGH`, `MEDIUM`, `LOW`) is used to score translation quality.
6. The agent returns valid ASL JSON using JSONata query language (not legacy JSONPath).
7. The `StubAIAgent` class is replaced with a client that calls the agent service.
8. The Translation Engine's `_translate_node` method (line 117 in `engine.py`) successfully falls back to the agent when no built-in translator matches.
9. `uv run pytest` passes in both `ai-agent/` and `n8n-to-sfn/`.
10. `uv run ruff check` passes.

## Implementation Details

### Files to Modify

- `ai-agent/` (new component directory)
- `ai-agent/pyproject.toml`
- `ai-agent/src/phaeton_ai_agent/` (new package)
- `ai-agent/src/phaeton_ai_agent/agent.py` (Strands Agents implementation)
- `ai-agent/src/phaeton_ai_agent/handler.py` (Lambda/service entry point)
- `n8n-to-sfn/src/n8n_to_sfn/ai_agent/fallback.py` (replace StubAIAgent with service client)
- `n8n-to-sfn/src/n8n_to_sfn/engine.py` (wire agent client)

### Technical Approach

1. **Agent Service (Component 5):**
   - Use Strands Agents SDK to create an agent that accepts node JSON, node type, expressions, and workflow context.
   - Use the `PROMPT_TEMPLATE` from `fallback.py` (line 38) as the base prompt, with placeholders: `{node_json}`, `{node_type}`, `{expressions}`, `{workflow_context}`, `{position}`, `{target_state_type}`.
   - The agent should output valid ASL state definitions using JSONata.
   - Deploy on AWS AgentCore with a Lambda handler entry point.

2. **Client Integration:**
   - Replace `StubAIAgent` with an `AIAgentClient` that invokes the agent service via HTTP or AWS SDK.
   - The client implements `AIAgentProtocol` so the engine can use it transparently.
   - Parse the agent response into `AITranslationResult` with confidence scoring.

3. **Engine Integration:**
   - In `TranslationEngine.__init__` (line 52), accept an `AIAgentProtocol` (already present as `ai_agent` parameter).
   - In `_translate_node` (line 117), the existing fallback to `self._ai_agent` should work once `StubAIAgent` is replaced.

### Testing Requirements

- `ai-agent/tests/test_agent.py` — unit tests with mocked LLM responses.
- `n8n-to-sfn/tests/test_ai_agent_client.py` — integration tests with mocked HTTP calls.
- Test that the agent returns valid ASL for common unsupported node types.
- Test confidence scoring and error handling for malformed LLM responses.
- `MockAIAgent` (line 112 in `fallback.py`) can be used for engine-level tests.
