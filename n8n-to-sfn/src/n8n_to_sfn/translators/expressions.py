"""
Expression translation (Category A n8n expressions to JSONata).

Translates n8n template expressions (wrapped in ``{{ }}``) into JSONata
expressions (wrapped in ``{% %}``) for use in ASL state machines.
"""

from __future__ import annotations

import re
from typing import cast

from n8n_to_sfn.errors import ExpressionTranslationError

type JsonValue = (
    str | int | float | bool | None | dict[str, JsonValue] | list[JsonValue]
)

# ---------------------------------------------------------------------------
# Translation rules: each is (compiled regex, replacement function or template)
# Rules are ordered from most specific to most general.
# ---------------------------------------------------------------------------

_RULES: list[tuple[re.Pattern[str], str]] = []


def _rule(pattern: str, replacement: str) -> None:
    """Register a translation rule."""
    _RULES.append((re.compile(pattern), replacement))


# --- Array / Object spread ---
_rule(
    r"\[\s*\.\.\.\$json\.(\w[\w.]*)\s*,\s*\.\.\.\$json\.(\w[\w.]*)\s*\]",
    r"$append($states.input.\1, $states.input.\2)",
)
_rule(
    r"\{\s*\.\.\.\$json\.(\w[\w.]*)\s*,\s*\.\.\.\$json\.(\w[\w.]*)\s*\}",
    r"$merge([$states.input.\1, $states.input.\2])",
)

# --- Sort with comparator ---
_rule(
    r"\$json\.([\w.]+)\.sort\(\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*=>\s*\2\.(\w+)\s*-\s*\3\.(\w+)\s*\)",
    r"$sort($states.input.\1, function($\2,$\3){ $\2.\4 > $\3.\5 })",
)

# --- Reduce with sum pattern ---
_rule(
    r"\$json\.([\w.]+)\.reduce\(\s*\(\s*\w+\s*,\s*\w+\s*\)\s*=>\s*\w+\s*\+\s*\w+\.(\w+)\s*,\s*0\s*\)",
    r"$sum($states.input.\1.\2)",
)

# --- Map: .map(i => i.field) ---
_rule(
    r"\$json\.([\w.]+)\.map\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)",
    r"$states.input.\1.\2",
)

# --- Filter: .filter(i => i.field) ---
_rule(
    r"\$json\.([\w.]+)\.filter\(\s*\w+\s*=>\s*\w+\.(\w+)\s*\)",
    r"$states.input.\1[\2 = true]",
)

# --- String methods ---
_rule(
    r"\$json\.([\w.]+)\.toUpperCase\(\)",
    r"$uppercase($states.input.\1)",
)
_rule(
    r"\$json\.([\w.]+)\.toLowerCase\(\)",
    r"$lowercase($states.input.\1)",
)
_rule(
    r"\$json\.([\w.]+)\.trim\(\)",
    r"$trim($states.input.\1)",
)
_rule(
    r"\$json\.([\w.]+)\.split\(\s*'([^']*)'\s*\)",
    r"$split($states.input.\1, '\2')",
)
_rule(
    r"\$json\.([\w.]+)\.replace\(\s*'([^']*)'\s*,\s*'([^']*)'\s*\)",
    r"$replace($states.input.\1, '\2', '\3')",
)
_rule(
    r"\$json\.([\w.]+)\.includes\(\s*'([^']*)'\s*\)",
    r"$contains($states.input.\1, '\2')",
)

# --- .length on arrays vs strings ---
# arr.length → $count (if path suggests array, but we can't always tell; default to $length)
_rule(
    r"\$json\.([\w.]*arr[\w.]*)\.length",
    r"$count($states.input.\1)",
)
_rule(
    r"\$json\.([\w.]+)\.length",
    r"$length($states.input.\1)",
)

# --- Math functions ---
_rule(r"Math\.round\(\$json\.([\w.]+)\)", r"$round($states.input.\1)")
_rule(r"Math\.floor\(\$json\.([\w.]+)\)", r"$floor($states.input.\1)")
_rule(r"Math\.ceil\(\$json\.([\w.]+)\)", r"$ceil($states.input.\1)")

# --- Global functions ---
_rule(r"Object\.keys\(\$json\)", r"$keys($states.input)")
_rule(r"JSON\.stringify\(\$json\)", r"$string($states.input)")
_rule(r"parseInt\(\$json\.([\w.]+)\)", r"$number($states.input.\1)")

# --- Date ---
_rule(r"new Date\(\)\.toISOString\(\)", r"$now()")

# --- Template literals ---
# Handled separately in _translate_template_literal

# --- Ternary: $json.a > 10 ? 'high' : 'low' ---
# This is handled by the general $json replacement since JSONata has ternary too

# --- General $json.field replacement (must be last) ---
# This replaces all remaining $json references with $states.input


def _replace_json_refs(expr: str) -> str:
    """Replace all ``$json`` references with ``$states.input``."""
    return re.sub(r"\$json\b", "$states.input", expr)


def _translate_template_literal(expr: str) -> str:
    """
    Translate JS template literals to JSONata string concatenation.

    Converts ``Hello ${$json.name}`` to ``"Hello " & $states.input.name``.
    """
    # Match template literal pattern: `...${expr}...`
    if not (expr.startswith("`") and expr.endswith("`")):
        return expr

    inner = expr[1:-1]
    parts: list[str] = []
    last_end = 0

    for match in re.finditer(r"\$\{([^}]+)\}", inner):
        prefix = inner[last_end : match.start()]
        if prefix:
            parts.append(f'"{prefix}"')
        interpolated = match.group(1).strip()
        interpolated = _replace_json_refs(interpolated)
        parts.append(interpolated)
        last_end = match.end()

    suffix = inner[last_end:]
    if suffix:
        parts.append(f'"{suffix}"')

    if not parts:
        return '""'

    return " & ".join(parts)


def translate_expression(expr: str) -> str:
    """
    Translate a single n8n expression to JSONata.

    The input should be the raw expression content (without ``{{ }}`` wrapper).
    Returns the JSONata expression (without ``{% %}`` wrapper).

    Raises ``ExpressionTranslationError`` if the expression cannot be translated.
    """
    stripped = expr.strip()

    # Template literals
    if stripped.startswith("`") and stripped.endswith("`"):
        return _translate_template_literal(stripped)

    # Try each rule in order
    for pattern, replacement in _RULES:
        new_val, count = pattern.subn(replacement, stripped)
        if count > 0:
            # Also replace any remaining $json refs in the result
            return _replace_json_refs(new_val)

    # Fallback: if expression contains $json, do simple replacement
    if "$json" in stripped:
        return _replace_json_refs(stripped)

    # If it contains cross-node refs, it's Category B/C
    if "$(" in stripped or "$node[" in stripped or "$execution" in stripped:
        raise ExpressionTranslationError(
            expr,
            expression=expr,
        )

    # Simple literal or unknown — pass through with $json replacement
    return _replace_json_refs(stripped)


def translate_n8n_expression(expr: str) -> str:
    """
    Translate an n8n expression (with ``{{ }}`` wrapper) to JSONata (with ``{% %}`` wrapper).

    This is the main entry point for expression translation.
    """
    stripped = expr.strip()

    # Strip {{ }} wrapper
    if stripped.startswith("{{") and stripped.endswith("}}"):
        inner = stripped[2:-2].strip()
    elif stripped.startswith("="):
        # n8n also uses = prefix for expressions
        inner = stripped[1:].strip()
    else:
        inner = stripped

    result = translate_expression(inner)
    return f"{{% {result} %}}"


def translate_all_expressions(
    parameters: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """
    Walk a parameters dict and translate all n8n expressions.

    Expression strings are those wrapped in ``{{ }}``. Non-expression values
    are passed through unchanged.
    """
    return cast(dict[str, JsonValue], _walk_and_translate(parameters))


def _walk_and_translate(value: JsonValue) -> JsonValue:
    """Recursively walk a value and translate expressions."""
    if isinstance(value, str):
        if "{{" in value and "}}" in value:
            return translate_n8n_expression(value)
        return value
    if isinstance(value, dict):
        return {k: _walk_and_translate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_walk_and_translate(item) for item in value]
    return value
