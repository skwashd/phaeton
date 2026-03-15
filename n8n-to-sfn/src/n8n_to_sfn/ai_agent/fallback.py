"""AI agent fallback for Category C expressions and unresolvable nodes.

Provides a protocol interface for AI agent integration, a stub implementation,
and a mock implementation for testing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from phaeton_models.translator import ClassifiedNode
from pydantic import BaseModel

from n8n_to_sfn.translators.base import TranslationContext, TranslationResult


class Confidence(StrEnum):
    """Confidence level for AI-generated translations."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AITranslationResult(BaseModel):
    """Result from an AI agent translation attempt."""

    result: TranslationResult
    confidence: Confidence
    explanation: str = ""


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
You are translating an n8n workflow node into an AWS Step Functions ASL state.

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

## Constraints
1. Output must be valid ASL JSON
2. Use JSONata (not JSONPath) for all data transformations
3. Use SSM Parameter Store for any credentials
4. Flag any uncertainty in the output
5. All state names must be 1-128 characters
"""


class AIAgentProtocol(Protocol):
    """Protocol defining the AI agent fallback interface."""

    def translate_node(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult:
        """Translate a node using AI agent fallback."""
        ...

    def translate_expression(
        self,
        expr: str,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> str:
        """Translate a single expression using AI agent fallback."""
        ...


class StubAIAgent:
    """Stub implementation that raises NotImplementedError."""

    def translate_node(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult:
        """Raise NotImplementedError — LLM integration not yet implemented."""
        msg = f"AI agent not implemented for node: {node.node.name} ({node.node.type})"
        raise NotImplementedError(msg)

    def translate_expression(
        self,
        expr: str,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> str:
        """Raise NotImplementedError — LLM integration not yet implemented."""
        msg = f"AI agent not implemented for expression: {expr}"
        raise NotImplementedError(msg)


class MockAIAgent:
    """Mock implementation that returns preconfigured responses for testing."""

    def __init__(
        self,
        node_responses: dict[str, TranslationResult] | None = None,
        expression_responses: dict[str, str] | None = None,
    ) -> None:
        """Initialize with preconfigured responses."""
        self._node_responses = node_responses or {}
        self._expression_responses = expression_responses or {}

    def translate_node(
        self,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> TranslationResult:
        """Return preconfigured response or a default TranslationResult."""
        if node.node.name in self._node_responses:
            return self._node_responses[node.node.name]
        return TranslationResult(
            metadata={"ai_generated": True, "confidence": "MEDIUM"},
            warnings=[f"AI-generated translation for: {node.node.name}"],
        )

    def translate_expression(
        self,
        expr: str,
        node: ClassifiedNode,
        context: TranslationContext,
    ) -> str:
        """Return preconfigured response or the original expression."""
        return self._expression_responses.get(expr, expr)
