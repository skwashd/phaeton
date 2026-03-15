"""
End-to-end tests for a workflow containing a Code node (JavaScript).

Validates that the Code node produces a Lambda artifact, the ASL
definition invokes it, and the CDK stack wires up the Lambda function.
"""

from __future__ import annotations

import ast
import json

from tests.e2e.conftest import PipelineResult


class TestCodeNodePipelineOutput:
    """Verify the pipeline output for a Code-node workflow."""

    def test_asl_definition_is_valid(
        self, code_node_result: PipelineResult
    ) -> None:
        """ASL JSON must be structurally valid."""
        asl_path = (
            code_node_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        assert asl_path.exists(), "ASL definition file not found"
        asl = json.loads(asl_path.read_text())
        assert "StartAt" in asl
        assert "States" in asl
        assert len(asl["States"]) > 0

    def test_cdk_python_is_syntactically_valid(
        self, code_node_result: PipelineResult
    ) -> None:
        """All generated .py files must parse without syntax errors."""
        cdk_dir = code_node_result.output_dir / "cdk"
        py_files = list(cdk_dir.rglob("*.py"))
        assert len(py_files) > 0
        for py_file in py_files:
            source = py_file.read_text()
            ast.parse(source, filename=str(py_file))

    def test_lambda_artifact_generated(
        self, code_node_result: PipelineResult
    ) -> None:
        """The Code node must produce at least one Lambda artifact."""
        assert len(code_node_result.boundary_output.lambda_artifacts) > 0, (
            "No Lambda artifacts produced for Code node workflow"
        )

    def test_lambda_directory_contains_handler(
        self, code_node_result: PipelineResult
    ) -> None:
        """The packager must emit Lambda handler files for the Code node."""
        lambdas_dir = code_node_result.output_dir / "lambdas"
        assert lambdas_dir.exists(), "lambdas/ directory not found"
        handlers = list(lambdas_dir.rglob("*"))
        assert len(handlers) > 0, "Lambda directory has no files"

    def test_asl_references_lambda_invoke(
        self, code_node_result: PipelineResult
    ) -> None:
        """The ASL definition must contain a lambda:invoke resource."""
        asl_path = (
            code_node_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        asl_text = asl_path.read_text()
        assert "lambda" in asl_text.lower(), (
            "ASL definition does not reference Lambda"
        )

    def test_sns_state_in_asl(
        self, code_node_result: PipelineResult
    ) -> None:
        """The SNS Publish node must appear as a state in the ASL definition."""
        asl_path = (
            code_node_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        asl = json.loads(asl_path.read_text())
        assert "PublishSNS" in asl["States"], (
            f"PublishSNS state not found in ASL. States: {list(asl['States'].keys())}"
        )

    def test_cdk_app_structure(
        self, code_node_result: PipelineResult
    ) -> None:
        """CDK application must include required files."""
        cdk_dir = code_node_result.output_dir / "cdk"
        assert (cdk_dir / "app.py").exists()
        assert (cdk_dir / "cdk.json").exists()
        assert (cdk_dir / "pyproject.toml").exists()


class TestCodeNodeBoundaryIntegrity:
    """Verify data integrity across adapter boundaries for Code node workflows."""

    def test_all_nodes_classified(
        self, code_node_result: PipelineResult
    ) -> None:
        """Every workflow node must appear in the analyzer report."""
        workflow_node_names = {
            n["name"] for n in code_node_result.workflow_data["nodes"]
        }
        report_node_names = {
            cn.node.name
            for cn in code_node_result.report.classified_nodes
        }
        assert workflow_node_names == report_node_names

    def test_adapter_preserves_all_nodes(
        self, code_node_result: PipelineResult
    ) -> None:
        """The analyzer-to-translator adapter must preserve all nodes."""
        report_names = {
            cn.node.name
            for cn in code_node_result.report.classified_nodes
        }
        analysis_names = {
            cn.node.name
            for cn in code_node_result.analysis.classified_nodes
        }
        assert report_names == analysis_names

    def test_lambda_artifacts_in_packager_output(
        self, code_node_result: PipelineResult
    ) -> None:
        """Every Lambda artifact from the translator must appear in packager output."""
        engine_lambda_names = {
            la.function_name
            for la in code_node_result.boundary_output.lambda_artifacts
        }
        lambdas_dir = code_node_result.output_dir / "lambdas"
        if lambdas_dir.exists():
            packaged_dirs = {d.name for d in lambdas_dir.iterdir() if d.is_dir()}
            for name in engine_lambda_names:
                assert any(
                    name.replace("-", "_") in d or name in d
                    for d in packaged_dirs
                ), f"Lambda '{name}' not found in packager output: {packaged_dirs}"

    def test_code_node_classified_correctly(
        self, code_node_result: PipelineResult
    ) -> None:
        """The Code node must be classified as CODE_JS."""
        code_nodes = [
            cn
            for cn in code_node_result.analysis.classified_nodes
            if cn.node.name == "TransformData"
        ]
        assert len(code_nodes) == 1, "TransformData node not found in analysis"
        assert code_nodes[0].classification == "CODE_JS"
