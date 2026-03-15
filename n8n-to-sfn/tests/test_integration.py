"""End-to-end integration tests.

Each test loads a fixture n8n workflow JSON, simulates Component 2 analysis,
runs the full translation engine, and validates the output ASL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from phaeton_models.translator import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.engine import TranslationEngine
from n8n_to_sfn.models.n8n import N8nNode, N8nWorkflow
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.code_node import CodeNodeTranslator
from n8n_to_sfn.translators.flow_control import FlowControlTranslator
from n8n_to_sfn.translators.triggers import TriggerTranslator

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers: simulate Component 2 analysis from raw n8n JSON
# ---------------------------------------------------------------------------

_TYPE_TO_CLASSIFICATION: dict[str, NodeClassification] = {
    "n8n-nodes-base.manualTrigger": NodeClassification.TRIGGER,
    "n8n-nodes-base.scheduleTrigger": NodeClassification.TRIGGER,
    "n8n-nodes-base.webhook": NodeClassification.TRIGGER,
    "n8n-nodes-base.awsS3": NodeClassification.AWS_NATIVE,
    "n8n-nodes-base.awsDynamoDB": NodeClassification.AWS_NATIVE,
    "n8n-nodes-base.awsSqs": NodeClassification.AWS_NATIVE,
    "n8n-nodes-base.awsSns": NodeClassification.AWS_NATIVE,
    "n8n-nodes-base.awsLambda": NodeClassification.AWS_NATIVE,
    "n8n-nodes-base.if": NodeClassification.FLOW_CONTROL,
    "n8n-nodes-base.switch": NodeClassification.FLOW_CONTROL,
    "n8n-nodes-base.wait": NodeClassification.FLOW_CONTROL,
    "n8n-nodes-base.noOp": NodeClassification.FLOW_CONTROL,
    "n8n-nodes-base.merge": NodeClassification.FLOW_CONTROL,
    "n8n-nodes-base.splitInBatches": NodeClassification.FLOW_CONTROL,
}


def _classify_node(node: N8nNode) -> NodeClassification:
    """Classify a node by its type, with code node language detection."""
    if node.type == "n8n-nodes-base.code":
        lang = node.parameters.get("language", "javaScript")
        if lang == "python":
            return NodeClassification.CODE_PYTHON
        return NodeClassification.CODE_JS
    return _TYPE_TO_CLASSIFICATION.get(node.type, NodeClassification.UNSUPPORTED)


def _load_and_analyze(fixture_name: str) -> tuple[WorkflowAnalysis, N8nWorkflow]:
    """Load a fixture JSON and produce a simulated WorkflowAnalysis."""
    path = FIXTURES / fixture_name
    raw = json.loads(path.read_text())
    workflow = N8nWorkflow.model_validate(raw)

    classified_nodes: list[ClassifiedNode] = []
    for node in workflow.nodes:
        classified_nodes.append(
            ClassifiedNode(
                node=node,
                classification=_classify_node(node),
            )
        )

    edges: list[DependencyEdge] = []
    for source_name, conn_map in workflow.connections.items():
        main_outputs = conn_map.get("main", [])
        for output_index, targets in enumerate(main_outputs):
            for target in targets:
                edges.append(
                    DependencyEdge(
                        from_node=source_name,
                        to_node=target.node,
                        edge_type="CONNECTION",
                        output_index=output_index,
                    )
                )

    analysis = WorkflowAnalysis(
        classified_nodes=classified_nodes,
        dependency_edges=edges,
        confidence_score=0.9,
    )
    return analysis, workflow


def _make_engine() -> TranslationEngine:
    """Create a fully-wired engine with all translators."""
    return TranslationEngine(
        translators=[
            TriggerTranslator(),
            FlowControlTranslator(),
            AWSServiceTranslator(),
            CodeNodeTranslator(),
        ],
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestSimpleS3Pipeline:
    """Tests for simple S3 pipeline workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, self.workflow = _load_and_analyze("simple_s3_pipeline.json")
        self.output = _make_engine().translate(self.analysis)

    def test_produces_state_machine(self) -> None:
        """Test workflow produces a state machine."""
        assert self.output.state_machine is not None
        assert self.output.state_machine.start_at is not None

    def test_contains_s3_states(self) -> None:
        """Test state machine contains S3 states."""
        states = self.output.state_machine.states
        assert "S3Get" in states
        assert "S3Put" in states

    def test_trigger_produces_artifact(self) -> None:
        """Test trigger produces artifact."""
        assert len(self.output.trigger_artifacts) == 1

    def test_s3get_has_correct_resource(self) -> None:
        """Test S3Get has correct resource."""
        state = self.output.state_machine.states["S3Get"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "getObject" in dumped["Resource"]

    def test_s3put_has_correct_resource(self) -> None:
        """Test S3Put has correct resource."""
        state = self.output.state_machine.states["S3Put"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "putObject" in dumped["Resource"]

    def test_valid_asl_json(self) -> None:
        """Test state machine produces valid ASL JSON."""
        dumped = self.output.state_machine.model_dump(by_alias=True)
        assert "StartAt" in dumped
        assert "States" in dumped
        assert "QueryLanguage" in dumped

    def test_conversion_report(self) -> None:
        """Test conversion report is correct."""
        report = self.output.conversion_report
        assert report["total_nodes"] == 3
        assert report["confidence_score"] == 0.9


class TestWebhookToDynamoDB:
    """Tests for webhook to DynamoDB workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("webhook_to_dynamodb.json")
        self.output = _make_engine().translate(self.analysis)

    def test_webhook_trigger_artifact(self) -> None:
        """Test webhook trigger artifact type."""
        assert len(self.output.trigger_artifacts) == 1
        from n8n_to_sfn.translators.base import TriggerType

        assert self.output.trigger_artifacts[0].trigger_type == TriggerType.LAMBDA_FURL

    def test_webhook_lambda_artifact(self) -> None:
        """Test webhook produces lambda artifact."""
        assert len(self.output.lambda_artifacts) >= 1
        handler = self.output.lambda_artifacts[0].handler_code
        assert "start_execution" in handler

    def test_dynamodb_state_present(self) -> None:
        """Test DynamoDB state is present."""
        assert "DDBPut" in self.output.state_machine.states

    def test_dynamodb_uses_put_item(self) -> None:
        """Test DynamoDB uses putItem resource."""
        state = self.output.state_machine.states["DDBPut"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "putItem" in dumped["Resource"]


class TestIfBranchWorkflow:
    """Tests for IF branch workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("if_branch_workflow.json")
        self.output = _make_engine().translate(self.analysis)

    def test_if_becomes_choice_state(self) -> None:
        """Test IF node becomes Choice state."""
        state = self.output.state_machine.states["IF"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert dumped["Type"] == "Choice"

    def test_both_branches_present(self) -> None:
        """Test both branches are present in state machine."""
        states = self.output.state_machine.states
        assert "SNSPublish" in states
        assert "SQSSend" in states

    def test_sns_uses_publish(self) -> None:
        """Test SNS uses publish resource."""
        state = self.output.state_machine.states["SNSPublish"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "publish" in dumped["Resource"]

    def test_sqs_uses_send_message(self) -> None:
        """Test SQS uses sendMessage resource."""
        state = self.output.state_machine.states["SQSSend"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "sendMessage" in dumped["Resource"]


class TestScheduleLambdaWorkflow:
    """Tests for schedule Lambda workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("schedule_lambda_workflow.json")
        self.output = _make_engine().translate(self.analysis)

    def test_schedule_trigger_artifact(self) -> None:
        """Test schedule trigger artifact type."""
        assert len(self.output.trigger_artifacts) == 1
        from n8n_to_sfn.translators.base import TriggerType

        assert (
            self.output.trigger_artifacts[0].trigger_type
            == TriggerType.EVENTBRIDGE_SCHEDULE
        )

    def test_lambda_state_present(self) -> None:
        """Test Lambda state is present."""
        assert "Lambda" in self.output.state_machine.states

    def test_lambda_uses_invoke(self) -> None:
        """Test Lambda uses invoke resource."""
        state = self.output.state_machine.states["Lambda"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "lambda:invoke" in dumped["Resource"]


class TestCodeNodeWorkflow:
    """Tests for code node workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("code_node_workflow.json")
        self.output = _make_engine().translate(self.analysis)

    def test_code_node_produces_lambda_artifact(self) -> None:
        """Test code node produces lambda artifact."""
        code_lambdas = [
            a for a in self.output.lambda_artifacts if "code_node" in a.function_name
        ]
        assert len(code_lambdas) == 1

    def test_code_node_state_present(self) -> None:
        """Test code node state is present."""
        assert "Code" in self.output.state_machine.states

    def test_code_handler_contains_user_code(self) -> None:
        """Test code handler contains user code."""
        code_lambdas = [
            a for a in self.output.lambda_artifacts if "code_node" in a.function_name
        ]
        assert "items.map" in code_lambdas[0].handler_code

    def test_s3_state_wired_after_code(self) -> None:
        """Test S3 state is wired after code node."""
        assert "S3Put" in self.output.state_machine.states


class TestWaitAndNotify:
    """Tests for wait and notify workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("wait_and_notify.json")
        self.output = _make_engine().translate(self.analysis)

    def test_wait_state_present(self) -> None:
        """Test Wait state is present."""
        state = self.output.state_machine.states["Wait"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert dumped["Type"] == "Wait"

    def test_wait_30_seconds(self) -> None:
        """Test Wait state has 30 seconds."""
        state = self.output.state_machine.states["Wait"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert dumped["Seconds"] == 30

    def test_sns_after_wait(self) -> None:
        """Test SNS state is after wait."""
        assert "SNSPublish" in self.output.state_machine.states


class TestErrorHandlingWorkflow:
    """Tests for error handling workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("error_handling_workflow.json")
        self.output = _make_engine().translate(self.analysis)

    def test_s3get_has_retry(self) -> None:
        """Test S3Get has retry configuration."""
        state = self.output.state_machine.states["S3Get"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "Retry" in dumped
        # Should have explicit retry from retryOnFail=true
        retries = dumped["Retry"]
        assert len(retries) >= 1
        # Check at least one retry with States.ALL (explicit) exists
        all_error_equals = [r["ErrorEquals"] for r in retries]
        assert any("States.ALL" in eq for eq in all_error_equals)

    def test_s3get_retry_max_attempts(self) -> None:
        """Test S3Get retry has correct max attempts."""
        state = self.output.state_machine.states["S3Get"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        retries = dumped["Retry"]
        # The explicit retry from node settings should have MaxAttempts=5
        explicit = [r for r in retries if "States.ALL" in r["ErrorEquals"]]
        assert any(r.get("MaxAttempts") == 5 for r in explicit)

    def test_s3put_present(self) -> None:
        """Test S3Put state is present."""
        assert "S3Put" in self.output.state_machine.states

    def test_both_states_present(self) -> None:
        """Test both S3 states are present."""
        states = self.output.state_machine.states
        assert "S3Get" in states
        assert "S3Put" in states


class TestMultiStepETL:
    """Tests for multi-step ETL workflow."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analysis, _ = _load_and_analyze("multi_step_etl.json")
        self.output = _make_engine().translate(self.analysis)

    def test_all_non_trigger_states_present(self) -> None:
        """Test all non-trigger states are present."""
        states = self.output.state_machine.states
        assert "DDBQuery" in states
        assert "PyCode" in states
        assert "SQSSend" in states
        assert "SNSNotify" in states

    def test_schedule_trigger_artifact(self) -> None:
        """Test schedule trigger artifact is present."""
        assert len(self.output.trigger_artifacts) == 1

    def test_dynamodb_query_resource(self) -> None:
        """Test DynamoDB query resource is correct."""
        state = self.output.state_machine.states["DDBQuery"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "query" in dumped["Resource"]

    def test_python_code_lambda_artifact(self) -> None:
        """Test Python code lambda artifact is correct."""
        py_lambdas = [
            a for a in self.output.lambda_artifacts if "code_node" in a.function_name
        ]
        assert len(py_lambdas) == 1
        from n8n_to_sfn.translators.base import LambdaRuntime

        assert py_lambdas[0].runtime == LambdaRuntime.PYTHON

    def test_sqs_send_resource(self) -> None:
        """Test SQS send resource is correct."""
        state = self.output.state_machine.states["SQSSend"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "sendMessage" in dumped["Resource"]

    def test_sns_publish_resource(self) -> None:
        """Test SNS publish resource is correct."""
        state = self.output.state_machine.states["SNSNotify"]
        dumped = state if isinstance(state, dict) else state.model_dump(by_alias=True)
        assert "publish" in dumped["Resource"]

    def test_state_machine_serializes_to_valid_json(self) -> None:
        """Test state machine serializes to valid JSON."""
        dumped = self.output.state_machine.model_dump(by_alias=True)
        json_str = json.dumps(dumped, indent=2)
        parsed = json.loads(json_str)
        assert "StartAt" in parsed
        assert "States" in parsed
        assert len(parsed["States"]) == 4

    def test_conversion_report_has_all_nodes(self) -> None:
        """Test conversion report has all nodes."""
        report = self.output.conversion_report
        assert report["total_nodes"] == 5


class TestAllFixturesRoundTrip:
    """Ensure all fixtures can be loaded, analyzed, translated, and serialized."""

    @pytest.fixture(
        params=[
            "simple_s3_pipeline.json",
            "webhook_to_dynamodb.json",
            "if_branch_workflow.json",
            "schedule_lambda_workflow.json",
            "code_node_workflow.json",
            "wait_and_notify.json",
            "error_handling_workflow.json",
            "multi_step_etl.json",
        ]
    )
    def fixture_name(self, request: pytest.FixtureRequest) -> str:
        """Provide fixture names as test parameters."""
        return request.param

    def test_roundtrip_produces_valid_state_machine(self, fixture_name: str) -> None:
        """Test roundtrip produces valid state machine."""
        analysis, _ = _load_and_analyze(fixture_name)
        engine = _make_engine()
        output = engine.translate(analysis)
        assert output.state_machine is not None
        dumped = output.state_machine.model_dump(by_alias=True)
        assert "StartAt" in dumped
        assert "States" in dumped
        # Must be serializable to JSON
        json_str = json.dumps(dumped)
        assert len(json_str) > 0

    def test_roundtrip_has_no_critical_errors(self, fixture_name: str) -> None:
        """Test roundtrip has no critical errors."""
        analysis, _ = _load_and_analyze(fixture_name)
        engine = _make_engine()
        output = engine.translate(analysis)
        # No "No translator found" warnings (everything should be handled)
        critical_warnings = [w for w in output.warnings if "No translator found" in w]
        assert critical_warnings == [], f"Unhandled nodes: {critical_warnings}"
