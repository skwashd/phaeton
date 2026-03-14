"""Tests for the matcher module."""

from datetime import UTC, datetime

import pytest

from n8n_release_parser.matcher import (
    calculate_spec_coverage,
    extract_base_url_from_node,
    fuzzy_match_url,
    map_operations,
    match_all_nodes,
    match_by_service_name,
    match_node_to_spec,
)
from n8n_release_parser.models import (
    ApiSpecEntry,
    ApiSpecIndex,
    CredentialType,
    NodeApiMapping,
    NodeCatalog,
    NodeTypeEntry,
    ResourceOperation,
    SpecEndpoint,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slack_spec() -> ApiSpecEntry:
    """Provide slack_spec fixture."""
    return ApiSpecEntry(
        spec_filename="slack-web-api.json",
        service_name="Slack",
        base_urls=["https://slack.com/api"],
        auth_type="oauth2",
        spec_format="openapi3",
        endpoints=[
            SpecEndpoint(
                resource="message",
                operation="postMessage",
                endpoint="POST /chat.postMessage",
            ),
            SpecEndpoint(
                resource="channel",
                operation="list",
                endpoint="GET /conversations.list",
            ),
            SpecEndpoint(
                resource="channel",
                operation="create",
                endpoint="POST /conversations.create",
            ),
        ],
    )


@pytest.fixture
def github_spec() -> ApiSpecEntry:
    """Provide github_spec fixture."""
    return ApiSpecEntry(
        spec_filename="github-rest-api.json",
        service_name="GitHub",
        base_urls=["https://api.github.com"],
        auth_type="bearer",
        spec_format="openapi3",
        endpoints=[
            SpecEndpoint(
                resource="repos",
                operation="listForUser",
                endpoint="GET /users/{username}/repos",
            ),
            SpecEndpoint(
                resource="issues",
                operation="create",
                endpoint="POST /repos/{owner}/{repo}/issues",
            ),
        ],
    )


@pytest.fixture
def spec_index(slack_spec: ApiSpecEntry, github_spec: ApiSpecEntry) -> ApiSpecIndex:
    """Provide spec_index fixture."""
    return ApiSpecIndex(
        entries=[slack_spec, github_spec],
        index_timestamp=datetime.now(tz=UTC),
    )


@pytest.fixture
def slack_node() -> NodeTypeEntry:
    """Provide slack_node fixture."""
    return NodeTypeEntry(
        node_type="n8n-nodes-base.slack",
        type_version=2,
        display_name="Slack",
        request_defaults={"baseURL": "https://slack.com/api"},
        credential_types=[CredentialType(name="slackOAuth2Api")],
        resource_operations=[
            ResourceOperation(resource="message", operation="postMessage"),
            ResourceOperation(resource="channel", operation="list"),
            ResourceOperation(resource="channel", operation="create"),
        ],
    )


@pytest.fixture
def node_no_url() -> NodeTypeEntry:
    """Provide node_no_url fixture."""
    return NodeTypeEntry(
        node_type="n8n-nodes-base.set",
        type_version=1,
        display_name="Set",
    )


@pytest.fixture
def node_unmatched() -> NodeTypeEntry:
    """Provide node_unmatched fixture."""
    return NodeTypeEntry(
        node_type="n8n-nodes-base.unknownWidget",
        type_version=1,
        display_name="Unknown Widget",
        request_defaults={"baseURL": "https://totally-unique-service.example.com/v1"},
        resource_operations=[
            ResourceOperation(resource="widget", operation="frobnicate"),
        ],
    )


# ---------------------------------------------------------------------------
# Tests for extract_base_url_from_node
# ---------------------------------------------------------------------------


class TestExtractBaseUrlFromNode:
    """Tests for ExtractBaseUrlFromNode."""

    def test_extract_base_url_from_node(self, slack_node: NodeTypeEntry) -> None:
        """Test extract base url from node."""
        url = extract_base_url_from_node(slack_node)
        assert url == "https://slack.com/api"

    def test_extract_base_url_missing(self, node_no_url: NodeTypeEntry) -> None:
        """Test extract base url missing."""
        url = extract_base_url_from_node(node_no_url)
        assert url is None

    def test_extract_base_url_from_url_key(self) -> None:
        """Test extract base url from url key."""
        node = NodeTypeEntry(
            node_type="n8n-nodes-base.httpBin",
            type_version=1,
            display_name="HTTPBin",
            request_defaults={"url": "https://httpbin.org"},
        )
        url = extract_base_url_from_node(node)
        assert url == "https://httpbin.org"


# ---------------------------------------------------------------------------
# Tests for fuzzy_match_url
# ---------------------------------------------------------------------------


class TestFuzzyMatchUrl:
    """Tests for FuzzyMatchUrl."""

    def test_fuzzy_match_url_exact(self, spec_index: ApiSpecIndex) -> None:
        """Test fuzzy match url exact."""
        results = fuzzy_match_url("https://slack.com/api", spec_index)
        assert len(results) >= 1
        assert results[0].service_name == "Slack"

    def test_fuzzy_match_url_fuzzy(self, spec_index: ApiSpecIndex) -> None:
        """Test fuzzy match url fuzzy."""
        # Slightly different URL that should still match via fuzzy
        results = fuzzy_match_url("https://slack.com/api/", spec_index, threshold=0.8)
        assert len(results) >= 1
        assert results[0].service_name == "Slack"

    def test_fuzzy_match_url_no_match(self, spec_index: ApiSpecIndex) -> None:
        """Test fuzzy match url no match."""
        results = fuzzy_match_url(
            "https://totally-unknown-service.example.com/v99",
            spec_index,
        )
        assert results == []


# ---------------------------------------------------------------------------
# Tests for match_by_service_name
# ---------------------------------------------------------------------------


class TestMatchByServiceName:
    """Tests for MatchByServiceName."""

    def test_match_by_service_name_exact(self, spec_index: ApiSpecIndex) -> None:
        """Test match by service name exact."""
        results = match_by_service_name("n8n-nodes-base.slack", spec_index)
        assert len(results) >= 1
        assert results[0].service_name == "Slack"

    def test_match_by_service_name_case_insensitive(
        self, spec_index: ApiSpecIndex
    ) -> None:
        """Test match by service name case insensitive."""
        results = match_by_service_name("n8n-nodes-base.SLACK", spec_index)
        assert len(results) >= 1
        assert results[0].service_name == "Slack"

    def test_match_by_service_name_with_suffix(self, spec_index: ApiSpecIndex) -> None:
        """Test match by service name with suffix."""
        results = match_by_service_name("n8n-nodes-base.slackApi", spec_index)
        assert len(results) >= 1
        assert results[0].service_name == "Slack"


# ---------------------------------------------------------------------------
# Tests for map_operations
# ---------------------------------------------------------------------------


class TestMapOperations:
    """Tests for MapOperations."""

    def test_map_operations_full_match(
        self, slack_node: NodeTypeEntry, slack_spec: ApiSpecEntry
    ) -> None:
        """Test map operations full match."""
        mapped, unmapped = map_operations(slack_node, slack_spec)
        assert len(mapped) == 3
        assert len(unmapped) == 0
        assert "message:postMessage" in mapped
        assert mapped["message:postMessage"] == "POST /chat.postMessage"

    def test_map_operations_partial_match(self, slack_spec: ApiSpecEntry) -> None:
        """Test map operations partial match."""
        node = NodeTypeEntry(
            node_type="n8n-nodes-base.slack",
            type_version=2,
            display_name="Slack",
            resource_operations=[
                ResourceOperation(resource="message", operation="postMessage"),
                ResourceOperation(resource="reaction", operation="add"),
            ],
        )
        mapped, unmapped = map_operations(node, slack_spec)
        # postMessage should match; reaction:add likely won't
        assert "message:postMessage" in mapped
        assert len(unmapped) >= 1
        assert "reaction:add" in unmapped


# ---------------------------------------------------------------------------
# Tests for calculate_spec_coverage
# ---------------------------------------------------------------------------


class TestCalculateSpecCoverage:
    """Tests for CalculateSpecCoverage."""

    def test_calculate_spec_coverage(self) -> None:
        """Test calculate spec coverage."""
        mapped = {
            "message:send": "POST /chat.postMessage",
            "channel:list": "GET /conversations.list",
        }
        unmapped = ["reaction:add"]
        coverage = calculate_spec_coverage(mapped, unmapped)
        assert coverage == pytest.approx(2 / 3)

    def test_coverage_all_mapped(self) -> None:
        """Test coverage all mapped."""
        mapped = {"a:b": "GET /a"}
        coverage = calculate_spec_coverage(mapped, [])
        assert coverage == pytest.approx(1.0)

    def test_coverage_none_mapped(self) -> None:
        """Test coverage none mapped."""
        coverage = calculate_spec_coverage({}, ["a:b"])
        assert coverage == pytest.approx(0.0)

    def test_coverage_empty(self) -> None:
        """Test coverage empty."""
        coverage = calculate_spec_coverage({}, [])
        assert coverage == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests for match_node_to_spec (full pipeline)
# ---------------------------------------------------------------------------


class TestMatchNodeToSpec:
    """Tests for MatchNodeToSpec."""

    def test_match_node_to_spec_full_pipeline(
        self,
        slack_node: NodeTypeEntry,
        spec_index: ApiSpecIndex,
    ) -> None:
        """Test match node to spec full pipeline."""
        mapping = match_node_to_spec(slack_node, spec_index)
        assert mapping is not None
        assert isinstance(mapping, NodeApiMapping)
        assert mapping.node_type == "n8n-nodes-base.slack"
        assert mapping.api_spec == "slack-web-api.json"
        assert mapping.spec_format == "openapi3"
        assert mapping.auth_type == "oauth2"
        assert mapping.credential_type == "slackOAuth2Api"
        assert mapping.spec_coverage > 0.0
        assert len(mapping.operation_mappings) > 0

    def test_match_node_to_spec_no_match(
        self,
        node_unmatched: NodeTypeEntry,
        spec_index: ApiSpecIndex,
    ) -> None:
        """Test match node to spec no match."""
        mapping = match_node_to_spec(node_unmatched, spec_index)
        # No URL match and no name match => None
        assert mapping is None

    def test_match_node_to_spec_name_fallback(
        self,
        spec_index: ApiSpecIndex,
    ) -> None:
        """When there's no URL, matching falls back to service name."""
        node = NodeTypeEntry(
            node_type="n8n-nodes-base.slack",
            type_version=1,
            display_name="Slack",
            resource_operations=[
                ResourceOperation(resource="message", operation="postMessage"),
            ],
        )
        mapping = match_node_to_spec(node, spec_index)
        assert mapping is not None
        assert mapping.api_spec == "slack-web-api.json"


# ---------------------------------------------------------------------------
# Tests for match_all_nodes
# ---------------------------------------------------------------------------


class TestMatchAllNodes:
    """Tests for MatchAllNodes."""

    def test_match_all_nodes(
        self,
        slack_node: NodeTypeEntry,
        node_no_url: NodeTypeEntry,
        spec_index: ApiSpecIndex,
    ) -> None:
        """Test match all nodes."""
        catalog = NodeCatalog(
            n8n_version="1.20.0",
            release_date=datetime.now(tz=UTC),
            entries=[slack_node, node_no_url],
        )
        mappings = match_all_nodes(catalog, spec_index)
        # slack_node should match; node_no_url (Set) should not
        assert len(mappings) >= 1
        matched_types = [m.node_type for m in mappings]
        assert "n8n-nodes-base.slack" in matched_types
