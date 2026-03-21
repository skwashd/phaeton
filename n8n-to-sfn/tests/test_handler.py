"""Tests for the Lambda handler entry point."""

from __future__ import annotations

import os
from unittest import mock

from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)
from phaeton_models.translator_output import TranslationOutput

from n8n_to_sfn.handler import create_default_engine, handler
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.picofun import PicoFunTranslator


def _node(
    name: str,
    node_type: str = "n8n-nodes-base.set",
    classification: NodeClassification = NodeClassification.FLOW_CONTROL,
) -> ClassifiedNode:
    """Create a classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type=node_type,
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
        ),
        classification=classification,
    )


def _valid_payload() -> dict:
    """Return a minimal valid WorkflowAnalysis payload."""
    analysis = WorkflowAnalysis(
        classified_nodes=[
            _node("SetFields", classification=NodeClassification.FLOW_CONTROL),
            _node("End", classification=NodeClassification.FLOW_CONTROL),
        ],
        dependency_edges=[
            DependencyEdge(from_node="SetFields", to_node="End", edge_type="CONNECTION"),
        ],
    )
    return analysis.model_dump(mode="json")


class TestHandler:
    """Tests for the Lambda handler function."""

    def test_valid_payload_returns_translation_output(self) -> None:
        """Handler with a valid payload returns a TranslationOutput-conforming response."""
        result = handler(_valid_payload(), None)

        assert "error" not in result
        output = TranslationOutput.model_validate(result)
        assert output.state_machine is not None
        assert len(output.state_machine["States"]) >= 1

    def test_invalid_payload_returns_validation_error(self) -> None:
        """Handler with an invalid payload returns a structured 400 error."""
        result = handler({"bad": "data"}, None)

        assert "error" in result
        assert result["error"]["status_code"] == 400
        assert result["error"]["error_type"] == "ValidationError"
        assert "message" in result["error"]
        assert result["error"]["details"] is not None

    def test_empty_payload_returns_validation_error(self) -> None:
        """Handler with an empty payload returns a structured error."""
        result = handler({}, None)

        assert "error" in result
        assert result["error"]["status_code"] == 400

    def test_response_conforms_to_translation_output(self) -> None:
        """Successful response can be round-tripped through TranslationOutput."""
        result = handler(_valid_payload(), None)
        assert "error" not in result

        output = TranslationOutput.model_validate(result)
        re_dumped = output.model_dump(mode="json")
        assert "state_machine" in re_dumped
        assert "lambda_artifacts" in re_dumped
        assert "conversion_report" in re_dumped

    def test_conversion_report_present(self) -> None:
        """Successful response includes a conversion report."""
        result = handler(_valid_payload(), None)

        assert "error" not in result
        report = result["conversion_report"]
        assert "total_nodes" in report
        assert "translated_nodes" in report
        assert "warning_count" in report

    def test_workflow_with_unsupported_node(self) -> None:
        """Workflow with translatable and untranslatable nodes produces warnings."""
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("Good", classification=NodeClassification.FLOW_CONTROL),
                _node(
                    "Unknown",
                    node_type="n8n-nodes-base.ftp",
                    classification=NodeClassification.UNSUPPORTED,
                ),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="Good", to_node="Unknown", edge_type="CONNECTION"
                ),
            ],
        )
        result = handler(analysis.model_dump(mode="json"), None)

        assert "error" not in result
        assert len(result["warnings"]) > 0
        assert any("unsupported" in w.lower() or "Unsupported" in w for w in result["warnings"])


class TestCreateDefaultEngine:
    """Tests for the create_default_engine factory."""

    def test_creates_engine_with_all_translators(self) -> None:
        """Factory creates an engine with thirteen translators."""
        engine = create_default_engine()
        assert len(engine._translators) == 13

    def test_engine_can_translate_basic_workflow(self) -> None:
        """Engine from factory can translate a minimal workflow."""
        engine = create_default_engine()
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        output = engine.translate(analysis)
        assert output.state_machine is not None

    def test_no_spec_bucket_gives_empty_spec_directory(self) -> None:
        """Without PHAETON_SPEC_BUCKET, engine has empty spec_directory."""
        env = {k: v for k, v in os.environ.items() if k != "PHAETON_SPEC_BUCKET"}
        with mock.patch.dict(os.environ, env, clear=True):
            engine = create_default_engine()
        assert engine._spec_directory == ""

    def test_no_spec_bucket_picofun_has_no_bridge(self) -> None:
        """Without PHAETON_SPEC_BUCKET, PicoFunTranslator has no bridge."""
        env = {k: v for k, v in os.environ.items() if k != "PHAETON_SPEC_BUCKET"}
        with mock.patch.dict(os.environ, env, clear=True):
            engine = create_default_engine()
        picofun = [t for t in engine._translators if isinstance(t, PicoFunTranslator)]
        assert len(picofun) == 1
        assert picofun[0]._bridge is None

    def test_spec_bucket_sets_spec_directory(self) -> None:
        """With PHAETON_SPEC_BUCKET set, engine has a non-empty spec_directory."""
        with mock.patch.dict(
            os.environ, {"PHAETON_SPEC_BUCKET": "my-bucket"}, clear=False
        ):
            engine = create_default_engine()
        assert engine._spec_directory != ""
        assert "phaeton-specs-" in engine._spec_directory

    def test_spec_bucket_picofun_has_bridge(self) -> None:
        """With PHAETON_SPEC_BUCKET set, PicoFunTranslator has a bridge."""
        with mock.patch.dict(
            os.environ, {"PHAETON_SPEC_BUCKET": "my-bucket"}, clear=False
        ):
            engine = create_default_engine()
        picofun = [t for t in engine._translators if isinstance(t, PicoFunTranslator)]
        assert len(picofun) == 1
        assert picofun[0]._bridge is not None

    def test_spec_prefix_defaults_to_specs_slash(self) -> None:
        """PHAETON_SPEC_PREFIX defaults to 'specs/' when not set."""
        env = {k: v for k, v in os.environ.items() if k != "PHAETON_SPEC_PREFIX"}
        env["PHAETON_SPEC_BUCKET"] = "my-bucket"
        with mock.patch.dict(os.environ, env, clear=True):
            engine = create_default_engine()
        assert engine._spec_directory != ""
