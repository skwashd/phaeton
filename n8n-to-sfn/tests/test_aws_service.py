"""Tests for AWS service translator."""

from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.aws_service import AWSServiceTranslator
from n8n_to_sfn.translators.base import TranslationContext


def _aws_node(name, node_type, params=None):
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.AWS_NATIVE,
    )


def _context():
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
    )


class TestAWSServiceTranslator:
    def setup_method(self):
        self.translator = AWSServiceTranslator()

    def test_can_translate(self):
        node = _aws_node("S3", "n8n-nodes-base.awsS3")
        assert self.translator.can_translate(node)

    def test_s3_put_object(self):
        node = _aws_node(
            "S3Put",
            "n8n-nodes-base.awsS3",
            {
                "resource": "object",
                "operation": "create",
                "bucketName": "my-bucket",
                "fileName": "test.txt",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["S3Put"]
        assert "putObject" in state_dict["Resource"]
        # Params should be PascalCase
        args = state_dict.get("Arguments", {})
        if args:
            assert "BucketName" in args or "FileName" in args

    def test_s3_get_object(self):
        node = _aws_node(
            "S3Get",
            "n8n-nodes-base.awsS3",
            {
                "resource": "object",
                "operation": "get",
                "bucketName": "my-bucket",
                "key": "file.json",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["S3Get"]
        assert "getObject" in state_dict["Resource"]

    def test_dynamodb_put_item(self):
        node = _aws_node(
            "DDBPut",
            "n8n-nodes-base.awsDynamoDB",
            {
                "resource": "item",
                "operation": "create",
                "tableName": "MyTable",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["DDBPut"]
        assert "putItem" in state_dict["Resource"]

    def test_dynamodb_query(self):
        node = _aws_node(
            "DDBQuery",
            "n8n-nodes-base.awsDynamoDB",
            {
                "resource": "item",
                "operation": "query",
                "tableName": "MyTable",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["DDBQuery"]
        assert "query" in state_dict["Resource"]

    def test_sqs_send_message(self):
        node = _aws_node(
            "SQS",
            "n8n-nodes-base.awsSqs",
            {
                "resource": "message",
                "operation": "send",
                "queueUrl": "https://sqs.us-east-1.amazonaws.com/123/q",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["SQS"]
        assert "sendMessage" in state_dict["Resource"]

    def test_sns_publish(self):
        node = _aws_node(
            "SNS",
            "n8n-nodes-base.awsSns",
            {
                "resource": "topic",
                "operation": "publish",
                "topicArn": "arn:aws:sns:us-east-1:123:MyTopic",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["SNS"]
        assert "publish" in state_dict["Resource"]

    def test_lambda_invoke(self):
        node = _aws_node(
            "Lambda",
            "n8n-nodes-base.awsLambda",
            {
                "function": "my-function",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["Lambda"]
        assert "lambda:invoke" in state_dict["Resource"]

    def test_default_retry_present(self):
        node = _aws_node(
            "S3",
            "n8n-nodes-base.awsS3",
            {
                "resource": "object",
                "operation": "get",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["S3"]
        assert "Retry" in state_dict
        assert len(state_dict["Retry"]) > 0
        retry = state_dict["Retry"][0]
        assert retry["ErrorEquals"] == ["States.TaskFailed"]

    def test_camel_to_pascal_params(self):
        node = _aws_node(
            "S3",
            "n8n-nodes-base.awsS3",
            {
                "resource": "object",
                "operation": "get",
                "bucketName": "test",
                "key": "file.txt",
            },
        )
        result = self.translator.translate(node, _context())
        state_dict = result.states["S3"]
        args = state_dict.get("Arguments", {})
        if args:
            for key in args:
                assert key[0].isupper(), f"Key {key} should be PascalCase"
