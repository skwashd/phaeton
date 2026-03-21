"""
Contract tests: Component 2 (Analyzer) -> Component 3 (Translator).

Verifies that ConversionReport output can be deserialized by the adapter
and converted to a valid WorkflowAnalysis, covering:
- JSON round-trip serialization across the boundary
- Enum value compatibility between NodeCategory and NodeClassification
- Expression category mapping
- Field name and structural transformations
"""

from __future__ import annotations

from phaeton_models.adapters.analyzer_to_translator import (
    convert_report_to_analysis,
)
from phaeton_models.analyzer import (
    ConversionReport,
    NodeCategory,
)
from phaeton_models.analyzer import (
    ExpressionCategory as AnalyzerExpressionCategory,
)
from phaeton_models.translator import (
    ExpressionCategory as TranslatorExpressionCategory,
)
from phaeton_models.translator import (
    NodeClassification,
    WorkflowAnalysis,
)


class TestJsonRoundTrip:
    """ConversionReport survives JSON serialization across the boundary."""

    def test_report_serializes_and_adapter_accepts(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Serialize report to JSON, deserialize, then convert via adapter."""
        json_data = sample_conversion_report.model_dump(mode="json")
        restored = ConversionReport.model_validate(json_data)
        analysis = convert_report_to_analysis(restored)
        assert isinstance(analysis, WorkflowAnalysis)

    def test_report_json_string_round_trip(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Verify JSON string serialization fidelity."""
        json_str = sample_conversion_report.model_dump_json()
        restored = ConversionReport.model_validate_json(json_str)
        analysis = convert_report_to_analysis(restored)
        assert isinstance(analysis, WorkflowAnalysis)
        assert len(analysis.classified_nodes) == len(
            sample_conversion_report.classified_nodes,
        )

    def test_analysis_output_is_valid_pydantic(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """WorkflowAnalysis produced by adapter is itself serializable."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        json_data = analysis.model_dump(mode="json")
        restored = WorkflowAnalysis.model_validate(json_data)
        assert restored.confidence_score == analysis.confidence_score


class TestNodeCategoryEnumMapping:
    """Every NodeCategory value has a corresponding NodeClassification."""

    def test_all_node_categories_map_to_classifications(self) -> None:
        """Adapter must handle every NodeCategory value."""
        for cat in NodeCategory:
            assert cat.value in [nc.value for nc in NodeClassification], (
                f"NodeCategory.{cat.name} ({cat.value!r}) has no matching "
                f"NodeClassification"
            )

    def test_all_classifications_have_source_category(self) -> None:
        """Every NodeClassification should originate from a NodeCategory."""
        for nc in NodeClassification:
            assert nc.value in [cat.value for cat in NodeCategory], (
                f"NodeClassification.{nc.name} ({nc.value!r}) has no matching "
                f"NodeCategory"
            )

    def test_category_to_classification_via_adapter(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Verify adapter maps each node's category correctly."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        for orig, converted in zip(
            sample_conversion_report.classified_nodes,
            analysis.classified_nodes,
            strict=True,
        ):
            assert converted.classification.value == orig.category.value


class TestExpressionCategoryMapping:
    """Expression categories bridge correctly across the boundary."""

    def test_jsonata_direct_maps_to_jsonata_direct(self) -> None:
        """JSONATA_DIRECT is preserved across the boundary."""
        assert AnalyzerExpressionCategory.JSONATA_DIRECT.value == (
            TranslatorExpressionCategory.JSONATA_DIRECT.value
        )

    def test_variable_reference_maps_to_requires_variables(self) -> None:
        """VARIABLE_REFERENCE becomes REQUIRES_VARIABLES."""
        assert AnalyzerExpressionCategory.VARIABLE_REFERENCE.value != (
            TranslatorExpressionCategory.REQUIRES_VARIABLES.value
        )

    def test_lambda_required_maps_to_requires_lambda(self) -> None:
        """LAMBDA_REQUIRED becomes REQUIRES_LAMBDA."""
        assert AnalyzerExpressionCategory.LAMBDA_REQUIRED.value != (
            TranslatorExpressionCategory.REQUIRES_LAMBDA.value
        )

    def test_expression_categories_fully_covered_by_adapter(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Adapter handles all three expression categories in fixture."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        categories_seen = set()
        for node in analysis.classified_nodes:
            for expr in node.expressions:
                categories_seen.add(expr.category)
        assert TranslatorExpressionCategory.JSONATA_DIRECT in categories_seen
        assert TranslatorExpressionCategory.REQUIRES_VARIABLES in categories_seen
        assert TranslatorExpressionCategory.REQUIRES_LAMBDA in categories_seen


class TestFieldMapping:
    """Field names and structures transform correctly across the boundary."""

    def test_raw_expression_becomes_original(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """ClassifiedExpression.raw_expression maps to .original."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        all_originals = [
            expr.original
            for node in analysis.classified_nodes
            for expr in node.expressions
        ]
        all_raw = [
            expr.raw_expression
            for expr in sample_conversion_report.classified_expressions
        ]
        assert sorted(all_originals) == sorted(all_raw)

    def test_referenced_nodes_becomes_node_references(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """ClassifiedExpression.referenced_nodes maps to .node_references."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        all_refs = [
            ref
            for node in analysis.classified_nodes
            for expr in node.expressions
            for ref in expr.node_references
        ]
        assert "Transform" in all_refs

    def test_expressions_redistributed_to_nodes(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Top-level expressions are grouped by node_name into per-node lists."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        node_map = {n.node.name: n for n in analysis.classified_nodes}
        # DynamoDB Put had 2 expressions, Transform had 1
        assert len(node_map["DynamoDB Put"].expressions) == 2
        assert len(node_map["Transform"].expressions) == 1

    def test_payload_warnings_become_strings(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """PayloadWarning objects become formatted strings."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        assert len(analysis.payload_warnings) == len(
            sample_conversion_report.payload_warnings,
        )
        for warning in analysis.payload_warnings:
            assert isinstance(warning, str)
            assert ":" in warning  # format: "node_name: description"

    def test_unsupported_nodes_become_names(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Unsupported ClassifiedNodes become a list of node name strings."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        assert analysis.unsupported_nodes == ["Unsupported"]

    def test_confidence_score_preserved(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Confidence score passes through unchanged."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        assert analysis.confidence_score == sample_conversion_report.confidence_score


class TestDependencyEdgeParsing:
    """Graph metadata converts to typed DependencyEdge objects."""

    def test_edges_parsed_from_graph_metadata(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Both from_node/to_node and source_node/target_node variants work."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        assert len(analysis.dependency_edges) == 2
        edge_names = [(e.from_node, e.to_node) for e in analysis.dependency_edges]
        assert ("Schedule Trigger", "DynamoDB Put") in edge_names
        assert ("Transform", "DynamoDB Put") in edge_names

    def test_edge_types_uppercased(
        self,
        sample_conversion_report: ConversionReport,
    ) -> None:
        """Edge type strings normalize to uppercase literals."""
        analysis = convert_report_to_analysis(sample_conversion_report)
        for edge in analysis.dependency_edges:
            assert edge.edge_type in ("CONNECTION", "DATA_REFERENCE")


class TestSchemaCompatibility:
    """JSON schema produced by Component 2 is consumable by Component 3 adapter."""

    def test_report_schema_includes_all_required_fields(self) -> None:
        """ConversionReport schema has fields the adapter reads."""
        schema = ConversionReport.model_json_schema()
        required = schema.get("required", [])
        adapter_reads = [
            "classified_nodes",
            "classified_expressions",
            "payload_warnings",
            "unsupported_nodes",
            "confidence_score",
            "graph_metadata",
        ]
        for field in adapter_reads:
            assert field in required, (
                f"ConversionReport missing required field {field!r}"
            )

    def test_analysis_schema_covers_adapter_output(self) -> None:
        """WorkflowAnalysis schema matches what the adapter produces."""
        schema = WorkflowAnalysis.model_json_schema()
        props = schema.get("properties", {})
        expected_fields = [
            "classified_nodes",
            "dependency_edges",
            "variables_needed",
            "payload_warnings",
            "unsupported_nodes",
            "confidence_score",
        ]
        for field in expected_fields:
            assert field in props, f"WorkflowAnalysis missing field {field!r}"
