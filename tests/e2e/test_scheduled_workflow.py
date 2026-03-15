"""End-to-end tests for a workflow with a Schedule Trigger.

Validates that the schedule trigger produces an EventBridge rule artifact,
Lambda invoke and SQS states appear in the ASL definition, and the CDK
stack references the schedule infrastructure.
"""

from __future__ import annotations

import ast
import json

from tests.e2e.conftest import PipelineResult


class TestScheduledPipelineOutput:
    """Verify the pipeline output for a scheduled workflow."""

    def test_asl_definition_is_valid(
        self, scheduled_result: PipelineResult
    ) -> None:
        """ASL JSON must be structurally valid."""
        asl_path = (
            scheduled_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        assert asl_path.exists(), "ASL definition file not found"
        asl = json.loads(asl_path.read_text())
        assert "StartAt" in asl
        assert "States" in asl
        assert len(asl["States"]) > 0

    def test_cdk_python_is_syntactically_valid(
        self, scheduled_result: PipelineResult
    ) -> None:
        """All generated .py files must parse without syntax errors."""
        cdk_dir = scheduled_result.output_dir / "cdk"
        py_files = list(cdk_dir.rglob("*.py"))
        assert len(py_files) > 0
        for py_file in py_files:
            source = py_file.read_text()
            ast.parse(source, filename=str(py_file))

    def test_trigger_artifact_is_schedule(
        self, scheduled_result: PipelineResult
    ) -> None:
        """The trigger artifact must be an EventBridge schedule."""
        triggers = scheduled_result.boundary_output.trigger_artifacts
        assert len(triggers) > 0, "No trigger artifacts produced"
        schedule_triggers = [
            t for t in triggers if t.trigger_type == "EVENTBRIDGE_SCHEDULE"
        ]
        assert len(schedule_triggers) > 0, (
            f"No EVENTBRIDGE_SCHEDULE trigger found. Types: "
            f"{[t.trigger_type for t in triggers]}"
        )

    def test_sqs_state_in_asl(
        self, scheduled_result: PipelineResult
    ) -> None:
        """The SQS SendMessage node must appear as a state in the ASL."""
        asl_path = (
            scheduled_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        asl = json.loads(asl_path.read_text())
        assert "SendToSQS" in asl["States"], (
            f"SendToSQS state not found. States: {list(asl['States'].keys())}"
        )

    def test_lambda_invoke_state_in_asl(
        self, scheduled_result: PipelineResult
    ) -> None:
        """The Lambda invoke node must appear as a state in the ASL."""
        asl_path = (
            scheduled_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        asl = json.loads(asl_path.read_text())
        assert "InvokeLambda" in asl["States"], (
            f"InvokeLambda state not found. States: {list(asl['States'].keys())}"
        )

    def test_cdk_app_structure(
        self, scheduled_result: PipelineResult
    ) -> None:
        """CDK application must include required files."""
        cdk_dir = scheduled_result.output_dir / "cdk"
        assert (cdk_dir / "app.py").exists()
        assert (cdk_dir / "cdk.json").exists()
        assert (cdk_dir / "pyproject.toml").exists()

    def test_iam_policy_references_sqs(
        self, scheduled_result: PipelineResult
    ) -> None:
        """IAM policy must reference SQS permissions."""
        stack_path = (
            scheduled_result.output_dir
            / "cdk"
            / "stacks"
            / "workflow_stack.py"
        )
        assert stack_path.exists()
        stack_code = stack_path.read_text()
        assert "sqs" in stack_code.lower(), (
            "Stack code does not reference SQS"
        )


class TestScheduledBoundaryIntegrity:
    """Verify data integrity across adapter boundaries for scheduled workflows."""

    def test_all_nodes_classified(
        self, scheduled_result: PipelineResult
    ) -> None:
        """Every workflow node must appear in the analyzer report."""
        workflow_node_names = {
            n["name"] for n in scheduled_result.workflow_data["nodes"]
        }
        report_node_names = {
            cn.node.name
            for cn in scheduled_result.report.classified_nodes
        }
        assert workflow_node_names == report_node_names

    def test_adapter_preserves_all_nodes(
        self, scheduled_result: PipelineResult
    ) -> None:
        """The analyzer-to-translator adapter must preserve all nodes."""
        report_names = {
            cn.node.name
            for cn in scheduled_result.report.classified_nodes
        }
        analysis_names = {
            cn.node.name
            for cn in scheduled_result.analysis.classified_nodes
        }
        assert report_names == analysis_names

    def test_schedule_trigger_classified_correctly(
        self, scheduled_result: PipelineResult
    ) -> None:
        """The schedule trigger must be classified as TRIGGER."""
        trigger_nodes = [
            cn
            for cn in scheduled_result.analysis.classified_nodes
            if cn.node.name == "ScheduleTrigger"
        ]
        assert len(trigger_nodes) == 1
        assert trigger_nodes[0].classification == "TRIGGER"

    def test_asl_states_cover_non_trigger_nodes(
        self, scheduled_result: PipelineResult
    ) -> None:
        """Every non-trigger node from the analysis must appear as an ASL state."""
        asl_path = (
            scheduled_result.output_dir
            / "statemachine"
            / "definition.asl.json"
        )
        asl = json.loads(asl_path.read_text())
        state_names = set(asl["States"].keys())

        non_trigger_names = {
            cn.node.name
            for cn in scheduled_result.analysis.classified_nodes
            if cn.classification != "TRIGGER"
        }
        for name in non_trigger_names:
            assert name in state_names, (
                f"Node '{name}' not found in ASL states: {state_names}"
            )

    def test_no_pydantic_validation_errors(
        self, scheduled_result: PipelineResult
    ) -> None:
        """Pipeline completes without Pydantic ValidationError at any boundary."""
        assert scheduled_result.output_dir.exists()
