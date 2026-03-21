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
{preamble}const handler = async (event) => {{
  const items = event.items || [event];
{shims}  // --- Begin n8n Code node content ---
{original_code}
  // --- End n8n Code node content ---
  return {{ items: result }};
}};
exports.handler = handler;
"""

_PY_TEMPLATE = """\
\"\"\"Auto-generated wrapper for n8n Code node: {node_name}.\"\"\"

{preamble}
def handler(event, context):
    \"\"\"Lambda handler wrapping n8n code node.\"\"\"
    items = event.get("items", [event])
{shims}    # --- Begin n8n Code node content ---
{original_code}
    # --- End n8n Code node content ---
    return {{"items": result}}
"""

# n8n globals that can be shimmed to Lambda event data.
_JS_SHIMS: dict[str, str] = {
    "$input": (
        "  const $input = {\n"
        "    all: () => items,\n"
        "    first: () => items[0],\n"
        "    last: () => items[items.length - 1],\n"
        "    item: items[0],\n"
        "  };\n"
    ),
    "$json": "  const $json = (items[0] && items[0].json) ? items[0].json : {};\n",
    "$items": "  const $items = items;\n",
    "$node": "  const $node = {};\n",
}

_PY_SHIMS: dict[str, str] = {
    "$input": (
        "    class _N8nInput:\n"
        '        """Shim for n8n $input global."""\n'
        "\n"
        "        @staticmethod\n"
        "        def all():\n"
        '            """Return all items."""\n'
        "            return items\n"
        "\n"
        "        @staticmethod\n"
        "        def first():\n"
        '            """Return the first item."""\n'
        "            return items[0]\n"
        "\n"
        "        @staticmethod\n"
        "        def last():\n"
        '            """Return the last item."""\n'
        "            return items[-1]\n"
        "\n"
        "        item = property(lambda self: items[0])\n"
        "\n"
        "    _input = _N8nInput()\n"
    ),
    "$json": '    _json = items[0].get("json", {}) if items else {}\n',
    "$items": "    _items = items\n",
    "$node": "    _node = {}\n",
}

# Globals that cannot be automatically translated.
_UNTRANSLATABLE_GLOBALS: dict[str, str] = {
    "$env": "n8n $env detected; use Lambda environment variables (os.environ) instead.",
    "$execution": (
        "n8n $execution detected; use Lambda context parameter for execution metadata."
    ),
    "$workflow": (
        "n8n $workflow detected; use a Lambda environment variable for workflow metadata."
    ),
    "$prevNode": "n8n $prevNode detected; no direct Lambda equivalent is available.",
    "$parameter": "n8n $parameter detected; no direct Lambda equivalent is available.",
}

# Combined list of all known n8n globals for detection.
_ALL_GLOBALS = list(_JS_SHIMS) + list(_UNTRANSLATABLE_GLOBALS)


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


def _detect_n8n_globals(code: str) -> set[str]:
    """Detect n8n globals referenced in user code."""
    found: set[str] = set()
    for glob in _ALL_GLOBALS:
        # Match $global as a whole word (not preceded by alnum/underscore).
        escaped = re.escape(glob)
        if re.search(rf"(?<![a-zA-Z0-9_]){escaped}\b", code):
            found.add(glob)
    return found


def _build_js_shims(detected: set[str]) -> str:
    """Build JavaScript shim lines for detected n8n globals."""
    parts: list[str] = []
    for glob in sorted(detected):
        if glob in _JS_SHIMS:
            parts.append(_JS_SHIMS[glob])
    return "".join(parts)


def _build_py_shims(detected: set[str]) -> str:
    """Build Python shim lines for detected n8n globals."""
    parts: list[str] = []
    for glob in sorted(detected):
        if glob in _PY_SHIMS:
            parts.append(_PY_SHIMS[glob])
    return "".join(parts)


def _build_warnings(node_name: str, detected: set[str]) -> list[str]:
    """Build warnings for untranslatable globals and general review note."""
    warnings: list[str] = []
    for glob in sorted(detected):
        if glob in _UNTRANSLATABLE_GLOBALS:
            warnings.append(f"Code node '{node_name}': {_UNTRANSLATABLE_GLOBALS[glob]}")
    # Always add a general review note for any remaining n8n patterns.
    warnings.append(
        f"Code node '{node_name}': review handler for n8n-specific "
        f"globals beyond $input, $json, $items."
    )
    return warnings


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
        detected = _detect_n8n_globals(code)

        # Build preamble for luxon DateTime if used.
        preamble = ""
        if re.search(r"\bDateTime\b", code):
            preamble = "const { DateTime } = require('luxon');\n"

        handler_code = _JS_TEMPLATE.format(
            node_name=node.node.name,
            preamble=preamble,
            shims=_build_js_shims(detected),
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

        state = TaskState(  # type: ignore[missing-argument]
            resource="arn:aws:states:::lambda:invoke",  # type: ignore[unknown-argument]
            end=True,
        )
        state = apply_error_handling(state, node)

        return TranslationResult(
            states={node.node.name: state},
            lambda_artifacts=[artifact],
            warnings=_build_warnings(node.node.name, detected),
        )

    def _translate_python(
        self, node: ClassifiedNode, context: TranslationContext
    ) -> TranslationResult:
        """Translate a Python Code node."""
        code = node.node.parameters.get("pythonCode", "")
        func_name = _sanitize_name(node.node.name)
        detected = _detect_n8n_globals(code)

        # Python code uses underscore-prefixed names since $ is invalid.
        # Rewrite $global references to _global in the user code.
        rewritten_code = code
        for glob in sorted(detected & set(_PY_SHIMS)):
            py_name = glob.replace("$", "_")
            rewritten_code = re.sub(
                rf"(?<![a-zA-Z0-9_])\{glob}\b", py_name, rewritten_code
            )

        preamble = ""
        handler_code = _PY_TEMPLATE.format(
            node_name=node.node.name,
            preamble=preamble,
            shims=_build_py_shims(detected),
            original_code=_indent_code(rewritten_code, spaces=4),
        )
        deps = _detect_py_dependencies(code)

        artifact = LambdaArtifact(
            function_name=func_name,
            runtime=LambdaRuntime.PYTHON,
            handler_code=handler_code,
            dependencies=deps,
            directory_name=func_name,
        )

        state = TaskState(  # type: ignore[missing-argument]
            resource="arn:aws:states:::lambda:invoke",  # type: ignore[unknown-argument]
            end=True,
        )
        state = apply_error_handling(state, node)

        return TranslationResult(
            states={node.node.name: state},
            lambda_artifacts=[artifact],
            warnings=_build_warnings(node.node.name, detected),
        )
