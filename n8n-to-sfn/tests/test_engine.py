"""Tests for the translation engine orchestrator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.models.asl import PassState
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    TranslationContext,
    TranslationResult,
)


def _node(
    name: str,
    node_type: str = "n8n-nodes-base.set",
    classification: NodeClassification = NodeClassification.FLOW_CONTROL,
) -> ClassifiedNode:
    """Create a classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
        ),
        classification=classification,
    )


class AllPassTranslator(BaseTranslator):
    """Mock translator that translates everything to Pass states."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Check if node can be translated."""
        return node.classification != NodeClassification.UNSUPPORTED

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate node to Pass state."""
        return TranslationResult(
            states={node.node.name: PassState()},
        )


class SelectiveTranslator(BaseTranslator):
    """Translates only FLOW_CONTROL nodes."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Check if node is FLOW_CONTROL."""
        return node.classification == NodeClassification.FLOW_CONTROL

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate node to Pass state."""
        return TranslationResult(
            states={node.node.name: PassState()},
        )


class TestEngine:
    """Tests for TranslationEngine."""

    def test_basic_translation(self) -> None:
        """Test basic two-node translation."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)

        assert "A" in output.state_machine.states
        assert "B" in output.state_machine.states
        assert output.state_machine.start_at == "A"

    def test_topological_ordering(self) -> None:
        """Test nodes are topologically ordered."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("C"), _node("A"), _node("B")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="C", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert output.state_machine.start_at == "A"

    def test_unsupported_nodes_produce_warnings(self) -> None:
        """Test unsupported nodes produce warnings."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("OK"),
                _node("Bad", classification=NodeClassification.UNSUPPORTED),
            ],
            dependency_edges=[
                DependencyEdge(from_node="OK", to_node="Bad", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert any(
            "Unsupported" in w or "unsupported" in w.lower() for w in output.warnings
        )
        assert "OK" in output.state_machine.states

    def test_validator_called_on_output(self) -> None:
        """Test validator is called on output."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert output.state_machine is not None
        dumped = output.state_machine.model_dump(by_alias=True)
        assert "StartAt" in dumped
        assert "States" in dumped

    def test_no_translator_match_produces_warning(self) -> None:
        """Test no translator match produces warning."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("A", classification=NodeClassification.AWS_NATIVE),
            ],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[SelectiveTranslator()])
        output = engine.translate(analysis)
        assert any("No translator" in w for w in output.warnings)

    def test_conversion_report(self) -> None:
        """Test conversion report is generated."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="CONNECTION"),
            ],
            confidence_score=0.85,
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert output.conversion_report["total_nodes"] == 2
        assert output.conversion_report["confidence_score"] == 0.85

    def test_single_node_gets_end_true(self) -> None:
        """Test single node gets end=True."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("Only")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        state = output.state_machine.states["Only"]
        assert state.end is True

    def test_data_reference_edges_dont_wire_transitions(self) -> None:
        """Test data reference edges do not wire transitions."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="DATA_REFERENCE"),
            ],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        state_a = output.state_machine.states["A"]
        assert state_a.next is None
        assert state_a.end is True


class TestEngineAIAgent:
    """Tests for TranslationEngine AI agent integration."""

    def test_stub_ai_agent_produces_warning(self) -> None:
        """Test stub AI agent produces warning."""

        class StubAgent:
            def translate_node(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                msg = f"Not implemented for {node.node.name}"
                raise NotImplementedError(msg)

        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("X", classification=NodeClassification.GRAPHQL_API),
            ],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[], ai_agent=StubAgent())
        output = engine.translate(analysis)
        assert any("AI agent not implemented" in w for w in output.warnings)

    def test_mock_ai_agent_result_incorporated(self) -> None:
        """Test mock AI agent result is incorporated."""

        class MockAgent:
            def translate_node(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                return TranslationResult(
                    states={
                        node.node.name: PassState(
                            comment="AI-generated",
                        ),
                    },
                    metadata={"ai_generated": True, "confidence": "HIGH"},
                )

        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("AI", classification=NodeClassification.GRAPHQL_API),
            ],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[], ai_agent=MockAgent())
        output = engine.translate(analysis)
        assert "AI" in output.state_machine.states
        state = output.state_machine.states["AI"]
        assert state.comment == "AI-generated"
