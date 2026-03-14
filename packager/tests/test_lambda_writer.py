"""Tests for the Lambda function writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
)
from n8n_to_sfn_packager.writers.lambda_writer import LambdaWriter


@pytest.fixture
def writer() -> LambdaWriter:
    """Create a LambdaWriter instance."""
    return LambdaWriter()


@pytest.fixture
def python_spec() -> LambdaFunctionSpec:
    """Create a Python Lambda function spec for testing."""
    return LambdaFunctionSpec(
        function_name="slack_api",
        runtime=LambdaRuntime.PYTHON,
        handler_code='def handler(event, context):\n    return {"ok": True}',
        description="PicoFun Slack API client",
        source_node_name="Slack",
        dependencies=["httpx==0.27.0", "aws-lambda-powertools==2.40.0"],
        function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
    )


@pytest.fixture
def nodejs_spec() -> LambdaFunctionSpec:
    """Create a Node.js Lambda function spec for testing."""
    return LambdaFunctionSpec(
        function_name="code_node_transform",
        runtime=LambdaRuntime.NODEJS,
        handler_code="const result = items.map(i => ({ ...i, processed: true }));",
        description="Lift-and-shift JS code node",
        source_node_name="Code",
        dependencies=["luxon@3.4.4"],
        function_type=LambdaFunctionType.CODE_NODE_JS,
    )


@pytest.fixture
def python_no_deps_spec() -> LambdaFunctionSpec:
    """Create a Python Lambda function spec with no dependencies."""
    return LambdaFunctionSpec(
        function_name="simple_handler",
        runtime=LambdaRuntime.PYTHON,
        handler_code="def handler(event, context):\n    return event",
        description="Simple handler with no deps",
        source_node_name="Code",
        dependencies=[],
        function_type=LambdaFunctionType.CODE_NODE_PYTHON,
    )


class TestPythonLambda:
    """Tests for Python Lambda function writing."""

    def test_handler_file_exists(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that handler.py is created."""
        result = writer.write(python_spec, tmp_path)
        assert (result / "handler.py").exists()

    def test_pyproject_toml_exists(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that pyproject.toml is created."""
        result = writer.write(python_spec, tmp_path)
        assert (result / "pyproject.toml").exists()

    def test_uv_lock_generated(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that uv.lock is generated."""
        result = writer.write(python_spec, tmp_path)
        assert (result / "uv.lock").exists()

    def test_pyproject_contains_dependencies(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that pyproject.toml contains expected dependencies."""
        result = writer.write(python_spec, tmp_path)
        content = (result / "pyproject.toml").read_text()
        assert "httpx==0.27.0" in content
        assert "aws-lambda-powertools==2.40.0" in content

    def test_handler_has_comment_header(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that handler.py has source node comment header."""
        result = writer.write(python_spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert "Source n8n node: Slack" in content
        assert "Function type: picofun_api_client" in content

    def test_no_deps_still_valid(
        self,
        writer: LambdaWriter,
        python_no_deps_spec: LambdaFunctionSpec,
        tmp_path: Path,
    ) -> None:
        """Test that a Python Lambda with no dependencies is still valid."""
        result = writer.write(python_no_deps_spec, tmp_path)
        assert (result / "pyproject.toml").exists()
        assert (result / "uv.lock").exists()


class TestNodejsLambda:
    """Tests for Node.js Lambda function writing."""

    def test_handler_file_exists(
        self, writer: LambdaWriter, nodejs_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that handler.js is created."""
        result = writer.write(nodejs_spec, tmp_path)
        assert (result / "handler.js").exists()

    def test_package_json_exists(
        self, writer: LambdaWriter, nodejs_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that package.json is created."""
        result = writer.write(nodejs_spec, tmp_path)
        assert (result / "package.json").exists()

    def test_package_json_valid(
        self, writer: LambdaWriter, nodejs_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that package.json has correct content."""
        result = writer.write(nodejs_spec, tmp_path)
        pkg = json.loads((result / "package.json").read_text())
        assert pkg["name"] == "code_node_transform"
        assert pkg["version"] == "1.0.0"
        assert pkg["main"] == "handler.js"
        assert "luxon" in pkg["dependencies"]
        assert pkg["dependencies"]["luxon"] == "3.4.4"

    def test_js_code_node_wrapper(
        self, writer: LambdaWriter, nodejs_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that JS handler wraps code node content correctly."""
        result = writer.write(nodejs_spec, tmp_path)
        content = (result / "handler.js").read_text()
        assert "Begin n8n Code node content" in content
        assert "End n8n Code node content" in content
        assert "exports.handler = handler;" in content

    def test_handler_has_comment_header(
        self, writer: LambdaWriter, nodejs_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that handler.js has source node comment header."""
        result = writer.write(nodejs_spec, tmp_path)
        content = (result / "handler.js").read_text()
        assert "Source n8n node: Code" in content
        assert "Function type: code_node_js" in content


class TestWriteAll:
    """Tests for writing multiple Lambda functions."""

    def test_mixed_lambdas(
        self,
        writer: LambdaWriter,
        python_spec: LambdaFunctionSpec,
        nodejs_spec: LambdaFunctionSpec,
        tmp_path: Path,
    ) -> None:
        """Test that write_all handles mixed Python and Node.js Lambdas."""
        paths = writer.write_all([python_spec, nodejs_spec], tmp_path)
        assert len(paths) == 2
        assert (paths[0] / "handler.py").exists()
        assert (paths[1] / "handler.js").exists()


class TestSanitisation:
    """Tests for function name sanitisation."""

    def test_special_chars_sanitised(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that special characters in function names are sanitised."""
        spec = LambdaFunctionSpec(
            function_name="my_func",
            runtime=LambdaRuntime.NODEJS,
            handler_code="exports.handler = async () => {};",
            function_type=LambdaFunctionType.CODE_NODE_JS,
        )
        result = writer.write(spec, tmp_path)
        assert result.exists()
        # Directory name should be filesystem-safe
        assert result.name == "my_func"
