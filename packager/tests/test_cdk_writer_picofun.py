"""Tests for PicoFun construct support in the CDK writer."""

from __future__ import annotations

from pathlib import Path

import pytest

from n8n_to_sfn_packager.models.inputs import (
    ConversionReport,
    CredentialSpec,
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
    PackagerInput,
    StateMachineDefinition,
    WorkflowMetadata,
)
from n8n_to_sfn_packager.models.ssm import SSMParameterDefinition
from n8n_to_sfn_packager.writers.cdk_writer import CDKWriter
from n8n_to_sfn_packager.writers.picofun_writer import PicoFunOutput


def _make_metadata() -> WorkflowMetadata:
    """Return minimal workflow metadata."""
    return WorkflowMetadata(
        workflow_name="pf-test-wf",
        source_n8n_version="1.42.0",
        converter_version="0.1.0",
        timestamp="2025-06-15T10:30:00Z",
        confidence_score=0.9,
    )


def _make_state_machine() -> StateMachineDefinition:
    """Return minimal state machine."""
    return StateMachineDefinition(
        asl={"StartAt": "Done", "States": {"Done": {"Type": "Succeed"}}},
    )


def _make_conversion_report() -> ConversionReport:
    """Return minimal conversion report."""
    return ConversionReport(total_nodes=2, confidence_score=0.9)


@pytest.fixture
def picofun_spec() -> LambdaFunctionSpec:
    """Create a PicoFun API client function spec."""
    return LambdaFunctionSpec(
        function_name="slack_post_message",
        function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
        runtime=LambdaRuntime.PYTHON,
        handler_code="def handler(event, context): return event",
        dependencies=["picorun", "requests"],
        source_node_name="Slack",
    )


@pytest.fixture
def regular_spec() -> LambdaFunctionSpec:
    """Create a regular Python function spec."""
    return LambdaFunctionSpec(
        function_name="process_data",
        function_type=LambdaFunctionType.CODE_NODE_PYTHON,
        runtime=LambdaRuntime.PYTHON,
        handler_code="def handler(event, context): return event",
        dependencies=[],
        source_node_name="Code",
    )


@pytest.fixture
def picofun_output(tmp_path: Path) -> PicoFunOutput:
    """Create a mock PicoFunOutput with valid paths."""
    layer_dir = tmp_path / "picofun_layer" / "layer"
    layer_dir.mkdir(parents=True)
    construct_file = tmp_path / "picofun_layer" / "main.tf"
    construct_file.touch()
    return PicoFunOutput(layer_dir=layer_dir, construct_file=construct_file)


def _make_input(
    functions: list[LambdaFunctionSpec],
) -> PackagerInput:
    """Build a PackagerInput with the given Lambda functions."""
    return PackagerInput(
        metadata=_make_metadata(),
        state_machine=_make_state_machine(),
        lambda_functions=functions,
        credentials=[
            CredentialSpec(
                parameter_path="/pf-test-wf/creds/token",
                credential_type="apiKey",
            ),
        ],
        conversion_report=_make_conversion_report(),
    )


class TestPicoFunFunctionsExcludedFromLambdaSection:
    """Verify PICOFUN_API_CLIENT functions are skipped from _wf_lambda_functions."""

    def test_picofun_functions_excluded_from_lambda_section(
        self,
        picofun_spec: LambdaFunctionSpec,
        regular_spec: LambdaFunctionSpec,
    ) -> None:
        """PICOFUN_API_CLIENT functions must not appear as lambda_.Function constructs."""
        input_data = _make_input([picofun_spec, regular_spec])
        code, _warnings = CDKWriter._wf_lambda_functions(input_data)

        assert "process_data" in code
        assert "slack_post_message" not in code

    def test_only_picofun_produces_empty_lambda_section(
        self,
        picofun_spec: LambdaFunctionSpec,
    ) -> None:
        """When all functions are PicoFun, no lambda_.Function constructs are generated."""
        input_data = _make_input([picofun_spec])
        code, _warnings = CDKWriter._wf_lambda_functions(input_data)

        assert "lambda_.Function(" not in code


class TestPicoFunImportAdded:
    """Verify PicoFun construct import is present when PicoFun functions exist."""

    def test_picofun_import_added(
        self,
        picofun_spec: LambdaFunctionSpec,
    ) -> None:
        """PicoFunConstruct import appears when has_picofun is True."""
        input_data = _make_input([picofun_spec])
        imports = CDKWriter._wf_imports(input_data, has_picofun=True)

        assert "from construct import PicoFunConstruct" in imports

    def test_no_picofun_import_when_false(
        self,
        regular_spec: LambdaFunctionSpec,
    ) -> None:
        """PicoFunConstruct import is absent when has_picofun is False."""
        input_data = _make_input([regular_spec])
        imports = CDKWriter._wf_imports(input_data, has_picofun=False)

        assert "PicoFunConstruct" not in imports


class TestPicoFunConstructSectionGenerated:
    """Verify _wf_picofun_construct produces valid Python code."""

    def test_picofun_construct_section_generated(
        self,
        picofun_spec: LambdaFunctionSpec,
        picofun_output: PicoFunOutput,
    ) -> None:
        """_wf_picofun_construct generates PicoFunConstruct instantiation."""
        input_data = _make_input([picofun_spec])
        code = CDKWriter._wf_picofun_construct(input_data, picofun_output)

        assert "PicoFunConstruct(" in code
        assert '"slack_post_message"' in code
        assert "picofun_layer" in code

    def test_picofun_construct_wires_lambda_functions(
        self,
        picofun_spec: LambdaFunctionSpec,
        picofun_output: PicoFunOutput,
    ) -> None:
        """Generated code wires PicoFun lambdas into lambda_functions dict."""
        input_data = _make_input([picofun_spec])
        code = CDKWriter._wf_picofun_construct(input_data, picofun_output)

        assert 'lambda_functions["slack_post_message"]' in code
        assert 'picofun.lambda_functions["slack_post_message"]' in code

    def test_picofun_construct_syntactically_valid(
        self,
        picofun_spec: LambdaFunctionSpec,
        picofun_output: PicoFunOutput,
    ) -> None:
        """Generated PicoFun construct code is syntactically valid Python."""
        input_data = _make_input([picofun_spec])
        code = CDKWriter._wf_picofun_construct(input_data, picofun_output)

        # Wrap in a function body so indented code is valid
        wrapped = "def _gen():\n" + code
        compile(wrapped, "<picofun_construct>", "exec")

    def test_picofun_construct_returns_empty_without_output(
        self,
        picofun_spec: LambdaFunctionSpec,
    ) -> None:
        """_wf_picofun_construct returns empty when picofun_output is None."""
        input_data = _make_input([picofun_spec])
        code = CDKWriter._wf_picofun_construct(input_data, None)

        assert code == ""


class TestNoPicoFunSectionWhenNoFunctions:
    """Verify no PicoFun sections appear when no PICOFUN_API_CLIENT functions exist."""

    def test_no_picofun_section_when_no_functions(
        self,
        regular_spec: LambdaFunctionSpec,
        tmp_path: Path,
    ) -> None:
        """Full stack generation with only regular functions has no PicoFun artifacts."""
        input_data = _make_input([regular_spec])
        writer = CDKWriter()
        iam_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": ["*"],
                },
            ],
        }
        ssm_params = [
            SSMParameterDefinition(
                parameter_path="/wf/creds/token",
                description="API token",
                placeholder_value="<your-token>",
            ),
        ]
        cdk_dir, _warnings = writer.write(input_data, iam_policy, ssm_params, tmp_path)

        stack_code = (cdk_dir / "stacks" / "workflow_stack.py").read_text()

        assert "PicoFunConstruct" not in stack_code
        assert "picofun" not in stack_code.lower().replace("picofun_api_client", "")

    def test_no_picofun_construct_with_only_regular_functions(
        self,
        regular_spec: LambdaFunctionSpec,
        picofun_output: PicoFunOutput,
    ) -> None:
        """_wf_picofun_construct returns empty when no PicoFun functions exist."""
        input_data = _make_input([regular_spec])
        code = CDKWriter._wf_picofun_construct(input_data, picofun_output)

        assert code == ""
