"""Tests for code node translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import LambdaRuntime, TranslationContext
from n8n_to_sfn.translators.code_node import CodeNodeTranslator


def _code_node(
    name: str, classification: NodeClassification, params: dict
) -> ClassifiedNode:
    """Create a code classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type="n8n-nodes-base.code",
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params,
        ),
        classification=classification,
    )


def _context() -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[])
    )


class TestCodeNodeTranslator:
    """Tests for CodeNodeTranslator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = CodeNodeTranslator()

    def test_can_translate_js(self) -> None:
        """Test can_translate returns True for JS code nodes."""
        node = _code_node("JS", NodeClassification.CODE_JS, {})
        assert self.translator.can_translate(node)

    def test_can_translate_python(self) -> None:
        """Test can_translate returns True for Python code nodes."""
        node = _code_node("Py", NodeClassification.CODE_PYTHON, {})
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-code nodes."""
        node = _code_node("X", NodeClassification.FLOW_CONTROL, {})
        assert not self.translator.can_translate(node)

    def test_js_produces_task_and_artifact(self) -> None:
        """Test JS code node produces task state and lambda artifact."""
        node = _code_node(
            "My JS Code",
            NodeClassification.CODE_JS,
            {"jsCode": "const result = items.map(i => i.json);"},
        )
        result = self.translator.translate(node, _context())
        assert "My JS Code" in result.states
        assert len(result.lambda_artifacts) == 1
        artifact = result.lambda_artifacts[0]
        assert artifact.runtime == LambdaRuntime.NODEJS
        assert "My JS Code" in artifact.handler_code
        assert "const result = items.map(i => i.json);" in artifact.handler_code

    def test_python_produces_task_and_artifact(self) -> None:
        """Test Python code node produces task state and lambda artifact."""
        node = _code_node(
            "My Py Code",
            NodeClassification.CODE_PYTHON,
            {"pythonCode": "result = [item for item in items]"},
        )
        result = self.translator.translate(node, _context())
        assert "My Py Code" in result.states
        assert len(result.lambda_artifacts) == 1
        artifact = result.lambda_artifacts[0]
        assert artifact.runtime == LambdaRuntime.PYTHON
        assert "result = [item for item in items]" in artifact.handler_code

    def test_js_detects_require_deps(self) -> None:
        """Test JS code node detects require dependencies."""
        node = _code_node(
            "Deps",
            NodeClassification.CODE_JS,
            {"jsCode": "const axios = require('axios');\nconst _ = require('lodash');"},
        )
        result = self.translator.translate(node, _context())
        deps = result.lambda_artifacts[0].dependencies
        assert "axios" in deps
        assert "lodash" in deps
        assert "luxon" in deps  # Always included

    def test_python_detects_import_deps(self) -> None:
        """Test Python code node detects import dependencies."""
        node = _code_node(
            "PyDeps",
            NodeClassification.CODE_PYTHON,
            {"pythonCode": "import pandas\nfrom numpy import array"},
        )
        result = self.translator.translate(node, _context())
        deps = result.lambda_artifacts[0].dependencies
        assert "pandas" in deps
        assert "numpy" in deps

    def test_name_sanitization(self) -> None:
        """Test function name is sanitized from node name."""
        node = _code_node(
            "My Cool Node!",
            NodeClassification.CODE_JS,
            {"jsCode": "const result = [];"},
        )
        result = self.translator.translate(node, _context())
        artifact = result.lambda_artifacts[0]
        assert artifact.function_name == "code_node_my_cool_node_"
        assert " " not in artifact.function_name

    def test_task_state_has_lambda_resource(self) -> None:
        """Test task state has lambda invoke resource."""
        node = _code_node("T", NodeClassification.CODE_JS, {"jsCode": ""})
        result = self.translator.translate(node, _context())
        state = result.states["T"]
        assert state.resource == "arn:aws:states:::lambda:invoke"

    def test_warning_about_globals(self) -> None:
        """Test warning about n8n globals is present."""
        node = _code_node("W", NodeClassification.CODE_JS, {"jsCode": ""})
        result = self.translator.translate(node, _context())
        assert any("review" in w.lower() or "n8n" in w.lower() for w in result.warnings)

    def test_js_input_all_shimmed(self) -> None:
        """Test JS code using $input.all() gets a compatibility shim."""
        node = _code_node(
            "InputAll",
            NodeClassification.CODE_JS,
            {"jsCode": "const data = $input.all();"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "const $input" in handler
        assert "all: () => items" in handler

    def test_js_json_shimmed(self) -> None:
        """Test JS code using $json gets mapped to event.items[0].json."""
        node = _code_node(
            "JsonRef",
            NodeClassification.CODE_JS,
            {"jsCode": "const val = $json.name;"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "const $json" in handler
        assert "items[0]" in handler

    def test_js_items_shimmed(self) -> None:
        """Test JS code using $items gets mapped to items."""
        node = _code_node(
            "ItemsRef",
            NodeClassification.CODE_JS,
            {"jsCode": "const all = $items;"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "const $items = items;" in handler

    def test_js_no_globals_no_shims(self) -> None:
        """Test JS code with no n8n globals produces no shims."""
        node = _code_node(
            "NoGlobals",
            NodeClassification.CODE_JS,
            {"jsCode": "const result = items.map(i => i.json);"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "const $input" not in handler
        assert "const $json" not in handler
        assert "const $items" not in handler

    def test_js_untranslatable_globals_warning(self) -> None:
        """Test that untranslatable globals emit warnings."""
        node = _code_node(
            "EnvRef",
            NodeClassification.CODE_JS,
            {"jsCode": "const key = $env.API_KEY;\nconst id = $execution.id;"},
        )
        result = self.translator.translate(node, _context())
        env_warnings = [w for w in result.warnings if "$env" in w]
        exec_warnings = [w for w in result.warnings if "$execution" in w]
        assert len(env_warnings) == 1
        assert len(exec_warnings) == 1
        assert "environment variable" in env_warnings[0].lower()

    def test_js_luxon_datetime_preamble(self) -> None:
        """Test that luxon DateTime usage adds require to preamble."""
        node = _code_node(
            "LuxonNode",
            NodeClassification.CODE_JS,
            {"jsCode": "const now = DateTime.now();"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "const { DateTime } = require('luxon');" in handler

    def test_js_no_datetime_no_preamble(self) -> None:
        """Test that luxon preamble is not added when DateTime is unused."""
        node = _code_node(
            "NoLuxon",
            NodeClassification.CODE_JS,
            {"jsCode": "const result = [];"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "require('luxon')" not in handler

    def test_python_input_shimmed(self) -> None:
        """Test Python code using $input gets a compatibility shim."""
        node = _code_node(
            "PyInput",
            NodeClassification.CODE_PYTHON,
            {"pythonCode": "data = $input.all()"},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "_N8nInput" in handler
        assert "_input.all()" in handler

    def test_python_json_shimmed(self) -> None:
        """Test Python code using $json gets shimmed and rewritten."""
        node = _code_node(
            "PyJson",
            NodeClassification.CODE_PYTHON,
            {"pythonCode": 'val = $json["name"]'},
        )
        result = self.translator.translate(node, _context())
        handler = result.lambda_artifacts[0].handler_code
        assert "_json" in handler
        assert '_json["name"]' in handler
