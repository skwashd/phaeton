"""Tests for the PicoFun artifact writer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from n8n_to_sfn_packager.models.inputs import (
    LambdaFunctionSpec,
    LambdaFunctionType,
    LambdaRuntime,
)
from n8n_to_sfn_packager.writers.picofun_writer import PicoFunOutput, PicoFunWriter


@pytest.fixture
def picofun_spec() -> LambdaFunctionSpec:
    """Create a PicoFun Lambda function spec for testing."""
    return LambdaFunctionSpec(
        function_name="slack_api",
        runtime=LambdaRuntime.PYTHON,
        handler_code='def handler(event, context):\n    return {"ok": True}',
        description="PicoFun Slack API client",
        source_node_name="Slack",
        dependencies=["httpx==0.27.0"],
        function_type=LambdaFunctionType.PICOFUN_API_CLIENT,
    )


@pytest.fixture
def writer() -> PicoFunWriter:
    """Create a PicoFunWriter instance."""
    return PicoFunWriter()


@patch("picofun.iac.terraform.TerraformGenerator")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Template")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Layer")
@patch("n8n_to_sfn_packager.writers.picofun_writer._create_config")
def test_write_creates_layer_directory(
    mock_create_config: MagicMock,
    mock_layer_cls: MagicMock,
    mock_template_cls: MagicMock,
    mock_tf_gen_cls: MagicMock,
    writer: PicoFunWriter,
    picofun_spec: LambdaFunctionSpec,
    tmp_path: Path,
) -> None:
    """Test that write creates the picorun layer directory."""
    mock_config = MagicMock()
    mock_config.template_path = "/fake/template"
    mock_create_config.return_value = mock_config

    result = writer.write(
        picofun_functions=[picofun_spec],
        namespace="test",
        output_dir=tmp_path,
    )

    mock_layer_cls.assert_called_once_with(mock_config)
    mock_layer_cls.return_value.prepare.assert_called_once()
    assert result.layer_dir == tmp_path / "picofun_layer" / "layer"


@patch("picofun.iac.terraform.TerraformGenerator")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Template")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Layer")
@patch("n8n_to_sfn_packager.writers.picofun_writer._create_config")
def test_write_creates_cdk_construct(
    mock_create_config: MagicMock,
    mock_layer_cls: MagicMock,
    mock_template_cls: MagicMock,
    mock_tf_gen_cls: MagicMock,
    writer: PicoFunWriter,
    picofun_spec: LambdaFunctionSpec,
    tmp_path: Path,
) -> None:
    """Test that write generates the CDK construct file."""
    mock_config = MagicMock()
    mock_config.template_path = "/fake/template"
    mock_create_config.return_value = mock_config

    result = writer.write(
        picofun_functions=[picofun_spec],
        namespace="test",
        output_dir=tmp_path,
    )

    mock_tf_gen_cls.assert_called_once_with(
        mock_template_cls.return_value, "test", mock_config
    )
    mock_tf_gen_cls.return_value.generate.assert_called_once_with(["slack_api"])
    assert result.construct_file == tmp_path / "picofun_layer" / "main.tf"


@patch("picofun.iac.terraform.TerraformGenerator")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Template")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Layer")
@patch("n8n_to_sfn_packager.writers.picofun_writer._create_config")
def test_write_returns_output_metadata(
    mock_create_config: MagicMock,
    mock_layer_cls: MagicMock,
    mock_template_cls: MagicMock,
    mock_tf_gen_cls: MagicMock,
    writer: PicoFunWriter,
    picofun_spec: LambdaFunctionSpec,
    tmp_path: Path,
) -> None:
    """Test that write returns PicoFunOutput with correct path metadata."""
    mock_config = MagicMock()
    mock_config.template_path = "/fake/template"
    mock_create_config.return_value = mock_config

    result = writer.write(
        picofun_functions=[picofun_spec],
        namespace="test",
        output_dir=tmp_path,
    )

    assert isinstance(result, PicoFunOutput)
    assert isinstance(result.layer_dir, Path)
    assert isinstance(result.construct_file, Path)
    assert result.layer_dir == tmp_path / "picofun_layer" / "layer"
    assert result.construct_file == tmp_path / "picofun_layer" / "main.tf"


@patch("picofun.iac.terraform.TerraformGenerator")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Template")
@patch("n8n_to_sfn_packager.writers.picofun_writer.Layer")
@patch("n8n_to_sfn_packager.writers.picofun_writer._create_config")
def test_skip_when_no_picofun_functions(
    mock_create_config: MagicMock,
    mock_layer_cls: MagicMock,
    mock_template_cls: MagicMock,
    mock_tf_gen_cls: MagicMock,
    writer: PicoFunWriter,
    tmp_path: Path,
) -> None:
    """Test that no PicoFun API calls are made when function list is empty."""
    mock_config = MagicMock()
    mock_config.template_path = "/fake/template"
    mock_create_config.return_value = mock_config

    result = writer.write(
        picofun_functions=[],
        namespace="test",
        output_dir=tmp_path,
    )

    mock_layer_cls.assert_called_once_with(mock_config)
    mock_layer_cls.return_value.prepare.assert_called_once()
    mock_tf_gen_cls.return_value.generate.assert_called_once_with([])
    assert isinstance(result, PicoFunOutput)
