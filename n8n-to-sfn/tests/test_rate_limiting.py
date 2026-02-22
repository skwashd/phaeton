"""Tests for rate limiting and concurrency controls."""

from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.asl import RetryConfig
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.base import TranslationContext, build_error_handling
from n8n_to_sfn.translators.flow_control import FlowControlTranslator


def _node(name, node_type, params=None, classification=NodeClassification.AWS_NATIVE):
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=classification,
    )


def _context(rate_limits=None):
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        rate_limits=rate_limits or {},
    )


class TestAWSServiceRetryDefaults:
    def setup_method(self):
        self.translator = AWSServiceTranslator()

    def test_s3_has_default_retry(self):
        node = _node(
            "S3",
            "n8n-nodes-base.awsS3",
            {
                "resource": "object",
                "operation": "get",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["S3"]
        assert "Retry" in state
        retry = state["Retry"][0]
        assert retry["ErrorEquals"] == ["States.TaskFailed"]
        assert retry["MaxAttempts"] == 3
        assert retry["IntervalSeconds"] == 2
        assert retry["BackoffRate"] == 2.0

    def test_dynamodb_has_default_retry(self):
        node = _node(
            "DDB",
            "n8n-nodes-base.awsDynamoDB",
            {
                "resource": "item",
                "operation": "get",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["DDB"]
        assert "Retry" in state
        assert state["Retry"][0]["MaxAttempts"] == 3

    def test_sqs_has_default_retry(self):
        node = _node(
            "SQS",
            "n8n-nodes-base.awsSqs",
            {
                "resource": "message",
                "operation": "send",
            },
        )
        result = self.translator.translate(node, _context())
        state = result.states["SQS"]
        assert "Retry" in state


class TestSplitInBatchesConcurrency:
    def setup_method(self):
        self.translator = FlowControlTranslator()

    def test_split_in_batches_max_concurrency_1(self):
        node = _node(
            "Batch",
            "n8n-nodes-base.splitInBatches",
            {"batchSize": 10},
            classification=NodeClassification.FLOW_CONTROL,
        )
        result = self.translator.translate(node, _context())
        state = result.states["Batch"]
        assert state.type == "Map"
        assert state.max_concurrency == 1


class TestRetryBackoffConfig:
    def test_backoff_rate_on_default_retry(self):
        default = RetryConfig(
            error_equals=["States.TaskFailed"],
            max_attempts=3,
            interval_seconds=2,
            backoff_rate=2.0,
            max_delay_seconds=30,
        )
        dumped = default.model_dump(by_alias=True)
        assert dumped["BackoffRate"] == 2.0
        assert dumped["MaxDelaySeconds"] == 30
        assert dumped["IntervalSeconds"] == 2

    def test_retry_with_jitter_strategy(self):
        retry = RetryConfig(
            error_equals=["States.TaskFailed"],
            max_attempts=3,
            interval_seconds=1,
            backoff_rate=2.0,
            jitter_strategy="FULL",
        )
        dumped = retry.model_dump(by_alias=True)
        assert dumped["JitterStrategy"] == "FULL"

    def test_explicit_retry_from_node_settings(self):
        node = _node(
            "API", "n8n-nodes-base.awsS3", classification=NodeClassification.AWS_NATIVE
        )
        node.node.retry_on_fail = True
        node.node.max_tries = 5
        node.node.wait_between_tries = 3000
        retries, _ = build_error_handling(node)
        assert len(retries) == 1
        assert retries[0].max_attempts == 5
        assert retries[0].interval_seconds == 3
        assert retries[0].backoff_rate == 2.0
