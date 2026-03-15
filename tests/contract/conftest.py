"""
Shared fixtures for contract tests.

Provides representative model instances that cover all fields, ensuring
contract tests exercise the full serialisation surface between components.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from phaeton_models.analyzer import (
    ClassifiedExpression as AnalyzerExpression,
)
from phaeton_models.analyzer import (
    ClassifiedNode as AnalyzerNode,
)
from phaeton_models.analyzer import (
    ConversionReport,
    NodeCategory,
    PayloadWarning,
)
from phaeton_models.analyzer import (
    ExpressionCategory as AnalyzerExpressionCategory,
)
from phaeton_models.n8n_workflow import N8nNode
from phaeton_models.translator_output import (
    CredentialArtifact,
    LambdaArtifact,
    TranslationOutput,
    TriggerArtifact,
)
from phaeton_models.translator_output import (
    LambdaRuntime as EngLambdaRuntime,
)
from phaeton_models.translator_output import (
    TriggerType as EngTriggerType,
)


def _make_node(
    name: str,
    node_type: str = "n8n-nodes-base.dynamoDb",
    node_id: str = "node-1",
) -> N8nNode:
    """Build a minimal N8nNode for testing."""
    return N8nNode(
        id=node_id,
        name=name,
        type=node_type,
        typeVersion=1,
        position=[0.0, 0.0],
    )


@pytest.fixture
def sample_conversion_report() -> ConversionReport:
    """Build a representative ConversionReport covering all fields."""
    trigger_node = _make_node("Schedule Trigger", "n8n-nodes-base.scheduleTrigger", "t1")
    dynamo_node = _make_node("DynamoDB Put", "n8n-nodes-base.dynamoDb", "n1")
    code_node = _make_node("Transform", "n8n-nodes-base.code", "n2")
    unsupported_node = _make_node("Unsupported", "n8n-nodes-base.unknown", "n3")

    return ConversionReport(
        source_workflow_name="test-workflow",
        source_n8n_version="1.50.0",
        analyzer_version="0.1.0",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        total_nodes=4,
        classification_summary={
            NodeCategory.AWS_NATIVE: 1,
            NodeCategory.CODE_JS: 1,
            NodeCategory.TRIGGER: 1,
            NodeCategory.UNSUPPORTED: 1,
        },
        classified_nodes=[
            AnalyzerNode(
                node=trigger_node,
                category=NodeCategory.TRIGGER,
                translation_strategy="trigger_translator",
            ),
            AnalyzerNode(
                node=dynamo_node,
                category=NodeCategory.AWS_NATIVE,
                translation_strategy="aws_service",
            ),
            AnalyzerNode(
                node=code_node,
                category=NodeCategory.CODE_JS,
                translation_strategy="code_node",
                notes="Inline JavaScript",
            ),
            AnalyzerNode(
                node=unsupported_node,
                category=NodeCategory.UNSUPPORTED,
                translation_strategy="none",
            ),
        ],
        expression_summary={
            AnalyzerExpressionCategory.JSONATA_DIRECT: 1,
            AnalyzerExpressionCategory.VARIABLE_REFERENCE: 1,
            AnalyzerExpressionCategory.LAMBDA_REQUIRED: 1,
        },
        classified_expressions=[
            AnalyzerExpression(
                node_name="DynamoDB Put",
                parameter_path="parameters.key",
                raw_expression="{{ $json.id }}",
                category=AnalyzerExpressionCategory.JSONATA_DIRECT,
                jsonata_preview="$.id",
                referenced_nodes=[],
                reason="simple property access",
            ),
            AnalyzerExpression(
                node_name="DynamoDB Put",
                parameter_path="parameters.value",
                raw_expression="{{ $node['Transform'].json.output }}",
                category=AnalyzerExpressionCategory.VARIABLE_REFERENCE,
                referenced_nodes=["Transform"],
                reason="cross-node reference",
            ),
            AnalyzerExpression(
                node_name="Transform",
                parameter_path="parameters.code",
                raw_expression="items.map(i => i.json.x + 1)",
                category=AnalyzerExpressionCategory.LAMBDA_REQUIRED,
                reason="complex transformation",
            ),
        ],
        payload_warnings=[
            PayloadWarning(
                node_name="DynamoDB Put",
                warning_type="large_payload",
                description="Payload may exceed 256KB limit",
                severity="medium",
                recommendation="Add a payload size check",
            ),
        ],
        cross_node_references=[],
        unsupported_nodes=[
            AnalyzerNode(
                node=unsupported_node,
                category=NodeCategory.UNSUPPORTED,
                translation_strategy="none",
            ),
        ],
        trigger_nodes=[
            AnalyzerNode(
                node=trigger_node,
                category=NodeCategory.TRIGGER,
                translation_strategy="trigger_translator",
            ),
        ],
        sub_workflows_detected=[],
        required_picofun_clients=[],
        required_credentials=["dynamodb"],
        confidence_score=0.85,
        blocking_issues=[],
        graph_metadata={
            "edges": [
                {
                    "from_node": "Schedule Trigger",
                    "to_node": "DynamoDB Put",
                    "edge_type": "connection",
                    "output_index": 0,
                },
                {
                    "source_node": "Transform",
                    "target_node": "DynamoDB Put",
                    "edge_type": "data_reference",
                },
            ],
        },
    )


@pytest.fixture
def sample_translation_output() -> TranslationOutput:
    """Build a representative TranslationOutput covering all fields."""
    return TranslationOutput(
        state_machine={
            "StartAt": "DynamoDB_Put",
            "States": {
                "DynamoDB_Put": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::dynamodb:putItem",
                    "End": True,
                },
            },
        },
        lambda_artifacts=[
            LambdaArtifact(
                function_name="transform_handler",
                runtime=EngLambdaRuntime.NODEJS,
                handler_code="exports.handler = async (event) => event;",
                dependencies=["aws-sdk"],
                directory_name="transform",
            ),
            LambdaArtifact(
                function_name="picofun_slack_client",
                runtime=EngLambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return event",
                dependencies=["requests"],
                directory_name="slack_client",
            ),
            LambdaArtifact(
                function_name="webhook_handler",
                runtime=EngLambdaRuntime.PYTHON,
                handler_code="def handler(event, context): return {}",
                dependencies=[],
                directory_name="webhook",
            ),
        ],
        trigger_artifacts=[
            TriggerArtifact(
                trigger_type=EngTriggerType.EVENTBRIDGE_SCHEDULE,
                config={"schedule_expression": "rate(5 minutes)"},
            ),
            TriggerArtifact(
                trigger_type=EngTriggerType.LAMBDA_FURL,
                config={"path": "/webhook"},
                lambda_artifact=LambdaArtifact(
                    function_name="webhook_handler",
                    runtime=EngLambdaRuntime.PYTHON,
                    handler_code="def handler(event, context): return {}",
                    dependencies=[],
                ),
            ),
            TriggerArtifact(
                trigger_type=EngTriggerType.MANUAL,
                config={},
            ),
        ],
        credential_artifacts=[
            CredentialArtifact(
                parameter_path="/phaeton/creds/slack",
                credential_type="oauth2",
                auth_type="oauth2",
                placeholder_value="CHANGE_ME",
            ),
            CredentialArtifact(
                parameter_path="phaeton/creds/api-key",
                credential_type="api_key",
                auth_type="api_key",
                placeholder_value="",
            ),
        ],
        conversion_report={
            "source_n8n_version": "1.50.0",
            "converter_version": "0.1.0",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "confidence_score": 0.85,
            "total_nodes": 4,
            "classification_breakdown": {"AWS_NATIVE": 1, "CODE_JS": 1},
            "expression_breakdown": {"JSONATA_DIRECT": 1},
            "unsupported_nodes": ["Unsupported"],
            "payload_warnings": ["large payload"],
            "ai_assisted_nodes": [],
        },
        warnings=["Unsupported node skipped"],
    )
