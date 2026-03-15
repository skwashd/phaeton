"""Tests for the Lambda function writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    WebhookAuthConfig,
    WebhookAuthType,
)
from n8n_to_sfn_packager.writers.lambda_writer import (
    LambdaWriter,
    LayerSpec,
    analyze_shared_dependencies,
)


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

    def test_requirements_txt_exists(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that requirements.txt is created alongside pyproject.toml."""
        result = writer.write(python_spec, tmp_path)
        assert (result / "requirements.txt").exists()

    def test_requirements_txt_contains_dependencies(
        self, writer: LambdaWriter, python_spec: LambdaFunctionSpec, tmp_path: Path
    ) -> None:
        """Test that requirements.txt contains the same dependencies."""
        result = writer.write(python_spec, tmp_path)
        content = (result / "requirements.txt").read_text()
        assert "httpx==0.27.0" in content
        assert "aws-lambda-powertools==2.40.0" in content

    def test_requirements_txt_empty_when_no_deps(
        self,
        writer: LambdaWriter,
        python_no_deps_spec: LambdaFunctionSpec,
        tmp_path: Path,
    ) -> None:
        """Test that requirements.txt is empty when there are no dependencies."""
        result = writer.write(python_no_deps_spec, tmp_path)
        content = (result / "requirements.txt").read_text()
        assert content == ""

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


class TestWebhookAuthCodeInjection:
    """Tests for webhook authentication code injection in handlers."""

    def test_api_key_auth_preamble(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that API key auth injects SSM client and _authenticate function."""
        spec = LambdaFunctionSpec(
            function_name="webhook_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context):\n    return {'statusCode': 200}",
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            source_node_name="Webhook",
            webhook_auth=WebhookAuthConfig(
                auth_type=WebhookAuthType.API_KEY,
                credential_parameter_path="/wf/webhooks/api-key",
            ),
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert "boto3.client" in content
        assert "_get_webhook_secret" in content
        assert "_authenticate" in content
        assert "x-api-key" in content
        assert '"statusCode": 401' in content

    def test_hmac_auth_preamble(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that HMAC auth injects signature verification logic."""
        spec = LambdaFunctionSpec(
            function_name="webhook_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context):\n    return {'statusCode': 200}",
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            source_node_name="Webhook",
            webhook_auth=WebhookAuthConfig(
                auth_type=WebhookAuthType.HMAC_SHA256,
                credential_parameter_path="/wf/webhooks/signing-secret",
                header_name="x-hub-signature-256",
            ),
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert "hmac.new" in content
        assert "hashlib.sha256" in content
        assert "compare_digest" in content
        assert "x-hub-signature-256" in content
        assert '"statusCode": 403' in content

    def test_custom_header_name(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that custom header name is used in auth code."""
        spec = LambdaFunctionSpec(
            function_name="webhook_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context):\n    return {'statusCode': 200}",
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            source_node_name="Webhook",
            webhook_auth=WebhookAuthConfig(
                auth_type=WebhookAuthType.API_KEY,
                credential_parameter_path="/wf/webhooks/api-key",
                header_name="authorization",
            ),
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert '"authorization"' in content

    def test_no_auth_no_preamble(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that webhook handler without auth has no auth preamble."""
        spec = LambdaFunctionSpec(
            function_name="webhook_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context):\n    return {'statusCode': 200}",
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            source_node_name="Webhook",
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert "_authenticate" not in content
        assert "WEBHOOK_AUTH_PARAMETER" not in content

    def test_handler_code_preserved_with_auth(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that original handler code is preserved after auth preamble."""
        handler = "def handler(event, context):\n    return {'statusCode': 200}"
        spec = LambdaFunctionSpec(
            function_name="webhook_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code=handler,
            function_type=LambdaFunctionType.WEBHOOK_HANDLER,
            source_node_name="Webhook",
            webhook_auth=WebhookAuthConfig(
                auth_type=WebhookAuthType.API_KEY,
                credential_parameter_path="/wf/webhooks/api-key",
            ),
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert handler in content

    def test_callback_handler_also_gets_auth(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that callback handlers also receive auth injection."""
        spec = LambdaFunctionSpec(
            function_name="callback_handler",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context):\n    return {'statusCode': 200}",
            function_type=LambdaFunctionType.CALLBACK_HANDLER,
            source_node_name="Wait",
            webhook_auth=WebhookAuthConfig(
                auth_type=WebhookAuthType.API_KEY,
                credential_parameter_path="/wf/callbacks/api-key",
            ),
        )
        result = writer.write(spec, tmp_path)
        content = (result / "handler.py").read_text()
        assert "_authenticate" in content


class TestAnalyzeSharedDependencies:
    """Tests for the shared dependency analysis function."""

    def test_no_shared_deps_single_function(self) -> None:
        """Test that a single function produces no layers."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
        ]
        layers, excluded = analyze_shared_dependencies(specs)
        assert layers == []
        assert excluded == {}

    def test_shared_deps_same_runtime(self) -> None:
        """Test that deps shared by 2+ functions of the same runtime are layered."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4", "lodash@4.17.21"],
            ),
            LambdaFunctionSpec(
                function_name="fn_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4", "axios@1.6.0"],
            ),
        ]
        layers, excluded = analyze_shared_dependencies(specs)
        assert len(layers) == 1
        assert layers[0].layer_name == "nodejs-shared"
        assert layers[0].runtime == LambdaRuntime.NODEJS
        assert layers[0].dependencies == ["luxon@3.4.4"]
        assert sorted(layers[0].function_names) == ["fn_a", "fn_b"]
        assert excluded == {
            "fn_a": {"luxon@3.4.4"},
            "fn_b": {"luxon@3.4.4"},
        }

    def test_no_shared_deps_different_runtimes(self) -> None:
        """Test that deps are not shared across different runtimes."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="fn_b",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                dependencies=["luxon==3.4.4"],
            ),
        ]
        layers, excluded = analyze_shared_dependencies(specs)
        assert layers == []
        assert excluded == {}

    def test_no_shared_deps_disjoint(self) -> None:
        """Test that functions with completely different deps produce no layer."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="fn_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["axios@1.6.0"],
            ),
        ]
        layers, excluded = analyze_shared_dependencies(specs)
        assert layers == []
        assert excluded == {}

    def test_mixed_runtimes_both_have_shared(self) -> None:
        """Test layers are created per-runtime when both have shared deps."""
        specs = [
            LambdaFunctionSpec(
                function_name="js_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="js_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
            LambdaFunctionSpec(
                function_name="py_a",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                dependencies=["httpx==0.27.0"],
            ),
            LambdaFunctionSpec(
                function_name="py_b",
                runtime=LambdaRuntime.PYTHON,
                handler_code="def handler(event, context): pass",
                function_type=LambdaFunctionType.CODE_NODE_PYTHON,
                dependencies=["httpx==0.27.0"],
            ),
        ]
        layers, _excluded = analyze_shared_dependencies(specs)
        assert len(layers) == 2
        layer_names = {layer.layer_name for layer in layers}
        assert layer_names == {"nodejs-shared", "python-shared"}

    def test_empty_specs(self) -> None:
        """Test that empty specs produce no layers."""
        layers, excluded = analyze_shared_dependencies([])
        assert layers == []
        assert excluded == {}

    def test_no_dependencies(self) -> None:
        """Test that functions with no deps produce no layers."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=[],
            ),
            LambdaFunctionSpec(
                function_name="fn_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=[],
            ),
        ]
        layers, excluded = analyze_shared_dependencies(specs)
        assert layers == []
        assert excluded == {}


class TestWriteLayer:
    """Tests for Lambda Layer directory writing."""

    def test_nodejs_layer_directory_structure(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Node.js layer creates nodejs/package.json."""
        layer = LayerSpec(
            layer_name="nodejs-shared",
            runtime=LambdaRuntime.NODEJS,
            dependencies=["luxon@3.4.4", "lodash@4.17.21"],
            function_names=["fn_a", "fn_b"],
        )
        result = writer.write_layer(layer, tmp_path)
        assert result == tmp_path / "layers" / "nodejs-shared"
        pkg_path = result / "nodejs" / "package.json"
        assert pkg_path.exists()
        pkg = json.loads(pkg_path.read_text())
        assert pkg["dependencies"]["luxon"] == "3.4.4"
        assert pkg["dependencies"]["lodash"] == "4.17.21"

    def test_python_layer_directory_structure(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Python layer creates pyproject.toml."""
        layer = LayerSpec(
            layer_name="python-shared",
            runtime=LambdaRuntime.PYTHON,
            dependencies=["httpx==0.27.0", "aws-lambda-powertools==2.40.0"],
            function_names=["fn_a", "fn_b"],
        )
        result = writer.write_layer(layer, tmp_path)
        assert result == tmp_path / "layers" / "python-shared"
        pyproject_path = result / "pyproject.toml"
        assert pyproject_path.exists()
        content = pyproject_path.read_text()
        assert "httpx==0.27.0" in content
        assert "aws-lambda-powertools==2.40.0" in content

    def test_python_layer_requirements_txt(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Python layer creates requirements.txt alongside pyproject.toml."""
        layer = LayerSpec(
            layer_name="python-shared",
            runtime=LambdaRuntime.PYTHON,
            dependencies=["httpx==0.27.0", "aws-lambda-powertools==2.40.0"],
            function_names=["fn_a", "fn_b"],
        )
        result = writer.write_layer(layer, tmp_path)
        req_path = result / "requirements.txt"
        assert req_path.exists()
        content = req_path.read_text()
        assert "httpx==0.27.0" in content
        assert "aws-lambda-powertools==2.40.0" in content

    def test_nodejs_layer_no_requirements_txt(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Node.js layers do not generate requirements.txt."""
        layer = LayerSpec(
            layer_name="nodejs-shared",
            runtime=LambdaRuntime.NODEJS,
            dependencies=["luxon@3.4.4"],
            function_names=["fn_a"],
        )
        result = writer.write_layer(layer, tmp_path)
        assert not (result / "requirements.txt").exists()

    def test_nodejs_layer_version_parsing(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Node.js layer handles == version separator."""
        layer = LayerSpec(
            layer_name="nodejs-shared",
            runtime=LambdaRuntime.NODEJS,
            dependencies=["luxon==3.4.4"],
            function_names=["fn_a"],
        )
        result = writer.write_layer(layer, tmp_path)
        pkg = json.loads((result / "nodejs" / "package.json").read_text())
        assert pkg["dependencies"]["luxon"] == "3.4.4"


class TestExcludedDependencies:
    """Tests for dependency exclusion from individual function packages."""

    def test_nodejs_excludes_layered_deps(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Node.js function excludes layered deps from package.json."""
        spec = LambdaFunctionSpec(
            function_name="fn_a",
            runtime=LambdaRuntime.NODEJS,
            handler_code="exports.handler = async () => {};",
            function_type=LambdaFunctionType.CODE_NODE_JS,
            dependencies=["luxon@3.4.4", "axios@1.6.0"],
        )
        result = writer.write(spec, tmp_path, excluded_dependencies={"luxon@3.4.4"})
        pkg = json.loads((result / "package.json").read_text())
        assert "luxon" not in pkg["dependencies"]
        assert "axios" in pkg["dependencies"]

    def test_python_excludes_layered_deps(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that Python function excludes layered deps from pyproject.toml."""
        spec = LambdaFunctionSpec(
            function_name="fn_a",
            runtime=LambdaRuntime.PYTHON,
            handler_code="def handler(event, context): pass",
            function_type=LambdaFunctionType.CODE_NODE_PYTHON,
            dependencies=["httpx==0.27.0", "boto3==1.34.0"],
        )
        result = writer.write(spec, tmp_path, excluded_dependencies={"httpx==0.27.0"})
        content = (result / "pyproject.toml").read_text()
        assert "httpx==0.27.0" not in content
        assert "boto3==1.34.0" in content

    def test_no_exclusion_keeps_all_deps(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that no exclusion keeps all deps in the package."""
        spec = LambdaFunctionSpec(
            function_name="fn_a",
            runtime=LambdaRuntime.NODEJS,
            handler_code="exports.handler = async () => {};",
            function_type=LambdaFunctionType.CODE_NODE_JS,
            dependencies=["luxon@3.4.4", "axios@1.6.0"],
        )
        result = writer.write(spec, tmp_path)
        pkg = json.loads((result / "package.json").read_text())
        assert "luxon" in pkg["dependencies"]
        assert "axios" in pkg["dependencies"]


class TestWriteAllWithLayers:
    """Tests for write_all with automatic layer generation."""

    def test_write_all_creates_layers(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that write_all creates layer directories for shared deps."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4", "lodash@4.17.21"],
            ),
            LambdaFunctionSpec(
                function_name="fn_b",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4", "axios@1.6.0"],
            ),
        ]
        paths = writer.write_all(specs, tmp_path)
        assert len(paths) == 2

        # Layer directory should exist
        layer_dir = tmp_path / "layers" / "nodejs-shared"
        assert layer_dir.exists()
        pkg = json.loads((layer_dir / "nodejs" / "package.json").read_text())
        assert "luxon" in pkg["dependencies"]

        # Function packages should exclude shared deps
        pkg_a = json.loads((paths[0] / "package.json").read_text())
        assert "luxon" not in pkg_a["dependencies"]
        assert "lodash" in pkg_a["dependencies"]

        pkg_b = json.loads((paths[1] / "package.json").read_text())
        assert "luxon" not in pkg_b["dependencies"]
        assert "axios" in pkg_b["dependencies"]

    def test_write_all_no_shared_deps(
        self, writer: LambdaWriter, tmp_path: Path
    ) -> None:
        """Test that write_all with no shared deps creates no layers."""
        specs = [
            LambdaFunctionSpec(
                function_name="fn_a",
                runtime=LambdaRuntime.NODEJS,
                handler_code="exports.handler = async () => {};",
                function_type=LambdaFunctionType.CODE_NODE_JS,
                dependencies=["luxon@3.4.4"],
            ),
        ]
        paths = writer.write_all(specs, tmp_path)
        assert len(paths) == 1
        assert not (tmp_path / "layers").exists()
