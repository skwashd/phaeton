"""Tests for the translation engine orchestrator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)
from phaeton_models.translator_output import TranslationOutput

from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.models.asl import MapState, ParallelState, PassState, StateMachine
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    CredentialArtifact,
    TranslationContext,
    TranslationResult,
)
from n8n_to_sfn.translators.flow_control import FlowControlTranslator


def _sm(output: TranslationOutput) -> StateMachine:
    """Deserialize the output state_machine dict back to a StateMachine model."""
    return StateMachine.model_validate(output.state_machine)


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

        sm = _sm(output)
        assert "A" in sm.states
        assert "B" in sm.states
        assert sm.start_at == "A"

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
        assert _sm(output).start_at == "A"

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
        assert "OK" in _sm(output).states

    def test_validator_called_on_output(self) -> None:
        """Test validator is called on output."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert output.state_machine is not None
        assert "StartAt" in output.state_machine
        assert "States" in output.state_machine

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
        state = _sm(output).states["Only"]
        assert state.end is True  # type: ignore[unresolved-attribute]

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
        state_a = _sm(output).states["A"]
        assert state_a.next is None  # type: ignore[unresolved-attribute]
        assert state_a.end is True  # type: ignore[unresolved-attribute]


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
        engine = TranslationEngine(translators=[], ai_agent=StubAgent())  # type: ignore[invalid-argument-type]
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
        engine = TranslationEngine(translators=[], ai_agent=MockAgent())  # type: ignore[invalid-argument-type]
        output = engine.translate(analysis)
        assert "AI" in _sm(output).states
        state = _sm(output).states["AI"]
        assert state.comment == "AI-generated"


class MergePassTranslator(BaseTranslator):
    """Translator that handles Merge nodes with metadata and others as Pass."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Accept all non-unsupported nodes."""
        return node.classification != NodeClassification.UNSUPPORTED

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate Merge nodes with metadata, everything else as Pass."""
        if node.node.type == "n8n-nodes-base.merge":
            mode = node.node.parameters.get("mode", "append")
            return TranslationResult(
                states={node.node.name: PassState(comment=f"Merge: {node.node.name}")},
                metadata={"merge_node": True, "merge_mode": str(mode)},
            )
        return TranslationResult(
            states={node.node.name: PassState(comment=node.node.name)},
        )


def _merge_node(
    name: str,
    node_type: str = "n8n-nodes-base.set",
    params: dict[str, object] | None = None,
) -> ClassifiedNode:
    """Create a classified node for merge tests."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


class TestEngineMergeParallel:
    """Tests for Merge node -> Parallel state post-processing."""

    def test_two_branch_merge(self) -> None:
        """Test IF -> BranchA / BranchB -> Merge produces Parallel state."""
        # Graph: Fork -> BranchA -> Merge
        #        Fork -> BranchB -> Merge
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("BranchA"),
                _merge_node("BranchB"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
                _merge_node("After"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="Fork", to_node="BranchA", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="Fork", to_node="BranchB", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="BranchA", to_node="Merge", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="BranchB", to_node="Merge", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="Merge", to_node="After", edge_type="CONNECTION"
                ),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        # Fork should now be a Parallel state
        assert "Fork" in _sm(output).states
        fork_state = _sm(output).states["Fork"]
        assert isinstance(fork_state, ParallelState)
        assert len(fork_state.branches) == 2
        # Branch states should not be at top level
        assert "BranchA" not in _sm(output).states
        assert "BranchB" not in _sm(output).states
        assert "Merge" not in _sm(output).states

        # After should still exist
        assert "After" in _sm(output).states

        # Each branch should contain its respective state
        branch_start_ats = {b.start_at for b in fork_state.branches}
        assert "BranchA" in branch_start_ats
        assert "BranchB" in branch_start_ats

    def test_three_branch_merge(self) -> None:
        """Test fork with three branches merging produces Parallel with 3 branches."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("A"),
                _merge_node("B"),
                _merge_node("C"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="Fork", to_node="A", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="B", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="C", edge_type="CONNECTION"),
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="C", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        fork_state = _sm(output).states["Fork"]
        assert isinstance(fork_state, ParallelState)
        assert len(fork_state.branches) == 3

    def test_merge_mode_in_comment(self) -> None:
        """Test merge mode is reflected in the Parallel state comment."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("A"),
                _merge_node("B"),
                _merge_node(
                    "Merge", "n8n-nodes-base.merge", params={"mode": "combine"}
                ),
            ],
            dependency_edges=[
                DependencyEdge(from_node="Fork", to_node="A", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="B", edge_type="CONNECTION"),
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        fork_state = _sm(output).states["Fork"]
        assert isinstance(fork_state, ParallelState)
        assert "combine" in fork_state.comment  # type: ignore[unsupported-operator]

    def test_multi_step_branches(self) -> None:
        """Test branches with multiple steps are collected correctly."""
        # Fork -> A1 -> A2 -> Merge
        # Fork -> B1 -> B2 -> Merge
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("A1"),
                _merge_node("A2"),
                _merge_node("B1"),
                _merge_node("B2"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="Fork", to_node="A1", edge_type="CONNECTION"),
                DependencyEdge(from_node="A1", to_node="A2", edge_type="CONNECTION"),
                DependencyEdge(from_node="A2", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="B1", edge_type="CONNECTION"),
                DependencyEdge(from_node="B1", to_node="B2", edge_type="CONNECTION"),
                DependencyEdge(from_node="B2", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        fork_state = _sm(output).states["Fork"]
        assert isinstance(fork_state, ParallelState)
        assert len(fork_state.branches) == 2
        # Each branch should have 2 states
        for branch in fork_state.branches:
            assert len(branch.states) == 2
        # Multi-step states should not be at top level
        for name in ("A1", "A2", "B1", "B2", "Merge"):
            assert name not in _sm(output).states

    def test_merge_single_incoming_warns(self) -> None:
        """Test merge with single incoming branch produces warning."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("A"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        assert any("expected >=2" in w for w in output.warnings)

    def test_parallel_state_wires_to_downstream(self) -> None:
        """Test Parallel state wires Next to the state after the merge."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("A"),
                _merge_node("B"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
                _merge_node("Final"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="Fork", to_node="A", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="B", edge_type="CONNECTION"),
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(
                    from_node="Merge", to_node="Final", edge_type="CONNECTION"
                ),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        fork_state = _sm(output).states["Fork"]
        assert isinstance(fork_state, ParallelState)
        assert fork_state.next == "Final"

    def test_parallel_asl_serialization(self) -> None:
        """Test the Parallel state serializes to valid ASL structure."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _merge_node("Fork"),
                _merge_node("A"),
                _merge_node("B"),
                _merge_node("Merge", "n8n-nodes-base.merge"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="Fork", to_node="A", edge_type="CONNECTION"),
                DependencyEdge(from_node="Fork", to_node="B", edge_type="CONNECTION"),
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[MergePassTranslator()])
        output = engine.translate(analysis)

        asl = output.state_machine
        fork_asl = asl["States"]["Fork"]
        assert fork_asl["Type"] == "Parallel"
        assert "Branches" in fork_asl
        assert len(fork_asl["Branches"]) == 2
        for branch in fork_asl["Branches"]:
            assert "StartAt" in branch
            assert "States" in branch


class SplitInBatchesTranslator(BaseTranslator):
    """Translator that delegates SplitInBatches to FlowControlTranslator."""

    def __init__(self) -> None:
        """Initialize with a FlowControlTranslator for SplitInBatches nodes."""
        self._fc = FlowControlTranslator()

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Accept all non-unsupported nodes."""
        return node.classification != NodeClassification.UNSUPPORTED

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Delegate SplitInBatches, translate everything else as Pass."""
        if node.node.type == "n8n-nodes-base.splitInBatches":
            return self._fc.translate(node, context)
        return TranslationResult(
            states={node.node.name: PassState(comment=node.node.name)},
        )


def _sib_node(
    name: str,
    node_type: str = "n8n-nodes-base.set",
    params: dict[str, object] | None = None,
) -> ClassifiedNode:
    """Create a classified node for SplitInBatches tests."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


class TestEngineSplitInBatches:
    """Tests for SplitInBatches -> Map state post-processing."""

    def test_simple_loop_body(self) -> None:
        """
        Test SplitInBatches with a single-node loop body.

        Graph: SIB --(done, idx 0)--> After
               SIB --(loop, idx 1)--> LoopStep --> SIB
        """
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node("SIB", "n8n-nodes-base.splitInBatches"),
                _sib_node("LoopStep"),
                _sib_node("After"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="After",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
                DependencyEdge(
                    from_node="SIB",
                    to_node="LoopStep",
                    edge_type="CONNECTION",
                    output_index=1,
                ),
                DependencyEdge(
                    from_node="LoopStep",
                    to_node="SIB",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        # SIB should be a Map state
        sib_state = _sm(output).states["SIB"]
        assert isinstance(sib_state, MapState)
        assert sib_state.max_concurrency == 1

        # LoopStep should be inside the ItemProcessor, not top-level
        assert "LoopStep" not in _sm(output).states
        inner_states = sib_state.item_processor.states  # type: ignore[unresolved-attribute]
        assert "LoopStep" in inner_states  # type: ignore[unsupported-operator]

        # Inner state should be terminal
        loop_step = inner_states["LoopStep"]  # type: ignore[not-subscriptable]
        assert loop_step["End"] is True

        # After should still be at top level
        assert "After" in _sm(output).states

    def test_multi_step_loop_body(self) -> None:
        """
        Test SplitInBatches with a multi-step loop body.

        Graph: SIB --(done)--> After
               SIB --(loop)--> Step1 --> Step2 --> SIB
        """
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node("SIB", "n8n-nodes-base.splitInBatches"),
                _sib_node("Step1"),
                _sib_node("Step2"),
                _sib_node("After"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="After",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
                DependencyEdge(
                    from_node="SIB",
                    to_node="Step1",
                    edge_type="CONNECTION",
                    output_index=1,
                ),
                DependencyEdge(
                    from_node="Step1",
                    to_node="Step2",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
                DependencyEdge(
                    from_node="Step2",
                    to_node="SIB",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        sib_state = _sm(output).states["SIB"]
        assert isinstance(sib_state, MapState)

        inner_states = sib_state.item_processor.states  # type: ignore[unresolved-attribute]
        assert "Step1" in inner_states  # type: ignore[unsupported-operator]
        assert "Step2" in inner_states  # type: ignore[unsupported-operator]
        assert len(inner_states) == 2  # type: ignore[invalid-argument-type]

        # Step1 should chain to Step2
        assert inner_states["Step1"]["Next"] == "Step2"  # type: ignore[not-subscriptable]
        # Step2 should be terminal
        assert inner_states["Step2"]["End"] is True  # type: ignore[not-subscriptable]

        # Inner states should not be at top level
        assert "Step1" not in _sm(output).states
        assert "Step2" not in _sm(output).states

    def test_custom_batch_size(self) -> None:
        """Test SplitInBatches with custom batchSize."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node(
                    "SIB",
                    "n8n-nodes-base.splitInBatches",
                    params={"batchSize": 50},
                ),
                _sib_node("LoopStep"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="LoopStep",
                    edge_type="CONNECTION",
                    output_index=1,
                ),
                DependencyEdge(
                    from_node="LoopStep",
                    to_node="SIB",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        sib_state = _sm(output).states["SIB"]
        assert isinstance(sib_state, MapState)
        assert "batch_size=50" in sib_state.comment  # type: ignore[unsupported-operator]

    def test_no_loop_output_warns(self) -> None:
        """Test SplitInBatches with no loop output produces warning."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node("SIB", "n8n-nodes-base.splitInBatches"),
                _sib_node("After"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="After",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        assert any("no loop output" in w for w in output.warnings)

    def test_map_state_wires_to_downstream(self) -> None:
        """Test Map state wires Next to the state after the loop."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node("SIB", "n8n-nodes-base.splitInBatches"),
                _sib_node("LoopStep"),
                _sib_node("Final"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="Final",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
                DependencyEdge(
                    from_node="SIB",
                    to_node="LoopStep",
                    edge_type="CONNECTION",
                    output_index=1,
                ),
                DependencyEdge(
                    from_node="LoopStep",
                    to_node="SIB",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        sib_state = _sm(output).states["SIB"]
        assert isinstance(sib_state, MapState)
        assert sib_state.next == "Final"

    def test_map_asl_serialization(self) -> None:
        """Test the Map state serializes to valid ASL structure."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _sib_node("SIB", "n8n-nodes-base.splitInBatches"),
                _sib_node("Process"),
                _sib_node("Done"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="SIB",
                    to_node="Done",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
                DependencyEdge(
                    from_node="SIB",
                    to_node="Process",
                    edge_type="CONNECTION",
                    output_index=1,
                ),
                DependencyEdge(
                    from_node="Process",
                    to_node="SIB",
                    edge_type="CONNECTION",
                    output_index=0,
                ),
            ],
        )
        engine = TranslationEngine(translators=[SplitInBatchesTranslator()])
        output = engine.translate(analysis)

        asl = output.state_machine
        sib_asl = asl["States"]["SIB"]
        assert sib_asl["Type"] == "Map"
        assert sib_asl["MaxConcurrency"] == 1
        assert "ItemProcessor" in sib_asl
        ip = sib_asl["ItemProcessor"]
        assert ip["ProcessorConfig"]["Mode"] == "INLINE"
        assert ip["StartAt"] == "Process"
        assert "Process" in ip["States"]


class CredentialTranslator(BaseTranslator):
    """Translator that emits credential artifacts for testing."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Accept all non-unsupported nodes."""
        return node.classification != NodeClassification.UNSUPPORTED

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate node to Pass state with a credential artifact if applicable."""
        creds: list[CredentialArtifact] = []
        if node.node.type == "n8n-nodes-base.slack":
            creds.append(
                CredentialArtifact(
                    parameter_path=f"/phaeton/creds/{node.node.name}",
                    credential_type="oauth2",
                    auth_type="oauth2",
                )
            )
        return TranslationResult(
            states={node.node.name: PassState()},
            credential_artifacts=creds,
        )


class TestEngineOutputModel:
    """Tests for shared TranslationOutput boundary model integration."""

    def test_state_machine_is_dict(self) -> None:
        """Engine output state_machine is a plain dict, not a Pydantic model."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert isinstance(output.state_machine, dict)
        assert "StartAt" in output.state_machine
        assert "States" in output.state_machine

    def test_credential_artifacts_populated(self) -> None:
        """Credential artifacts are collected from translator results."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=N8nNode(
                        id="slack1",
                        name="slack1",
                        type="n8n-nodes-base.slack",
                        type_version=1,
                        position=[0, 0],
                    ),
                    classification=NodeClassification.PICOFUN_API,
                ),
            ],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[CredentialTranslator()])
        output = engine.translate(analysis)
        assert len(output.credential_artifacts) == 1
        assert output.credential_artifacts[0].credential_type == "oauth2"
        assert output.credential_artifacts[0].parameter_path == "/phaeton/creds/slack1"

    def test_credential_artifacts_empty_when_no_credentials(self) -> None:
        """Credential artifacts list is empty when no nodes need credentials."""
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[AllPassTranslator()])
        output = engine.translate(analysis)
        assert output.credential_artifacts == []

    def test_round_trip_serialization(self) -> None:
        """TranslationOutput round-trips through model_dump and model_validate."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=N8nNode(
                        id="slack1",
                        name="slack1",
                        type="n8n-nodes-base.slack",
                        type_version=1,
                        position=[0, 0],
                    ),
                    classification=NodeClassification.PICOFUN_API,
                ),
                _node("B"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="slack1", to_node="B", edge_type="CONNECTION"),
            ],
        )
        engine = TranslationEngine(translators=[CredentialTranslator()])
        output = engine.translate(analysis)

        dumped = output.model_dump(mode="json")
        restored = TranslationOutput.model_validate(dumped)
        assert restored.state_machine == output.state_machine
        assert len(restored.credential_artifacts) == len(output.credential_artifacts)
        assert restored.warnings == output.warnings


class TestEngineSpecDirectory:
    """Tests for spec_directory pass-through."""

    def test_spec_directory_defaults_to_empty(self) -> None:
        """Engine defaults spec_directory to empty string."""
        engine = TranslationEngine(translators=[AllPassTranslator()])
        assert engine._spec_directory == ""

    def test_spec_directory_stored(self) -> None:
        """Engine stores provided spec_directory."""
        engine = TranslationEngine(
            translators=[AllPassTranslator()], spec_directory="/tmp/specs"
        )
        assert engine._spec_directory == "/tmp/specs"

    def test_spec_directory_passed_to_context(self) -> None:
        """Engine passes spec_directory through to TranslationContext."""
        captured_contexts: list[TranslationContext] = []

        class CapturingTranslator(BaseTranslator):
            """Translator that captures the context it receives."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Capture context and return a Pass state."""
                captured_contexts.append(context)
                return TranslationResult(states={node.node.name: PassState()})

        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(
            translators=[CapturingTranslator()], spec_directory="/tmp/my-specs"
        )
        engine.translate(analysis)

        assert len(captured_contexts) == 1
        assert captured_contexts[0].spec_directory == "/tmp/my-specs"

    def test_spec_directory_empty_by_default_in_context(self) -> None:
        """Engine with no spec_directory passes empty string to context."""
        captured_contexts: list[TranslationContext] = []

        class CapturingTranslator(BaseTranslator):
            """Translator that captures the context it receives."""

            def can_translate(self, node: ClassifiedNode) -> bool:
                """Accept all nodes."""
                return True

            def translate(
                self, node: ClassifiedNode, context: TranslationContext
            ) -> TranslationResult:
                """Capture context and return a Pass state."""
                captured_contexts.append(context)
                return TranslationResult(states={node.node.name: PassState()})

        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        engine = TranslationEngine(translators=[CapturingTranslator()])
        engine.translate(analysis)

        assert len(captured_contexts) == 1
        assert captured_contexts[0].spec_directory == ""
