"""Tests for AI agent fallback module."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.ai_agent.fallback import (
    AITranslationResult,
    Confidence,
    MockAIAgent,
)
from n8n_to_sfn.models.asl import PassState
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext, TranslationResult


def _node(name: str = "TestNode") -> ClassifiedNode:
    """Create a classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.httpRequest",
            type_version=1,
            position=[0, 0],
            parameters={},
        ),
        classification=NodeClassification.GRAPHQL_API,
    )


def _context() -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
    )



class TestMockAIAgent:
    """Tests for MockAIAgent."""

    def test_translate_node_default_response(self) -> None:
        """Test translate_node returns default response."""
        agent = MockAIAgent()
        result = agent.translate_node(_node("Foo"), _context())
        assert isinstance(result, TranslationResult)
        assert result.metadata.get("ai_generated") is True
        assert any("Foo" in w for w in result.warnings)

    def test_translate_node_preconfigured_response(self) -> None:
        """Test translate_node returns preconfigured response."""
        custom_result = TranslationResult(
            states={"Custom": PassState(end=True)},
            metadata={"custom": True},
        )
        agent = MockAIAgent(node_responses={"MyNode": custom_result})
        result = agent.translate_node(_node("MyNode"), _context())
        assert "Custom" in result.states
        assert result.metadata.get("custom") is True

    def test_translate_expression_default_passthrough(self) -> None:
        """Test translate_expression returns expression as-is by default."""
        agent = MockAIAgent()
        result = agent.translate_expression("{{ $json.x }}", _node(), _context())
        assert result == "{{ $json.x }}"

    def test_translate_expression_preconfigured(self) -> None:
        """Test translate_expression returns preconfigured response."""
        agent = MockAIAgent(
            expression_responses={"{{ $json.x }}": "$states.input.x"},
        )
        result = agent.translate_expression("{{ $json.x }}", _node(), _context())
        assert result == "$states.input.x"


class TestAITranslationResult:
    """Tests for AITranslationResult."""

    def test_construction(self) -> None:
        """Test AITranslationResult construction."""
        result = AITranslationResult(
            result=TranslationResult(),
            confidence=Confidence.HIGH,
            explanation="Test explanation",
        )
        assert result.confidence == Confidence.HIGH
        assert result.explanation == "Test explanation"

    def test_confidence_values(self) -> None:
        """Test Confidence enum values."""
        assert Confidence.HIGH == "HIGH"
        assert Confidence.MEDIUM == "MEDIUM"
        assert Confidence.LOW == "LOW"
