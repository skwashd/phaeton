"""Tests for trigger translator."""

from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext, TriggerType
from n8n_to_sfn.translators.triggers import TriggerTranslator


def _trigger_node(name, node_type, params=None):
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type=node_type,
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.TRIGGER,
    )


def _context(workflow_name="test-workflow"):
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


class TestTriggerTranslator:
    def setup_method(self):
        self.translator = TriggerTranslator()

    def test_can_translate(self):
        node = _trigger_node("T", "n8n-nodes-base.scheduleTrigger")
        assert self.translator.can_translate(node)

    def test_schedule_with_cron(self):
        node = _trigger_node(
            "Sched",
            "n8n-nodes-base.scheduleTrigger",
            {
                "rule": {
                    "values": [
                        {"mode": "cronExpression", "cronExpression": "0 9 * * *"}
                    ]
                },
            },
        )
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        artifact = result.trigger_artifacts[0]
        assert artifact.trigger_type == TriggerType.EVENTBRIDGE_SCHEDULE
        assert "cron" in artifact.config.get("schedule_expression", "")

    def test_schedule_with_interval(self):
        node = _trigger_node(
            "Sched",
            "n8n-nodes-base.scheduleTrigger",
            {
                "rule": {"values": [{"mode": "everyX", "value": 10}]},
            },
        )
        result = self.translator.translate(node, _context())
        artifact = result.trigger_artifacts[0]
        assert artifact.trigger_type == TriggerType.EVENTBRIDGE_SCHEDULE
        assert "rate" in artifact.config.get("schedule_expression", "")

    def test_webhook(self):
        node = _trigger_node(
            "Webhook",
            "n8n-nodes-base.webhook",
            {
                "httpMethod": "POST",
                "path": "/webhook",
            },
        )
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        artifact = result.trigger_artifacts[0]
        assert artifact.trigger_type == TriggerType.LAMBDA_FURL
        assert len(result.lambda_artifacts) == 1
        handler = result.lambda_artifacts[0].handler_code
        assert "start_execution" in handler

    def test_manual(self):
        node = _trigger_node("Manual", "n8n-nodes-base.manualTrigger")
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        assert result.trigger_artifacts[0].trigger_type == TriggerType.MANUAL
        assert len(result.lambda_artifacts) == 0

    def test_webhook_handler_is_valid_python(self):
        node = _trigger_node("WH", "n8n-nodes-base.webhook")
        result = self.translator.translate(node, _context())
        handler_code = result.lambda_artifacts[0].handler_code
        # Should compile as valid Python
        compile(handler_code, "<webhook>", "exec")

    def test_unknown_trigger_fallback(self):
        node = _trigger_node("Slack", "n8n-nodes-base.slackTrigger")
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        assert result.trigger_artifacts[0].trigger_type == TriggerType.LAMBDA_FURL
        assert any(
            "unsupported" in w.lower() or "manual" in w.lower() for w in result.warnings
        )
