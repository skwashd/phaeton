"""Lambda function writer.

Generates Lambda function directories with handler code and dependency
manifests. Python Lambdas use ``pyproject.toml`` + ``uv.lock``; Node.js
Lambdas use ``package.json``.

Also generates Lambda Layer directories for dependencies shared across
multiple functions of the same runtime, reducing individual package sizes.
"""

from __future__ import annotations

import json
import re
import subprocess
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    WebhookAuthType,
)


@dataclass
class LayerSpec:
    """Specification for a shared dependency Lambda Layer."""

    layer_name: str
    runtime: LambdaRuntime
    dependencies: list[str]
    function_names: list[str] = field(default_factory=list)


def analyze_shared_dependencies(
    specs: list[LambdaFunctionSpec],
) -> tuple[list[LayerSpec], dict[str, set[str]]]:
    """Identify dependencies shared by 2+ functions of the same runtime.

    Args:
        specs: All Lambda function specifications.

    Returns:
        A tuple of ``(layer_specs, excluded_deps_by_function)``.
        ``excluded_deps_by_function`` maps each function name to the set of
        dependency strings that belong in a shared layer and should be
        excluded from the individual function package.

    """
    layers: list[LayerSpec] = []
    excluded: dict[str, set[str]] = {}

    by_runtime: dict[LambdaRuntime, list[LambdaFunctionSpec]] = {}
    for spec in specs:
        by_runtime.setdefault(spec.runtime, []).append(spec)

    for runtime, funcs in sorted(by_runtime.items(), key=lambda x: x[0].value):
        if len(funcs) < 2:
            continue

        dep_counts: Counter[str] = Counter()
        dep_to_funcs: dict[str, list[str]] = {}
        for func in funcs:
            for dep in func.dependencies:
                dep_counts[dep] += 1
                dep_to_funcs.setdefault(dep, []).append(func.function_name)

        shared_deps = sorted(dep for dep, count in dep_counts.items() if count >= 2)
        if not shared_deps:
            continue

        layer_name = f"{runtime.value}-shared"
        func_names = sorted(
            {fn for dep in shared_deps for fn in dep_to_funcs[dep]}
        )

        layers.append(
            LayerSpec(
                layer_name=layer_name,
                runtime=runtime,
                dependencies=shared_deps,
                function_names=func_names,
            )
        )

        for dep in shared_deps:
            for fn_name in dep_to_funcs[dep]:
                excluded.setdefault(fn_name, set()).add(dep)

    return layers, excluded


class LambdaWriteError(Exception):
    """Raised when Lambda function generation fails."""


class LambdaWriter:
    """Generates Lambda function directories from specs."""

    def write(
        self,
        spec: LambdaFunctionSpec,
        output_dir: Path,
        excluded_dependencies: set[str] | None = None,
    ) -> Path:
        """Write a single Lambda function directory.

        Args:
            spec: The Lambda function specification.
            output_dir: Root output directory.
            excluded_dependencies: Dependencies to exclude (they live in a
                shared layer instead).

        Returns:
            Path to the created Lambda directory.

        """
        safe_name = self._sanitise_dir_name(spec.function_name)
        func_dir = output_dir / "lambdas" / safe_name
        func_dir.mkdir(parents=True, exist_ok=True)

        if spec.runtime == LambdaRuntime.PYTHON:
            self._write_python_lambda(spec, func_dir, excluded_dependencies)
        else:
            self._write_nodejs_lambda(spec, func_dir, excluded_dependencies)

        return func_dir

    def write_layer(self, layer: LayerSpec, output_dir: Path) -> Path:
        """Write a Lambda Layer directory with the shared dependency manifest.

        Args:
            layer: The layer specification.
            output_dir: Root output directory.

        Returns:
            Path to the created layer directory.

        """
        layer_dir = output_dir / "layers" / layer.layer_name

        if layer.runtime == LambdaRuntime.NODEJS:
            nodejs_dir = layer_dir / "nodejs"
            nodejs_dir.mkdir(parents=True, exist_ok=True)

            deps: dict[str, str] = {}
            for dep in layer.dependencies:
                if "@" in dep:
                    name, version = dep.rsplit("@", 1)
                    deps[name] = version
                elif "==" in dep:
                    name, version = dep.split("==", 1)
                    deps[name] = version
                else:
                    deps[dep] = "*"

            package_json = {
                "name": f"{layer.layer_name}-layer",
                "version": "1.0.0",
                "dependencies": deps,
            }
            (nodejs_dir / "package.json").write_text(
                json.dumps(package_json, indent=2) + "\n"
            )
        else:
            layer_dir.mkdir(parents=True, exist_ok=True)

            deps_lines = ""
            if layer.dependencies:
                formatted = ",\n".join(
                    f'    "{dep}"' for dep in layer.dependencies
                )
                deps_lines = f"\n{formatted},\n"

            pyproject = textwrap.dedent(f"""\
                [project]
                name = "{layer.layer_name}-layer"
                version = "1.0.0"
                requires-python = ">=3.12"
                dependencies = [{deps_lines}]

                [build-system]
                requires = ["hatchling"]
                build-backend = "hatchling.build"
            """)
            (layer_dir / "pyproject.toml").write_text(pyproject)

        return layer_dir

    def write_all(
        self, specs: list[LambdaFunctionSpec], output_dir: Path
    ) -> list[Path]:
        """Write all Lambda function directories and shared dependency layers.

        Analyses dependencies across all functions, creates shared layers for
        dependencies used by 2+ functions of the same runtime, and excludes
        those dependencies from individual function packages.

        Args:
            specs: List of Lambda function specifications.
            output_dir: Root output directory.

        Returns:
            List of paths to the created function directories.

        """
        layers, excluded = analyze_shared_dependencies(specs)

        for layer in layers:
            self.write_layer(layer, output_dir)

        return [
            self.write(
                spec,
                output_dir,
                excluded_dependencies=excluded.get(spec.function_name),
            )
            for spec in specs
        ]

    @staticmethod
    def _sanitise_dir_name(name: str) -> str:
        """Sanitise a function name for use as a directory name."""
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

    def _write_python_lambda(
        self,
        spec: LambdaFunctionSpec,
        func_dir: Path,
        excluded_dependencies: set[str] | None = None,
    ) -> None:
        """Generate Python Lambda artifacts: handler.py, pyproject.toml, uv.lock."""
        # handler.py
        handler_code = self._build_handler(spec)
        (func_dir / "handler.py").write_text(handler_code)

        # pyproject.toml — exclude deps that live in a shared layer
        deps = [
            d
            for d in spec.dependencies
            if not excluded_dependencies or d not in excluded_dependencies
        ]
        deps_lines = ""
        if deps:
            formatted = ",\n".join(f'    "{dep}"' for dep in deps)
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

    def _write_nodejs_lambda(
        self,
        spec: LambdaFunctionSpec,
        func_dir: Path,
        excluded_dependencies: set[str] | None = None,
    ) -> None:
        """Generate Node.js Lambda artifacts: handler.js, package.json."""
        # handler.js
        handler_code = self._build_handler(spec)
        (func_dir / "handler.js").write_text(handler_code)

        # package.json — exclude deps that live in a shared layer
        func_deps = [
            d
            for d in spec.dependencies
            if not excluded_dependencies or d not in excluded_dependencies
        ]
        deps: dict[str, str] = {}
        for dep in func_deps:
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

        # Inject authentication preamble for webhook/callback handlers
        if spec.webhook_auth and spec.function_type in (
            LambdaFunctionType.WEBHOOK_HANDLER,
            LambdaFunctionType.CALLBACK_HANDLER,
        ):
            auth_code = self._generate_auth_preamble(spec)
            return header + "\n" + auth_code + "\n" + spec.handler_code + "\n"

        return header + "\n" + spec.handler_code + "\n"

    @staticmethod
    def _generate_auth_preamble(spec: LambdaFunctionSpec) -> str:
        """Generate Python authentication preamble for webhook handlers."""
        auth = spec.webhook_auth
        if auth is None:
            return ""

        common = textwrap.dedent("""\
            import json
            import os

            import boto3

            _ssm = boto3.client("ssm")
            _cached_secret = None


            def _get_webhook_secret():
                global _cached_secret  # noqa: PLW0603
                if _cached_secret is None:
                    resp = _ssm.get_parameter(
                        Name=os.environ["WEBHOOK_AUTH_PARAMETER"],
                        WithDecryption=True,
                    )
                    _cached_secret = resp["Parameter"]["Value"]
                return _cached_secret

        """)

        if auth.auth_type == WebhookAuthType.API_KEY:
            verify = textwrap.dedent(f"""\
                def _authenticate(event):
                    secret = _get_webhook_secret()
                    request_key = event.get("headers", {{}}).get("{auth.header_name}", "")
                    if request_key != secret:
                        return {{
                            "statusCode": 401,
                            "body": json.dumps({{"error": "Unauthorized"}}),
                        }}
                    return None

            """)
        else:
            verify = textwrap.dedent(f"""\
                import hashlib
                import hmac


                def _authenticate(event):
                    secret = _get_webhook_secret()
                    body = event.get("body", "")
                    signature = event.get("headers", {{}}).get("{auth.header_name}", "")
                    expected = "sha256=" + hmac.new(
                        secret.encode(), body.encode(), hashlib.sha256,
                    ).hexdigest()
                    if not hmac.compare_digest(expected, signature):
                        return {{
                            "statusCode": 403,
                            "body": json.dumps({{"error": "Invalid signature"}}),
                        }}
                    return None

            """)

        return common + verify

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
