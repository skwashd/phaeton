"""
Cross-node reference translator (Category B to Step Functions Variables).

Resolves n8n cross-node references (e.g., ``$('NodeName').first().json.field``)
into Step Functions Variables via ``Assign`` blocks and JSONata variable references.
"""

from __future__ import annotations

import re

from phaeton_models.translator import (
    ExpressionCategory,
    WorkflowAnalysis,
)
from pydantic import BaseModel


class VariableResolution(BaseModel):
    """Result of resolving all cross-node references in a workflow."""

    assignments: dict[str, dict[str, str]] = {}
    expression_replacements: dict[str, str] = {}


def _to_camel_case(name: str) -> str:
    """Convert a node name to camelCase for variable naming."""
    # Remove non-alphanumeric chars, split into words
    words = re.split(r"[^a-zA-Z0-9]+", name)
    words = [w for w in words if w]
    if not words:
        return "var"
    result = words[0].lower()
    for w in words[1:]:
        result += w.capitalize()
    return result


def _make_variable_name(node_name: str, used_names: set[str]) -> str:
    """Generate a unique variable name from a node name."""
    base = _to_camel_case(node_name) + "Result"
    if base not in used_names:
        used_names.add(base)
        return base
    counter = 2
    while f"{base}{counter}" in used_names:
        counter += 1
    name = f"{base}{counter}"
    used_names.add(name)
    return name


# Patterns for cross-node references
_PATTERNS = [
    # $('NodeName').first().json.field.subfield
    re.compile(r"""\$\(\s*['"]([^'"]+)['"]\s*\)\.first\(\)\.json(?:\.(\S+))?"""),
    # $('NodeName').last().json.field.subfield
    re.compile(r"""\$\(\s*['"]([^'"]+)['"]\s*\)\.last\(\)\.json(?:\.(\S+))?"""),
    # $('NodeName').all()
    re.compile(r"""\$\(\s*['"]([^'"]+)['"]\s*\)\.all\(\)"""),
    # $('NodeName').item.json.field.subfield
    re.compile(r"""\$\(\s*['"]([^'"]+)['"]\s*\)\.item\.json(?:\.(\S+))?"""),
    # $node["NodeName"].json.field.subfield (legacy)
    re.compile(r"""\$node\[\s*["']([^"']+)["']\s*\]\.json(?:\.(\S+))?"""),
]

# Execution metadata patterns
_EXECUTION_PATTERNS = {
    re.compile(r"\$execution\.id"): "{% $states.context.Execution.Id %}",
    re.compile(r"\$execution\.resumeUrl"): None,  # Needs special handling
}


class _ResolutionState:
    """Mutable state accumulated during cross-node reference resolution."""

    def __init__(self) -> None:
        """Initialize empty resolution state."""
        self.assignments: dict[str, dict[str, str]] = {}
        self.replacements: dict[str, str] = {}
        self.used_names: set[str] = set()
        self.node_to_var: dict[str, str] = {}


def _resolve_single_expression(
    raw: str,
    inner: str,
    state: _ResolutionState,
) -> None:
    """Resolve a single Category B expression into assignments/replacements."""
    # Check execution metadata
    for pattern, replacement in _EXECUTION_PATTERNS.items():
        if pattern.search(inner) and replacement is not None:
            state.replacements[raw] = replacement
            return

    # Check cross-node reference patterns
    for pattern in _PATTERNS:
        match = pattern.search(inner)
        if not match:
            continue

        ref_node = match.group(1)
        field_path = (
            match.group(2) if match.lastindex and match.lastindex >= 2 else None
        )

        if ref_node not in state.node_to_var:
            var_name = _make_variable_name(ref_node, state.used_names)
            state.node_to_var[ref_node] = var_name
            state.assignments[ref_node] = {var_name: "{% $states.result %}"}

        var_name = state.node_to_var[ref_node]
        if field_path:
            state.replacements[raw] = f"{{% ${var_name}.{field_path} %}}"
        else:
            state.replacements[raw] = f"{{% ${var_name} %}}"
        return


def resolve_cross_node_references(
    analysis: WorkflowAnalysis,
) -> VariableResolution:
    """Scan all Category B expressions and produce Assign blocks + replacements."""
    state = _ResolutionState()

    for cn in analysis.classified_nodes:
        for expr in cn.expressions:
            if expr.category != ExpressionCategory.REQUIRES_VARIABLES:
                continue

            raw = expr.original
            inner = raw.strip()
            if inner.startswith("{{") and inner.endswith("}}"):
                inner = inner[2:-2].strip()

            _resolve_single_expression(raw, inner, state)

    return VariableResolution(
        assignments=state.assignments,
        expression_replacements=state.replacements,
    )
