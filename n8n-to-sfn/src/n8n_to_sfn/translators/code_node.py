"""Code node translator for JS and Python lift-and-shift to Lambda."""

from __future__ import annotations

import re

from phaeton_models.translator import ClassifiedNode, NodeClassification

from n8n_to_sfn.models.asl import TaskState
from n8n_to_sfn.translators.base import (
    BaseTranslator,
    LambdaArtifact,
    LambdaRuntime,
    TranslationContext,
    TranslationResult,
    apply_error_handling,
)

_JS_TEMPLATE = """\
// Auto-generated wrapper for n8n Code node: {node_name}
const handler = async (event) => {{
  const items = event.items || [event];
  // --- Begin n8n Code node content ---
{original_code}
  // --- End n8n Code node content ---
  return {{ items: result }};
}};
exports.handler = handler;
"""

_PY_TEMPLATE = """\
\"\"\"Auto-generated wrapper for n8n Code node: {node_name}.\"\"\"


def handler(event, context):
    \"\"\"Lambda handler wrapping n8n code node.\"\"\"
    items = event.get("items", [event])
    # --- Begin n8n Code node content ---
{original_code}
    # --- End n8n Code node content ---
    return {{"items": result}}
"""


def _sanitize_name(name: str) -> str:
    """Convert a node name to a valid Lambda function name."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return f"code_node_{sanitized.lower()}"


def _detect_js_dependencies(code: str) -> list[str]:
    """Scan JS code for require() calls and return dependency names."""
    deps: set[str] = {"luxon"}  # Always include luxon (n8n bundles it)
    for match in re.finditer(r"""require\(\s*['"]([^'"]+)['"]\s*\)""", code):
        dep = match.group(1)
        if not dep.startswith("."):
            deps.add(dep)
    return sorted(deps)


def _detect_py_dependencies(code: str) -> list[str]:
    """Scan Python code for import statements and return dependency names."""
    deps: set[str] = set()
    for match in re.finditer(r"^\s*(?:import|from)\s+(\w+)", code, re.MULTILINE):
        module = match.group(1)
        # Skip stdlib modules (rough heuristic)
        stdlib = {
            "os",
            "sys",
            "json",
            "re",
            "math",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "typing",
            "pathlib",
            "io",
            "csv",
            "hashlib",
            "base64",
            "uuid",
            "copy",
            "logging",
            "urllib",
            "http",
            "email",
            "html",
            "xml",
            "sqlite3",
            "subprocess",
            "threading",
            "multiprocessing",
            "socket",
            "ssl",
            "asyncio",
            "contextlib",
            "abc",
            "dataclasses",
            "enum",
            "string",
            "textwrap",
            "struct",
            "operator",
            "decimal",
            "fractions",
            "random",
            "statistics",
            "time",
            "calendar",
            "zlib",
            "gzip",
            "zipfile",
            "tarfile",
            "tempfile",
            "shutil",
            "glob",
            "fnmatch",
            "inspect",
            "traceback",
            "warnings",
            "pprint",
            "unittest",
        }
        if module not in stdlib:
            deps.add(module)
    return sorted(deps)


def _indent_code(code: str, spaces: int = 2) -> str:
    """Indent code by the specified number of spaces."""
    prefix = " " * spaces
    lines = code.split("\n")
    return "\n".join(prefix + line if line.strip() else line for line in lines)


class CodeNodeTranslator(BaseTranslator):
    """Translates n8n Code nodes into Lambda invoke Task states."""

    def can_translate(self, node: ClassifiedNode) -> bool:
        """Return True for CODE_JS and CODE_PYTHON classifications."""
        return node.classification in (
            NodeClassification.CODE_JS,
            NodeClassification.CODE_PYTHON,
        )

    def translate(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a Code node into a Lambda Task state + artifact."""
        if node.classification == NodeClassification.CODE_JS:
            return self._translate_js(node, context)
        return self._translate_python(node, context)

    def _translate_js(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a JavaScript Code node."""
        code = node.node.parameters.get("jsCode", "")
        func_name = _sanitize_name(node.node.name)
        handler_code = _JS_TEMPLATE.format(
            node_name=node.node.name,
            original_code=_indent_code(code),
        )
        deps = _detect_js_dependencies(code)

        artifact = LambdaArtifact(
            function_name=func_name,
            runtime=LambdaRuntime.NODEJS,
            handler_code=handler_code,
            dependencies=deps,
            directory_name=func_name,
        )

        state = TaskState(
            resource="arn:aws:states:::lambda:invoke",
            end=True,
        )
        state = apply_error_handling(state, node)

        return TranslationResult(
            states={node.node.name: state},
            lambda_artifacts=[artifact],
            warnings=[
                f"Code node '{node.node.name}': review handler for n8n-specific "
                f"globals beyond $input, $json, $items.",
            ],
        )

    def _translate_python(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a Python Code node."""
        code = node.node.parameters.get("pythonCode", "")
        func_name = _sanitize_name(node.node.name)
        handler_code = _PY_TEMPLATE.format(
            node_name=node.node.name,
            original_code=_indent_code(code, spaces=4),
        )
        deps = _detect_py_dependencies(code)

        artifact = LambdaArtifact(
            function_name=func_name,
            runtime=LambdaRuntime.PYTHON,
            handler_code=handler_code,
            dependencies=deps,
            directory_name=func_name,
        )

        state = TaskState(
            resource="arn:aws:states:::lambda:invoke",
            end=True,
        )
        state = apply_error_handling(state, node)

        return TranslationResult(
            states={node.node.name: state},
            lambda_artifacts=[artifact],
            warnings=[
                f"Code node '{node.node.name}': review handler for n8n-specific "
                f"globals beyond $input, $json, $items.",
            ],
        )
