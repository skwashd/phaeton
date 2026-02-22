"""Detects cross-node data references in n8n expressions."""

import re

from pydantic import BaseModel

from workflow_analyzer.models.n8n_workflow import N8nNode

# Patterns for cross-node references in n8n expressions
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("$('NodeName')", re.compile(r"\$\('([^']+)'\)")),
    ('$("NodeName")', re.compile(r'\$\("([^"]+)"\)')),
    ('$node["NodeName"]', re.compile(r'\$node\["([^"]+)"\]')),
    ("$node.NodeName", re.compile(r"\$node\.([A-Za-z_][A-Za-z0-9_ ]*)")),
]


class CrossNodeReference(BaseModel):
    """A detected cross-node data reference in an expression."""

    source_node_name: str
    target_node_name: str
    expression: str
    reference_pattern: str


def detect_cross_node_references(
    expressions: list[tuple[N8nNode, str, str]],
) -> list[CrossNodeReference]:
    """Detect cross-node references in a list of expressions."""
    results: list[CrossNodeReference] = []
    for node, _param_path, expr_str in expressions:
        for pattern_desc, pattern in _PATTERNS:
            for match in pattern.finditer(expr_str):
                ref_name = match.group(1)
                if ref_name != node.name:
                    results.append(
                        CrossNodeReference(
                            source_node_name=ref_name,
                            target_node_name=node.name,
                            expression=expr_str,
                            reference_pattern=pattern_desc,
                        )
                    )
    return results
