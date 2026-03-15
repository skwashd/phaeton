"""Set/Edit Fields node translator.

Converts ``n8n-nodes-base.set`` nodes into Step Functions ``Pass`` states
with JSONata ``Output`` expressions for field mapping.
"""

from __future__ import annotations

from typing import Any

from phaeton_models.translator import ClassifiedNode

from n8n_to_sfn.models.asl import PassState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    TranslationContext,
    TranslationResult,
)
from n8n_to_sfn.translators.expressions import translate_expression

_SET_NODE_TYPE = "n8n-nodes-base.set"

type _FieldValue = str | int | float | bool | None


def _is_n8n_expression(value: _FieldValue) -> bool:
    """Return True if the value is an n8n expression string."""
    return isinstance(value, str) and "{{" in value and "}}" in value


def _strip_expression_wrapper(value: str) -> str:
    """Strip ``={{ }}`` or ``{{ }}`` wrappers from an n8n expression."""
    stripped = value.strip()
    if stripped.startswith("={{"):
        stripped = stripped[1:]
    if stripped.startswith("{{") and stripped.endswith("}}"):
        return stripped[2:-2].strip()
    return stripped


def _translate_value(value: _FieldValue, field_type: str) -> str:
    """Translate a single field value to a JSONata expression string.

    Returns the raw JSONata expression (without ``{% %}`` wrapper).
    """
    if _is_n8n_expression(value):
        inner = _strip_expression_wrapper(str(value))
        return translate_expression(inner)

    if field_type == "number":
        return str(value)
    if field_type == "boolean":
        return "true" if value else "false"
    # String literal — quote it
    escaped = str(value).replace("'", "\\'")
    return f"'{escaped}'"


def _build_manual_output(
    assignments: list[dict[str, Any]],
    include_input: bool,
) -> str:
    """Build a JSONata Output expression from manual field assignments.

    Parameters
    ----------
    assignments:
        List of ``{ name, value, type }`` dicts from n8n parameters.
    include_input:
        When True, merge assigned fields into ``$states.input`` (default
        behaviour).  When False, output only the assigned fields.

    """
    field_parts: list[str] = []
    for assignment in assignments:
        name = assignment.get("name", "")
        value = assignment.get("value", "")
        field_type = assignment.get("type", "string")
        if not name:
            continue
        jsonata_value = _translate_value(value, field_type)
        field_parts.append(f"'{name}': {jsonata_value}")

    fields_obj = "{ " + ", ".join(field_parts) + " }"

    if include_input:
        return f"{{% $merge([$states.input, {fields_obj}]) %}}"
    return f"{{% {fields_obj} %}}"


def _build_raw_output(json_output: str) -> str:
    """Build a JSONata Output expression from a raw JSON expression."""
    if _is_n8n_expression(json_output):
        inner = _strip_expression_wrapper(json_output)
        translated = translate_expression(inner)
        return f"{{% {translated} %}}"
    # Treat as literal JSON — pass through as-is via JSONata
    return f"{{% {json_output} %}}"


class SetNodeTranslator(BaseTranslator):
    """Translates Set/Edit Fields nodes into ``Pass`` states with JSONata Output."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True for ``n8n-nodes-base.set`` nodes."""
        return node.node.type == _SET_NODE_TYPE

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a Set node into a Pass state with JSONata Output."""
        params = node.node.parameters
        mode = str(params.get("mode", "manual"))
        warnings: list[str] = []

        if mode == "raw":
            output_expr = self._translate_raw_mode(params, warnings)
        else:
            output_expr = self._translate_manual_mode(params)

        state = PassState(
            output=output_expr,
            end=True,
        )

        return TranslationResult(
            states={node.node.name: state},
            warnings=warnings,
        )

    @staticmethod
    def _translate_manual_mode(params: dict[str, Any]) -> str:
        """Translate manual (set specified) mode."""
        assignments_container = params.get("assignments", {})
        assignments: list[dict[str, Any]] = []
        if isinstance(assignments_container, dict):
            assignments = assignments_container.get("assignments", [])
        elif isinstance(assignments_container, list):
            assignments = assignments_container

        include_input = not params.get("options", {}).get("keepOnlySet", False)

        return _build_manual_output(assignments, include_input)

    @staticmethod
    def _translate_raw_mode(
        params: dict[str, Any], warnings: list[str]
    ) -> str:
        """Translate raw JSON expression mode."""
        json_output = params.get("jsonOutput", "")
        if not json_output:
            warnings.append("Set node in raw mode has empty jsonOutput.")
            return "{% {} %}"
        return _build_raw_output(str(json_output))
