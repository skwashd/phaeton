"""Tests for code node translator."""

from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import LambdaRuntime, TranslationContext
from n8n_to_sfn.translators.code_node import CodeNodeTranslator


def _code_node(name, classification, params):
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.code",
            type_version=1,
            position=[0, 0],
            parameters=params,
        ),
        classification=classification,
    )


def _context():
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[])
    )


class TestCodeNodeTranslator:
    def setup_method(self):
        self.translator = CodeNodeTranslator()

    def test_can_translate_js(self):
        node = _code_node("JS", NodeClassification.CODE_JS, {})
        assert self.translator.can_translate(node)

    def test_can_translate_python(self):
        node = _code_node("Py", NodeClassification.CODE_PYTHON, {})
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self):
        node = _code_node("X", NodeClassification.FLOW_CONTROL, {})
        assert not self.translator.can_translate(node)

    def test_js_produces_task_and_artifact(self):
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

    def test_python_produces_task_and_artifact(self):
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

    def test_js_detects_require_deps(self):
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

    def test_python_detects_import_deps(self):
        node = _code_node(
            "PyDeps",
            NodeClassification.CODE_PYTHON,
            {"pythonCode": "import pandas\nfrom numpy import array"},
        )
        result = self.translator.translate(node, _context())
        deps = result.lambda_artifacts[0].dependencies
        assert "pandas" in deps
        assert "numpy" in deps

    def test_name_sanitization(self):
        node = _code_node(
            "My Cool Node!",
            NodeClassification.CODE_JS,
            {"jsCode": "const result = [];"},
        )
        result = self.translator.translate(node, _context())
        artifact = result.lambda_artifacts[0]
        assert artifact.function_name == "code_node_my_cool_node_"
        assert " " not in artifact.function_name

    def test_task_state_has_lambda_resource(self):
        node = _code_node("T", NodeClassification.CODE_JS, {"jsCode": ""})
        result = self.translator.translate(node, _context())
        state = result.states["T"]
        assert state.resource == "arn:aws:states:::lambda:invoke"

    def test_warning_about_globals(self):
        node = _code_node("W", NodeClassification.CODE_JS, {"jsCode": ""})
        result = self.translator.translate(node, _context())
        assert any("review" in w.lower() or "n8n" in w.lower() for w in result.warnings)
