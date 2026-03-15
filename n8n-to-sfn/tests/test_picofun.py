"""Tests for PicoFun API client translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.picofun import PicoFunTranslator


def _picofun_node(
    name: str,
    params: dict | None = None,
    credentials: dict | None = None,
    api_spec: str | None = None,
) -> ClassifiedNode:
    """Create a PicoFun classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.slack",
            type_version=1,
            position=[0, 0],
            parameters=params or {},
            credentials=credentials,
        ),
        classification=NodeClassification.PICOFUN_API,
        api_spec=api_spec,
    )


def _context(workflow_name: str = "test-workflow") -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


class TestPicoFunTranslator:
    """Tests for PicoFunTranslator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = PicoFunTranslator()

    def test_can_translate(self) -> None:
        """Test can_translate returns True for PicoFun nodes."""
        node = _picofun_node("Slack")
        assert self.translator.can_translate(node)

    def test_cannot_translate_other(self) -> None:
        """Test can_translate returns False for non-PicoFun nodes."""
        node = ClassifiedNode(
            node=N8nNode(id="x", name="x", type="x", type_version=1, position=[0, 0]),
            classification=NodeClassification.FLOW_CONTROL,
        )
        assert not self.translator.can_translate(node)

    def test_api_key_auth(self) -> None:
        """Test API key auth credential artifact."""
        node = _picofun_node(
            "Slack",
            params={
                "operation": "postMessage",
                "resource": "chat",
                "channel": "#general",
            },
            credentials={"slackApi": {"id": "1", "name": "Slack"}},
            api_spec="slack-api.yaml",
        )
        result = self.translator.translate(node, _context())
        assert "Slack" in result.states
        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "slackApi"
        assert cred.auth_type == "api_key"
        assert "/n8n-sfn/" in cred.parameter_path

    def test_oauth2_auth(self) -> None:
        """Test OAuth2 auth credential artifact."""
        node = _picofun_node(
            "Salesforce",
            params={"operation": "get", "resource": "contact"},
            credentials={"salesforceOAuth2Api": {"id": "1", "name": "SF"}},
        )
        result = self.translator.translate(node, _context())
        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.auth_type == "oauth2"

    def test_parameter_mapping(self) -> None:
        """Test parameter mapping in state arguments."""
        node = _picofun_node(
            "API",
            params={"operation": "get", "resource": "user", "userId": "123"},
        )
        result = self.translator.translate(node, _context())
        state = result.states["API"]
        assert state.arguments is not None
        assert state.arguments["Payload"]["parameters"]["userId"] == "123"

    def test_ssm_path_convention(self) -> None:
        """Test SSM path convention for credentials."""
        node = _picofun_node(
            "Node",
            params={},
            credentials={"myApi": {"id": "1"}},
        )
        result = self.translator.translate(node, _context("My Workflow"))
        cred = result.credential_artifacts[0]
        assert cred.parameter_path == "/n8n-sfn/my-workflow/myApi"

    def test_default_retry_present(self) -> None:
        """Test default retry is present."""
        node = _picofun_node("R", params={})
        result = self.translator.translate(node, _context())
        state = result.states["R"]
        assert state.retry is not None
        assert len(state.retry) > 0

    def test_lambda_artifact_created(self) -> None:
        """Test lambda artifact is created."""
        node = _picofun_node("L", params={}, api_spec="api.yaml")
        result = self.translator.translate(node, _context())
        assert len(result.lambda_artifacts) == 1
        artifact = result.lambda_artifacts[0]
        assert "picofun" in artifact.function_name
        assert "api.yaml" in artifact.handler_code
