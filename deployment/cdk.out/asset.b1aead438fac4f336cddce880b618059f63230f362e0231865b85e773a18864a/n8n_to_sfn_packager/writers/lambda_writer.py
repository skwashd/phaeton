"""Lambda function writer.

Generates Lambda function directories with handler code and dependency
manifests. Python Lambdas use ``pyproject.toml`` + ``uv.lock``; Node.js
Lambdas use ``package.json``.
"""

from __future__ import annotations

import json
import re
import subprocess
import textwrap
from pathlib import Path

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
)


class LambdaWriteError(Exception):
    """Raised when Lambda function generation fails."""


class LambdaWriter:
    """Generates Lambda function directories from specs."""

    def write(self, spec: LambdaFunctionSpec, output_dir: Path) -> Path:
        """Write a single Lambda function directory.

        Args:
            spec: The Lambda function specification.
            output_dir: Root output directory.

        Returns:
            Path to the created Lambda directory.

        """
        safe_name = self._sanitise_dir_name(spec.function_name)
        func_dir = output_dir / "lambdas" / safe_name
        func_dir.mkdir(parents=True, exist_ok=True)

        if spec.runtime == LambdaRuntime.PYTHON:
            self._write_python_lambda(spec, func_dir)
        else:
            self._write_nodejs_lambda(spec, func_dir)

        return func_dir

    def write_all(
        self, specs: list[LambdaFunctionSpec], output_dir: Path
    ) -> list[Path]:
        """Write all Lambda function directories.

        Args:
            specs: List of Lambda function specifications.
            output_dir: Root output directory.

        Returns:
            List of paths to the created directories.

        """
        return [self.write(spec, output_dir) for spec in specs]

    @staticmethod
    def _sanitise_dir_name(name: str) -> str:
        """Sanitise a function name for use as a directory name."""
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    def _write_python_lambda(self, spec: LambdaFunctionSpec, func_dir: Path) -> None:
        """Generate Python Lambda artifacts: handler.py, pyproject.toml, uv.lock."""
        # handler.py
        handler_code = self._build_handler(spec)
        (func_dir / "handler.py").write_text(handler_code)

        # pyproject.toml
        deps_lines = ""
        if spec.dependencies:
            formatted = ",\n".join(f'    "{dep}"' for dep in spec.dependencies)
            deps_lines = f"\n{formatted},\n"

        pyproject = textwrap.dedent(f"""\
            [project]
            name = "{spec.function_name}"
            version = "1.0.0"
            requires-python = ">=3.12"
            dependencies = [{deps_lines}]

            [build-system]
            requires = ["hatchling"]
            build-backend = "hatchling.build"
        """)
        (func_dir / "pyproject.toml").write_text(pyproject)

        # uv.lock
        self._run_uv_lock(func_dir, spec.function_name)

    def _write_nodejs_lambda(self, spec: LambdaFunctionSpec, func_dir: Path) -> None:
        """Generate Node.js Lambda artifacts: handler.js, package.json."""
        # handler.js
        handler_code = self._build_handler(spec)
        (func_dir / "handler.js").write_text(handler_code)

        # package.json
        deps: dict[str, str] = {}
        for dep in spec.dependencies:
            if "@" in dep:
                name, version = dep.rsplit("@", 1)
                deps[name] = version
            elif "==" in dep:
                name, version = dep.split("==", 1)
                deps[name] = version
            else:
                deps[dep] = "*"

        package_json = {
            "name": spec.function_name,
            "version": "1.0.0",
            "main": "handler.js",
            "dependencies": deps,
        }
        (func_dir / "package.json").write_text(
            json.dumps(package_json, indent=2) + "\n"
        )

    def _build_handler(self, spec: LambdaFunctionSpec) -> str:
        """Build the handler file content with comment header and wrapper."""
        header = (
            f"# Auto-generated Lambda function\n"
            f"# Source n8n node: {spec.source_node_name}\n"
            f"# Function type: {spec.function_type.value}\n"
            f"# Description: {spec.description}\n"
        )
        if spec.runtime == LambdaRuntime.NODEJS:
            header = header.replace("# ", "// ")

        if (
            spec.function_type in (LambdaFunctionType.CODE_NODE_JS,)
            and spec.runtime == LambdaRuntime.NODEJS
        ):
            return self._wrap_js_code_node(header, spec)

        return header + "\n" + spec.handler_code + "\n"

    @staticmethod
    def _wrap_js_code_node(header: str, spec: LambdaFunctionSpec) -> str:
        """Wrap a JS code node in the standard Lambda handler template."""
        return (
            f"{header}\n"
            f"const handler = async (event) => {{\n"
            f"  const items = event.items || [event];\n"
            f"  // --- Begin n8n Code node content ---\n"
            f"  {spec.handler_code}\n"
            f"  // --- End n8n Code node content ---\n"
            f"  return {{ items: typeof result !== 'undefined' ? result : items }};\n"
            f"}};\n"
            f"exports.handler = handler;\n"
        )

    @staticmethod
    def _run_uv_lock(func_dir: Path, function_name: str) -> None:
        """Run ``uv lock`` in a Lambda directory to generate uv.lock."""
        try:
            subprocess.run(
                ["uv", "lock"],  # noqa: S607
                cwd=func_dir,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            msg = f"uv lock failed for Lambda '{function_name}': {e.stderr}"
            raise LambdaWriteError(msg) from e
