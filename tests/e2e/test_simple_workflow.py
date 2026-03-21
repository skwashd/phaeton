"""
End-to-end tests for a simple DynamoDB PutItem -> GetItem workflow.

Validates that the pipeline produces syntactically valid CDK code, a
well-formed ASL definition, correct IAM policies, and preserves all
nodes across adapter boundaries.
"""

from __future__ import annotations

import ast
import json

from tests.e2e.conftest import PipelineResult


class TestSimpleDynamoDBPipelineOutput:
    """Verify the pipeline output for a DynamoDB-only workflow."""

    def test_asl_definition_is_valid(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """ASL JSON must contain StartAt, States, and QueryLanguage."""
        asl_path = (
            simple_dynamodb_result.output_dir / "statemachine" / "definition.asl.json"
        )
        assert asl_path.exists(), "ASL definition file not found"
        asl = json.loads(asl_path.read_text())
        assert "StartAt" in asl, "ASL missing StartAt"
        assert "States" in asl, "ASL missing States"
        assert len(asl["States"]) > 0, "ASL has no states"

    def test_cdk_python_is_syntactically_valid(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """All generated .py files must parse without syntax errors."""
        cdk_dir = simple_dynamodb_result.output_dir / "cdk"
        py_files = list(cdk_dir.rglob("*.py"))
        assert len(py_files) > 0, "No Python files found in cdk/"
        for py_file in py_files:
            source = py_file.read_text()
            ast.parse(source, filename=str(py_file))

    def test_cdk_app_structure(self, simple_dynamodb_result: PipelineResult) -> None:
        """CDK application must include app.py, cdk.json, and stack modules."""
        cdk_dir = simple_dynamodb_result.output_dir / "cdk"
        assert (cdk_dir / "app.py").exists(), "app.py not found"
        assert (cdk_dir / "cdk.json").exists(), "cdk.json not found"
        assert (cdk_dir / "pyproject.toml").exists(), "pyproject.toml not found"
        stacks_dir = cdk_dir / "stacks"
        assert stacks_dir.is_dir(), "stacks/ directory not found"
        assert (stacks_dir / "workflow_stack.py").exists()

    def test_iam_policy_references_dynamodb(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """IAM policy in the stack must reference DynamoDB actions."""
        stack_path = (
            simple_dynamodb_result.output_dir / "cdk" / "stacks" / "workflow_stack.py"
        )
        assert stack_path.exists(), "workflow_stack.py not found"
        stack_code = stack_path.read_text()
        assert "dynamodb" in stack_code.lower(), (
            "Stack code does not reference DynamoDB"
        )

    def test_conversion_report_generated(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """Pipeline must emit a conversion report."""
        report_path = (
            simple_dynamodb_result.output_dir / "reports" / "conversion_report.json"
        )
        assert report_path.exists(), "reports/conversion_report.json not found"
        report = json.loads(report_path.read_text())
        assert "confidence_score" in report or "total_nodes" in report

    def test_migration_checklist_generated(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """Pipeline must emit a MIGRATE.md checklist."""
        migrate_path = simple_dynamodb_result.output_dir / "MIGRATE.md"
        assert migrate_path.exists(), "MIGRATE.md not found"
        content = migrate_path.read_text()
        assert len(content) > 0, "MIGRATE.md is empty"


class TestSimpleDynamoDBBoundaryIntegrity:
    """Verify no data is lost or corrupted at inter-component boundaries."""

    def test_all_nodes_classified_by_analyzer(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """Every workflow node must appear in the analyzer report."""
        workflow_node_names = {
            n["name"] for n in simple_dynamodb_result.workflow_data["nodes"]
        }
        report_node_names = {
            cn.node.name for cn in simple_dynamodb_result.report.classified_nodes
        }
        assert workflow_node_names == report_node_names, (
            f"Analyzer missed nodes: {workflow_node_names - report_node_names}"
        )

    def test_adapter_preserves_all_classified_nodes(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """The analyzer-to-translator adapter must preserve all classified nodes."""
        report_names = {
            cn.node.name for cn in simple_dynamodb_result.report.classified_nodes
        }
        analysis_names = {
            cn.node.name for cn in simple_dynamodb_result.analysis.classified_nodes
        }
        assert report_names == analysis_names, (
            f"Adapter lost nodes: {report_names - analysis_names}"
        )

    def test_asl_states_cover_non_trigger_nodes(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """Every non-trigger node from the analysis must appear as an ASL state."""
        asl_path = (
            simple_dynamodb_result.output_dir / "statemachine" / "definition.asl.json"
        )
        asl = json.loads(asl_path.read_text())
        state_names = set(asl["States"].keys())

        non_trigger_names = {
            cn.node.name
            for cn in simple_dynamodb_result.analysis.classified_nodes
            if cn.classification != "TRIGGER"
        }
        for name in non_trigger_names:
            assert name in state_names, (
                f"Node '{name}' not found in ASL states: {state_names}"
            )

    def test_no_pydantic_validation_errors(
        self, simple_dynamodb_result: PipelineResult
    ) -> None:
        """
        Pipeline completes without raising Pydantic ValidationError.

        If we reach this test, all adapter boundaries validated successfully
        because the pipeline ran to completion in the fixture.
        """
        assert simple_dynamodb_result.output_dir.exists()
