"""Tests for HTTP Request node translator."""

from __future__ import annotations

from phaeton_models.translator import (
    ClassifiedNode,
    NodeClassification,
    WorkflowAnalysis,
)

from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.base import TranslationContext
from n8n_to_sfn.translators.http_request import HttpRequestTranslator


def _http_node(
    name: str = "HTTP Request",
    params: dict | None = None,
    credentials: dict | None = None,
) -> ClassifiedNode:
    """Create an HTTP Request classified node for testing."""
    return ClassifiedNode(
        node=N8nNode(  # type: ignore[missing-argument]
            id=name,
            name=name,
            type="n8n-nodes-base.httpRequest",
            type_version=1,  # type: ignore[unknown-argument]
            position=[0, 0],
            parameters=params or {},
            credentials=credentials,
        ),
        classification=NodeClassification.PICOFUN_API,
    )


def _context(workflow_name: str = "test-workflow") -> TranslationContext:
    """Create a translation context for testing."""
    return TranslationContext(
        analysis=WorkflowAnalysis(classified_nodes=[], dependency_edges=[]),
        workflow_name=workflow_name,
    )


class TestHttpRequestTranslatorCanTranslate:
    """Tests for can_translate routing."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_can_translate_http_request(self) -> None:
        """Test can_translate returns True for httpRequest nodes."""
        node = _http_node()
        assert self.translator.can_translate(node)

    def test_cannot_translate_other_node(self) -> None:
        """Test can_translate returns False for non-httpRequest nodes."""
        node = ClassifiedNode(
            node=N8nNode(  # type: ignore[missing-argument]
                id="x",
                name="x",
                type="n8n-nodes-base.slack",
                type_version=1,
                position=[0, 0],  # type: ignore[unknown-argument]
            ),
            classification=NodeClassification.PICOFUN_API,
        )
        assert not self.translator.can_translate(node)


class TestSimpleRequests:
    """Tests for simple HTTP request translation without auth."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_simple_get(self) -> None:
        """Test simple GET request translation."""
        node = _http_node(
            params={"url": "https://api.example.com/data", "method": "GET"}
        )
        result = self.translator.translate(node, _context())

        assert "HTTP Request" in result.states
        state = result.states["HTTP Request"]
        assert state.resource == "arn:aws:states:::http:invoke"
        assert state.arguments is not None
        assert state.arguments["ApiEndpoint"] == "https://api.example.com/data"
        assert state.arguments["Method"] == "GET"

    def test_default_method_is_get(self) -> None:
        """Test that default method is GET when not specified."""
        node = _http_node(params={"url": "https://api.example.com"})
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert state.arguments["Method"] == "GET"

    def test_post_with_json_body(self) -> None:
        """Test POST request with JSON body."""
        node = _http_node(
            params={
                "url": "https://api.example.com/items",
                "method": "POST",
                "jsonBody": '{"name": "test", "value": 42}',
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert state.arguments["Method"] == "POST"
        assert state.arguments["RequestBody"] == '{"name": "test", "value": 42}'

    def test_put_method(self) -> None:
        """Test PUT method translation."""
        node = _http_node(
            params={
                "url": "https://api.example.com/items/1",
                "method": "PUT",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert state.arguments["Method"] == "PUT"

    def test_delete_method(self) -> None:
        """Test DELETE method translation."""
        node = _http_node(
            params={
                "url": "https://api.example.com/items/1",
                "method": "DELETE",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert state.arguments["Method"] == "DELETE"

    def test_patch_method(self) -> None:
        """Test PATCH method translation."""
        node = _http_node(
            params={
                "url": "https://api.example.com/items/1",
                "method": "PATCH",
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert state.arguments["Method"] == "PATCH"


class TestHeadersAndQueryParams:
    """Tests for custom headers and query parameters."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_custom_headers(self) -> None:
        """Test custom headers are mapped correctly."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "headerParameters": {
                    "parameters": [
                        {"name": "Content-Type", "value": "application/json"},
                        {"name": "X-Custom", "value": "hello"},
                    ],
                },
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        headers = state.arguments["Headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Custom"] == "hello"

    def test_query_parameters(self) -> None:
        """Test query parameters are mapped correctly."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "queryParameters": {
                    "parameters": [
                        {"name": "page", "value": "1"},
                        {"name": "limit", "value": "50"},
                    ],
                },
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        query = state.arguments["QueryParameters"]
        assert query["page"] == "1"
        assert query["limit"] == "50"

    def test_body_parameters(self) -> None:
        """Test form-style body parameters are mapped correctly."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "method": "POST",
                "bodyParameters": {
                    "parameters": [
                        {"name": "field1", "value": "value1"},
                        {"name": "field2", "value": "value2"},
                    ],
                },
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        body = state.arguments["RequestBody"]
        assert body["field1"] == "value1"
        assert body["field2"] == "value2"

    def test_no_headers_when_empty(self) -> None:
        """Test that Headers key is absent when no headers provided."""
        node = _http_node(params={"url": "https://api.example.com"})
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "Headers" not in state.arguments

    def test_no_body_when_empty(self) -> None:
        """Test that RequestBody key is absent when no body provided."""
        node = _http_node(params={"url": "https://api.example.com"})
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "RequestBody" not in state.arguments


class TestBearerTokenAuth:
    """Tests for bearer token authentication."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_bearer_token_auth(self) -> None:
        """Test bearer token auth creates credential artifact and header."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
            },
            credentials={"httpHeaderAuth": {"id": "1"}},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "httpHeaderAuth"
        assert cred.auth_type == "api_key"
        assert "/n8n-sfn/test-workflow/" in cred.parameter_path

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "Authorization" in state.arguments["Headers"]


class TestApiKeyAuth:
    """Tests for API key authentication via query parameters."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_query_auth(self) -> None:
        """Test API key auth via query parameter."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpQueryAuth",
            },
            credentials={"httpQueryAuth": {"id": "1"}},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "httpQueryAuth"
        assert cred.auth_type == "api_key"

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "api_key" in state.arguments["QueryParameters"]


class TestOAuth2Auth:
    """Tests for OAuth2 authentication."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_oauth2_auth(self) -> None:
        """Test OAuth2 auth creates credential artifact with connection ARN."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "googleOAuth2Api",
            },
            credentials={"googleOAuth2Api": {"id": "1"}},
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 1
        cred = result.credential_artifacts[0]
        assert cred.credential_type == "googleOAuth2Api"
        assert cred.auth_type == "oauth2"
        assert "/n8n-sfn/test-workflow/" in cred.parameter_path

        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "Authentication" in state.arguments

    def test_predefined_non_oauth(self) -> None:
        """Test predefined credential type without oauth in name."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "slackApi",
            },
            credentials={"slackApi": {"id": "1"}},
        )
        result = self.translator.translate(node, _context())

        cred = result.credential_artifacts[0]
        assert cred.auth_type == "api_key"


class TestNoAuth:
    """Tests for requests without authentication."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_no_auth(self) -> None:
        """Test request without authentication has no credential artifacts."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "none",
            }
        )
        result = self.translator.translate(node, _context())

        assert len(result.credential_artifacts) == 0
        state = result.states["HTTP Request"]
        assert state.arguments is not None
        assert "Authentication" not in state.arguments


class TestRetryAndErrorHandling:
    """Tests for default retry and error handling."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_default_retry_present(self) -> None:
        """Test default retry configuration is present."""
        node = _http_node(params={"url": "https://api.example.com"})
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        assert state.retry is not None
        assert len(state.retry) > 0
        assert state.retry[0].error_equals == ["States.TaskFailed"]


class TestAslValidity:
    """Tests for generated ASL validity."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.translator = HttpRequestTranslator()

    def test_serialized_state_has_required_fields(self) -> None:
        """Test that serialized state contains required ASL fields."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "method": "POST",
                "jsonBody": '{"key": "value"}',
            }
        )
        result = self.translator.translate(node, _context())

        state = result.states["HTTP Request"]
        serialized = state.model_dump(by_alias=True)
        assert serialized["Type"] == "Task"
        assert serialized["Resource"] == "arn:aws:states:::http:invoke"
        assert "Arguments" in serialized
        assert serialized["Arguments"]["ApiEndpoint"] == "https://api.example.com"
        assert serialized["Arguments"]["Method"] == "POST"

    def test_ssm_path_convention(self) -> None:
        """Test SSM path follows project convention."""
        node = _http_node(
            params={
                "url": "https://api.example.com",
                "authentication": "genericCredentialType",
                "genericAuthType": "httpHeaderAuth",
            },
            credentials={"httpHeaderAuth": {"id": "1"}},
        )
        result = self.translator.translate(node, _context("My Workflow"))

        cred = result.credential_artifacts[0]
        assert cred.parameter_path == "/n8n-sfn/my-workflow/httpHeaderAuth"
