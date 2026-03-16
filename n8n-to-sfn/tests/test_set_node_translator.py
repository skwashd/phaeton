"""Tests for Set/Edit Fields node translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.set_node import SetNodeTranslator


def _set_node(
    name: str = "Set Fields",
    params: dict | None = None,
) -> ClassifiedNode:
    """Create a Set classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type="n8n-nodes-base.set",
            type_version=3,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


def _context() -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name="test-workflow",
    )


class TestSetNodeCanTranslate:
    """Tests for can_translate routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_can_translate_set_node(self) -> None:
        """Test can_translate returns True for set nodes."""
        node = _set_node()
        assert self.translator.can_translate(node)

    def test_cannot_translate_other_node(self) -> None:
        """Test can_translate returns False for non-set nodes."""
        node = ClassifiedNode(
            node=N8nNode(  # type: ignore[missing-argument]
                id="x", name="x", type="n8n-nodes-base.httpRequest",
                type_version=1, position=[0, 0],  # type: ignore[unknown-argument]
            ),
            classification=NodeClassification.PICOFUN_API,
        )
        assert not self.translator.can_translate(node)


class TestManualModeStringFields:
    """Tests for manual mode with string field assignments."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_single_string_field(self) -> None:
        """Test single string field assignment produces Pass with Output."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "greeting", "value": "hello", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        assert "Set Fields" in result.states
        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Pass"
        assert "Output" in serialized
        assert "'greeting': 'hello'" in serialized["Output"]

    def test_multiple_fields(self) -> None:
        """Test multiple field assignments are all present in Output."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "first", "value": "a", "type": "string"},
                    {"name": "second", "value": "b", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        output = serialized["Output"]
        assert "'first': 'a'" in output
        assert "'second': 'b'" in output


class TestManualModeNumericFields:
    """Tests for manual mode with number field assignments."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_number_field(self) -> None:
        """Test number field produces numeric literal in JSONata."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "count", "value": 42, "type": "number"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "'count': 42" in serialized["Output"]


class TestManualModeBooleanFields:
    """Tests for manual mode with boolean field assignments."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_boolean_true(self) -> None:
        """Test boolean true field produces JSONata true literal."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "active", "value": True, "type": "boolean"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "'active': true" in serialized["Output"]

    def test_boolean_false(self) -> None:
        """Test boolean false field produces JSONata false literal."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "active", "value": False, "type": "boolean"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "'active': false" in serialized["Output"]


class TestManualModeExpressions:
    """Tests for manual mode with n8n expression references."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_expression_field(self) -> None:
        """Test n8n expression is translated to JSONata with $states.input."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "name", "value": "={{ $json.userName }}", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "$states.input.userName" in serialized["Output"]

    def test_expression_with_method_call(self) -> None:
        """Test n8n expression with method call translates correctly."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "upper", "value": "={{ $json.name.toUpperCase() }}", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "$uppercase($states.input.name)" in serialized["Output"]


class TestKeepOnlySetMode:
    """Tests for keepOnlySet vs merge behaviour."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_default_merges_with_input(self) -> None:
        """Test that default mode merges fields into $states.input."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "field1", "value": "val", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "$merge" in serialized["Output"]
        assert "$states.input" in serialized["Output"]

    def test_keep_only_set_excludes_input(self) -> None:
        """Test keepOnlySet outputs only assigned fields without $merge."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "field1", "value": "val", "type": "string"},
                ],
            },
            "options": {"keepOnlySet": True},
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "$merge" not in serialized["Output"]
        assert "'field1': 'val'" in serialized["Output"]


class TestRawMode:
    """Tests for raw JSON expression mode."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_raw_mode_literal_json(self) -> None:
        """Test raw mode with literal JSON passes through."""
        node = _set_node(params={
            "mode": "raw",
            "jsonOutput": '{"key": "value"}',
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Pass"
        assert '{"key": "value"}' in serialized["Output"]

    def test_raw_mode_expression(self) -> None:
        """Test raw mode with n8n expression translates correctly."""
        node = _set_node(params={
            "mode": "raw",
            "jsonOutput": "={{ $json.data }}",
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "$states.input.data" in serialized["Output"]

    def test_raw_mode_empty_warns(self) -> None:
        """Test raw mode with empty jsonOutput produces a warning."""
        node = _set_node(params={
            "mode": "raw",
            "jsonOutput": "",
        })
        result = self.translator.translate(node, _context())

        assert len(result.warnings) > 0
        assert "empty" in result.warnings[0].lower()


class TestNoLegacyJsonPath:
    """Tests that generated ASL uses JSONata and not legacy JSONPath constructs."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_no_result_selector(self) -> None:
        """Test that generated state does not use ResultSelector."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "x", "value": "1", "type": "number"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert "ResultSelector" not in serialized
        assert "ResultPath" not in serialized

    def test_uses_jsonata_output(self) -> None:
        """Test that generated state uses JSONata Output expression."""
        node = _set_node(params={
            "mode": "manual",
            "assignments": {
                "assignments": [
                    {"name": "x", "value": "hello", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Pass"
        assert "Output" in serialized
        assert serialized["Output"].startswith("{%")
        assert serialized["Output"].endswith("%}")


class TestDefaultMode:
    """Tests for default mode when mode parameter is absent."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = SetNodeTranslator()

    def test_defaults_to_manual(self) -> None:
        """Test that missing mode defaults to manual."""
        node = _set_node(params={
            "assignments": {
                "assignments": [
                    {"name": "x", "value": "hello", "type": "string"},
                ],
            },
        })
        result = self.translator.translate(node, _context())

        state = result.states["Set Fields"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Pass"
        assert "'x': 'hello'" in serialized["Output"]
