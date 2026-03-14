"""Tests for Pydantic models (n8n input, ASL output, analysis input)."""

from __future__ import annotations

import jsonschema
import pytest
from pydantic import ValidationError

from n8n_to_sfn.models.analysis import (
    ClassifiedExpression,
    ClassifiedNode,
    DependencyEdge,
    ExpressionCategory,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.asl import (
    CatchConfig,
    ChoiceRule,
    ChoiceState,
    FailState,
    ItemProcessor,
    MapState,
    ParallelState,
    PassState,
    ProcessorConfig,
    RetryConfig,
    StateMachine,
    SucceedState,
    TaskState,
    WaitState,
)
from n8n_to_sfn.models.n8n import (
    N8nConnectionTarget,
    N8nNode,
    N8nWorkflow,
)

# ---------------------------------------------------------------------------
# Task 1: n8n models
# ---------------------------------------------------------------------------


def _minimal_workflow() -> dict:
    """Create a minimal workflow dict."""
    return {
        "nodes": [
            {
                "id": "1",
                "name": "Start",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [250, 300],
            }
        ],
        "connections": {},
    }


def _multi_node_workflow() -> dict:
    """Create a multi-node workflow dict."""
    return {
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "1",
                "name": "Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [250, 300],
            },
            {
                "id": "2",
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 3,
                "position": [450, 300],
                "parameters": {"url": "https://api.example.com", "method": "GET"},
                "credentials": {"httpBasicAuth": {"id": "1", "name": "My Creds"}},
                "continueOnFail": True,
                "retryOnFail": True,
                "maxTries": 3,
                "waitBetweenTries": 2000,
            },
        ],
        "connections": {
            "Trigger": {
                "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1", "timezone": "UTC"},
    }


class TestN8nModels:
    """Tests for n8n Pydantic models."""

    def test_parse_minimal_workflow(self) -> None:
        """Test parsing minimal workflow."""
        wf = N8nWorkflow.model_validate(_minimal_workflow())
        assert len(wf.nodes) == 1
        assert wf.nodes[0].name == "Start"
        assert wf.nodes[0].type == "n8n-nodes-base.manualTrigger"
        assert wf.connections == {}

    def test_parse_multi_node_workflow(self) -> None:
        """Test parsing multi-node workflow."""
        wf = N8nWorkflow.model_validate(_multi_node_workflow())
        assert len(wf.nodes) == 2
        assert wf.name == "Test Workflow"

        http_node = wf.nodes[1]
        assert http_node.name == "HTTP Request"
        assert http_node.parameters["url"] == "https://api.example.com"
        assert http_node.credentials is not None
        assert http_node.continue_on_fail is True
        assert http_node.retry_on_fail is True
        assert http_node.max_tries == 3
        assert http_node.wait_between_tries == 2000

        conns = wf.connections["Trigger"]["main"][0]
        assert len(conns) == 1
        assert conns[0].node == "HTTP Request"
        assert conns[0].type == "main"
        assert conns[0].index == 0

    def test_settings_parsed(self) -> None:
        """Test workflow settings are parsed."""
        wf = N8nWorkflow.model_validate(_multi_node_workflow())
        assert wf.settings is not None
        assert wf.settings.execution_order == "v1"
        assert wf.settings.timezone == "UTC"

    def test_invalid_workflow_missing_nodes(self) -> None:
        """Test invalid workflow missing nodes raises error."""
        with pytest.raises(ValidationError):
            N8nWorkflow.model_validate({"connections": {}})

    def test_invalid_workflow_missing_connections(self) -> None:
        """Test invalid workflow missing connections raises error."""
        with pytest.raises(ValidationError):
            N8nWorkflow.model_validate({"nodes": []})

    def test_invalid_node_missing_required(self) -> None:
        """Test invalid node missing required fields raises error."""
        with pytest.raises(ValidationError):
            N8nNode.model_validate({"id": "1", "name": "Test"})

    def test_round_trip(self) -> None:
        """Test workflow round-trip serialization."""
        data = _multi_node_workflow()
        wf = N8nWorkflow.model_validate(data)
        json_str = wf.model_dump_json(by_alias=True)
        wf2 = N8nWorkflow.model_validate_json(json_str)
        assert wf2.name == wf.name
        assert len(wf2.nodes) == len(wf.nodes)
        for n1, n2 in zip(wf.nodes, wf2.nodes, strict=True):
            assert n1.id == n2.id
            assert n1.name == n2.name
            assert n1.type == n2.type

    def test_connection_target_model(self) -> None:
        """Test connection target model."""
        ct = N8nConnectionTarget(node="Next", type="main", index=0)
        assert ct.node == "Next"
        assert ct.type == "main"
        assert ct.index == 0


# ---------------------------------------------------------------------------
# Task 2: ASL models
# ---------------------------------------------------------------------------


class TestASLModels:
    """Tests for ASL Pydantic models."""

    def test_pass_state_serialize(self, asl_schema: dict) -> None:
        """Test Pass state serialization."""
        state = PassState(end=True)
        dumped = state.model_dump(by_alias=True)
        assert dumped["Type"] == "Pass"
        assert dumped["End"] is True
        sm = StateMachine(start_at="S", states={"S": state})
        self._validate(sm, asl_schema)

    def test_task_state_serialize(self, asl_schema: dict) -> None:
        """Test Task state serialization."""
        state = TaskState(
            resource="arn:aws:states:::aws-sdk:s3:getObject",
            arguments={"Bucket": "b", "Key": "k"},
            end=True,
        )
        dumped = state.model_dump(by_alias=True)
        assert dumped["Type"] == "Task"
        assert dumped["Resource"] == "arn:aws:states:::aws-sdk:s3:getObject"
        assert dumped["Arguments"] == {"Bucket": "b", "Key": "k"}
        sm = StateMachine(start_at="S", states={"S": state})
        self._validate(sm, asl_schema)

    def test_choice_state_jsonata(self, asl_schema: dict) -> None:
        """Test Choice state with JSONata condition."""
        rule = ChoiceRule(condition="$states.input.x > 0", next="Pos")
        state = ChoiceState(
            choices=[rule],
            default="Neg",
        )
        dumped = state.model_dump(by_alias=True)
        assert dumped["Choices"][0]["Condition"] == "$states.input.x > 0"
        assert dumped["Default"] == "Neg"
        sm = StateMachine(
            start_at="C",
            states={
                "C": state,
                "Pos": PassState(end=True),
                "Neg": PassState(end=True),
            },
        )
        self._validate(sm, asl_schema)

    def test_wait_state_seconds(self, asl_schema: dict) -> None:
        """Test Wait state with seconds."""
        state = WaitState(seconds=30, next="Done")
        dumped = state.model_dump(by_alias=True)
        assert dumped["Seconds"] == 30
        assert dumped["Next"] == "Done"
        sm = StateMachine(
            start_at="W",
            states={"W": state, "Done": PassState(end=True)},
        )
        self._validate(sm, asl_schema)

    def test_wait_state_timestamp(self, asl_schema: dict) -> None:
        """Test Wait state with timestamp."""
        state = WaitState(timestamp="2025-01-01T00:00:00Z", end=True)
        dumped = state.model_dump(by_alias=True)
        assert dumped["Timestamp"] == "2025-01-01T00:00:00Z"

    def test_succeed_state(self, asl_schema: dict) -> None:
        """Test Succeed state serialization."""
        state = SucceedState()
        dumped = state.model_dump(by_alias=True)
        assert dumped["Type"] == "Succeed"
        sm = StateMachine(start_at="S", states={"S": state})
        self._validate(sm, asl_schema)

    def test_fail_state(self, asl_schema: dict) -> None:
        """Test Fail state serialization."""
        state = FailState(error="CustomError", cause="Something went wrong")
        dumped = state.model_dump(by_alias=True)
        assert dumped["Error"] == "CustomError"
        assert dumped["Cause"] == "Something went wrong"
        sm = StateMachine(start_at="F", states={"F": state})
        self._validate(sm, asl_schema)

    def test_parallel_state(self, asl_schema: dict) -> None:
        """Test Parallel state serialization."""
        branch1 = StateMachine(
            start_at="A",
            states={"A": PassState(end=True)},
            query_language=None,
        )
        branch2 = StateMachine(
            start_at="B",
            states={"B": PassState(end=True)},
            query_language=None,
        )
        state = ParallelState(branches=[branch1, branch2], end=True)
        dumped = state.model_dump(by_alias=True)
        assert len(dumped["Branches"]) == 2
        sm = StateMachine(start_at="P", states={"P": state})
        self._validate(sm, asl_schema)

    def test_map_state(self, asl_schema: dict) -> None:
        """Test Map state serialization."""
        proc = ItemProcessor(
            processor_config=ProcessorConfig(mode="INLINE"),
            start_at="DoWork",
            states={"DoWork": PassState(end=True).model_dump(by_alias=True)},
        )
        state = MapState(
            item_processor=proc,
            max_concurrency=5,
            end=True,
        )
        dumped = state.model_dump(by_alias=True)
        assert dumped["MaxConcurrency"] == 5
        assert dumped["ItemProcessor"]["ProcessorConfig"]["Mode"] == "INLINE"
        sm = StateMachine(start_at="M", states={"M": state})
        self._validate(sm, asl_schema)

    def test_retry_config(self) -> None:
        """Test RetryConfig serialization."""
        retry = RetryConfig(
            error_equals=["States.TaskFailed"],
            interval_seconds=2,
            max_attempts=3,
            backoff_rate=2.0,
            max_delay_seconds=30,
            jitter_strategy="FULL",
        )
        dumped = retry.model_dump(by_alias=True)
        assert dumped["ErrorEquals"] == ["States.TaskFailed"]
        assert dumped["IntervalSeconds"] == 2
        assert dumped["JitterStrategy"] == "FULL"

    def test_catch_config(self) -> None:
        """Test CatchConfig serialization."""
        catch = CatchConfig(
            error_equals=["States.ALL"],
            next="HandleError",
        )
        dumped = catch.model_dump(by_alias=True)
        assert dumped["ErrorEquals"] == ["States.ALL"]
        assert dumped["Next"] == "HandleError"

    def test_task_with_retry_and_catch(self, asl_schema: dict) -> None:
        """Test Task state with retry and catch."""
        state = TaskState(
            resource="arn:aws:states:::lambda:invoke",
            retry=[
                RetryConfig(
                    error_equals=["States.TaskFailed"],
                    max_attempts=3,
                )
            ],
            catch=[
                CatchConfig(
                    error_equals=["States.ALL"],
                    next="Fallback",
                )
            ],
            next="Done",
        )
        sm = StateMachine(
            start_at="T",
            states={
                "T": state,
                "Done": PassState(end=True),
                "Fallback": FailState(error="Caught"),
            },
        )
        self._validate(sm, asl_schema)

    def test_complete_state_machine(self, asl_schema: dict) -> None:
        """Test complete state machine serialization."""
        sm = StateMachine(
            comment="A complete workflow",
            start_at="Start",
            states={
                "Start": PassState(next="Check"),
                "Check": ChoiceState(
                    choices=[
                        ChoiceRule(condition="$states.input.ready", next="Process")
                    ],
                    default="Wait",
                ),
                "Wait": WaitState(seconds=10, next="Check"),
                "Process": TaskState(
                    resource="arn:aws:states:::lambda:invoke",
                    next="Done",
                ),
                "Done": SucceedState(),
            },
        )
        self._validate(sm, asl_schema)

    def test_query_language_jsonata(self, asl_schema: dict) -> None:
        """Test query language is JSONata."""
        sm = StateMachine(start_at="S", states={"S": PassState(end=True)})
        dumped = sm.model_dump(by_alias=True)
        assert dumped["QueryLanguage"] == "JSONata"
        self._validate(sm, asl_schema)

    def test_state_must_have_next_or_end(self) -> None:
        """Test state without next or end."""
        state = PassState()
        dumped = state.model_dump(by_alias=True)
        assert "Next" not in dumped
        assert "End" not in dumped

    def test_assign_on_states(self, asl_schema: dict) -> None:
        """Test Assign on states."""
        state = PassState(
            assign={"myVar": "hello"},
            end=True,
        )
        dumped = state.model_dump(by_alias=True)
        assert dumped["Assign"] == {"myVar": "hello"}
        sm = StateMachine(start_at="S", states={"S": state})
        self._validate(sm, asl_schema)

    def test_output_jsonata_on_pass(self, asl_schema: dict) -> None:
        """Test Output JSONata on Pass state."""
        state = PassState(
            output="{% $states.input.name %}",
            end=True,
        )
        dumped = state.model_dump(by_alias=True)
        assert dumped["Output"] == "{% $states.input.name %}"
        sm = StateMachine(start_at="S", states={"S": state})
        self._validate(sm, asl_schema)

    def _validate(self, sm: StateMachine, schema: dict) -> None:
        """Validate state machine against ASL schema."""
        asl_json = sm.model_dump(by_alias=True)
        jsonschema.validate(instance=asl_json, schema=schema)


# ---------------------------------------------------------------------------
# Task 3: Analysis models
# ---------------------------------------------------------------------------


class TestAnalysisModels:
    """Tests for analysis Pydantic models."""

    def _make_node(
        self, name: str = "Test", node_type: str = "n8n-nodes-base.set"
    ) -> N8nNode:
        """Create an N8nNode for testing."""
        return N8nNode(
            id="1",
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
        )

    def test_node_classification_values(self) -> None:
        """Test NodeClassification enum values."""
        assert NodeClassification.AWS_NATIVE == "AWS_NATIVE"
        assert NodeClassification.FLOW_CONTROL == "FLOW_CONTROL"
        assert NodeClassification.UNSUPPORTED == "UNSUPPORTED"

    def test_expression_category_values(self) -> None:
        """Test ExpressionCategory enum values."""
        assert ExpressionCategory.JSONATA_DIRECT == "JSONATA_DIRECT"
        assert ExpressionCategory.REQUIRES_VARIABLES == "REQUIRES_VARIABLES"
        assert ExpressionCategory.REQUIRES_LAMBDA == "REQUIRES_LAMBDA"

    def test_classified_expression(self) -> None:
        """Test ClassifiedExpression construction."""
        expr = ClassifiedExpression(
            original="{{ $json.name }}",
            category=ExpressionCategory.JSONATA_DIRECT,
            node_references=[],
            parameter_path="parameters.value",
        )
        assert expr.original == "{{ $json.name }}"
        assert expr.category == ExpressionCategory.JSONATA_DIRECT

    def test_classified_node(self) -> None:
        """Test ClassifiedNode construction."""
        node = self._make_node()
        cn = ClassifiedNode(
            node=node,
            classification=NodeClassification.FLOW_CONTROL,
            expressions=[],
        )
        assert cn.classification == NodeClassification.FLOW_CONTROL

    def test_classified_node_with_api_spec(self) -> None:
        """Test ClassifiedNode with api_spec."""
        node = self._make_node(node_type="n8n-nodes-base.slack")
        cn = ClassifiedNode(
            node=node,
            classification=NodeClassification.PICOFUN_API,
            api_spec="slack-api.yaml",
            operation_mappings={"postMessage": "/chat.postMessage"},
        )
        assert cn.api_spec == "slack-api.yaml"
        assert cn.operation_mappings is not None

    def test_dependency_edge(self) -> None:
        """Test DependencyEdge construction."""
        edge = DependencyEdge(
            from_node="A",
            to_node="B",
            edge_type="CONNECTION",
        )
        assert edge.from_node == "A"
        assert edge.to_node == "B"
        assert edge.edge_type == "CONNECTION"

    def test_data_reference_edge(self) -> None:
        """Test DependencyEdge with DATA_REFERENCE type."""
        edge = DependencyEdge(
            from_node="Lookup",
            to_node="Merge",
            edge_type="DATA_REFERENCE",
        )
        assert edge.edge_type == "DATA_REFERENCE"

    def test_workflow_analysis(self) -> None:
        """Test WorkflowAnalysis construction."""
        node = self._make_node("Trigger", "n8n-nodes-base.manualTrigger")
        cn = ClassifiedNode(
            node=node,
            classification=NodeClassification.TRIGGER,
        )
        analysis = WorkflowAnalysis(
            classified_nodes=[cn],
            dependency_edges=[],
            variables_needed={},
            confidence_score=0.9,
        )
        assert len(analysis.classified_nodes) == 1
        assert analysis.confidence_score == 0.9

    def test_workflow_analysis_mixed_classifications(self) -> None:
        """Test WorkflowAnalysis with mixed node classifications."""
        nodes = [
            ClassifiedNode(
                node=self._make_node("Trigger", "n8n-nodes-base.scheduleTrigger"),
                classification=NodeClassification.TRIGGER,
            ),
            ClassifiedNode(
                node=self._make_node("S3 Get", "n8n-nodes-base.awsS3"),
                classification=NodeClassification.AWS_NATIVE,
            ),
            ClassifiedNode(
                node=self._make_node("IF", "n8n-nodes-base.if"),
                classification=NodeClassification.FLOW_CONTROL,
            ),
            ClassifiedNode(
                node=self._make_node("Slack", "n8n-nodes-base.slack"),
                classification=NodeClassification.PICOFUN_API,
            ),
            ClassifiedNode(
                node=self._make_node("Code", "n8n-nodes-base.code"),
                classification=NodeClassification.CODE_JS,
            ),
        ]
        edges = [
            DependencyEdge(
                from_node="Trigger", to_node="S3 Get", edge_type="CONNECTION"
            ),
            DependencyEdge(from_node="S3 Get", to_node="IF", edge_type="CONNECTION"),
        ]
        analysis = WorkflowAnalysis(
            classified_nodes=nodes,
            dependency_edges=edges,
            variables_needed={"lookupResult": "S3 Get"},
            payload_warnings=["Large payload at S3 Get"],
            unsupported_nodes=[],
            confidence_score=0.75,
        )
        assert len(analysis.classified_nodes) == 5
        assert len(analysis.dependency_edges) == 2
        assert analysis.variables_needed["lookupResult"] == "S3 Get"

    def test_round_trip(self) -> None:
        """Test WorkflowAnalysis round-trip serialization."""
        node = self._make_node()
        cn = ClassifiedNode(
            node=node,
            classification=NodeClassification.AWS_NATIVE,
            expressions=[
                ClassifiedExpression(
                    original="{{ $json.id }}",
                    category=ExpressionCategory.JSONATA_DIRECT,
                    parameter_path="parameters.key",
                ),
            ],
        )
        analysis = WorkflowAnalysis(
            classified_nodes=[cn],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="CONNECTION"),
            ],
            confidence_score=0.8,
        )
        json_str = analysis.model_dump_json()
        analysis2 = WorkflowAnalysis.model_validate_json(json_str)
        assert len(analysis2.classified_nodes) == 1
        assert (
            analysis2.classified_nodes[0].classification
            == NodeClassification.AWS_NATIVE
        )
        assert analysis2.confidence_score == 0.8
