"""Tests for PicoFun API client translator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.picofun import PicoFunTranslator
from n8n_to_sfn.translators.picofun_bridge import PicoFunBridge


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


def _picofun_node_with_mappings(
    name: str,
    params: dict[str, Any] | None = None,
    credentials: dict[str, Any] | None = None,
    api_spec: str | None = None,
    operation_mappings: dict[str, Any] | None = None,
) -> ClassifiedNode:
    """Create a PicoFun classified node with operation mappings for testing."""
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
        operation_mappings=operation_mappings,
    )


def _write_openapi3_spec(tmp_path: Path) -> str:
    """Write a minimal OpenAPI 3.0 spec and return the filename."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "paths": {
            "/messages": {
                "post": {
                    "operationId": "postMessage",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    filename = "test.json"
    (tmp_path / filename).write_text(json.dumps(spec))
    return filename


class TestPicoFunTranslatorBridge:
    """Tests for PicoFunTranslator with bridge-based code generation."""

    def test_generation_with_valid_spec(self, tmp_path: Path) -> None:
        """Valid spec and operation mappings produce handler code with picorun imports."""
        filename = _write_openapi3_spec(tmp_path)
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "postMessage", "resource": "chat"},
            api_spec=filename,
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert "picorun" in artifact.handler_code

    def test_graceful_degradation_missing_spec(self, tmp_path: Path) -> None:
        """Missing spec file produces placeholder code with warning comment."""
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "postMessage", "resource": "chat"},
            api_spec="nonexistent.json",
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert artifact.handler_code.startswith("#")
        assert "WARNING" in artifact.handler_code

    def test_graceful_degradation_unmapped_operation(self, tmp_path: Path) -> None:
        """Unknown operation produces placeholder code with warning comment."""
        filename = _write_openapi3_spec(tmp_path)
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "unknownOp", "resource": "chat"},
            api_spec=filename,
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert artifact.handler_code.startswith("#")
        assert "WARNING" in artifact.handler_code

    def test_graceful_degradation_render_error(self, tmp_path: Path) -> None:
        """PicoFun render failure produces placeholder code without propagating."""
        filename = _write_openapi3_spec(tmp_path)
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "postMessage", "resource": "chat"},
            api_spec=filename,
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        with patch.object(bridge, "render_endpoint", side_effect=RuntimeError("boom")):
            result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert artifact.handler_code.startswith("#")
        assert "WARNING" in artifact.handler_code

    def test_dependencies_populated(self, tmp_path: Path) -> None:
        """Successful generation populates dependencies with picorun stack."""
        filename = _write_openapi3_spec(tmp_path)
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "postMessage", "resource": "chat"},
            api_spec=filename,
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert artifact.dependencies == ["picorun", "requests", "aws-lambda-powertools"]

    def test_dependencies_include_boto3_with_credentials(self, tmp_path: Path) -> None:
        """Credentials on node add boto3 to dependencies."""
        filename = _write_openapi3_spec(tmp_path)
        bridge = PicoFunBridge(spec_directory=str(tmp_path))
        translator = PicoFunTranslator(bridge=bridge)
        node = _picofun_node_with_mappings(
            "Slack",
            params={"operation": "postMessage", "resource": "chat"},
            credentials={"slackApi": {"id": "1", "name": "Slack"}},
            api_spec=filename,
            operation_mappings={"chat:postMessage": "POST /messages"},
        )

        result = translator.translate(node, _context())

        artifact = result.lambda_artifacts[0]
        assert "boto3" in artifact.dependencies
