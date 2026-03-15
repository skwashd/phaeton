"""Classifies n8n workflow nodes into translation categories."""

from phaeton_models.analyzer import ClassifiedNode, NodeCategory

from workflow_analyzer.classifier.registry import (
    TRANSLATION_STRATEGIES,
    NodeRegistry,
)
from workflow_analyzer.models.n8n_workflow import N8nNode


class NodeClassifier:
    """Classifies each n8n node into a translation category."""

    def __init__(self, registry: NodeRegistry | None = None) -> None:
        """Initialize with an optional custom registry."""
        self._registry = registry or NodeRegistry()

    def classify(self, node: N8nNode) -> ClassifiedNode:
        """Classify a single node into a category."""
        category = self._determine_category(node)
        return ClassifiedNode(
            node=node,
            category=category,
            translation_strategy=TRANSLATION_STRATEGIES[category],
            notes=self._get_notes(node, category),
        )

    def classify_all(self, nodes: list[N8nNode]) -> list[ClassifiedNode]:
        """Classify all nodes in a workflow."""
        return [self.classify(node) for node in nodes]

    def _determine_category(self, node: N8nNode) -> NodeCategory:
        """Determine the classification category for a node."""
        node_type = node.type

        if self._registry.is_flow_control(node_type):
            return NodeCategory.FLOW_CONTROL

        if self._registry.is_trigger(node_type):
            return NodeCategory.TRIGGER

        if self._registry.is_aws_native(node_type):
            return NodeCategory.AWS_NATIVE

        if self._registry.is_code(node_type):
            return self._classify_code_node(node)

        if self._registry.is_http_request(node_type):
            return NodeCategory.PICOFUN_API

        if self._registry.is_n8n_base(node_type):
            return NodeCategory.PICOFUN_API

        return NodeCategory.UNSUPPORTED

    def _classify_code_node(self, node: N8nNode) -> NodeCategory:
        """Classify a code node based on its language parameter."""
        language = node.parameters.get("language", "javaScript")
        if language == "python":
            return NodeCategory.CODE_PYTHON
        return NodeCategory.CODE_JS

    def _get_notes(self, node: N8nNode, category: NodeCategory) -> str | None:
        """Generate notes for special classification cases."""
        if category == NodeCategory.UNSUPPORTED:
            return f"Node type '{node.type}' is not in the supported node registry"
        if category == NodeCategory.PICOFUN_API and self._registry.is_http_request(
            node.type
        ):
            return "HTTP Request node will need PicoFun API client generation"
        return None
