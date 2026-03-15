"""Tests for Loop node translation."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.flow_control import FlowControlTranslator


def _loop_node(
    name: str, params: dict | None = None
) -> ClassifiedNode:
    """Create a Loop classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.loop",
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


def _context(edges: list[DependencyEdge] | None = None) -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(
            classified_nodes=[],
            dependency_edges=edges or [],
        ),
    )


class TestLoopNodeCountBased:
    """Tests for count-based Loop node translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()

    def test_count_loop_produces_map_state(self) -> None:
        """Test count-based loop produces a Map state."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 5})
        result = self.translator.translate(node, _context())
        state = result.states["Loop"]
        assert state.type == "Map"

    def test_count_loop_max_concurrency(self) -> None:
        """Test count-based loop has MaxConcurrency=1 for sequential execution."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 5})
        result = self.translator.translate(node, _context())
        state = result.states["Loop"]
        assert state.max_concurrency == 1

    def test_count_loop_items_path(self) -> None:
        """Test count-based loop uses $range for ItemsPath."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 5})
        result = self.translator.translate(node, _context())
        state = result.states["Loop"]
        assert "$range" in state.items_path

    def test_count_loop_default_count(self) -> None:
        """Test count-based loop defaults to 10 iterations."""
        node = _loop_node("Loop", params={"loopMode": "count"})
        result = self.translator.translate(node, _context())
        assert result.metadata["loop_count"] == 10
        assert "count=10" in result.states["Loop"].comment

    def test_count_loop_custom_count(self) -> None:
        """Test count-based loop reads custom count from parameters."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 25})
        result = self.translator.translate(node, _context())
        assert result.metadata["loop_count"] == 25
        assert "count=25" in result.states["Loop"].comment

    def test_count_loop_metadata(self) -> None:
        """Test count-based loop sets correct metadata."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 3})
        result = self.translator.translate(node, _context())
        assert result.metadata["loop_node"] is True
        assert result.metadata["loop_mode"] == "count"
        assert result.metadata["loop_count"] == 3

    def test_count_loop_done_output(self) -> None:
        """Test count-based loop records the done output in metadata."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 5})
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="AfterLoop",
                edge_type="CONNECTION",
                output_index=0,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        assert result.metadata["done_next"] == "AfterLoop"

    def test_count_loop_inline_processor(self) -> None:
        """Test count-based loop has INLINE processor with placeholder."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 5})
        result = self.translator.translate(node, _context())
        state = result.states["Loop"]
        processor = state.item_processor
        assert processor.processor_config.mode == "INLINE"
        assert processor.start_at == "Loop_Item"
        assert "Loop_Item" in processor.states

    def test_default_mode_is_count(self) -> None:
        """Test that omitting loopMode defaults to count-based."""
        node = _loop_node("Loop")
        result = self.translator.translate(node, _context())
        state = result.states["Loop"]
        assert state.type == "Map"
        assert result.metadata["loop_mode"] == "count"


class TestLoopNodeConditionBased:
    """Tests for condition-based Loop node translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()

    def test_condition_loop_produces_choice_state(self) -> None:
        """Test condition-based loop produces a Choice state."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.x > 0"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["Loop"]
        assert state.type == "Choice"

    def test_condition_loop_choice_rule(self) -> None:
        """Test condition-based loop has correct choice rule."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.x > 0"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["Loop"]
        assert len(state.choices) == 1
        assert state.choices[0].condition == "$states.input.x > 0"
        assert state.choices[0].next == "LoopBody"

    def test_condition_loop_default_exit(self) -> None:
        """Test condition-based loop exits to done_next state."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.x > 0"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="AfterLoop",
                edge_type="CONNECTION",
                output_index=0,
            ),
            DependencyEdge(
                from_node="Loop",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["Loop"]
        assert state.default == "AfterLoop"

    def test_condition_loop_exit_placeholder_when_no_done_next(self) -> None:
        """Test condition-based loop creates exit placeholder when no done_next."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.x > 0"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        assert "Loop_Exit" in result.states
        exit_state = result.states["Loop_Exit"]
        assert exit_state.type == "Pass"
        assert exit_state.end is True

    def test_condition_loop_metadata(self) -> None:
        """Test condition-based loop sets correct metadata."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.x > 0"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="LoopBody",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        assert result.metadata["loop_node"] is True
        assert result.metadata["loop_mode"] == "condition"
        assert result.metadata["condition"] == "$states.input.x > 0"
        assert result.metadata["loop_body"] == "LoopBody"

    def test_condition_loop_default_condition(self) -> None:
        """Test condition-based loop defaults condition to 'true'."""
        node = _loop_node("Loop", params={"loopMode": "condition"})
        result = self.translator.translate(node, _context())
        assert result.metadata["condition"] == "true"


class TestLoopNodeBodyDetection:
    """Tests for loop body detection from the dependency graph."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()

    def test_count_loop_body_output_index(self) -> None:
        """Test count-based loop detects body via metadata for post-processing."""
        node = _loop_node("Loop", params={"loopMode": "count", "loopCount": 3})
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="AfterLoop",
                edge_type="CONNECTION",
                output_index=0,
            ),
            DependencyEdge(
                from_node="Loop",
                to_node="ProcessItem",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        assert result.metadata["done_next"] == "AfterLoop"

    def test_condition_loop_body_from_graph(self) -> None:
        """Test condition-based loop identifies body from dependency graph."""
        node = _loop_node(
            "Loop",
            params={"loopMode": "condition", "condition": "$states.input.count < 10"},
        )
        edges = [
            DependencyEdge(
                from_node="Loop",
                to_node="Done",
                edge_type="CONNECTION",
                output_index=0,
            ),
            DependencyEdge(
                from_node="Loop",
                to_node="Increment",
                edge_type="CONNECTION",
                output_index=1,
            ),
        ]
        result = self.translator.translate(node, _context(edges))
        state = result.states["Loop"]
        assert state.choices[0].next == "Increment"
        assert state.default == "Done"
        assert result.metadata["loop_body"] == "Increment"
        assert result.metadata["done_next"] == "Done"
