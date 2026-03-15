"""Core Strands Agent logic for AI-powered node and expression translation."""

from __future__ import annotations

import json
import logging
from typing import Any

from strands import Agent
from strands.models.bedrock import BedrockModel

from phaeton_ai_agent.models import (
    AIAgentResponse,
    Confidence,
    ExpressionResponse,
    ExpressionTranslationRequest,
    NodeTranslationRequest,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are translating an n8n workflow node into an AWS Step Functions ASL state.

## Constraints
1. Output must be valid ASL JSON
2. Use JSONata (not JSONPath) for all data transformations
3. Use SSM Parameter Store for any credentials
4. Flag any uncertainty in the output
5. All state names must be 1-128 characters
"""

NODE_PROMPT_TEMPLATE = """\
Translate the following n8n node into AWS Step Functions ASL state(s).

## Node Configuration
```json
{node_json}
```

## Node Type
{node_type}

## Expressions Requiring Translation
{expressions}

## Workflow Context
{workflow_context}

## Target State
- Position in ASL: {position}
- Target state type: {target_state_type}

Respond with a JSON object containing:
- "states": a dict mapping state names to ASL state definitions
- "confidence": "HIGH", "MEDIUM", or "LOW"
- "explanation": a brief explanation of the translation
- "warnings": a list of any warnings or caveats
"""

EXPRESSION_PROMPT_TEMPLATE = """\
Translate the following n8n expression into a JSONata expression suitable for \
AWS Step Functions.

## Expression
{expression}

## Node Context
```json
{node_json}
```

## Node Type
{node_type}

## Workflow Context
{workflow_context}

Respond with a JSON object containing:
- "translated": the translated JSONata expression
- "confidence": "HIGH", "MEDIUM", or "LOW"
- "explanation": a brief explanation of the translation
"""

# Module-level singleton, lazily initialized on first call
_agent: Agent | None = None


def _get_agent() -> Agent:
    """Get or create the Strands Agent singleton."""
    global _agent  # noqa: PLW0603
    if _agent is None:
        model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514",
            region_name="us-east-1",
        )
        _agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
        )
    return _agent


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from agent response text, handling markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


def translate_node(request: NodeTranslationRequest) -> AIAgentResponse:
    """
    Translate an n8n node using the Strands Agent.

    Parameters
    ----------
    request:
        The node translation request payload.

    Returns
    -------
    AIAgentResponse
        The translated ASL states with confidence and explanation.

    """
    try:
        agent = _get_agent()
        prompt = NODE_PROMPT_TEMPLATE.format(
            node_json=request.node_json,
            node_type=request.node_type,
            expressions=request.expressions,
            workflow_context=request.workflow_context,
            position=request.position,
            target_state_type=request.target_state_type,
        )
        result = agent(prompt)
        parsed = _parse_json_response(str(result))
        return AIAgentResponse.model_validate(parsed)
    except Exception:
        logger.exception("AI agent failed to translate node: %s", request.node_name)
        return AIAgentResponse(
            confidence=Confidence.LOW,
            explanation="AI agent encountered an error during translation.",
            warnings=[f"AI agent error translating node: {request.node_name}"],
        )


def translate_expression(request: ExpressionTranslationRequest) -> ExpressionResponse:
    """
    Translate an n8n expression using the Strands Agent.

    Parameters
    ----------
    request:
        The expression translation request payload.

    Returns
    -------
    ExpressionResponse
        The translated expression with confidence and explanation.

    """
    try:
        agent = _get_agent()
        prompt = EXPRESSION_PROMPT_TEMPLATE.format(
            expression=request.expression,
            node_json=request.node_json,
            node_type=request.node_type,
            workflow_context=request.workflow_context,
        )
        result = agent(prompt)
        parsed = _parse_json_response(str(result))
        return ExpressionResponse.model_validate(parsed)
    except Exception:
        logger.exception("AI agent failed to translate expression: %s", request.expression)
        return ExpressionResponse(
            translated=request.expression,
            confidence=Confidence.LOW,
            explanation="AI agent encountered an error during translation.",
        )
