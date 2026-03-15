"""Classifies n8n expressions into translation categories."""

import re

from phaeton_models.analyzer import ClassifiedExpression, ExpressionCategory
from phaeton_models.n8n_workflow import N8nNode

# Cross-node reference patterns (Category B)
_CROSS_NODE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\('[^']+'\)"),
    re.compile(r'\$\("[^"]+"\)'),
    re.compile(r'\$node\["[^"]+"\]'),
    re.compile(r"\$node\.[A-Za-z_]"),
]

_CROSS_NODE_NAME_EXTRACTORS: list[re.Pattern[str]] = [
    re.compile(r"\$\('([^']+)'\)"),
    re.compile(r'\$\("([^"]+)"\)'),
    re.compile(r'\$node\["([^"]+)"\]'),
    re.compile(r"\$node\.([A-Za-z_][A-Za-z0-9_ ]*)"),
]

# Category B indicator patterns
_VARIABLE_REF_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cross-node reference", _CROSS_NODE_PATTERNS[0]),
    ("cross-node reference", _CROSS_NODE_PATTERNS[1]),
    ("cross-node reference", _CROSS_NODE_PATTERNS[2]),
    ("cross-node reference", _CROSS_NODE_PATTERNS[3]),
    ("$execution reference", re.compile(r"\$execution\.")),
    ("$workflow reference", re.compile(r"\$workflow\.")),
    ("$prevNode reference", re.compile(r"\$prevNode\.")),
]

# Category C indicator patterns
_LAMBDA_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Node.js require() import", re.compile(r"require\(")),
    ("environment variable access", re.compile(r"\$env\.")),
    ("IIFE pattern", re.compile(r"\(function")),
    ("IIFE arrow pattern", re.compile(r"\(\(\) =>")),
    ("Luxon date manipulation", re.compile(r"\.luxon")),
    ("DateTime manipulation", re.compile(r"DateTime\.")),
    ("JMESPath usage", re.compile(r"\$jmespath\(")),
    ("async operation", re.compile(r"await ")),
    ("error handling (try/catch/throw)", re.compile(r"\b(try|catch|throw)\b")),
    ("complex reduce operation", re.compile(r"\.reduce\(")),
    ("Array.from usage", re.compile(r"Array\.from\(")),
    ("Map constructor", re.compile(r"new Map\(")),
    ("Set constructor", re.compile(r"new Set\(")),
    ("Object.entries usage", re.compile(r"Object\.entries\(")),
    ("Object.fromEntries usage", re.compile(r"Object\.fromEntries\(")),
    ("loop construct", re.compile(r"\b(for|while)\s")),
    ("do-while loop", re.compile(r"\bdo\s*\{")),
    ("RegExp usage", re.compile(r"RegExp\(")),
    ("multi-statement expression", re.compile(r";")),
]

# JSONata preview translation patterns
_JSONATA_TRANSLATIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\$json\.(\w+(?:\.\w+)*)"), r"$states.input.\1"),
    (re.compile(r"\.toUpperCase\(\)"), r" ~> $uppercase"),
    (re.compile(r"\.toLowerCase\(\)"), r" ~> $lowercase"),
    (re.compile(r"\.trim\(\)"), r" ~> $trim"),
    (re.compile(r"Math\.round\(([^)]+)\)"), r"$round(\1)"),
]


class ExpressionClassifier:
    """Classifies n8n expressions into translation categories."""

    def classify(
        self, node_name: str, parameter_path: str, expression: str
    ) -> ClassifiedExpression:
        """Classify a single expression into a category."""
        # Strip the '=' prefix if present for analysis
        expr = expression.lstrip("=").strip()
        # Also strip surrounding {{ }} for analysis
        inner = re.sub(r"^\{\{(.*)\}\}$", r"\1", expr, flags=re.DOTALL).strip()

        # Check Category C first (highest priority after B)
        lambda_reason = self._check_lambda_required(inner)

        # Check Category B
        var_reason, ref_nodes = self._check_variable_reference(inner)

        # Category B + C combination → Category C wins
        if lambda_reason and var_reason:
            return ClassifiedExpression(
                node_name=node_name,
                parameter_path=parameter_path,
                raw_expression=expression,
                category=ExpressionCategory.LAMBDA_REQUIRED,
                referenced_nodes=ref_nodes,
                reason=f"{lambda_reason}; also contains {var_reason}",
            )

        # Category C alone
        if lambda_reason:
            return ClassifiedExpression(
                node_name=node_name,
                parameter_path=parameter_path,
                raw_expression=expression,
                category=ExpressionCategory.LAMBDA_REQUIRED,
                reason=lambda_reason,
            )

        # Category B alone
        if var_reason:
            return ClassifiedExpression(
                node_name=node_name,
                parameter_path=parameter_path,
                raw_expression=expression,
                category=ExpressionCategory.VARIABLE_REFERENCE,
                referenced_nodes=ref_nodes,
                reason=var_reason,
            )

        # Category A: JSONata direct
        preview = self._generate_jsonata_preview(inner)
        return ClassifiedExpression(
            node_name=node_name,
            parameter_path=parameter_path,
            raw_expression=expression,
            category=ExpressionCategory.JSONATA_DIRECT,
            jsonata_preview=preview,
            reason="Expression can be translated directly to JSONata",
        )

    def classify_all(
        self, expressions: list[tuple[N8nNode, str, str]]
    ) -> list[ClassifiedExpression]:
        """Classify all expressions from a workflow."""
        return [
            self.classify(node.name, param_path, expr)
            for node, param_path, expr in expressions
        ]

    def _check_variable_reference(self, expr: str) -> tuple[str | None, list[str]]:
        """Check if the expression contains variable reference patterns."""
        ref_nodes: list[str] = []
        reason: str | None = None

        for desc, pattern in _VARIABLE_REF_PATTERNS:
            if pattern.search(expr):
                reason = desc
                break

        # Extract referenced node names
        for extractor in _CROSS_NODE_NAME_EXTRACTORS:
            for match in extractor.finditer(expr):
                name = match.group(1)
                if name not in ref_nodes:
                    ref_nodes.append(name)

        if ref_nodes and reason is None:
            reason = "cross-node reference"

        return reason, ref_nodes

    def _check_lambda_required(self, expr: str) -> str | None:
        """Check if the expression requires Lambda extraction."""
        for desc, pattern in _LAMBDA_PATTERNS:
            if pattern.search(expr):
                return desc
        return None

    def _generate_jsonata_preview(self, expr: str) -> str | None:
        """Generate a best-effort JSONata preview for Category A expressions."""
        result = expr
        matched = False
        for pattern, replacement in _JSONATA_TRANSLATIONS:
            new_result = pattern.sub(replacement, result)
            if new_result != result:
                matched = True
                result = new_result
        return result if matched else None
