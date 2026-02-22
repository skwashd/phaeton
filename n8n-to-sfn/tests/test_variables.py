"""Tests for cross-node variable translator (Category B)."""

from n8n_to_sfn.models.analysis import (
    ClassifiedExpression,
    ClassifiedNode,
    ExpressionCategory,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.n8n import N8nNode
from n8n_to_sfn.translators.variables import resolve_cross_node_references


def _node(name, classification=NodeClassification.FLOW_CONTROL):
    return N8nNode(
        id=name, name=name, type="n8n-nodes-base.set", type_version=1, position=[0, 0]
    )


def _cat_b_expr(original, refs=None):
    return ClassifiedExpression(
        original=original,
        category=ExpressionCategory.REQUIRES_VARIABLES,
        node_references=refs or [],
        parameter_path="parameters.value",
    )


class TestVariableResolution:
    def test_single_cross_node_reference(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Lookup"),
                    classification=NodeClassification.AWS_NATIVE,
                ),
                ClassifiedNode(
                    node=_node("Use"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('Lookup').first().json.id }}", ["Lookup"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "Lookup" in result.assignments
        assert "lookupResult" in result.assignments["Lookup"]
        original = "{{ $('Lookup').first().json.id }}"
        assert original in result.expression_replacements
        assert result.expression_replacements[original] == "{% $lookupResult.id %}"

    def test_multiple_references_same_node(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Source"),
                    classification=NodeClassification.AWS_NATIVE,
                ),
                ClassifiedNode(
                    node=_node("Consumer"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('Source').first().json.name }}", ["Source"]),
                        _cat_b_expr("{{ $('Source').first().json.email }}", ["Source"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        # Only one Assign block for Source
        assert len(result.assignments) == 1
        assert "Source" in result.assignments
        # Two replacements
        assert len(result.expression_replacements) == 2

    def test_references_to_different_nodes(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("A"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("B"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("C"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('A').first().json.x }}", ["A"]),
                        _cat_b_expr("{{ $('B').first().json.y }}", ["B"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "A" in result.assignments
        assert "B" in result.assignments
        assert len(result.assignments) == 2

    def test_variable_name_collision(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Lookup"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("Lookup!"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("X"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('Lookup').first().json.a }}", ["Lookup"]),
                        _cat_b_expr("{{ $('Lookup!').first().json.b }}", ["Lookup!"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        var_names = set()
        for assign_dict in result.assignments.values():
            var_names.update(assign_dict.keys())
        # Should have two distinct variable names
        assert len(var_names) == 2

    def test_execution_id_mapping(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Node"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $execution.id }}"),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "{{ $execution.id }}" in result.expression_replacements
        assert (
            result.expression_replacements["{{ $execution.id }}"]
            == "{% $states.context.Execution.Id %}"
        )

    def test_legacy_node_syntax(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Old"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("Consumer"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr('{{ $node["Old"].json.val }}', ["Old"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "Old" in result.assignments
        original = '{{ $node["Old"].json.val }}'
        assert original in result.expression_replacements
        assert "oldResult" in result.expression_replacements[original]

    def test_last_accessor(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Data"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("Use"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('Data').last().json.value }}", ["Data"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "Data" in result.assignments
        original = "{{ $('Data').last().json.value }}"
        assert original in result.expression_replacements

    def test_all_accessor(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("List"), classification=NodeClassification.AWS_NATIVE
                ),
                ClassifiedNode(
                    node=_node("Agg"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        _cat_b_expr("{{ $('List').all() }}", ["List"]),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert "List" in result.assignments

    def test_no_category_b_expressions(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                ClassifiedNode(
                    node=_node("Node"),
                    classification=NodeClassification.FLOW_CONTROL,
                    expressions=[
                        ClassifiedExpression(
                            original="{{ $json.name }}",
                            category=ExpressionCategory.JSONATA_DIRECT,
                        ),
                    ],
                ),
            ],
            dependency_edges=[],
        )
        result = resolve_cross_node_references(analysis)
        assert result.assignments == {}
        assert result.expression_replacements == {}
