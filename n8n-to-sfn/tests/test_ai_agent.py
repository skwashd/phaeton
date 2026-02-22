"""Tests for AI agent fallback module."""

import pytest

from n8n_to_sfn.ai_agent.fallback import (
    AITranslationResult,
    Confidence,
    MockAIAgent,
    StubAIAgent,
)
from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.asl import PassState
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext, TranslationResult


def _node(name="TestNode"):
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


def _context():
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
    )


class TestStubAIAgent:
    def test_translate_node_raises(self):
        agent = StubAIAgent()
        with pytest.raises(NotImplementedError, match="AI agent not implemented"):
            agent.translate_node(_node(), _context())

    def test_translate_expression_raises(self):
        agent = StubAIAgent()
        with pytest.raises(NotImplementedError, match="AI agent not implemented"):
            agent.translate_expression("{{ $json.x }}", _node(), _context())


class TestMockAIAgent:
    def test_translate_node_default_response(self):
        agent = MockAIAgent()
        result = agent.translate_node(_node("Foo"), _context())
        assert isinstance(result, TranslationResult)
        assert result.metadata.get("ai_generated") is True
        assert any("Foo" in w for w in result.warnings)

    def test_translate_node_preconfigured_response(self):
        custom_result = TranslationResult(
            states={"Custom": PassState(end=True)},
            metadata={"custom": True},
        )
        agent = MockAIAgent(node_responses={"MyNode": custom_result})
        result = agent.translate_node(_node("MyNode"), _context())
        assert "Custom" in result.states
        assert result.metadata.get("custom") is True

    def test_translate_expression_default_passthrough(self):
        agent = MockAIAgent()
        result = agent.translate_expression("{{ $json.x }}", _node(), _context())
        assert result == "{{ $json.x }}"

    def test_translate_expression_preconfigured(self):
        agent = MockAIAgent(
            expression_responses={"{{ $json.x }}": "$states.input.x"},
        )
        result = agent.translate_expression("{{ $json.x }}", _node(), _context())
        assert result == "$states.input.x"


class TestAITranslationResult:
    def test_construction(self):
        result = AITranslationResult(
            result=TranslationResult(),
            confidence=Confidence.HIGH,
            explanation="Test explanation",
        )
        assert result.confidence == Confidence.HIGH
        assert result.explanation == "Test explanation"

    def test_confidence_values(self):
        assert Confidence.HIGH == "HIGH"
        assert Confidence.MEDIUM == "MEDIUM"
        assert Confidence.LOW == "LOW"
