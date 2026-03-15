"""Tests for form trigger and webhook callback translation."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext, TriggerType
from n8n_to_sfn.translators.flow_control import FlowControlTranslator


def _wait_node(name: str, params: dict | None = None) -> ClassifiedNode:
    """Create a Wait classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.wait",
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=NodeClassification.FLOW_CONTROL,
    )


def _context() -> TranslationContext:
    """Create a minimal translation context."""
    return TranslationContext(
        analysis=WorkflowAnalysis(
            classified_nodes=[],
            dependency_edges=[],
        ),
    )


class TestFormTriggerCallback:
    """Tests for form submission callback translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()
        self.ctx = _context()

    def test_form_submission_produces_task_state(self) -> None:
        """Test form trigger produces a callback Task state, not a WaitState."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitForm"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["Type"] == "Task"
        assert dumped["Resource"] == "arn:aws:states:::lambda:invoke.waitForTaskToken"

    def test_form_submission_has_task_token_in_payload(self) -> None:
        """Test the callback payload includes the task token reference."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitForm"]
        dumped = state.model_dump(by_alias=True)
        payload = dumped["Arguments"]["Payload"]

        assert payload["taskToken.$"] == "$$.Task.Token"

    def test_form_submission_default_timeout(self) -> None:
        """Test form callback uses default 24-hour timeout."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitForm"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["TimeoutSeconds"] == 86400

    def test_form_submission_custom_timeout(self) -> None:
        """Test form callback respects custom timeout."""
        node = _wait_node(
            "WaitForm",
            {"resume": "n8nFormSubmission", "timeoutSeconds": 3600},
        )
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitForm"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["TimeoutSeconds"] == 3600

    def test_form_submission_generates_lambda_artifact(self) -> None:
        """Test a Lambda artifact is generated for the form handler."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        assert len(result.lambda_artifacts) == 1
        artifact = result.lambda_artifacts[0]
        assert artifact.function_name == "WaitForm_form_handler"
        assert "send_task_success" in artifact.handler_code
        assert "boto3" in artifact.dependencies

    def test_form_submission_generates_trigger_artifact(self) -> None:
        """Test a LAMBDA_FURL trigger artifact is generated."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        assert len(result.trigger_artifacts) == 1
        trigger = result.trigger_artifacts[0]
        assert trigger.trigger_type == TriggerType.LAMBDA_FURL
        assert trigger.lambda_artifact is not None
        assert trigger.config["handler_kind"] == "form"

    def test_form_submission_includes_form_config(self) -> None:
        """Test form config fields are passed in the payload."""
        node = _wait_node(
            "WaitForm",
            {
                "resume": "n8nFormSubmission",
                "formTitle": "Approval",
                "formDescription": "Please approve",
                "formFields": {"field1": "text"},
            },
        )
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitForm"]
        dumped = state.model_dump(by_alias=True)
        form_config = dumped["Arguments"]["Payload"]["formConfig"]

        assert form_config["formTitle"] == "Approval"
        assert form_config["formDescription"] == "Please approve"
        assert form_config["formFields"] == {"field1": "text"}

    def test_form_submission_metadata(self) -> None:
        """Test callback metadata is set correctly."""
        node = _wait_node("WaitForm", {"resume": "n8nFormSubmission"})
        result = self.translator.translate(node, self.ctx)

        assert result.metadata["callback_node"] is True
        assert result.metadata["resume_type"] == "n8nFormSubmission"
        assert result.metadata["timeout_seconds"] == 86400


class TestWebhookCallback:
    """Tests for webhook callback translation."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()
        self.ctx = _context()

    def test_webhook_produces_task_state(self) -> None:
        """Test webhook resume produces a callback Task state."""
        node = _wait_node("WaitWebhook", {"resume": "webhook"})
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitWebhook"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["Type"] == "Task"
        assert dumped["Resource"] == "arn:aws:states:::lambda:invoke.waitForTaskToken"

    def test_webhook_generates_lambda_artifact(self) -> None:
        """Test a Lambda artifact is generated for the webhook handler."""
        node = _wait_node("WaitWebhook", {"resume": "webhook"})
        result = self.translator.translate(node, self.ctx)

        assert len(result.lambda_artifacts) == 1
        artifact = result.lambda_artifacts[0]
        assert artifact.function_name == "WaitWebhook_webhook_handler"
        assert "send_task_success" in artifact.handler_code

    def test_webhook_generates_trigger_artifact(self) -> None:
        """Test a LAMBDA_FURL trigger artifact is generated for webhook."""
        node = _wait_node("WaitWebhook", {"resume": "webhook"})
        result = self.translator.translate(node, self.ctx)

        assert len(result.trigger_artifacts) == 1
        trigger = result.trigger_artifacts[0]
        assert trigger.trigger_type == TriggerType.LAMBDA_FURL
        assert trigger.config["handler_kind"] == "webhook"

    def test_webhook_default_timeout(self) -> None:
        """Test webhook callback uses default 24-hour timeout."""
        node = _wait_node("WaitWebhook", {"resume": "webhook"})
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitWebhook"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["TimeoutSeconds"] == 86400

    def test_webhook_metadata(self) -> None:
        """Test webhook callback metadata is set correctly."""
        node = _wait_node("WaitWebhook", {"resume": "webhook"})
        result = self.translator.translate(node, self.ctx)

        assert result.metadata["callback_node"] is True
        assert result.metadata["resume_type"] == "webhook"


class TestWaitStateUnchanged:
    """Verify non-callback Wait modes still produce WaitState."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = FlowControlTranslator()
        self.ctx = _context()

    def test_time_interval_still_produces_wait_state(self) -> None:
        """Test timeInterval resume still produces a WaitState."""
        node = _wait_node(
            "Wait10s",
            {"resume": "timeInterval", "amount": 10, "unit": "seconds"},
        )
        result = self.translator.translate(node, self.ctx)

        state = result.states["Wait10s"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["Type"] == "Wait"
        assert dumped["Seconds"] == 10
        assert len(result.lambda_artifacts) == 0
        assert len(result.trigger_artifacts) == 0

    def test_specific_time_still_produces_wait_state(self) -> None:
        """Test specificTime resume still produces a WaitState."""
        node = _wait_node(
            "WaitUntil",
            {"resume": "specificTime", "dateTime": "2025-01-01T00:00:00Z"},
        )
        result = self.translator.translate(node, self.ctx)

        state = result.states["WaitUntil"]
        dumped = state.model_dump(by_alias=True)

        assert dumped["Type"] == "Wait"
        assert dumped["Timestamp"] == "2025-01-01T00:00:00Z"
