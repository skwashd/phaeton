"""Tests for trigger translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext, TriggerType
from n8n_to_sfn.translators.triggers import TriggerTranslator


def _trigger_node(
    name: str, node_type: str, params: dict | None = None
) -> ClassifiedNode:
    """Create a trigger classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type=node_type,
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.TRIGGER,
    )


def _context(workflow_name: str = "test-workflow") -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


class TestTriggerTranslator:
    """Tests for TriggerTranslator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = TriggerTranslator()

    def test_can_translate(self) -> None:
        """Test can_translate returns True for trigger nodes."""
        node = _trigger_node("T", "n8n-nodes-base.scheduleTrigger")
        assert self.translator.can_translate(node)

    def test_schedule_with_cron(self) -> None:
        """Test schedule trigger with cron expression."""
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

    def test_schedule_with_interval(self) -> None:
        """Test schedule trigger with interval."""
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

    def test_webhook(self) -> None:
        """Test webhook trigger translation."""
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

    def test_manual(self) -> None:
        """Test manual trigger translation."""
        node = _trigger_node("Manual", "n8n-nodes-base.manualTrigger")
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        assert result.trigger_artifacts[0].trigger_type == TriggerType.MANUAL
        assert len(result.lambda_artifacts) == 0

    def test_webhook_handler_is_valid_python(self) -> None:
        """Test webhook handler is valid Python."""
        node = _trigger_node("WH", "n8n-nodes-base.webhook")
        result = self.translator.translate(node, _context())
        handler_code = result.lambda_artifacts[0].handler_code
        # Should compile as valid Python
        compile(handler_code, "<webhook>", "exec")

    def test_unknown_trigger_fallback(self) -> None:
        """Test unknown trigger falls back to Lambda FURL."""
        node = _trigger_node("Slack", "n8n-nodes-base.slackTrigger")
        result = self.translator.translate(node, _context())
        assert len(result.trigger_artifacts) == 1
        assert result.trigger_artifacts[0].trigger_type == TriggerType.LAMBDA_FURL
        assert any(
            "unsupported" in w.lower() or "manual" in w.lower() for w in result.warnings
        )
