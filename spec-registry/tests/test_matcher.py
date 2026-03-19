"""Tests for the matcher module."""

from __future__ import annotations

from phaeton_models.spec import ApiSpecEntry, ApiSpecIndex

from spec_registry.matcher import match_all_nodes, match_node_type


class TestMatchNodeTypeByFilename:
    """Tests for matching node types via spec filename convention."""

    def test_exact_filename_match(self, spec_index: ApiSpecIndex) -> None:
        """Node type matches spec filename with same service segment."""
        result = match_node_type("n8n-nodes-base.slack", spec_index)
        assert result is not None
        assert result.service_name == "Slack"

    def test_case_insensitive_match(self, spec_index: ApiSpecIndex) -> None:
        """Filename matching is case-insensitive."""
        result = match_node_type("n8n-nodes-base.SLACK", spec_index)
        assert result is not None
        assert result.service_name == "Slack"

    def test_github_match(self, spec_index: ApiSpecIndex) -> None:
        """GitHub node type matches the GitHub spec entry."""
        result = match_node_type("n8n-nodes-base.github", spec_index)
        assert result is not None
        assert result.service_name == "GitHub"

    def test_suffix_stripping(self, spec_index: ApiSpecIndex) -> None:
        """Common suffixes like 'Api' are stripped before matching."""
        result = match_node_type("n8n-nodes-base.slackApi", spec_index)
        assert result is not None
        assert result.service_name == "Slack"


class TestMatchNodeTypeByServiceName:
    """Tests for fallback matching via service name."""

    def test_service_name_fallback(self) -> None:
        """When filename doesn't match, falls back to service_name."""
        index = ApiSpecIndex(
            entries=[
                ApiSpecEntry(
                    spec_filename="some-random-name.json",
                    service_name="Slack",
                    base_urls=[],
                    auth_type="oauth2",
                    spec_format="openapi3",
                ),
            ],
        )
        result = match_node_type("n8n-nodes-base.slack", index)
        assert result is not None
        assert result.service_name == "Slack"


class TestMatchNodeTypeNoMatch:
    """Tests for non-matching node types."""

    def test_no_match(self, spec_index: ApiSpecIndex) -> None:
        """Unknown node types return None."""
        result = match_node_type("n8n-nodes-base.unknownWidget", spec_index)
        assert result is None

    def test_empty_index(self) -> None:
        """Empty index always returns None."""
        index = ApiSpecIndex(entries=[])
        result = match_node_type("n8n-nodes-base.slack", index)
        assert result is None


class TestMatchAllNodes:
    """Tests for batch matching."""

    def test_match_all_nodes(self, spec_index: ApiSpecIndex) -> None:
        """Batch match returns only successful matches."""
        node_types = [
            "n8n-nodes-base.slack",
            "n8n-nodes-base.set",
            "n8n-nodes-base.github",
        ]
        results = match_all_nodes(node_types, spec_index)

        assert "n8n-nodes-base.slack" in results
        assert results["n8n-nodes-base.slack"].service_name == "Slack"
        assert "n8n-nodes-base.github" in results
        assert results["n8n-nodes-base.github"].service_name == "GitHub"
        # "set" has no matching spec
        assert "n8n-nodes-base.set" not in results

    def test_match_all_nodes_empty(self, spec_index: ApiSpecIndex) -> None:
        """Empty input yields empty output."""
        results = match_all_nodes([], spec_index)
        assert results == {}

    def test_partial_match(self, spec_index: ApiSpecIndex) -> None:
        """Only matching node types appear in results."""
        node_types = ["n8n-nodes-base.unknownWidget", "n8n-nodes-base.slack"]
        results = match_all_nodes(node_types, spec_index)
        assert len(results) == 1
        assert "n8n-nodes-base.slack" in results
