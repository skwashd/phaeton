"""Tests for items model adapter."""

from n8n_to_sfn.items_adapter import ItemsModelAdapter, ItemsPattern
from n8n_to_sfn.models.analysis import (
    ClassifiedNode,
    DependencyEdge,
    NodeClassification,
    WorkflowAnalysis,
)
from n8n_to_sfn.models.n8n import N8nNode


def _node(name, params=None, classification=NodeClassification.AWS_NATIVE):
    return ClassifiedNode(
        node=N8nNode(
            id=name,
            name=name,
            type="n8n-nodes-base.awsS3",
            type_version=1,
            position=[0, 0],
            parameters=params or {},
        ),
        classification=classification,
    )


class TestItemsModelAdapter:
    def setup_method(self):
        self.adapter = ItemsModelAdapter()

    def test_single_item_pattern_for_simple_chain(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="B", edge_type="CONNECTION"),
            ],
        )
        segments = self.adapter.analyze(analysis)
        assert len(segments) == 1
        assert segments[0].pattern == ItemsPattern.SINGLE_ITEM
        assert set(segments[0].node_names) == {"A", "B"}

    def test_list_processing_pattern_getall(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("ListItems", params={"operation": "getAll"}),
                _node("Process"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="ListItems", to_node="Process", edge_type="CONNECTION"
                ),
            ],
        )
        segments = self.adapter.analyze(analysis)
        list_segs = [s for s in segments if s.pattern == ItemsPattern.LIST_PROCESSING]
        assert len(list_segs) == 1
        assert list_segs[0].root_node == "ListItems"
        assert "Process" in list_segs[0].node_names

    def test_list_processing_pattern_search(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("Search", params={"operation": "search"}),
            ],
            dependency_edges=[],
        )
        segments = self.adapter.analyze(analysis)
        list_segs = [s for s in segments if s.pattern == ItemsPattern.LIST_PROCESSING]
        assert len(list_segs) == 1
        assert list_segs[0].root_node == "Search"

    def test_list_processing_includes_downstream_chain(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("Query", params={"operation": "query"}),
                _node("Transform"),
                _node("Save"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="Query", to_node="Transform", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="Transform", to_node="Save", edge_type="CONNECTION"
                ),
            ],
        )
        segments = self.adapter.analyze(analysis)
        list_segs = [s for s in segments if s.pattern == ItemsPattern.LIST_PROCESSING]
        assert len(list_segs) == 1
        assert list_segs[0].node_names == ["Query", "Transform", "Save"]

    def test_multi_branch_merge_pattern(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("BranchA"),
                _node("BranchB"),
                _node("Merge"),
            ],
            dependency_edges=[
                DependencyEdge(
                    from_node="BranchA", to_node="Merge", edge_type="CONNECTION"
                ),
                DependencyEdge(
                    from_node="BranchB", to_node="Merge", edge_type="CONNECTION"
                ),
            ],
        )
        segments = self.adapter.analyze(analysis)
        merge_segs = [
            s for s in segments if s.pattern == ItemsPattern.MULTI_BRANCH_MERGE
        ]
        assert len(merge_segs) == 1
        assert merge_segs[0].root_node == "Merge"
        assert merge_segs[0].details["branch_count"] == "2"
        assert "BranchA" in merge_segs[0].node_names
        assert "BranchB" in merge_segs[0].node_names

    def test_three_branch_merge(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("A"),
                _node("B"),
                _node("C"),
                _node("Merge"),
            ],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="Merge", edge_type="CONNECTION"),
                DependencyEdge(from_node="C", to_node="Merge", edge_type="CONNECTION"),
            ],
        )
        segments = self.adapter.analyze(analysis)
        merge_segs = [
            s for s in segments if s.pattern == ItemsPattern.MULTI_BRANCH_MERGE
        ]
        assert len(merge_segs) == 1
        assert merge_segs[0].details["branch_count"] == "3"

    def test_accumulation_pattern(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B")],
            dependency_edges=[],
            variables_needed={"ref1": "A", "ref2": "B"},
        )
        segments = self.adapter.analyze(analysis)
        accum_segs = [s for s in segments if s.pattern == ItemsPattern.ACCUMULATION]
        assert len(accum_segs) == 1
        assert set(accum_segs[0].node_names) == {"A", "B"}

    def test_no_accumulation_without_variables(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A")],
            dependency_edges=[],
        )
        segments = self.adapter.analyze(analysis)
        accum_segs = [s for s in segments if s.pattern == ItemsPattern.ACCUMULATION]
        assert len(accum_segs) == 0

    def test_uncovered_nodes_become_single_item(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[
                _node("ListNode", params={"operation": "list"}),
                _node("Unrelated"),
            ],
            dependency_edges=[],
        )
        segments = self.adapter.analyze(analysis)
        single_segs = [s for s in segments if s.pattern == ItemsPattern.SINGLE_ITEM]
        assert len(single_segs) == 1
        assert "Unrelated" in single_segs[0].node_names

    def test_empty_workflow(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[],
            dependency_edges=[],
        )
        segments = self.adapter.analyze(analysis)
        assert segments == []

    def test_data_reference_edges_not_counted_as_merge(self):
        analysis = WorkflowAnalysis(
            classified_nodes=[_node("A"), _node("B"), _node("C")],
            dependency_edges=[
                DependencyEdge(from_node="A", to_node="C", edge_type="CONNECTION"),
                DependencyEdge(from_node="B", to_node="C", edge_type="DATA_REFERENCE"),
            ],
        )
        segments = self.adapter.analyze(analysis)
        merge_segs = [
            s for s in segments if s.pattern == ItemsPattern.MULTI_BRANCH_MERGE
        ]
        assert len(merge_segs) == 0
