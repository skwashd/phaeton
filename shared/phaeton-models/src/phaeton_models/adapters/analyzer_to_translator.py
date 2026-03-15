"""
Adapter converting workflow-analyzer output to translation engine input.

Bridges the contract gap between Component 2 (``ConversionReport``) and
Component 3 (``WorkflowAnalysis``) by mapping field names, enum values,
and structural differences.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from phaeton_models.analyzer import (
    ClassifiedExpression as AnalyzerClassifiedExpression,
)
from phaeton_models.analyzer import (
    ClassifiedNode as AnalyzerClassifiedNode,
)
from phaeton_models.analyzer import (
    ConversionReport,
)
from phaeton_models.analyzer import (
    ExpressionCategory as AnalyzerExpressionCategory,
)
from phaeton_models.translator import (
    ClassifiedExpression as SfnClassifiedExpression,
)
from phaeton_models.translator import (
    ClassifiedNode as SfnClassifiedNode,
)
from phaeton_models.translator import (
    DependencyEdge as SfnDependencyEdge,
)
from phaeton_models.translator import (
    ExpressionCategory as SfnExpressionCategory,
)
from phaeton_models.translator import (
    NodeClassification,
    WorkflowAnalysis,
)

_EXPRESSION_CATEGORY_MAP: dict[AnalyzerExpressionCategory, SfnExpressionCategory] = {
    AnalyzerExpressionCategory.JSONATA_DIRECT: SfnExpressionCategory.JSONATA_DIRECT,
    AnalyzerExpressionCategory.VARIABLE_REFERENCE: SfnExpressionCategory.REQUIRES_VARIABLES,
    AnalyzerExpressionCategory.LAMBDA_REQUIRED: SfnExpressionCategory.REQUIRES_LAMBDA,
}

_EDGE_TYPE_MAP: dict[str, str] = {
    "connection": "CONNECTION",
    "data_reference": "DATA_REFERENCE",
}


def convert_report_to_analysis(report: ConversionReport) -> WorkflowAnalysis:
    """
    Convert a ``ConversionReport`` into a ``WorkflowAnalysis``.

    Maps all field names, enum values, and structural differences between the
    two models. Top-level ``classified_expressions`` are redistributed to
    per-node expression lists.

    Parameters
    ----------
    report:
        The conversion feasibility report produced by the workflow analyzer.

    Returns
    -------
    WorkflowAnalysis
        The analysis model expected by the translation engine.

    """
    expressions_by_node = _group_expressions_by_node(report.classified_expressions)
    classified_nodes = [
        _convert_node(cn, expressions_by_node.get(cn.node.name, []))
        for cn in report.classified_nodes
    ]
    dependency_edges = _parse_dependency_edges(report.graph_metadata)
    payload_warnings = [
        f"{w.node_name}: {w.description}" for w in report.payload_warnings
    ]
    unsupported_nodes = [cn.node.name for cn in report.unsupported_nodes]

    return WorkflowAnalysis(
        classified_nodes=classified_nodes,
        dependency_edges=dependency_edges,
        variables_needed={},
        payload_warnings=payload_warnings,
        unsupported_nodes=unsupported_nodes,
        confidence_score=report.confidence_score,
    )


def _convert_node(
    cn: AnalyzerClassifiedNode,
    expressions: list[AnalyzerClassifiedExpression],
) -> SfnClassifiedNode:
    """Map an analyzer ``ClassifiedNode`` to the translator format."""
    classification = NodeClassification(cn.category.value)
    converted_expressions = [_convert_expression(expr) for expr in expressions]
    return SfnClassifiedNode(
        node=cn.node,
        classification=classification,
        expressions=converted_expressions,
    )


def _convert_expression(
    expr: AnalyzerClassifiedExpression,
) -> SfnClassifiedExpression:
    """Map an analyzer ``ClassifiedExpression`` to the translator format."""
    return SfnClassifiedExpression(
        original=expr.raw_expression,
        category=_EXPRESSION_CATEGORY_MAP[expr.category],
        node_references=expr.referenced_nodes,
        parameter_path=expr.parameter_path,
    )


def _group_expressions_by_node(
    expressions: list[AnalyzerClassifiedExpression],
) -> dict[str, list[AnalyzerClassifiedExpression]]:
    """Group classified expressions by their originating node name."""
    by_node: dict[str, list[AnalyzerClassifiedExpression]] = defaultdict(list)
    for expr in expressions:
        by_node[expr.node_name].append(expr)
    return dict(by_node)


def _parse_dependency_edges(
    graph_metadata: dict[str, Any],
) -> list[SfnDependencyEdge]:
    """Extract dependency edges from graph metadata if present."""
    raw_edges = graph_metadata.get("edges", [])
    edges: list[SfnDependencyEdge] = []
    for raw in raw_edges:
        edge_type_raw = raw.get("edge_type", "connection")
        edge_type = _EDGE_TYPE_MAP.get(edge_type_raw, edge_type_raw.upper())
        edges.append(
            SfnDependencyEdge(
                from_node=raw.get("from_node", raw.get("source_node", "")),
                to_node=raw.get("to_node", raw.get("target_node", "")),
                edge_type=edge_type,
                output_index=raw.get("output_index"),
            )
        )
    return edges
